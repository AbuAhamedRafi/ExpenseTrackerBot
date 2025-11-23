import os
import json
import google.generativeai as genai
from .notion_services import add_expense_to_notion, add_income_to_notion, get_all_categories, get_all_accounts

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def ask_gemini(text):
    """
    Sends text to Gemini and returns a JSON object if it's an expense/income,
    or a string response if it's conversation.
    Dynamically loads categories and accounts from Notion for context.
    """
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Fetch live data from Notion
    try:
        categories = get_all_categories()
        accounts = get_all_accounts()
    except Exception as e:
        # Fallback to basic categories if Notion fetch fails
        categories = ["Food", "Transport", "Shopping", "Entertainment", "Bills", "Health", "Education", "Others"]
        accounts = ["BRAC Bank Salary Account"]

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

    3. If the user message is conversational (e.g., "Hello", "How are you?"), 
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
    
    4. Do not include markdown formatting. Just the raw JSON string.
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


def process_transaction(transaction_data):
    """
    Processes the parsed data (expense or income) and adds it to Notion.
    """
    results = []
    
    if transaction_data["type"] == "expense":
        for item in transaction_data["data"]:
            # Validate required fields
            amount = item.get("amount")
            if amount is None or amount == 0:
                results.append({"success": False, "message": "❌ Amount is missing. Please specify an amount (e.g., 'Lunch 150')."})
                continue
                
            res = add_expense_to_notion(
                item["item"], 
                item["amount"], 
                item.get("category", ""), 
                item.get("account", "BRAC Bank Salary Account")
            )
            results.append(res)
            
    elif transaction_data["type"] == "income":
        for item in transaction_data["data"]:
            res = add_income_to_notion(
                item["source"], 
                item["amount"], 
                item.get("account", "BRAC Bank Salary Account")
            )
            results.append(res)

    # Check if all succeeded
    if all(r.get("success") for r in results):
        # Collect budget warnings and checklist messages
        warnings = [r.get("budget_warning") for r in results if r.get("budget_warning")]
        checklist_msgs = [r.get("checklist_ticked") for r in results if r.get("checklist_ticked")]
        return {"success": True, "count": len(results), "budget_warnings": warnings, "checklist_messages": checklist_msgs}
    else:
        errors = [r.get("message") for r in results if not r.get("success")]
        return {"success": False, "message": "; ".join(errors)}

