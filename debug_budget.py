import os
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from expenses.services import ask_gemini, process_transaction

# Test the same message
text = "Paid 3000 for lunch using millenium credit card"

print(f"Testing: '{text}'")
print("="*60)

# Step 1: Ask Gemini
gemini_response = ask_gemini(text)
print(f"\n1. Gemini Parsed:")
print(gemini_response)

# Step 2: Process transaction
if gemini_response["type"] == "expense":
    result = process_transaction(gemini_response)
    print(f"\n2. Process Result:")
    print(result)
    
    # Step 3: Check what was extracted
    print(f"\n3. Extracted Data:")
    for item in gemini_response["data"]:
        print(f"   Item: {item.get('item')}")
        print(f"   Amount: {item.get('amount')}")
        print(f"   Category: {item.get('category')}")
        print(f"   Account: {item.get('account')}")
