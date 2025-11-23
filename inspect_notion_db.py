import os
import requests
from dotenv import load_dotenv

load_dotenv()

def get_database_schema(db_id, db_name):
    url = f"https://api.notion.com/v1/databases/{db_id}"
    headers = {
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
        "Notion-Version": os.getenv("NOTION_VERSION", "2022-06-28"),
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        properties = data.get("properties", {})
        
        print(f"\n{'='*60}")
        print(f"{db_name} Database Properties:")
        print(f"{'='*60}")
        
        for prop_name, prop_data in properties.items():
            prop_type = prop_data.get("type")
            print(f"  - {prop_name}: {prop_type}")
    else:
        print(f"Error fetching {db_name}: {response.status_code}")
        print(response.text)

# Inspect all databases
get_database_schema(os.getenv("NOTION_EXPENSE_DB_ID"), "Expenses")
get_database_schema(os.getenv("NOTION_INCOME_DB_ID"), "Income")
get_database_schema(os.getenv("NOTION_ACCOUNTS_DB_ID"), "Accounts")
get_database_schema(os.getenv("NOTION_CATEGORIES_DB_ID"), "Categories")
