import os
import requests
from dotenv import load_dotenv

load_dotenv()

def inspect_fixed_expenses_db():
    # Using the old subscription DB ID (now renamed to Fixed Expenses Checklist)
    db_id = os.getenv("NOTION_SUBSCRIPTIONS_DB_ID")
    
    if not db_id:
        print("NOTION_SUBSCRIPTIONS_DB_ID not found in .env")
        return
    
    url = f"https://api.notion.com/v1/databases/{db_id}"
    headers = {
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
        "Notion-Version": os.getenv("NOTION_VERSION", "2022-06-28"),
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        
        # Get database name
        title_info = data.get("title", [])
        db_name = title_info[0].get("plain_text", "Unknown") if title_info else "Unknown"
        
        print(f"\n📋 Database: {db_name}")
        print("="*60)
        print(f"DB ID: {db_id}\n")
        
        # Get properties
        properties = data.get("properties", {})
        print("Properties:")
        for prop_name, prop_data in properties.items():
            prop_type = prop_data.get("type")
            print(f"  - {prop_name}: {prop_type}")
        
        # Query some sample entries
        print("\n\nSample Entries:")
        print("="*60)
        query_url = f"https://api.notion.com/v1/databases/{db_id}/query"
        query_response = requests.post(query_url, json={}, headers=headers)
        
        if query_response.status_code == 200:
            results = query_response.json().get("results", [])
            for page in results[:5]:  # Show first 5
                props = page.get("properties", {})
                
                # Get name
                name_prop = props.get("Name", {})
                title_list = name_prop.get("title", [])
                name = title_list[0].get("text", {}).get("content", "N/A") if title_list else "N/A"
                
                print(f"\n  Entry: {name}")
                
                # Show all properties
                for prop_name, prop_data in props.items():
                    prop_type = prop_data.get("type")
                    if prop_type == "checkbox":
                        value = prop_data.get("checkbox", False)
                        print(f"    {prop_name}: {value}")
                    elif prop_type == "number":
                        value = prop_data.get("number")
                        print(f"    {prop_name}: {value}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

inspect_fixed_expenses_db()
