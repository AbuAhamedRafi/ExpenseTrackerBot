import os
import json
import time
from datetime import datetime, timedelta
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

from .notion_client import get_database_id, get_all_page_names
from .models import TelegramLog

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
                        "loans",
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
   - **Loan** (relation) - Link to 'loans' DB for repayments
   - Year, Monthly, Weekly, Misc (formulas)

2. **income**
   - Name (title), Amount (number), Date (date)
   - Accounts (relation), Misc (text)
   - ⚠️ **NOTE**: Income has NO 'Category' property. Do NOT ask for category.

3. **categories**
   - Name (title), Monthly Budget (number)
   - Monthly Expense, Status Bar, Status (formulas)
   - Expenses (relation)

4. **accounts**
   - Name (title), Account Type (select: Bank/Credit Card/Debit Card)
   - Initial Amount, Credit Limit, Utilization (numbers)
   - **READ-ONLY (Formulas/Rollups)**: Current Balance, Total Income, Total Expense, Total Transfer In, Total Transfer Out, Credit Utilization
   - Date (date), Payment Account (relation)
   - **Loans** (relation)

5. **subscriptions** (Fixed Expenses Checklist)
   - Name (title), Type (select), Amount (number)
   - **READ-ONLY (Formula)**: Monthly Cost
   - Account, Category (relations), Expenses (relation)
   - Checkbox (checkbox)

6. **payments** (Pay/Transfer)
   - Name (title), Amount (number), Date (date)
   - From Account, To Account (relations)

7. **loans**
   - Name (title), **Loan Type** (select: "Cash Loan" or "Purchase Loan")
   - Total Debt Value (number), Start Date (date), Lender/Source (select: Bank/Friend/Family/Baba/Other)
   - Related Account (relation to accounts), Repayments (relation to expenses), Disbursements (relation to income)
   - **READ-ONLY**: Total Paid (rollup), Remaining Balance (formula), Progress Bar (formula), Status (formula)

🧠 LOGIC & MAPPINGS:
- **Expenses**: MUST have 'Accounts' and 'Categories'.
- **Income**: MUST have 'Accounts'. NO Category.
- **Transfers**: MUST have 'From Account' and 'To Account'.
- **Loans**:
   - **Cash Loan** (Loan Type="Cash Loan"): Creates Loan + Income. Income increases account balance.
   - **Purchase Loan** (Loan Type="Purchase Loan"): Creates Loan only. No Income. No account balance change.

🔄 LOAN WORKFLOWS (STRICTLY FOLLOW THIS):

   **Type A: Cash Loans (Borrowing Money)**
   - *Context*: "Borrowed 10k from Bank", "Took a loan of 5000", "Received loan from Baba"
   - ⚠️ **CRITICAL**: You MUST make TWO function calls in your response:
     1. **First call**: Create **Loan** entry:
        - Name="Loan from [Source]"
        - **Loan Type="Cash Loan"**
        - Total Debt Value=[amount]
        - Lender/Source="[Source]" (Bank/Friend/Family/Baba/Other)
        - Start Date=[Date]
        - Related Account=[Account name]
     2. **Second call**: Create **Income** entry:
        - Name="Loan received from [Source]"
        - Amount=[amount]
        - **Accounts=[Account name]** ← CRITICAL: This is REQUIRED. Income MUST have an account.
        - **DO NOT** include any relation to the loan. Just create the income.
   - **Account Selection**:
     - If user mentions an account (e.g., "in my salary account") → Use that account name
     - If no account mentioned → Use "BRAC Bank Salary Account" as default
   - **DO NOT** ask for category. **DO NOT** stop after just creating the loan.
   - **Result**: Account balance increases by loan amount.

   **Type B: Purchase Loans (Financing an Item)**
   - *Context*: "Took a loan of 20k for Monitor", "Bought Desktop on loan from Tanvir"
   - *Action*: Create **Loan** entry ONLY (one function call):
     - Name="[Item] Loan"
     - **Loan Type="Purchase Loan"**
     - Total Debt Value=[amount]
     - Lender/Source="[Source]"
     - Start Date=[Date]
     - Related Account=[Account name for payments]
     - **Leave Disbursements empty**
   - **DO NOT** create Income. **DO NOT** create a separate account for the loan.
   - **Result**: You owe money, but account balance stays the same.

💡 OPERATION EXAMPLES:
1. "Borrowed 50k from City Bank"
   -> Call 1: autonomous_operation(op="create", db="loans", data={{"Name": "Loan from City Bank", "Loan Type": "Cash Loan", "Total Debt Value": 50000, "Lender/Source": "Bank", "Related Account": "BRAC Bank Salary Account"}})
   -> Call 2: autonomous_operation(op="create", db="income", data={{"Name": "Loan received from City Bank", "Amount": 50000, "Accounts": "BRAC Bank Salary Account"}})

2. "Took a loan of 70000 to purchase a desktop from Tanvir on march 10th 2025"
   -> autonomous_operation(op="create", db="loans", data={{"Name": "Desktop Loan", "Loan Type": "Purchase Loan", "Total Debt Value": 70000, "Lender/Source": "Friend", "Start Date": "2025-03-10", "Related Account": "BRAC Bank Salary Account"}})




   **Type C: Repayments**
   - *Context*: "Paid 5000 for Loan", "Repaid Baba", "Paid 30000 for Desktop loan"
   - ⚠️ **CRITICAL**: The expense MUST be linked to the loan using the "Loan" property.
   - *Action*: Create **Expense** entry (Name="Loan Repayment", Amount=5000, Loan="[Loan Name]", Accounts=[Account]).
     - Use the exact LOAN NAME (e.g., "Desktop Loan", "Loan from City Bank") for the "Loan" property.
     - The system will auto-resolve the name to the correct loan ID.
   - **Result**: Notion will automatically update the loan's "Total Paid" and "Remaining Balance" formulas.

3. "Paid 5k for City Bank loan"
   -> autonomous_operation(op="create", db="expenses", data={{"Name": "Loan Repayment", "Amount": 5000, "Loan": "Loan from City Bank", "Accounts": "BRAC Bank Salary Account", "Categories": "Debt"}})

4. "Spent 500 on Food"
   -> autonomous_operation(op="create", db="expenses", data={{"Name": "Food", "Amount": 500, "Categories": "Food", "Accounts": "BRAC Bank Salary Account"}})

5. "Salary 50k"
   -> autonomous_operation(op="create", db="income", data={{"Name": "Salary", "Amount": 50000, "Accounts": "BRAC Bank Salary Account"}})
   (NO Category needed)

⚠️ CRITICAL RULES:
1. **Smart Defaults vs. Questions**:
   - Small expense (< 500) & missing account? -> Use "BRAC Bank Salary Account"
   - Large expense (> 500) & missing account? -> ASK "Which account did you use?"
   - Ambiguous category? -> Infer from context (e.g., "pathao" = Transport)
   - **Missing date? -> Use today's date: {current_date}**
   - **User mentions a date? -> Use THAT date, parse it correctly (e.g., "November 17th" = "2024-11-17", "march 10th 2025" = "2025-03-10")**
   - **Income Category? -> NEVER ASK. Income has no category.**
2. **Date Handling (VERY IMPORTANT)**:
   - If user says "today", "now", or nothing about date -> Use {current_date}
   - If user says "yesterday" -> Use previous day
   - If user mentions a specific date (e.g., "November 17th", "march 10th 2025") -> Parse and use that exact date
   - Always format dates as YYYY-MM-DD
   - If user only mentions month/day without year, assume current year: {current_year}
3. For simple expenses/income, use autonomous_operation with operation_type="create"
4. For queries, use autonomous_operation with operation_type="query" or "analyze"
5. Always provide a natural response along with the function call
6. For destructive operations (delete/update), the system will ask for confirmation automatically
7. If an operation fails, I'll give you the error - you can retry with corrections

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
                context_str = f"\\n\\n[System Context - Data from previous action]: {json.dumps(log.metadata)}"
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
                {"function": func_name, "result": {"success": False, "message": str(e)}}
            )

    return results
