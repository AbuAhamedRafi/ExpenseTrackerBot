import os
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from expenses.services import ask_gemini, process_transaction

def test_message(text):
    print(f"\n--- Testing Message: '{text}' ---")
    
    # 1. Ask Gemini
    print("🤖 Asking Gemini...")
    gemini_response = ask_gemini(text)
    print(f"🔹 Gemini Response: {gemini_response}")
    
    if gemini_response["type"] in ["expense", "income"]:
        # 2. Process Transaction (Add to Notion)
        print("📤 Sending to Notion...")
        result = process_transaction(gemini_response)
        print(f"✅ Result: {result}")
    else:
        print("ℹ️ Not an expense/income message.")

if __name__ == "__main__":
    # Test Expense
    test_message("Lunch 150")
    
    # Test Income
    test_message("Salary credited 50000")
