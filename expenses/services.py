import os
import json
import time
import google.generativeai as genai

from .notion_client import get_database_id, get_all_page_names
from .transaction_manager import add_expense, add_income
from .budget_tracker import get_monthly_summary, check_budget_impact

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# In-memory cache for categories and accounts (1 hour TTL)
_cache = {
    "categories": {"data": None, "timestamp": 0},
    "accounts": {"data": None, "timestamp": 0},
}
CACHE_DURATION = 3600


def get_cached_categories_and_accounts():
    """
    Get categories and accounts from cache or fetch if expired.
    Cache duration: 1 hour
    """
    current_time = time.time()

    # Check categories cache
    if (
        _cache["categories"]["data"] is None
        or (current_time - _cache["categories"]["timestamp"]) > CACHE_DURATION
    ):
        try:
            category_db_id = get_database_id("categories")
            _cache["categories"]["data"] = get_all_page_names(category_db_id)
            _cache["categories"]["timestamp"] = current_time
        except:
            # Fallback to basic categories if Notion fetch fails
            _cache["categories"]["data"] = [
                "Food",
                "Transport",
                "Shopping",
                "Entertainment",
                "Bills",
                "Health",
                "Education",
                "Others",
            ]
            _cache["categories"]["timestamp"] = current_time

    # Check accounts cache
    if (
        _cache["accounts"]["data"] is None
        or (current_time - _cache["accounts"]["timestamp"]) > CACHE_DURATION
    ):
        try:
            account_db_id = get_database_id("accounts")
            _cache["accounts"]["data"] = get_all_page_names(account_db_id)
            _cache["accounts"]["timestamp"] = current_time
        except:
            # Fallback if Notion fetch fails
            _cache["accounts"]["data"] = ["BRAC Bank Salary Account"]
            _cache["accounts"]["timestamp"] = current_time

    return _cache["categories"]["data"], _cache["accounts"]["data"]


def ask_gemini(text):
    """
    Sends text to Gemini and returns a JSON object if it's an expense/income,
    or a string response if it's conversation.
    Uses cached categories and accounts (1 hour TTL).
    """
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Get cached data (budget checks still use real-time data)
    categories, accounts = get_cached_categories_and_accounts()

    categories_list = ", ".join([f'"{cat}"' for cat in categories])
    accounts_list = ", ".join([f'"{acc}"' for acc in accounts])

    system_instruction = f"""
    You are an intelligent Expense Tracker Assistant with access to the user's Notion database.
    Your goal is to parse user messages into structured expense or income data.

    AVAILABLE CATEGORIES: {categories_list}
    AVAILABLE ACCOUNTS: {accounts_list}

    RULES:
    1. If the user message describes an EXPENSE (e.g., "Lunch 150", "Taxi 500 for office"), 
       output a JSON OBJECT with "type": "expense" and a "data" list.
       Each item in "data" must have:
       - "item": (string) Brief description.
       - "amount": (number) The cost.
       - "category": (string) Intelligently match the expense to ONE of the AVAILABLE CATEGORIES.
         Examples of smart matching:
         - "Lunch", "Dinner", "Snacks", "Breakfast", "Chips" → "Food"
         - "Taxi", "Uber", "Bus", "Rickshaw" → "Transportation"  
         - "Clothes", "Shoes" → "Shopping"
         - "Movie", "Game" → "Entertainment"
         - "Doctor", "Medicine" → "Health"
         - "Rent" → "Housing(rent)"
         - If nothing fits, use "Misc"
       - "account": (string) Extract from message or intelligently determine based on context.
         For salary/income, use "BRAC Bank Salary Account" as default.
         For credit card mentions, look for bank card accounts.
         Default to "BRAC Bank Salary Account" if unclear.
       
    2. If the user message describes INCOME (e.g., "Salary credited 50000", "Received 500 from friend"),
       output a JSON OBJECT with "type": "income" and a "data" list.
       Each item in "data" must have:
       - "source": (string) Description of income source.
       - "amount": (number) The amount.
       - "account": (string) For salary, use "BRAC Bank Salary Account". 
         For other income, extract from message or default to "BRAC Bank Salary Account".

    3. If the user asks for EXPENSE SUMMARY or wants to see spending overview (e.g., "Show my expenses", "How much did I spend?", "Expense summary", "My spending this month"),
       output a JSON OBJECT with "type": "summary".

    4. If the user asks about BUDGET CHECK for a hypothetical expense (e.g., "If I spend 500 on food", "Will I go over budget if I buy 1000 clothes", "Can I afford 300 for entertainment"),
       output a JSON OBJECT with "type": "budget_check" and "data" containing:
       - "category": (string) The category name
       - "amount": (number) The hypothetical amount

    5. If the user message is conversational (e.g., "Hello", "How are you?"), 
       output a JSON OBJECT with "type": "message" and "text": "Your reply here".
       
    Example JSON Output (Expense):
    {{
      "type": "expense",
      "data": [
        {{"item": "Lunch", "amount": 150, "category": "Food", "account": "BRAC Bank Salary Account"}}
      ]
    }}

    Example JSON Output (Income):
    {{
      "type": "income",
      "data": [
        {{"source": "Salary", "amount": 50000, "account": "BRAC Bank Salary Account"}}
      ]
    }}

    Example JSON Output (Summary):
    {{
      "type": "summary"
    }}

    Example JSON Output (Budget Check):
    {{
      "type": "budget_check",
      "data": {{
        "category": "Food",
        "amount": 500
      }}
    }}
    
    6. Do not include markdown formatting. Just the raw JSON string.
    """

    prompt = f"{system_instruction}\n\nUser Message: {text}"

    try:
        response = model.generate_content(prompt)
        content = response.text.strip()

        # Attempt to parse as JSON
        clean_content = content.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(clean_content)
            return data
        except json.JSONDecodeError:
            return {"type": "message", "text": content}

    except Exception as e:
        return {"type": "message", "text": f"Error processing with Gemini: {str(e)}"}


def _validate_category(category_name, item_label):
    """
    Validate that a category exists in Notion.
    Returns (is_valid, error_message)
    """
    if not category_name:
        return False, f"{item_label}: Category is missing"

    try:
        category_db_id = get_database_id("categories")
        from .notion_client import find_page_by_name

        cat_page = find_page_by_name(category_db_id, category_name)
        if not cat_page:
            return (
                False,
                f"{item_label}: Category '{category_name}' not found in Notion",
            )
        return True, None
    except Exception as e:
        return False, f"{item_label}: Failed to validate category - {str(e)}"


def _validate_account(account_name, item_label):
    """
    Validate that an account exists in Notion.
    Returns (is_valid, error_message)
    """
    if not account_name:
        return False, f"{item_label}: Account is missing"

    try:
        account_db_id = get_database_id("accounts")
        from .notion_client import find_page_by_name

        acc_page = find_page_by_name(account_db_id, account_name)
        if not acc_page:
            return False, f"{item_label}: Account '{account_name}' not found in Notion"
        return True, None
    except Exception as e:
        return False, f"{item_label}: Failed to validate account - {str(e)}"


def process_transaction(transaction_data):
    """
    Route transaction data to appropriate handler based on type.
    Uses partial-success pattern: validates all items, saves valid ones,
    reports failures clearly.

    This allows "Paid 200 for bike, 330 for youtube, 300 for utils" to
    save bike and youtube successfully while clearly reporting that utils
    failed validation. User gets immediate feedback and doesn't need to
    re-send valid transactions.
    """
    # Handle summary request
    if transaction_data["type"] == "summary":
        summary = get_monthly_summary()
        return {"success": True, "type": "summary", "data": summary}

    # Handle budget check
    elif transaction_data["type"] == "budget_check":
        data = transaction_data.get("data", {})
        category = data.get("category", "")
        amount = data.get("amount", 0)

        if not category or not amount:
            return {
                "success": False,
                "message": "Please specify both category and amount.",
            }

        check_result = check_budget_impact(category, amount)
        return {"success": True, "type": "budget_check", "data": check_result}

    # PHASE 1: VALIDATE ALL ITEMS AND SEPARATE VALID/INVALID
    validation_errors = []
    validated_items = []
    failed_items = []

    if transaction_data["type"] == "expense":
        for idx, item in enumerate(transaction_data["data"], 1):
            item_name = item.get("item", "Unknown")
            item_label = f"Expense #{idx} ({item_name})"
            item_errors = []

            # Validate amount
            amount = item.get("amount")
            if amount is None or amount == 0:
                item_errors.append(f"{item_label}: Amount is missing or zero")

            # Validate category
            category = item.get("category", "")
            is_valid, error = _validate_category(category, item_label)
            if not is_valid:
                item_errors.append(error)

            # Validate account
            account = item.get("account", "BRAC Bank Salary Account")
            is_valid_acc, error_acc = _validate_account(account, item_label)
            if not is_valid_acc:
                item_errors.append(error_acc)

            # Categorize this item
            if item_errors:
                validation_errors.extend(item_errors)
                failed_items.append(
                    {
                        "name": item_name,
                        "amount": item.get("amount"),
                        "errors": item_errors,
                    }
                )
            else:
                validated_items.append(("expense", item))

    elif transaction_data["type"] == "income":
        for idx, item in enumerate(transaction_data["data"], 1):
            source_name = item.get("source", "Unknown")
            item_label = f"Income #{idx} ({source_name})"
            item_errors = []

            # Validate amount
            amount = item.get("amount")
            if amount is None or amount == 0:
                item_errors.append(f"{item_label}: Amount is missing or zero")

            # Validate account
            account = item.get("account", "BRAC Bank Salary Account")
            is_valid, error = _validate_account(account, item_label)
            if not is_valid:
                item_errors.append(error)

            # Categorize this item
            if item_errors:
                validation_errors.extend(item_errors)
                failed_items.append(
                    {
                        "name": source_name,
                        "amount": item.get("amount"),
                        "errors": item_errors,
                    }
                )
            else:
                validated_items.append(("income", item))

    # PHASE 2: SAVE ALL VALID ITEMS
    successful_results = []
    execution_failures = []

    for trans_type, item in validated_items:
        try:
            if trans_type == "expense":
                res = add_expense(
                    item["item"],
                    item["amount"],
                    item.get("category", ""),
                    item.get("account", "BRAC Bank Salary Account"),
                )
            elif trans_type == "income":
                res = add_income(
                    item["source"],
                    item["amount"],
                    item.get("account", "BRAC Bank Salary Account"),
                )

            if res.get("success"):
                successful_results.append(
                    {"type": trans_type, "item": item, "result": res}
                )
            else:
                execution_failures.append(
                    {
                        "type": trans_type,
                        "item": item,
                        "error": res.get("message", "Unknown error"),
                    }
                )

        except Exception as e:
            execution_failures.append(
                {"type": trans_type, "item": item, "error": str(e)}
            )

    # PHASE 3: BUILD COMPREHENSIVE RESPONSE
    total_attempted = len(transaction_data.get("data", []))
    total_saved = len(successful_results)
    total_failed = len(failed_items) + len(execution_failures)

    # If nothing succeeded, return failure
    if total_saved == 0:
        error_msg = "❌ No transactions were saved.\n\n"
        if validation_errors:
            error_msg += "Validation errors:\n" + "\n".join(
                f"• {err}" for err in validation_errors
            )
        if execution_failures:
            error_msg += "\n\nExecution errors:\n" + "\n".join(
                f"• {f['item'].get('item') or f['item'].get('source')}: {f['error']}"
                for f in execution_failures
            )
        return {"success": False, "message": error_msg}

    # Build success response with warnings about failures
    warnings = [
        r["result"].get("budget_warning")
        for r in successful_results
        if r["result"].get("budget_warning")
    ]
    checklist_msgs = [
        r["result"].get("checklist_ticked")
        for r in successful_results
        if r["result"].get("checklist_ticked")
    ]

    response = {
        "success": True,
        "count": total_saved,
        "total_attempted": total_attempted,
        "budget_warnings": warnings,
        "checklist_messages": checklist_msgs,
        "saved_items": [
            {
                "name": r["item"].get("item") or r["item"].get("source"),
                "amount": r["item"].get("amount"),
            }
            for r in successful_results
        ],
    }

    # Add failure details if any
    if failed_items or execution_failures:
        response["partial_success"] = True
        response["failed_count"] = total_failed
        response["failures"] = []

        for failed in failed_items:
            response["failures"].append(
                {
                    "name": failed["name"],
                    "amount": failed.get("amount"),
                    "reason": "; ".join(failed["errors"]),
                }
            )

        for failed in execution_failures:
            response["failures"].append(
                {
                    "name": failed["item"].get("item") or failed["item"].get("source"),
                    "amount": failed["item"].get("amount"),
                    "reason": failed["error"],
                }
            )

    return response
