import os
import json
import datetime
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from django.conf import settings

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def ask_gemini(text):
    """
    Sends text to Gemini and returns a JSON object if it's an expense,
    or a string response if it's conversation.
    """
    model = genai.GenerativeModel("gemini-2.0-flash")

    system_instruction = """
    You are an intelligent Expense Tracker Assistant.
    Your goal is to parse user messages into structured expense data or reply conversationally.

    RULES:
    1. If the user message describes an expense (e.g., "Lunch 150", "Taxi 500 for office"), 
       output a JSON ARRAY of objects. Each object must have:
       - "item": (string) Brief description.
       - "amount": (number) The cost.
       - "category": (string) ONE of these exact categories: "Rent", "Daily Expense", "Transportation", "Food", "Shopping", "Items Bought", "Other".
       - "date": (string) Today's date in YYYY-MM-DD format.
       
       Example JSON Output:
       [{"item": "Lunch", "amount": 150, "category": "Food", "date": "2023-10-27"}]

    2. If the user message is conversational (e.g., "Hello", "How are you?", "Thanks"), 
       reply with a natural, friendly text response. Do NOT output JSON.
       
    3. If the message is unclear, ask for clarification.
    
    4. Do not include markdown formatting (like ```json) in your JSON output. Just the raw JSON string.
    """

    prompt = f"{system_instruction}\n\nUser Message: {text}"

    try:
        response = model.generate_content(prompt)
        content = response.text.strip()

        # Attempt to parse as JSON
        clean_content = content.replace("```json", "").replace("```", "").strip()

        if clean_content.startswith("[") or clean_content.startswith("{"):
            try:
                data = json.loads(clean_content)
                return {"type": "expense", "data": data}
            except json.JSONDecodeError:
                return {"type": "message", "text": content}
        else:
            return {"type": "message", "text": content}

    except Exception as e:
        return {"type": "error", "text": f"Error processing with Gemini: {str(e)}"}


def add_to_sheet(expense_data, raw_text):
    """
    Appends expense data to Google Sheet using the "Category as Column" template.
    """
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]

        # Try to load from Environment Variable first
        json_creds = os.getenv("GOOGLE_CREDENTIALS_JSON")

        if json_creds:
            creds_dict = json.loads(json_creds)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            # Fallback to file
            creds_path = os.path.join(settings.BASE_DIR, "credentials.json")
            if not os.path.exists(creds_path):
                return {
                    "message": "Credentials not found (Env or File).",
                }
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)

        client = gspread.authorize(creds)

        # Use the specific Spreadsheet ID provided by the user
        spreadsheet_id = "1LZaJL1evSBQSvEatcbMEOolfVnLqyN3YEwCan9SPT50"
        try:
            sheet = client.open_by_key(spreadsheet_id).sheet1
        except Exception as e:
            return {
                "success": False,
                "message": f"Could not open spreadsheet with ID {spreadsheet_id}: {str(e)}",
            }

        # --- Template Logic ---
        # 1. Find the Header Row (Look for "Date" in Column A)
        # We'll scan the first 20 rows to find the header
        header_row_index = None
        headers = []

        # Get first 20 rows to minimize API calls
        top_rows = sheet.get("A1:Z20")

        for idx, row in enumerate(top_rows):
            if row and row[0].strip() == "Date":
                header_row_index = idx + 1  # 1-based index
                headers = row
                break

        if not header_row_index:
            # Fallback if template is empty or different
            header_row_index = 1
            headers = [
                "Date",
                "Payment Type",
                "Description",
                "Rent",
                "Daily Expense",
                "Transportation",
                "Food",
                "Shopping",
                "Items Bought",
                "Other",
            ]
            if sheet.row_count == 0:
                sheet.append_row(headers)

        # 2. Map Categories to Column Indices (0-based relative to row list)
        # We normalize headers to lowercase for matching
        col_map = {h.lower().strip(): i for i, h in enumerate(headers)}

        # 3. Find the first empty row after the header
        # gspread's col_values truncates trailing empty cells.
        all_values = sheet.col_values(1)

        first_empty_row_idx = None

        # Check existing values starting from the header
        # start_row is 1-based
        start_row = header_row_index + 1
        for i in range(start_row - 1, len(all_values)):
            if not all_values[i].strip():
                first_empty_row_idx = i + 1
                break

        # If not found in the returned values, it means the rest of the sheet is empty
        # (or at least Column A is empty from here on)
        if not first_empty_row_idx:
            first_empty_row_idx = max(len(all_values) + 1, start_row)

        # Safety check: If we are about to write beyond the sheet limits, add rows
        if first_empty_row_idx > sheet.row_count:
            sheet.add_rows(5)  # Add a buffer of 5 rows

        # 4. Prepare and Update Rows
        current_row_idx = first_empty_row_idx

        for expense in expense_data:
            # Initialize a row with empty strings up to the last header column
            row_data = [""] * len(headers)

            # Fill standard columns
            # Date (Column A)
            row_data[0] = expense.get(
                "date", datetime.date.today().strftime("%Y-%m-%d")
            )

            # Description (Column C usually, check map)
            desc_idx = col_map.get("description", 2)
            if desc_idx < len(row_data):
                row_data[desc_idx] = expense.get("item", "Unknown")

            # Payment Type (Column B usually)
            pay_idx = col_map.get("payment type", 1)
            if pay_idx < len(row_data):
                row_data[pay_idx] = "Online/Cash"

            # Category Amount Mapping
            category = expense.get("category", "Other").strip()
            amount = expense.get("amount", 0)

            # Find the column for this category
            target_col_idx = col_map.get(category.lower())
            if target_col_idx is None:
                target_col_idx = col_map.get("other", len(headers) - 1)

            if target_col_idx < len(row_data):
                row_data[target_col_idx] = amount

            # Update the specific row in the sheet
            sheet.update(range_name=f"A{current_row_idx}", values=[row_data])

            current_row_idx += 1

        return {"success": True, "message": "Saved to Google Sheet inside Template."}

    except Exception as e:
        return {"success": False, "message": f"Google Sheets Error: {str(e)}"}
