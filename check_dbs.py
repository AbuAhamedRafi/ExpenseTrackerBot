import os
import requests
from dotenv import load_dotenv

load_dotenv()

def inspect_database(db_id, db_name):
    url = f"https://api.notion.com/v1/databases/{db_id}"
    headers = {
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
        "Notion-Version": os.getenv("NOTION_VERSION", "2022-06-28"),
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        title_info = data.get("title", [])
        if title_info:
            actual_name = title_info[0].get("plain_text", "Unknown")
        else:
            actual_name = "Unknown"
        
        print(f"\n{db_name} (Env variable)")
        print(f"  DB ID: {db_id}")
        print(f"  Actual Name: {actual_name}")
    else:
        print(f"Error for {db_name}: {response.status_code}")

# Check all databases
print("="*60)
print("DATABASE MAPPING CHECK")
print("="*60)

inspect_database(os.getenv("NOTION_EXPENSE_DB_ID"), "NOTION_EXPENSE_DB_ID")
inspect_database(os.getenv("NOTION_INCOME_DB_ID"), "NOTION_INCOME_DB_ID")
inspect_database(os.getenv("NOTION_ACCOUNTS_DB_ID"), "NOTION_ACCOUNTS_DB_ID")
inspect_database(os.getenv("NOTION_CATEGORIES_DB_ID"), "NOTION_CATEGORIES_DB_ID")
