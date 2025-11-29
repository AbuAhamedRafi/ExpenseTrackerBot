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


def ask_gemini(text, user_id=None):
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
                        "payments",
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

    # Get current date in UTC+6 (Bangladesh Standard Time)
    # This ensures "today" matches the user's local time, not the server's UTC time
    from datetime import timedelta
    from .models import TelegramLog

    utc_now = datetime.utcnow()
    bd_time = utc_now + timedelta(hours=6)
    current_date = bd_time.strftime("%Y-%m-%d")
    current_year = bd_time.year

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
   - Accounts (relation), Categories (relation), Subscriptions (relation)
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
   - **READ-ONLY (Formulas/Rollups)**: Current Balance, Total Income, Total Expense, Total Transfer In, Total Transfer Out, Credit Utilization
   - Date (date), Payment Account (relation)

5. **subscriptions** (Fixed Expenses Checklist)
   - Name (title), Type (select), Amount (number)
   - **READ-ONLY (Formula)**: Monthly Cost
   - Account, Category (relations), Expenses (relation)
   - Checkbox (checkbox)

6. **payments** (Credit Card Payments/Transfers)
   - Name (title), Amount (number), Date (date)
   - From Account, To Account (relations)

📝 AVAILABLE CATEGORIES: {categories_list}
💳 AVAILABLE ACCOUNTS: {accounts_list}

🔍 ACCOUNT SHORTCUTS:
When user mentions an account name in a query WITHOUT explicitly saying "filter by", automatically add the account filter:
- "Show my BRAC expenses" → Add Accounts relation filter for "BRAC Bank Salary Account"
- "My credit card spending" → Query accounts DB, identify credit card types, filter expenses by those accounts
- "What did I buy with UCB?" → Filter by "MasterCard Platinum (UCB)"
- "BRAC transactions this month" → Filter by "BRAC Bank Salary Account" + date filter (past month)

⚠️ ROLLUP/FORMULA AWARENESS:
- **NEVER attempt to update** these read-only fields: Current Balance, Total Income, Total Expense, Total Transfer In/Out, Credit Utilization, Monthly Cost, Monthly Expense
- **Use them for summaries**: "What's my credit card balance?" → Query the account page, read the `Current Balance` rollup directly
- **Don't manually calculate**: If the data exists in a rollup/formula, use it instead of summing expenses yourself

🧠 LOGIC & MAPPINGS:
1. **Payback Logic**:
   - "Payback TO [Person]" -> Expense (Category: "Payback" or similar, or just "Others" if not found).
   - "Payback FROM [Person]" -> Income.
   - "Paid back [Person]" -> Expense.
   - "Got back from [Person]" -> Income.

2. **Category Mapping**:
   - Map specific items to broader categories if exact match missing.
   - "Snacks", "Lunch", "Dinner", "Groceries" -> "Food"
   - "Uber", "Pathao", "Rickshaw", "Bus" -> "Transport"
   - "Mobile Bill", "Internet", "Electricity" -> "Bills"
   - "Medicine", "Doctor" -> "Health"

3. **Transfer Logic**:
   - Since there is no 'transfers' database, handle transfers as:
     - **Transfer Out**: Create an Expense in the source account.
     - **Transfer In**: Create an Income in the destination account.
     - **Credit Card Payment**: Create a **Payment** in the 'payments' database.
       - Set 'From Account' to the source (e.g., Bank).
       - Set 'To Account' to the destination (e.g., Credit Card).

4. **Subscription Payment Workflow (CRITICAL - Month-Aware)**:
   - When user says "Pay [Subscription Name]":
     1. **QUERY SUBSCRIPTION**: Search 'subscriptions' DB for that name (e.g., "Netflix")
     2. **GET SUBSCRIPTION ID**: Save the page ID for linking
     3. **CHECK STATUS**: Look at the 'Checkbox' property
     4. **IF CHECKED (True)**:
        a. **QUERY LINKED EXPENSES**: Search 'expenses' DB with:
           - Filter by `Subscriptions` relation = subscription ID (from step 2)
           - Filter by `Name` contains subscription name (e.g., "Netflix")
           - Sort by Date descending (most recent first)
        b. **GET MOST RECENT EXPENSE**: Take the first result
        c. **EXTRACT PAYMENT MONTH**: Get the month from the expense Date (format: "YYYY-MM", e.g., "2025-11")
        d. **GET CURRENT MONTH**: Format today's date as "YYYY-MM"
        e. **COMPARE MONTHS**:
           - If **SAME MONTH** → STOP. Reply: "⚠️ You already paid [Name] this month! Last payment: [date]"
           - If **DIFFERENT MONTH** (e.g., last was "2025-10", now "2025-11") → CONTINUE to step 5
     5. **IF UNCHECKED OR NEW MONTH**:
        a. **UNCHECK** (if it was checked): Update 'subscriptions' DB -> Set Checkbox = False
        b. **CREATE EXPENSE**: Add to 'expenses' DB:
           - Name: "[Subscription Name]"
           - Amount: (from subscription record)
           - Date: Today's date ({current_date})
           - Accounts: (from subscription record)
           - Categories: (from subscription record)
           - **Subscriptions** relation: Link to subscription ID from step 2
        c. **RE-CHECK**: Update 'subscriptions' DB -> Set Checkbox = True
        d. Reply: "✅ Paid [Name] for this month and marked as checked."

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
    data={{"Name": "Pathao Ride", "Amount": 120, "Categories": "Transport", "Date": "{current_date}"}},
    reasoning="Creating transportation expense"
  )

User: "Transfer 5000 from BRAC to XYZ Credit Card"
→ autonomous_operation(
    operation_type="create",
    database="expenses",
    data={{"Name": "Transfer to XYZ", "Amount": 5000, "Accounts": "BRAC Bank Salary Account", "Categories": "Transfer", "Date": "{current_date}"}},
    reasoning="Creating transfer expense from BRAC"
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

User: "I paid back 200 to Farha apu"
→ autonomous_operation(
    operation_type="create",
    database="expenses",
    data={{"Name": "Payback to Farha apu", "Amount": 200, "Categories": "Others", "Date": "{current_date}"}},
    reasoning="Creating expense for payback"
  )

🎭 PERSONALITY & BEHAVIOR:
- Be conversational and natural in your responses
- Use emojis occasionally (but not excessively)
- **Prefer action over questions**, but ASK if critical info is missing
- If user says "I spent X on Y", try to infer category/account
- If you can't safely infer (e.g., large amount, ambiguous category), ASK for clarification
- Default to "BRAC Bank Salary Account" for small daily expenses if unspecified
- Show personality but prioritize execution

⚠️ CRITICAL RULES:
1. **Smart Defaults vs. Questions**:
   - Small expense (< 500) & missing account? -> Use "BRAC Bank Salary Account"
   - Large expense (> 500) & missing account? -> ASK "Which account did you use?"
   - Ambiguous category? -> Infer from context (e.g., "pathao" = Transport)
   - Missing date? -> Use today's date ({current_date})
2. For simple expenses/income, use autonomous_operation with operation_type="create"
3. For queries, use autonomous_operation with operation_type="query" or "analyze"
4. Always provide a natural response along with the function call
5. For destructive operations (delete/update), the system will ask for confirmation automatically
6. If an operation fails, I'll give you the error - you can retry with corrections
7. ALWAYS use year {current_year} for current dates unless user specifies otherwise

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

    # Build chat history from TelegramLog
    # We fetch the last 10 messages to maintain context
    history = TelegramLog.objects.filter(user_id=str(user_id)).order_by("-timestamp")[
        :10
    ]

    # Convert to Gemini format
    chat_history = []
    # History is in reverse chronological order, so we need to reverse it back
    for log in reversed(history):
        role = "user" if log.role == "user" else "model"
        content = log.content

        # Inject system context (metadata) if available for model responses
        if log.role == "model" and log.metadata:
            import json

            try:
                # Add context about the data found/modified
                context_str = f"\n\n[System Context - Data from previous action]: {json.dumps(log.metadata)}"
                content += context_str
            except:
                pass

        chat_history.append({"role": role, "parts": [content]})

    try:
        chat = model.start_chat(history=chat_history)
        response = chat.send_message(text)

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
