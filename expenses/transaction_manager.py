"""
Transaction Manager - Handles expense and income transactions with Notion.
Includes duplicate detection and automatic checklist management.
"""

from datetime import datetime
from dateutil.relativedelta import relativedelta

from .notion_client import (
    get_database_id,
    query_database,
    create_page,
    update_page,
    find_page_by_name,
    archive_page,
    get_latest_entry,
)
from .budget_tracker import get_category_budget, calculate_category_spending


# Keywords that identify recurring/subscription expenses for duplicate detection
RECURRING_EXPENSE_KEYWORDS = [
    "subscription",
    "spotify",
    "netflix",
    "youtube",
    "prime",
    "amazon",
    "rent",
    "electricity",
    "water",
    "gas",
    "internet",
    "wifi",
    "broadband",
    "insurance",
    "premium",
    "emi",
    "installment",
    "membership",
    "gym",
    "phone bill",
    "mobile recharge",
    "postpaid",
]


def check_for_duplicate(item_name, database_type, month_start, month_end):
    """
    Check if a similar transaction already exists this month.
    Uses fuzzy name matching to find duplicates.

    Args:
        item_name: Transaction name to check
        database_type: 'expenses' or 'income'
        month_start: Month start date (ISO format)
        month_end: Month end date (ISO format)

    Returns:
        Duplicate date string if found, None otherwise
    """
    db_id = get_database_id(database_type)

    filter_params = {
        "and": [
            {"property": "Date", "date": {"on_or_after": month_start}},
            {"property": "Date", "date": {"before": month_end}},
        ]
    }

    existing = query_database(db_id, filter_params)
    item_lower = item_name.lower().strip()

    for page in existing:
        title_prop = page.get("properties", {}).get("Name", {})
        title_list = title_prop.get("title", [])

        if title_list:
            existing_name = title_list[0].get("text", {}).get("content", "")
            existing_lower = existing_name.lower()

            # Fuzzy match - check if names overlap
            if item_lower in existing_lower or existing_lower in item_lower:
                date_prop = page.get("properties", {}).get("Date", {})
                date_info = date_prop.get("date", {})
                if date_info:
                    return date_info.get("start")

    return None


def tick_subscription_checklist(expense_name):
    """
    Auto-tick matching item in subscription/fixed expenses checklist.

    Args:
        expense_name: Name of the expense to match

    Returns:
        True if found and ticked, False otherwise
    """
    db_id = get_database_id("subscriptions")
    if not db_id:
        return False

    pages = query_database(db_id)
    expense_lower = expense_name.lower().strip()

    for page in pages:
        title_prop = page.get("properties", {}).get("Name", {})
        title_list = title_prop.get("title", [])

        if title_list:
            page_name = title_list[0].get("text", {}).get("content", "")
            page_lower = page_name.lower()

            # Fuzzy match
            if expense_lower in page_lower or page_lower in expense_lower:
                # Tick the checkbox
                success = update_page(page["id"], {"Checkbox": {"checkbox": True}})
                return success

    return False


def add_expense(item, amount, category_name, account_name):
    """
    Add an expense transaction to Notion.
    Handles duplicate checking for recurring expenses and budget warnings.

    Args:
        item: Expense description
        amount: Expense amount
        category_name: Category name
        account_name: Account name

    Returns:
        Dict with:
        - success: bool
        - message: Error message (if failed)
        - duplicate: bool (if duplicate found)
        - budget_warning: Warning message (if over budget)
        - checklist_ticked: Confirmation message (if checklist item ticked)
    """
    # Check for duplicates only for recurring expenses
    is_recurring = any(kw in item.lower() for kw in RECURRING_EXPENSE_KEYWORDS)

    if is_recurring:
        now = datetime.now()
        month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        month_end = (now.replace(day=1) + relativedelta(months=1)).isoformat()

        duplicate_date = check_for_duplicate(item, "expenses", month_start, month_end)
        if duplicate_date:
            try:
                date_obj = datetime.fromisoformat(duplicate_date.replace("Z", "+00:00"))
                readable_date = date_obj.strftime("%B %d, %Y")
            except:
                readable_date = duplicate_date

            return {
                "success": False,
                "message": f"⚠️ You already paid '{item}' on {readable_date} this month.",
                "duplicate": True,
            }

    # Get database IDs
    expense_db_id = get_database_id("expenses")
    category_db_id = get_database_id("categories")
    account_db_id = get_database_id("accounts")

    # Find category and account IDs
    category_id = find_page_by_name(category_db_id, category_name)
    if not category_id:
        # Fallback to "Others" category
        category_id = find_page_by_name(category_db_id, "Others")

    account_id = find_page_by_name(account_db_id, account_name)

    # Build page properties
    properties = {
        "Name": {"title": [{"text": {"content": item}}]},
        "Amount": {"number": float(amount)},
        "Date": {"date": {"start": datetime.now().isoformat()}},
    }

    if category_id:
        properties["Categories"] = {"relation": [{"id": category_id}]}

    if account_id:
        properties["Accounts"] = {"relation": [{"id": account_id}]}

    # Create the expense
    success, result = create_page(expense_db_id, properties)

    if not success:
        return {"success": False, "message": result}

    # Check budget after adding expense
    budget_warning = None
    if category_id and category_name:
        budget = get_category_budget(category_name)

        if budget:
            now = datetime.now()
            month_start = now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
            month_end = (now.replace(day=1) + relativedelta(months=1)).isoformat()

            total_spent = calculate_category_spending(
                category_id, month_start, month_end
            )

            if total_spent > budget:
                overspend = total_spent - budget
                budget_warning = f"⚠️ Budget Alert: You've spent ${total_spent:.2f} in '{category_name}' this month (Budget: ${budget:.2f}). You're over by ${overspend:.2f}!"

    # Auto-tick checklist if applicable
    checklist_message = None
    if tick_subscription_checklist(item):
        checklist_message = f"✅ Marked '{item}' as paid in Fixed Expenses Checklist"

    return {
        "success": True,
        "budget_warning": budget_warning,
        "checklist_ticked": checklist_message,
    }


def add_income(source, amount, account_name):
    """
    Add an income transaction to Notion.
    Checks for duplicates to prevent double-entry.

    Args:
        source: Income source description
        amount: Income amount
        account_name: Account name

    Returns:
        Dict with:
        - success: bool
        - message: Error message (if failed)
        - duplicate: bool (if duplicate found)
    """
    # Check for duplicates
    now = datetime.now()
    month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    month_end = (now.replace(day=1) + relativedelta(months=1)).isoformat()

    duplicate_date = check_for_duplicate(source, "income", month_start, month_end)
    if duplicate_date:
        try:
            date_obj = datetime.fromisoformat(duplicate_date.replace("Z", "+00:00"))
            readable_date = date_obj.strftime("%B %d, %Y")
        except:
            readable_date = duplicate_date

        return {
            "success": False,
            "message": f"⚠️ '{source}' was already credited on {readable_date} this month.",
            "duplicate": True,
        }

    # Get database IDs
    income_db_id = get_database_id("income")
    account_db_id = get_database_id("accounts")

    # Find account ID
    account_id = find_page_by_name(account_db_id, account_name)

    # Build page properties
    properties = {
        "Name": {"title": [{"text": {"content": source}}]},
        "Amount": {"number": float(amount)},
        "Date": {"date": {"start": datetime.now().isoformat()}},
    }

    if account_id:
        properties["Accounts"] = {"relation": [{"id": account_id}]}

    # Create the income entry
    success, result = create_page(income_db_id, properties)

    if success:
        return {"success": True}
    else:
        return {"success": False, "message": result}


def delete_last_expense():
    """
    Delete/archive the most recent expense entry.

    Returns:
        Tuple of (success: bool, message: str, details: dict or None)
    """
    expense_db_id = get_database_id("expenses")
    if not expense_db_id:
        return False, "Expense database not configured", None

    # Get the latest expense
    latest_entry = get_latest_entry(expense_db_id)
    
    if not latest_entry:
        return False, "No expenses found to delete", None

    # Extract details before deletion
    page_id = latest_entry["id"]
    properties = latest_entry.get("properties", {})
    
    # Get item name
    item_prop = properties.get("Item", {})
    item_name = ""
    if item_prop.get("type") == "title":
        title_content = item_prop.get("title", [])
        if title_content:
            item_name = title_content[0].get("plain_text", "Unknown")
    
    # Get amount
    amount_prop = properties.get("Amount", {})
    amount = amount_prop.get("number", 0)
    
    # Get category
    category_prop = properties.get("Category", {})
    category = "Unknown"
    if category_prop.get("type") == "select":
        select_data = category_prop.get("select", {})
        if select_data:
            category = select_data.get("name", "Unknown")
    
    # Archive the page
    success, message = archive_page(page_id)
    
    if success:
        details = {
            "item": item_name,
            "amount": amount,
            "category": category
        }
        return True, f"Deleted expense: {item_name} - ${amount:.2f}", details
    
    return False, message, None


def delete_last_income():
    """
    Delete/archive the most recent income entry.

    Returns:
        Tuple of (success: bool, message: str, details: dict or None)
    """
    income_db_id = get_database_id("income")
    if not income_db_id:
        return False, "Income database not configured", None

    # Get the latest income
    latest_entry = get_latest_entry(income_db_id)
    
    if not latest_entry:
        return False, "No income entries found to delete", None

    # Extract details before deletion
    page_id = latest_entry["id"]
    properties = latest_entry.get("properties", {})
    
    # Get source name
    source_prop = properties.get("Source", {})
    source_name = ""
    if source_prop.get("type") == "title":
        title_content = source_prop.get("title", [])
        if title_content:
            source_name = title_content[0].get("plain_text", "Unknown")
    
    # Get amount
    amount_prop = properties.get("Amount", {})
    amount = amount_prop.get("number", 0)
    
    # Archive the page
    success, message = archive_page(page_id)
    
    if success:
        details = {
            "source": source_name,
            "amount": amount
        }
        return True, f"Deleted income: {source_name} - ${amount:.2f}", details
    
    return False, message, None
