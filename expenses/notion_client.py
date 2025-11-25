"""
Notion API Client - Base functions for interacting with Notion databases.
Handles authentication, database queries, and page operations.
"""

import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configure session with connection pooling and retries
_session = None


def get_session():
    """Get or create a requests session with retry strategy and connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()

        # Retry strategy for transient failures
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PATCH", "DELETE"],
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20,
            pool_block=False,
        )

        _session.mount("https://", adapter)
        _session.mount("http://", adapter)

    return _session


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
        "payments": "NOTION_PAYMENTS_DB_ID",
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

    try:
        session = get_session()
        response = session.post(url, json=payload, headers=get_headers(), timeout=25)

        if response.status_code == 200:
            return response.json().get("results", [])
        return []
    except requests.exceptions.RequestException:
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

    try:
        session = get_session()
        response = session.post(url, json=payload, headers=get_headers(), timeout=25)

        if response.status_code == 200:
            return True, response.json()
        return False, response.text
    except requests.exceptions.Timeout:
        return False, "Notion API request timed out after 25 seconds"
    except requests.exceptions.RequestException as e:
        return False, f"Notion API request failed: {str(e)}"


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

    try:
        session = get_session()
        response = session.patch(url, json=payload, headers=get_headers(), timeout=25)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


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
    if not isinstance(name_value, str):
        return None

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


def archive_page(page_id):
    """
    Archive (soft delete) a Notion page.

    Args:
        page_id: Page ID to archive

    Returns:
        Tuple of (success: bool, message: str)
    """
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"archived": True}

    try:
        session = get_session()
        response = session.patch(url, json=payload, headers=get_headers(), timeout=25)

        if response.status_code == 200:
            return True, "Page archived successfully"
        return False, f"Failed to archive: {response.text}"
    except requests.exceptions.RequestException as e:
        return False, f"Archive request failed: {str(e)}"


def get_latest_entry(database_id, sorts=None):
    """
    Get the most recent entry from a database.

    Args:
        database_id: Database ID to query
        sorts: Optional sort configuration (defaults to created_time descending)

    Returns:
        Page object or None if not found
    """
    url = f"https://api.notion.com/v1/databases/{database_id}/query"

    # Default sort by creation time, newest first
    if sorts is None:
        sorts = [{"timestamp": "created_time", "direction": "descending"}]

    payload = {"sorts": sorts, "page_size": 1}

    try:
        session = get_session()
        response = session.post(url, json=payload, headers=get_headers(), timeout=25)

        if response.status_code == 200:
            results = response.json().get("results", [])
            return results[0] if results else None
        return None
    except requests.exceptions.RequestException:
        return None


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
