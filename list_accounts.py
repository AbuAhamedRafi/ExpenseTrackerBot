import os
import requests
from dotenv import load_dotenv

load_dotenv()

def list_accounts():
    db_id = os.getenv("NOTION_ACCOUNTS_DB_ID")
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
        "Notion-Version": os.getenv("NOTION_VERSION", "2022-06-28"),
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, json={})
    
    if response.status_code == 200:
        results = response.json().get("results", [])
        print("\n📋 Your Notion Accounts:")
        print("="*50)
        for page in results:
            name_prop = page.get("properties", {}).get("Name", {})
            title_list = name_prop.get("title", [])
            if title_list:
                account_name = title_list[0].get("text", {}).get("content", "")
                print(f"  - {account_name}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

list_accounts()
