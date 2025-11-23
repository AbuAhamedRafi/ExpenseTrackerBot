"""
Utility functions for managing and inspecting Notion databases.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def get_headers():
    """Returns Notion API headers."""
    return {
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
        "Notion-Version": os.getenv("NOTION_VERSION", "2022-06-28"),
        "Content-Type": "application/json"
    }


def list_accounts():
    """Lists all accounts from the Notion Accounts database."""
    db_id = os.getenv("NOTION_ACCOUNTS_DB_ID")
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    
    response = requests.post(url, headers=get_headers(), json={})
    
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


def list_categories():
    """Lists all categories from the Notion Categories database."""
    db_id = os.getenv("NOTION_CATEGORIES_DB_ID")
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    
    response = requests.post(url, headers=get_headers(), json={})
    
    if response.status_code == 200:
        results = response.json().get("results", [])
        print("\n📋 Your Notion Categories:")
        print("="*50)
        for page in results:
            name_prop = page.get("properties", {}).get("Name", {})
            title_list = name_prop.get("title", [])
            if title_list:
                category_name = title_list[0].get("text", {}).get("content", "")
                print(f"  - {category_name}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)


if __name__ == "__main__":
    """
    Run this script directly to view accounts and categories.
    Usage: python -m expenses.utils
    """
    list_accounts()
    list_categories()
