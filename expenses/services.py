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
  )
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
