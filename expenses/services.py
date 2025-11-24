import os
import json
import time
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

from .notion_client import get_database_id, get_all_page_names

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
    Sends text to Gemini with autonomous operation capabilities.
    Gemini can perform ANY Notion operation using the autonomous_operation function.
    """
    # Get cached data
    categories, accounts = get_cached_categories_and_accounts()
    categories_list = ", ".join([f'"{cat}"' for cat in categories])
    accounts_list = ", ".join([f'"{acc}"' for acc in accounts])

    # Define the autonomous operation function
    autonomous_func = FunctionDeclaration(
        name="autonomous_operation",
        description="Execute ANY Notion database operation - queries, creates, updates, deletes, transfers, analytics, etc.",
        parameters={
            "type": "object",
            "properties": {
                "operation_type": {
                    "type": "string",
                    "enum": ["query", "create", "update", "delete", "analyze"],
                    "description": "Type of operation: query (read data), create (add new), update (modify existing), delete (remove), analyze (calculate/aggregate)",
                },
                "database": {
                    "type": "string",
                    "enum": [
                        "expenses",
                        "income",
                        "categories",
                        "accounts",
                        "subscriptions",
                        "transfers",
                    ],
                    "description": "Target database",
                },
                "filters": {
                    "type": "object",
                    "description": "Query filters (for query/analyze). Use Notion filter syntax.",
                },
                "data": {
                    "type": "object",
                    "description": "Data to create/update. Use property names from schema.",
                },
                "page_id": {
                    "type": "string",
                    "description": "Page ID for update/delete operations",
                },
                "analysis_type": {
                    "type": "string",
                    "enum": ["sum", "average", "count"],
                    "description": "Type of analysis for analyze operations",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explain what you're doing and why (for user confirmation)",
                },
            },
            "required": ["operation_type", "database", "reasoning"],
        },
    )

    # Create tool
    autonomous_tool = Tool(function_declarations=[autonomous_func])

    # Get current date dynamically
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_year = datetime.now().year

    # Build comprehensive system instruction
    system_instruction = f"""You are an autonomous financial assistant with FULL access to the user's Notion finance tracker.

🎯 YOUR CAPABILITIES:
You can perform ANY operation on these databases using the autonomous_operation function:

⏰ CURRENT DATE CONTEXT:
- Today's date: {current_date}
- Current year: {current_year}
- ALWAYS use {current_year} for the year when creating expenses/income unless user specifies otherwise
- Format dates as: YYYY-MM-DD (e.g., {current_date})

📊 DATABASES & SCHEMAS:

1. **expenses**
   - Name (title), Amount (number), Date (date)
   - Accounts (relation), Categories (relation)
   - Year, Monthly, Weekly, Misc (formulas)

2. **income**
   - Name (title), Amount (number), Date (date)
   - Accounts (relation), Misc (text)

3. **categories**
   - Name (title), Monthly Budget (number)
   - Monthly Expense, Status Bar, Status (formulas)
   - Expenses (relation)

4. **accounts**
   - Name (title), Account Type (select: Bank/Credit Card)
   - Initial Amount, Credit Limit, Utilization (numbers)
   - Current Balance, Total Income/Expense/Transfer (formulas)
   - Date (date), Payment Account (relation)

5. **subscriptions** (Fixed Expenses Checklist)
   - Name (title), Type (select), Amount (number)
   - Monthly Cost (formula), Checkbox (checkbox)
   - Account, Category (relations)

6. **transfers** (Pay/Transfer)
   - Name (title), Amount (number), Date (date)
   - From Account, To Account (relations)

📝 AVAILABLE CATEGORIES: {categories_list}
💳 AVAILABLE ACCOUNTS: {accounts_list}

🔍 NOTION FILTER SYNTAX EXAMPLES:

Simple filter:
{{"property": "Amount", "number": {{"greater_than": 500}}}}

Compound filter (AND):
{{
  "and": [
    {{"property": "Amount", "number": {{"greater_than": 500}}}},
    {{"property": "Date", "date": {{"past_week": {{}}}}}}
  ]
}}

Date filters:
- {{"property": "Date", "date": {{"past_week": {{}}}}}}
- {{"property": "Date", "date": {{"past_month": {{}}}}}}
- {{"property": "Date", "date": {{"equals": "2025-11-24"}}}}
- {{"property": "Date", "date": {{"on_or_after": "2025-11-01"}}}}

Text filters:
- {{"property": "Name", "title": {{"contains": "lunch"}}}}

Checkbox filters:
- {{"property": "Checkbox", "checkbox": {{"equals": false}}}}

💡 OPERATION EXAMPLES:

User: "Show me all expenses over 500 taka from last week"
→ autonomous_operation(
    operation_type="query",
    database="expenses",
    filters={{"and": [{{"property": "Amount", "number": {{"greater_than": 500}}}}, {{"property": "Date", "date": {{"past_week": {{}}}}}}]}},
    reasoning="Querying expenses over 500 from last week"
  )

User: "I took a pathao ride for 120 taka"
→ autonomous_operation(
    operation_type="create",
    database="expenses",
    data={{"Name": "Pathao Ride", "Amount": 120, "Categories": "Transportation", "Date": "{current_date}"}},
    reasoning="Creating transportation expense"
  )

User: "Transfer 5000 from BRAC to XYZ Credit Card"
→ autonomous_operation(
    operation_type="create",
    database="transfers",
    data={{"Name": "Transfer to XYZ", "Amount": 5000, "From Account": "BRAC Bank Salary Account", "To Account": "XYZ Credit Card", "Date": "{current_date}"}},
    reasoning="Creating transfer record"
  )

User: "Add a new category called Gifts with 2000 budget"
→ autonomous_operation(
    operation_type="create",
    database="categories",
    data={{"Name": "Gifts", "Monthly Budget": 2000}},
    reasoning="Creating new category with budget"
  )

User: "Which subscriptions are unchecked?"
→ autonomous_operation(
    operation_type="query",
    database="subscriptions",
    filters={{"property": "Checkbox", "checkbox": {{"equals": false}}}},
    reasoning="Finding unpaid subscriptions"
  )

User: "What's my average daily spending?"
→ autonomous_operation(
    operation_type="analyze",
    database="expenses",
    filters={{"property": "Date", "date": {{"past_month": {{}}}}}},
    analysis_type="average",
    reasoning="Calculating average daily spending"
  )

🎭 PERSONALITY:
- Be conversational and natural
- Use emojis occasionally (but not excessively)
- Don't ask unnecessary clarifying questions - make reasonable assumptions
- If something is ambiguous, just pick the most likely interpretation
- Show personality but stay helpful

⚠️ IMPORTANT RULES:
1. For simple expenses/income, use autonomous_operation with operation_type="create"
2. For complex queries, analytics, or anything unusual, use autonomous_operation
3. Always provide a natural response along with the function call
4. For destructive operations (delete/update), the system will ask for confirmation automatically
5. If an operation fails, I'll give you the error - you can retry with corrections
6. ALWAYS use year {current_year} for current dates unless user specifies otherwise
7. Default account is "BRAC Bank Salary Account" if not specified

🚀 BE CREATIVE AND AUTONOMOUS:
- You're not limited to predefined functions
- Figure out what the user wants and make it happen
- Combine operations if needed
- Be proactive - suggest insights when you see patterns"""

    # Initialize model
    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        tools=[autonomous_tool],
        system_instruction=system_instruction,
    )

    try:
        response = model.generate_content(text)

        # Check if Gemini wants to call functions
        function_calls = []
        natural_response = ""

        for part in response.parts:
            if part.function_call:
                function_calls.append(
                    {
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args),
                    }
                )
            elif part.text:
                natural_response += part.text

        # Return structured response
        return {
            "message": natural_response or "Let me help you with that!",
            "function_calls": function_calls if function_calls else None,
        }

    except Exception as e:
        return {
            "message": f"Oops! Something went wrong: {str(e)}",
            "function_calls": None,
        }


def execute_function_calls(function_calls, user_id=None):
    """
    Execute function calls from Gemini and return results.

    Args:
        function_calls: List of function calls from Gemini
        user_id: Telegram user ID (for confirmations)

    Returns:
        Dict with execution results
    """
    from .autonomous import execute_autonomous_operation

    results = []

    for call in function_calls:
        func_name = call["name"]
        args = call["args"]

        try:
            if func_name == "autonomous_operation":
                # Execute autonomous operation
                result = execute_autonomous_operation(args, user_id)
                results.append({"function": func_name, "result": result})
            else:
                # Unknown function
                results.append(
                    {
                        "function": func_name,
                        "result": {
                            "success": False,
                            "error": f"Unknown function: {func_name}",
                        },
                    }
                )

        except Exception as e:
            results.append(
                {"function": func_name, "result": {"success": False, "error": str(e)}}
            )

    return results
