"""
Notion API Client - Base functions for interacting with Notion databases.
Handles authentication, database queries, and page operations.
"""

import os
import requests


def get_headers():
    """Build Notion API request headers with auth token."""
    return {
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
        "Content-Type": "application/json",
        "Notion-Version": os.getenv("NOTION_VERSION", "2022-06-28"),
    }


def get_database_id(db_type):
    """
    Get Notion database ID from environment variables.

    Args:
        db_type: One of 'expenses', 'income', 'accounts', 'categories'

    Returns:
        Database ID string or None if not found
    """
    db_map = {
        "expenses": "NOTION_EXPENSE_DB_ID",
        "income": "NOTION_INCOME_DB_ID",
        "accounts": "NOTION_ACCOUNTS_DB_ID",
        "categories": "NOTION_CATEGORIES_DB_ID",
        "subscriptions": "NOTION_SUBSCRIPTIONS_DB_ID",
    }
    env_key = db_map.get(db_type)
    return os.getenv(env_key) if env_key else None


def query_database(database_id, filter_params=None):
    """
    Query a Notion database with optional filters.

    Args:
        database_id: Notion database ID
        filter_params: Optional filter object for the query

    Returns:
        List of page objects or empty list on failure
    """
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    payload = {"filter": filter_params} if filter_params else {}

    response = requests.post(url, json=payload, headers=get_headers())

    if response.status_code == 200:
        return response.json().get("results", [])
    return []


def create_page(database_id, properties):
    """
    Create a new page in a Notion database.

    Args:
        database_id: Target database ID
        properties: Page properties dict

    Returns:
        Tuple of (success: bool, response_data: dict or error_message: str)
    """
    url = "https://api.notion.com/v1/pages"
    payload = {"parent": {"database_id": database_id}, "properties": properties}

    response = requests.post(url, json=payload, headers=get_headers())

    if response.status_code == 200:
        return True, response.json()
    return False, response.text


def update_page(page_id, properties):
    """
    Update an existing Notion page.

    Args:
        page_id: Page ID to update
        properties: Updated properties dict

    Returns:
        True if successful, False otherwise
    """
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": properties}

    response = requests.patch(url, json=payload, headers=get_headers())
    return response.status_code == 200


def find_page_by_name(database_id, name_value):
    """
    Find a page in a database by matching its title/name property.
    Uses case-insensitive fuzzy matching.

    Args:
        database_id: Database to search
        name_value: Name to search for

    Returns:
        Page ID if found, None otherwise
    """
    pages = query_database(database_id)
    name_lower = name_value.lower().strip()

    for page in pages:
        title_prop = page.get("properties", {}).get("Name", {})
        title_list = title_prop.get("title", [])

        if title_list:
            page_name = title_list[0].get("text", {}).get("content", "")
            page_name_lower = page_name.lower().strip()

            # Exact match first
            if page_name_lower == name_lower:
                return page["id"]

            # Fuzzy match as fallback
            if name_lower in page_name_lower:
                return page["id"]

    return None


def get_all_page_names(database_id):
    """
    Get all page names from a database.

    Args:
        database_id: Database to query

    Returns:
        List of page name strings
    """
    pages = query_database(database_id)
    names = []

    for page in pages:
        title_prop = page.get("properties", {}).get("Name", {})
        title_list = title_prop.get("title", [])

        if title_list:
            name = title_list[0].get("text", {}).get("content", "")
            names.append(name)

    return names


def extract_number_property(page, property_name):
    """
    Extract a number value from a page property.
    Handles both direct number fields and formula results.

    Args:
        page: Notion page object
        property_name: Name of the property to extract

    Returns:
        Number value or None if not found/invalid
    """
    properties = page.get("properties", {})
    prop = properties.get(property_name, {})
    prop_type = prop.get("type")

    if prop_type == "number":
        return prop.get("number")
    elif prop_type == "formula":
        formula_result = prop.get("formula", {})
        if formula_result.get("type") == "number":
            return formula_result.get("number")

    return None
