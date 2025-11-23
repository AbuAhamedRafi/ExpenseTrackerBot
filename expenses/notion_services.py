import os
import requests
from datetime import datetime


def get_headers():
    return {
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
        "Content-Type": "application/json",
        "Notion-Version": os.getenv("NOTION_VERSION", "2022-06-28"),
    }


def get_database_id(name):
    if name == "expenses":
        return os.getenv("NOTION_EXPENSE_DB_ID")
    elif name == "income":
        return os.getenv("NOTION_INCOME_DB_ID")
    elif name == "accounts":
        return os.getenv("NOTION_ACCOUNTS_DB_ID")
    elif name == "categories":
        return os.getenv("NOTION_CATEGORIES_DB_ID")
    return None


def find_page_by_name(database_id, name_property, name_value):
    """
    Finds a page in a database by its name property.
    Returns the page ID if found, else None.
    Uses case-insensitive matching.
    """
    url = f"https://api.notion.com/v1/databases/{database_id}/query"

    # Get all pages (no filter)
    response = requests.post(url, json={}, headers=get_headers())

    if response.status_code == 200:
        results = response.json().get("results", [])
        name_value_lower = name_value.lower().strip()

        for page in results:
            name_prop = page.get("properties", {}).get(name_property, {})
            title_list = name_prop.get("title", [])

            if title_list:
                page_name = title_list[0].get("text", {}).get("content", "")

                # Exact match (case-insensitive)
                if page_name.lower().strip() == name_value_lower:
                    return page["id"]

                # Fuzzy match: check if search term is in the page name
                if name_value_lower in page_name.lower():
                    return page["id"]

    return None


def get_all_pages_from_database(database_id):
    """
    Fetches all pages from a Notion database.
    Returns a list of page names.
    """
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    response = requests.post(url, json={}, headers=get_headers())

    names = []
    if response.status_code == 200:
        results = response.json().get("results", [])

        for page in results:
            name_prop = page.get("properties", {}).get("Name", {})
            title_list = name_prop.get("title", [])

            if title_list:
                page_name = title_list[0].get("text", {}).get("content", "")
                names.append(page_name)

    return names


def get_all_categories():
    """Fetches all category names from Notion."""
    category_db_id = get_database_id("categories")
    return get_all_pages_from_database(category_db_id)


def get_all_accounts():
    """Fetches all account names from Notion."""
    account_db_id = get_database_id("accounts")
    return get_all_pages_from_database(account_db_id)


def get_category_budget(category_name):
    """Fetches the monthly budget for a specific category."""
    category_db_id = get_database_id("categories")
    url = f"https://api.notion.com/v1/databases/{category_db_id}/query"

    response = requests.post(url, json={}, headers=get_headers())

    if response.status_code == 200:
        results = response.json().get("results", [])

        for page in results:
            name_prop = page.get("properties", {}).get("Name", {})
            title_list = name_prop.get("title", [])

            if title_list:
                page_name = title_list[0].get("text", {}).get("content", "")

                if page_name.lower().strip() == category_name.lower().strip():
                    # Found the category, get the budget
                    properties = page.get("properties", {})

                    # Check for budget property
                    for prop_name in [
                        "Budget",
                        "Monthly Budget",
                        "Limit",
                        "Monthly Cost",
                    ]:
                        if prop_name in properties:
                            budget_prop = properties[prop_name]
                            budget_type = budget_prop.get("type")

                            if budget_type == "number":
                                return budget_prop.get("number")
                            elif budget_type == "formula":
                                # For formula fields
                                formula_result = budget_prop.get("formula", {})
                                if formula_result.get("type") == "number":
                                    return formula_result.get("number")

    return None


def get_category_spending_this_month(
    category_id, current_month_start, current_month_end
):
    """Calculates total spending for a category in the current month."""
    expense_db_id = get_database_id("expenses")
    url = f"https://api.notion.com/v1/databases/{expense_db_id}/query"

    # Query expenses in current month with this category
    payload = {
        "filter": {
            "and": [
                {"property": "Date", "date": {"on_or_after": current_month_start}},
                {"property": "Date", "date": {"before": current_month_end}},
                {"property": "Categories", "relation": {"contains": category_id}},
            ]
        }
    }

    response = requests.post(url, json=payload, headers=get_headers())

    total = 0
    if response.status_code == 200:
        results = response.json().get("results", [])

        for page in results:
            amount_prop = page.get("properties", {}).get("Amount", {})
            if amount_prop.get("type") == "number":
                amount = amount_prop.get("number", 0)
                if amount:
                    total += amount

    return total


def get_monthly_expense_summary():
    """
    Get comprehensive expense summary for current month.
    Returns total spent, breakdown by category with budgets.
    """
    from dateutil.relativedelta import relativedelta

    # Calculate current month boundaries
    now = datetime.now()
    current_month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    next_month = now.replace(day=1) + relativedelta(months=1)
    current_month_end = next_month.isoformat()
    month_name = now.strftime("%B %Y")

    # Get all categories
    category_db_id = get_database_id("categories")
    categories_url = f"https://api.notion.com/v1/databases/{category_db_id}/query"
    categories_response = requests.post(categories_url, json={}, headers=get_headers())

    category_summary = []
    total_spent = 0
    total_budget = 0

    if categories_response.status_code == 200:
        categories = categories_response.json().get("results", [])

        for cat_page in categories:
            cat_name_prop = cat_page.get("properties", {}).get("Name", {})
            cat_title_list = cat_name_prop.get("title", [])

            if cat_title_list:
                cat_name = cat_title_list[0].get("text", {}).get("content", "")
                cat_id = cat_page["id"]

                # Get spending for this category
                spent = get_category_spending_this_month(
                    cat_id, current_month_start, current_month_end
                )

                if spent > 0:  # Only include categories with spending
                    # Get budget
                    budget = get_category_budget(cat_name)

                    category_summary.append(
                        {"name": cat_name, "spent": spent, "budget": budget}
                    )

                    total_spent += spent
                    if budget:
                        total_budget += budget

    # Get total income for the month
    income_db_id = get_database_id("income")
    income_url = f"https://api.notion.com/v1/databases/{income_db_id}/query"
    income_payload = {
        "filter": {
            "and": [
                {"property": "Date", "date": {"on_or_after": current_month_start}},
                {"property": "Date", "date": {"before": current_month_end}},
            ]
        }
    }

    total_income = 0
    income_response = requests.post(
        income_url, json=income_payload, headers=get_headers()
    )
    if income_response.status_code == 200:
        income_results = income_response.json().get("results", [])
        for page in income_results:
            amount_prop = page.get("properties", {}).get("Amount", {})
            if amount_prop.get("type") == "number":
                amount = amount_prop.get("number", 0)
                if amount:
                    total_income += amount

    return {
        "month": month_name,
        "total_spent": total_spent,
        "total_income": total_income,
        "total_budget": total_budget,
        "categories": category_summary,
        "remaining": total_income - total_spent,
    }


def check_budget_impact(category_name, additional_amount):
    """
    Check if spending additional amount in a category will exceed budget.
    Returns status and details.
    """
    from dateutil.relativedelta import relativedelta

    # Calculate current month boundaries
    now = datetime.now()
    current_month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    next_month = now.replace(day=1) + relativedelta(months=1)
    current_month_end = next_month.isoformat()

    # Find category ID
    category_db_id = get_database_id("categories")
    category_id = find_page_by_name(category_db_id, "Name", category_name)

    if not category_id:
        return {
            "status": "unknown",
            "message": f"Category '{category_name}' not found.",
        }

    # Get current spending
    current_spent = get_category_spending_this_month(
        category_id, current_month_start, current_month_end
    )

    # Get budget
    budget = get_category_budget(category_name)

    if not budget:
        return {
            "status": "no_budget",
            "message": f"No budget set for '{category_name}'.",
            "current_spent": current_spent,
            "projected_spent": current_spent + additional_amount,
        }

    projected_spent = current_spent + additional_amount
    remaining = budget - projected_spent
    percentage = (projected_spent / budget) * 100

    if projected_spent > budget:
        status = "over_budget"
        message = f"⚠️ You will go over budget!"
    elif percentage >= 90:
        status = "close_to_limit"
        message = f"⚠️ You are close to your budget, be cautious!"
    elif percentage >= 75:
        status = "approaching_limit"
        message = f"✅ You are within budget but approaching the limit."
    else:
        status = "safe"
        message = f"✅ You are well within your budget!"

    return {
        "status": status,
        "message": message,
        "category": category_name,
        "current_spent": current_spent,
        "projected_spent": projected_spent,
        "budget": budget,
        "remaining": remaining,
        "percentage": percentage,
    }


def tick_fixed_expense_checkbox(expense_name, amount):
    """
    Finds matching fixed expense in checklist and ticks the checkbox.
    Returns True if found and ticked, False otherwise.
    """
    fixed_expenses_db_id = os.getenv("NOTION_SUBSCRIPTIONS_DB_ID")
    if not fixed_expenses_db_id:
        return False

    # Query all fixed expenses
    url = f"https://api.notion.com/v1/databases/{fixed_expenses_db_id}/query"
    response = requests.post(url, json={}, headers=get_headers())

    if response.status_code == 200:
        results = response.json().get("results", [])
        expense_name_lower = expense_name.lower().strip()

        for page in results:
            name_prop = page.get("properties", {}).get("Name", {})
            title_list = name_prop.get("title", [])

            if title_list:
                page_name = title_list[0].get("text", {}).get("content", "")

                # Fuzzy match: check if expense name contains or is contained in fixed expense name
                if (
                    expense_name_lower in page_name.lower()
                    or page_name.lower() in expense_name_lower
                ):
                    # Found match, tick the checkbox
                    page_id = page["id"]

                    update_url = f"https://api.notion.com/v1/pages/{page_id}"
                    update_payload = {"properties": {"Checkbox": {"checkbox": True}}}

                    update_response = requests.patch(
                        update_url, json=update_payload, headers=get_headers()
                    )

                    if update_response.status_code == 200:
                        return True

    return False


def check_duplicate_expense(item_name, current_month_start, current_month_end):
    """
    Checks if a similar expense exists in the current month.
    Returns the date of the duplicate if found, else None.
    """
    expense_db_id = get_database_id("expenses")
    url = f"https://api.notion.com/v1/databases/{expense_db_id}/query"

    # Query expenses in the current month
    payload = {
        "filter": {
            "and": [
                {"property": "Date", "date": {"on_or_after": current_month_start}},
                {"property": "Date", "date": {"before": current_month_end}},
            ]
        }
    }

    response = requests.post(url, json=payload, headers=get_headers())

    if response.status_code == 200:
        results = response.json().get("results", [])
        item_name_lower = item_name.lower().strip()

        for page in results:
            name_prop = page.get("properties", {}).get("Name", {})
            title_list = name_prop.get("title", [])

            if title_list:
                existing_name = title_list[0].get("text", {}).get("content", "")

                # Check if the item names are similar (case-insensitive, contains check)
                if (
                    item_name_lower in existing_name.lower()
                    or existing_name.lower() in item_name_lower
                ):
                    # Get the date of the duplicate
                    date_prop = page.get("properties", {}).get("Date", {})
                    date_info = date_prop.get("date", {})
                    if date_info:
                        return date_info.get("start", "")

    return None


def check_duplicate_income(source_name, current_month_start, current_month_end):
    """
    Checks if a similar income exists in the current month.
    Returns the date of the duplicate if found, else None.
    """
    income_db_id = get_database_id("income")
    url = f"https://api.notion.com/v1/databases/{income_db_id}/query"

    # Query income in the current month
    payload = {
        "filter": {
            "and": [
                {"property": "Date", "date": {"on_or_after": current_month_start}},
                {"property": "Date", "date": {"before": current_month_end}},
            ]
        }
    }

    response = requests.post(url, json=payload, headers=get_headers())

    if response.status_code == 200:
        results = response.json().get("results", [])
        source_name_lower = source_name.lower().strip()

        for page in results:
            name_prop = page.get("properties", {}).get("Name", {})
            title_list = name_prop.get("title", [])

            if title_list:
                existing_name = title_list[0].get("text", {}).get("content", "")

                # Check if the source names are similar (case-insensitive, contains check)
                if (
                    source_name_lower in existing_name.lower()
                    or existing_name.lower() in source_name_lower
                ):
                    # Get the date of the duplicate
                    date_prop = page.get("properties", {}).get("Date", {})
                    date_info = date_prop.get("date", {})
                    if date_info:
                        return date_info.get("start", "")

    return None


def add_expense_to_notion(
    item, amount, category_name, account_name="BRAC Bank Salary Account"
):
    """
    Adds an expense to the Notion database.
    Checks for duplicates in the current month for subscription/recurring items only.
    """
    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    # Define keywords that indicate recurring/subscription expenses
    recurring_keywords = [
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

    # Check if this is a recurring expense
    is_recurring = any(keyword in item.lower() for keyword in recurring_keywords)

    # Only check for duplicates if it's a recurring expense
    if is_recurring:
        # Calculate current month boundaries
        now = datetime.now()
        current_month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        next_month = now.replace(day=1) + relativedelta(months=1)
        current_month_end = next_month.isoformat()

        # Check for duplicate
        duplicate_date = check_duplicate_expense(
            item, current_month_start, current_month_end
        )
        if duplicate_date:
            # Parse the date to make it readable
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

    expense_db_id = get_database_id("expenses")
    category_db_id = get_database_id("categories")
    account_db_id = get_database_id("accounts")

    # Find Category ID
    category_id = find_page_by_name(category_db_id, "Name", category_name)
    if not category_id:
        # Fallback to "Others" or create? For now, let's try "Others" or just leave empty
        category_id = find_page_by_name(category_db_id, "Name", "Others")

    # Find Account ID
    account_id = find_page_by_name(account_db_id, "Name", account_name)

    payload = {
        "parent": {"database_id": expense_db_id},
        "properties": {
            "Name": {"title": [{"text": {"content": item}}]},
            "Amount": {"number": float(amount)},
            "Date": {"date": {"start": datetime.now().isoformat()}},
        },
    }

    # Add Relations if found
    if category_id:
        payload["properties"]["Categories"] = {"relation": [{"id": category_id}]}

    if account_id:
        payload["properties"]["Accounts"] = {"relation": [{"id": account_id}]}

    response = requests.post(
        "https://api.notion.com/v1/pages", json=payload, headers=get_headers()
    )

    if response.status_code == 200:
        # Expense added successfully, now check budget
        budget_warning = None

        if category_id and category_name:
            budget = get_category_budget(category_name)

            if budget:
                # Calculate current spending including this new expense
                from datetime import datetime
                from dateutil.relativedelta import relativedelta

                now = datetime.now()
                current_month_start = now.replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                ).isoformat()
                next_month = now.replace(day=1) + relativedelta(months=1)
                current_month_end = next_month.isoformat()

                total_spent = get_category_spending_this_month(
                    category_id, current_month_start, current_month_end
                )

                if total_spent > budget:
                    overspend = total_spent - budget
                    budget_warning = f"⚠️ Budget Alert: You've spent ${total_spent:.2f} in '{category_name}' this month (Budget: ${budget:.2f}). You're over by ${overspend:.2f}!"

        # Check if this is a fixed expense and tick checkbox
        checklist_message = None
        if tick_fixed_expense_checkbox(item, amount):
            checklist_message = (
                f"✅ Marked '{item}' as paid in Fixed Expenses Checklist"
            )

        return {
            "success": True,
            "budget_warning": budget_warning,
            "checklist_ticked": checklist_message,
        }
    else:
        return {"success": False, "message": response.text}


def add_income_to_notion(source, amount, account_name="BRAC Bank Salary Account"):
    """
    Adds an income to the Notion database.
    Checks for duplicates in the current month first.
    """
    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    # Calculate current month boundaries
    now = datetime.now()
    current_month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    next_month = now.replace(day=1) + relativedelta(months=1)
    current_month_end = next_month.isoformat()

    # Check for duplicate
    duplicate_date = check_duplicate_income(
        source, current_month_start, current_month_end
    )
    if duplicate_date:
        # Parse the date to make it readable
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

    income_db_id = get_database_id("income")
    account_db_id = get_database_id("accounts")

    # Find Account ID
    account_id = find_page_by_name(account_db_id, "Name", account_name)

    payload = {
        "parent": {"database_id": income_db_id},
        "properties": {
            "Name": {"title": [{"text": {"content": source}}]},
            "Amount": {"number": float(amount)},
            "Date": {"date": {"start": datetime.now().isoformat()}},
        },
    }

    if account_id:
        payload["properties"]["Accounts"] = {"relation": [{"id": account_id}]}

    response = requests.post(
        "https://api.notion.com/v1/pages", json=payload, headers=get_headers()
    )

    if response.status_code == 200:
        return {"success": True}
    else:
        return {"success": False, "message": response.text}
