import os
import requests
from dotenv import load_dotenv

load_dotenv()

def get_category_budget(category_name):
    """Fetch budget for a specific category"""
    db_id = os.getenv("NOTION_CATEGORIES_DB_ID")
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
        "Notion-Version": os.getenv("NOTION_VERSION", "2022-06-28"),
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, json={})
    
    if response.status_code == 200:
        results = response.json().get("results", [])
        
        for page in results:
            name_prop = page.get("properties", {}).get("Name", {})
            title_list = name_prop.get("title", [])
            
            if title_list:
                page_name = title_list[0].get("text", {}).get("content", "")
                
                if page_name.lower() == category_name.lower():
                    # Found the category, get the budget
                    properties = page.get("properties", {})
                    
                    # Check for common budget property names
                    for prop_name in ["Budget", "Monthly Budget", "Limit"]:
                        if prop_name in properties:
                            budget_prop = properties[prop_name]
                            budget_type = budget_prop.get("type")
                            
                            if budget_type == "number":
                                return budget_prop.get("number")
                    
                    print(f"Available properties for {page_name}:")
                    for prop_name, prop_data in properties.items():
                        print(f"  - {prop_name}: {prop_data.get('type')}")
                    
    return None

# Test
categories = ["Transportation", "Food", "Shopping", "Entertainment", "Health", "Housing(rent)"]
print("\n📊 Category Budgets:")
print("="*50)
for cat in categories:
    budget = get_category_budget(cat)
    if budget:
        print(f"{cat}: ${budget}")
    else:
        print(f"{cat}: No budget set")
