"""
Autonomous Operations Module - Enables Gemini to perform ANY Notion operation.
Includes schema inspection, validation, smart execution, and confirmation management.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from django.utils import timezone

from .notion_client import (
    get_database_id,
    query_database,
    create_page,
    update_page,
    archive_page,
    find_page_by_name,
    get_session,
    get_headers,
)


# ============================================================================
# SCHEMA INSPECTOR - Dynamically fetch and cache database schemas
# ============================================================================


class SchemaInspector:
    """Fetches and caches Notion database schemas for validation."""

    _cache = {}
    _cache_duration = 3600  # 1 hour

    # Fallback schemas if Notion API fails
    _fallback_schemas = {
        "loans": {
            "Name": "title",
            "Total Debt Value": "number",
            "Start Date": "date",
            "Lender/Source": "select",
            "Repayments": "relation",
            "Disbursements": "relation",
            "Related Account": "relation",
            "Total Paid": "rollup",
            "Remaining Balance": "formula",
            "Progress Bar": "formula",
            "Status": "formula",
        },
        "expenses": {
            "Name": "title",
            "Amount": "number",
            "Date": "date",
            "Accounts": "relation",
            "Categories": "relation",
            "Subscriptions": "relation",
            "Loan Repayment": "relation",
            "Year": "formula",
            "Monthly": "formula",
            "Weekly": "formula",
            "Misc": "formula",
        },
        "income": {
            "Name": "title",
            "Amount": "number",
            "Date": "date",
            "Accounts": "relation",
            "Loan Disbursement": "relation",
            "Misc": "text",
        },
        "categories": {
            "Name": "title",
            "Monthly Budget": "number",
            "Monthly Expense": "formula",
            "Status Bar": "formula",
            "Expenses": "relation",
            "Status": "formula",
        },
        "accounts": {
            "Name": "title",
            "Current Balance": "formula",
            "Initial Amount": "number",
            "Total Income": "formula",
            "Total Expense": "formula",
            "Total Transfer Out": "formula",
            "Total Transfer In": "formula",
            "Account Type": "select",
            "Credit Limit": "number",
            "Credit Utilization": "formula",
            "Date": "date",
            "Payment Account": "relation",
            "Linked Loans": "relation",
            "Utilization": "number",
        },
        "subscriptions": {
            "Name": "title",
            "Type": "select",
            "Amount": "number",
            "Monthly Cost": "formula",
            "Account": "relation",
            "Category": "relation",
            "Expenses": "relation",
            "Checkbox": "checkbox",
        },
        "payments": {
            "Name": "title",
            "Amount": "number",
            "Date": "date",
            "From Account": "relation",
            "To Account": "relation",
        },
    }

    @classmethod
    def get_schema(cls, database_name: str) -> Dict[str, str]:
        """Get schema for a database (cached or fresh)."""
        current_time = time.time()

        # Check cache
        if database_name in cls._cache:
            cached_data = cls._cache[database_name]
            if current_time - cached_data["timestamp"] < cls._cache_duration:
                return cached_data["schema"]

        # Fetch from Notion
        try:
            db_id = get_database_id(database_name)
            if not db_id:
                return cls._fallback_schemas.get(database_name, {})

            schema = cls._fetch_schema_from_notion(db_id)

            # Cache it
            cls._cache[database_name] = {"schema": schema, "timestamp": current_time}

            return schema
        except Exception:
            # Fallback to hardcoded schema
            return cls._fallback_schemas.get(database_name, {})

    @classmethod
    def _fetch_schema_from_notion(cls, database_id: str) -> Dict[str, str]:
        """Fetch schema from Notion API."""
        url = f"https://api.notion.com/v1/databases/{database_id}"

        session = get_session()
        response = session.get(url, headers=get_headers(), timeout=25)

        if response.status_code != 200:
            raise Exception("Failed to fetch schema")

        data = response.json()
        properties = data.get("properties", {})

        schema = {}
        for prop_name, prop_data in properties.items():
            schema[prop_name] = prop_data.get("type", "unknown")

        return schema

    @classmethod
    def validate_property(cls, database_name: str, property_name: str) -> bool:
        """Check if a property exists in a database schema."""
        schema = cls.get_schema(database_name)
        return property_name in schema

    @classmethod
    def get_property_type(cls, database_name: str, property_name: str) -> Optional[str]:
        """Get the type of a property."""
        schema = cls.get_schema(database_name)
        return schema.get(property_name)


# ============================================================================
# OPERATION VALIDATOR - Validate operations before execution
# ============================================================================


class OperationValidator:
    """Validates Gemini's proposed operations against Notion API constraints."""

    # Valid Notion filter operators by property type
    _valid_filters = {
        "number": [
            "equals",
            "does_not_equal",
            "greater_than",
            "less_than",
            "greater_than_or_equal_to",
            "less_than_or_equal_to",
        ],
        "text": [
            "equals",
            "does_not_equal",
            "contains",
            "does_not_contain",
            "starts_with",
            "ends_with",
        ],
        "title": [
            "equals",
            "does_not_equal",
            "contains",
            "does_not_contain",
            "starts_with",
            "ends_with",
        ],
        "date": [
            "equals",
            "before",
            "after",
            "on_or_before",
            "on_or_after",
            "past_week",
            "past_month",
            "past_year",
            "next_week",
            "next_month",
            "next_year",
        ],
        "checkbox": ["equals", "does_not_equal"],
        "select": ["equals", "does_not_equal"],
        "relation": ["contains", "does_not_contain", "is_empty", "is_not_empty"],
    }

    @classmethod
    def validate(cls, operation: Dict) -> Tuple[bool, str]:
        """
        Validate an operation.
        Returns: (is_valid, error_message)
        """
        # Check required fields
        if "database" not in operation:
            return False, "Missing 'database' field"

        if "operation_type" not in operation:
            return False, "Missing 'operation_type' field"

        database = operation["database"]
        op_type = operation["operation_type"]

        # Validate database exists
        if database not in [
            "expenses",
            "income",
            "categories",
            "accounts",
            "subscriptions",
            "payments",
            "loans",
        ]:
            return False, f"Unknown database: {database}"

        # Validate operation type
        if op_type not in ["query", "create", "update", "delete", "analyze"]:
            return False, f"Unknown operation type: {op_type}"

        # Validate based on operation type
        if op_type == "create":
            return cls._validate_create(database, operation.get("data", {}))
        elif op_type == "query" or op_type == "analyze":
            return cls._validate_query(database, operation.get("filters", {}))
        elif op_type == "update":
            if "page_id" not in operation:
                return False, "Update operation requires 'page_id'"
            return cls._validate_create(database, operation.get("data", {}))
        elif op_type == "delete":
            if "page_id" not in operation:
                return False, "Delete operation requires 'page_id'"
            return True, ""

        return True, ""

    @classmethod
    def _validate_create(cls, database: str, data: Dict) -> Tuple[bool, str]:
        """Validate create/update data."""
        if not data:
            return False, "No data provided for create operation"

        # Check if properties exist in schema
        for prop_name in data.keys():
            if not SchemaInspector.validate_property(database, prop_name):
                return (
                    False,
                    f"Property '{prop_name}' does not exist in {database} database",
                )

        return True, ""

    @classmethod
    def _validate_query(cls, database: str, filters: Dict) -> Tuple[bool, str]:
        """Validate query filters."""
        if not filters:
            return True, ""  # Empty filter is valid (returns all)

        # Validate filter structure
        if "and" in filters or "or" in filters:
            # Compound filter
            filter_list = filters.get("and", filters.get("or", []))
            for f in filter_list:
                valid, error = cls._validate_single_filter(database, f)
                if not valid:
                    return False, error
        else:
            # Single filter
            return cls._validate_single_filter(database, filters)

        return True, ""

    @classmethod
    def _validate_single_filter(
        cls, database: str, filter_obj: Dict
    ) -> Tuple[bool, str]:
        """Validate a single filter object."""
        if "property" not in filter_obj:
            return False, "Filter missing 'property' field"

        prop_name = filter_obj["property"]

        # Check if property exists
        if not SchemaInspector.validate_property(database, prop_name):
            return False, f"Property '{prop_name}' does not exist in {database}"

        # Get property type
        prop_type = SchemaInspector.get_property_type(database, prop_name)

        # For Notion filters, the structure is: {"property": "Name", "type": {"operator": value}}
        # Example: {"property": "Date", "date": {"past_week": {}}}
        # We just need to check if the property type key exists in the filter
        if prop_type and prop_type in filter_obj:
            # Valid filter structure
            return True, ""

        # If property type not in filter, it might still be valid (e.g., formula properties)
        # Be lenient and allow it
        return True, ""


# ============================================================================
# CONFIRMATION MANAGER - Handle destructive operation confirmations
# ============================================================================


# ============================================================================
# CONFIRMATION MANAGER - Handle destructive operation confirmations
# ============================================================================


class ConfirmationManager:
    """Manages pending confirmations for destructive operations using Database."""

    _expiry_minutes = 5

    @classmethod
    def store_pending(cls, user_id: str, operation: Dict) -> None:
        """Store a pending operation requiring confirmation."""
        from .models import PendingConfirmation

        expires_at = timezone.now() + timedelta(minutes=cls._expiry_minutes)

        # Update or create
        PendingConfirmation.objects.update_or_create(
            user_id=str(user_id),
            defaults={"operation_data": operation, "expires_at": expires_at},
        )

    @classmethod
    def get_pending(cls, user_id: str) -> Optional[Dict]:
        """Get pending operation for a user."""
        from .models import PendingConfirmation

        try:
            pending = PendingConfirmation.objects.get(user_id=str(user_id))

            # Check if expired
            # Note: We use naive datetime comparison or timezone aware depending on settings.
            # Assuming naive for simplicity as per project style, or use timezone.now() if configured.
            # But the project uses datetime.now() elsewhere.
            if timezone.now().timestamp() > pending.expires_at.timestamp():
                pending.delete()
                return None

            return pending.operation_data
        except PendingConfirmation.DoesNotExist:
            return None

    @classmethod
    def clear_pending(cls, user_id: str) -> None:
        """Clear pending operation for a user."""
        from .models import PendingConfirmation

        PendingConfirmation.objects.filter(user_id=str(user_id)).delete()

    @classmethod
    def cleanup_expired(cls) -> None:
        """Remove all expired pending operations."""
        from .models import PendingConfirmation

        # Simple cleanup: delete all where expires_at < now
        # We'll do this safely
        now = timezone.now()
        PendingConfirmation.objects.filter(expires_at__lt=now).delete()


# ============================================================================
# SMART EXECUTOR - Execute validated operations with retry logic
# ============================================================================


class SmartExecutor:
    """Executes validated Notion operations with idempotency and retry logic."""

    @classmethod
    def _sanitize_input(cls, data: Any) -> Any:
        """Convert MapComposite and other Protobuf types to native Python types."""
        if hasattr(data, "items"):  # MapComposite or dict
            return {k: cls._sanitize_input(v) for k, v in data.items()}
        elif isinstance(data, str) or isinstance(data, bytes):
            return data
        elif hasattr(data, "__iter__"):  # RepeatedComposite, list, tuple
            return [cls._sanitize_input(item) for item in data]
        else:
            return data

    @classmethod
    def execute(cls, operation: Dict, retry_count: int = 0) -> Dict:
        """
        Execute an operation.
        Returns: {"success": bool, "message": str, "data": Any}
        """
        # Sanitize the entire operation object first
        operation = cls._sanitize_input(operation)

        op_type = operation["operation_type"]
        database = operation["database"]

        try:
            if op_type == "query":
                return cls._handle_query(database, operation.get("filters", {}))
            elif op_type == "create":
                return cls._handle_create(database, operation["data"])
            elif op_type == "update":
                # If page_id is provided, update directly
                if "page_id" in operation:
                    return cls._handle_update(operation["page_id"], operation["data"])
                # If filters are provided, query first then update
                elif "filters" in operation:
                    return cls._handle_bulk_update(
                        operation["database"], operation["filters"], operation["data"]
                    )
                else:
                    return {
                        "success": False,
                        "message": "Update requires 'page_id' or 'filters'",
                    }
            elif op_type == "delete":
                return cls._handle_delete(operation["page_id"])
            elif op_type == "analyze":
                return cls._handle_analyze(
                    database,
                    operation.get("filters", {}),
                    operation.get("analysis_type"),
                )
            else:
                return {
                    "success": False,
                    "message": f"Unknown operation type: {op_type}",
                }

        except Exception as e:
            error_msg = str(e)

            # Retry logic (only once)
            if retry_count == 0:
                # Check idempotency before retry
                if cls._check_idempotency(operation):
                    return {"success": True, "message": "Operation already completed"}

                # Return error for Gemini to correct
                return {
                    "success": False,
                    "message": f"Operation failed: {error_msg}",
                    "retry_suggested": True,
                }
            else:
                return {
                    "success": False,
                    "message": f"Operation failed after retry: {error_msg}",
                }

    @classmethod
    def _handle_query(cls, database: str, filters: Dict) -> Dict:
        """Handle query operation."""
        db_id = get_database_id(database)
        if not db_id:
            return {"success": False, "message": f"Database '{database}' not found"}

        # Resolve relation names to IDs in filters
        if filters:
            filters = cls._resolve_filters(filters)

        results = query_database(db_id, filters if filters else None)

        # Format results for Gemini
        formatted_results = cls._format_query_results(results)

        return {
            "success": True,
            "message": f"Found {len(results)} results",
            "data": formatted_results,
        }

    @classmethod
    def _resolve_filters(cls, filters: Dict) -> Dict:
        """Recursively resolve relation names to IDs in filters."""
        if not filters:
            return filters

        resolved = filters.copy()

        # Handle compound filters (and/or)
        if "and" in resolved:
            resolved["and"] = [cls._resolve_filters(f) for f in resolved["and"]]
        if "or" in resolved:
            resolved["or"] = [cls._resolve_filters(f) for f in resolved["or"]]

        # Handle property filters
        if "property" in resolved:
            prop_name = resolved["property"]

            # Check if this is a relation property we know
            relation_map = {
                "Categories": "categories",
                "Accounts": "accounts",
                "Category": "categories",
                "Account": "accounts",
                "Payment Account": "accounts",
                "Subscriptions": "subscriptions",
                "Expenses": "expenses",
                "Loan Repayment": "loans",
                "Loan Disbursement": "loans",
                "Linked Loans": "loans",
                "Repayments": "expenses",
                "Disbursements": "income",
                "Related Account": "accounts",
            }

            target_db = relation_map.get(prop_name)
            if target_db:
                # This is a relation filter. Check if it's using a text/select/relation filter type
                # Notion requires "relation": {"contains": "id"}

                # Extract the value to search for
                search_value = None
                if "select" in resolved and "equals" in resolved["select"]:
                    search_value = resolved["select"]["equals"]
                elif (
                    "multi_select" in resolved
                    and "contains" in resolved["multi_select"]
                ):
                    search_value = resolved["multi_select"]["contains"]
                elif "rich_text" in resolved and "contains" in resolved["rich_text"]:
                    search_value = resolved["rich_text"]["contains"]
                elif "rich_text" in resolved and "equals" in resolved["rich_text"]:
                    search_value = resolved["rich_text"]["equals"]
                elif "relation" in resolved and "contains" in resolved["relation"]:
                    # Gemini might try to use the name in the relation filter
                    val = resolved["relation"]["contains"]
                    # If it's not a UUID, assume it's a name
                    if len(val) != 36:
                        search_value = val

                if search_value:
                    # Resolve name to ID
                    page_id = cls._resolve_relation_id(prop_name, search_value)
                    if page_id:
                        # Replace with valid relation filter
                        return {
                            "property": prop_name,
                            "relation": {"contains": page_id},
                        }

        return resolved

    @classmethod
    def _handle_create(cls, database: str, data: Dict) -> Dict:
        """Handle create operation."""
        db_id = get_database_id(database)
        if not db_id:
            return {"success": False, "message": f"Database '{database}' not found"}

        # Build properties based on schema
        properties = cls._build_properties(database, data)

        success, result = create_page(db_id, properties)

        if success:
            # Return clean success message, not the full Notion object
            item_name = data.get("Name", "Item")
            return {"success": True, "message": f"Created {item_name} successfully"}
        else:
            return {"success": False, "message": result}

    @classmethod
    def _handle_update(cls, page_id: str, data: Dict) -> Dict:
        """Handle update operation."""
        # We don't know which database, but update_page doesn't need it
        properties = data  # Assume data is already in Notion property format

        success = update_page(page_id, properties)

        if success:
            return {"success": True, "message": "Updated successfully"}
        else:
            return {"success": False, "message": "Update failed"}

    @classmethod
    def _handle_bulk_update(cls, database: str, filters: Dict, data: Dict) -> Dict:
        """Handle update by query (bulk update)."""
        # 1. Find pages to update
        query_result = cls._handle_query(database, filters)
        if not query_result["success"]:
            return query_result

        pages = query_result["data"]
        if not pages:
            return {"success": False, "message": "No items found to update"}

        # 2. Update each page
        # Note: query_result['data'] is formatted, we need raw IDs.
        # We should modify _handle_query to return raw IDs or re-query here.
        # For safety, let's re-query to get raw IDs
        db_id = get_database_id(database)
        raw_results = query_database(db_id, filters)

        updated_count = 0
        for page in raw_results:
            page_id = page["id"]
            # Build properties for this specific page update
            properties = cls._build_properties(database, data)
            if update_page(page_id, properties):
                updated_count += 1

        return {
            "success": True,
            "message": f"Updated {updated_count} items successfully",
        }

    @classmethod
    def _handle_delete(cls, page_id: str) -> Dict:
        """Handle delete operation."""
        success, message = archive_page(page_id)

        if success:
            return {"success": True, "message": message}
        else:
            return {"success": False, "message": message}

    @classmethod
    def _handle_analyze(cls, database: str, filters: Dict, analysis_type: str) -> Dict:
        """Handle analysis operation (aggregate, average, etc.)."""
        # First query the data
        query_result = cls._handle_query(database, filters)

        if not query_result["success"]:
            return query_result

        results = query_result["data"]

        # Perform analysis
        if analysis_type == "sum":
            total = sum(item.get("Amount", 0) for item in results)
            return {
                "success": True,
                "message": f"Total: {total}",
                "data": {"total": total},
            }
        elif analysis_type == "average":
            amounts = [item.get("Amount", 0) for item in results]
            avg = sum(amounts) / len(amounts) if amounts else 0
            return {
                "success": True,
                "message": f"Average: {avg:.2f}",
                "data": {"average": avg},
            }
        elif analysis_type == "count":
            return {
                "success": True,
                "message": f"Count: {len(results)}",
                "data": {"count": len(results)},
            }
        else:
            return {
                "success": False,
                "message": f"Unknown analysis type: {analysis_type}",
            }

    @classmethod
    def _check_idempotency(cls, operation: Dict) -> bool:
        """Check if operation was already completed."""
        # For creates: check if item with same name exists
        if operation["operation_type"] == "create":
            db_id = get_database_id(operation["database"])
            data = operation["data"]

            if "Name" in data:
                existing_id = find_page_by_name(db_id, data["Name"])
                return existing_id is not None

        # For deletes: check if page still exists (would need to query)
        # For now, return False (assume not completed)
        return False

    @classmethod
    def _build_properties(cls, database: str, data: Dict) -> Dict:
        """Build Notion properties from simple data dict."""
        properties = {}
        schema = SchemaInspector.get_schema(database)

        for key, value in data.items():
            prop_type = schema.get(key)

            if prop_type == "title":
                properties[key] = {"title": [{"text": {"content": str(value)}}]}
            elif prop_type == "number":
                properties[key] = {"number": float(value)}
            elif prop_type == "date":
                properties[key] = {"date": {"start": value}}
            elif prop_type == "checkbox":
                properties[key] = {"checkbox": bool(value)}
            elif prop_type == "select":
                properties[key] = {"select": {"name": str(value)}}
            elif prop_type == "relation":
                # Need to resolve names to page IDs
                if isinstance(value, str):
                    # Try to find page by name
                    page_id = cls._resolve_relation_id(key, value)
                    if page_id:
                        properties[key] = {"relation": [{"id": page_id}]}
                elif isinstance(value, list):
                    # Multiple relations
                    relation_ids = []
                    for v in value:
                        page_id = cls._resolve_relation_id(key, v)
                        if page_id:
                            relation_ids.append({"id": page_id})
                    if relation_ids:
                        properties[key] = {"relation": relation_ids}

        return properties

    @classmethod
    def _resolve_relation_id(cls, property_name: str, value: str) -> Optional[str]:
        """Resolve a relation name to a page ID."""
        # Map property names to their target databases
        relation_map = {
            "Categories": "categories",
            "Accounts": "accounts",
            "Category": "categories",
            "Account": "accounts",
            "From Account": "accounts",
            "To Account": "accounts",
            "Payment Account": "accounts",
            "Subscriptions": "subscriptions",
            "Expenses": "expenses",
            "Loan Repayment": "loans",
            "Loan Disbursement": "loans",
            "Linked Loans": "loans",
            "Repayments": "expenses",
            "Disbursements": "income",
            "Related Account": "accounts",
        }

        target_db = relation_map.get(property_name)
        if not target_db:
            # Unknown relation, assume value is already an ID
            return value if len(value) == 36 else None  # UUID length check

        # Look up the page by name
        db_id = get_database_id(target_db)
        if db_id:
            return find_page_by_name(db_id, value)

        return None

    @classmethod
    def _format_query_results(cls, results: List[Dict]) -> List[Dict]:
        """Format Notion query results for Gemini."""
        formatted = []

        for page in results:
            props = page.get("properties", {})
            formatted_page = {}

            # Include Metadata
            formatted_page["id"] = page.get("id")
            formatted_page["created_time"] = page.get("created_time")
            formatted_page["last_edited_time"] = page.get("last_edited_time")
            formatted_page["url"] = page.get("url")

            for prop_name, prop_data in props.items():
                prop_type = prop_data.get("type")

                try:
                    if prop_type == "title":
                        title_content = prop_data.get("title", [])
                        if title_content:
                            formatted_page[prop_name] = title_content[0].get(
                                "plain_text", ""
                            )
                    elif prop_type == "number":
                        formatted_page[prop_name] = prop_data.get("number")
                    elif prop_type == "date":
                        date_obj = prop_data.get("date", {})
                        if date_obj:
                            formatted_page[prop_name] = date_obj.get("start")
                    elif prop_type == "checkbox":
                        formatted_page[prop_name] = prop_data.get("checkbox")
                    elif prop_type == "select":
                        select_obj = prop_data.get("select", {})
                        if select_obj:
                            formatted_page[prop_name] = select_obj.get("name")
                    elif prop_type == "multi_select":
                        multi_select = prop_data.get("multi_select", [])
                        formatted_page[prop_name] = [
                            item.get("name") for item in multi_select
                        ]
                    elif prop_type == "relation":
                        # Return list of relation IDs for context
                        relations = prop_data.get("relation", [])
                        formatted_page[prop_name] = [r.get("id") for r in relations]
                    elif prop_type == "formula":
                        # Extract the computed value from formula
                        formula = prop_data.get("formula", {})
                        formula_type = formula.get("type")
                        if formula_type == "number":
                            formatted_page[prop_name] = formula.get("number")
                        elif formula_type == "string":
                            formatted_page[prop_name] = formula.get("string")
                        elif formula_type == "boolean":
                            formatted_page[prop_name] = formula.get("boolean")
                        elif formula_type == "date":
                            date_obj = formula.get("date", {})
                            if date_obj:
                                formatted_page[prop_name] = date_obj.get("start")
                    elif prop_type == "rollup":
                        # Extract the computed value from rollup
                        rollup = prop_data.get("rollup", {})
                        rollup_type = rollup.get("type")
                        if rollup_type == "number":
                            formatted_page[prop_name] = rollup.get("number")
                        elif rollup_type == "array":
                            # Try to extract values from array
                            array_items = rollup.get("array", [])
                            # Simplify: just return the raw list of values if simple
                            formatted_page[prop_name] = array_items
                    elif prop_type == "url":
                        formatted_page[prop_name] = prop_data.get("url")
                    elif prop_type == "email":
                        formatted_page[prop_name] = prop_data.get("email")
                    elif prop_type == "phone_number":
                        formatted_page[prop_name] = prop_data.get("phone_number")

                except Exception:
                    # If any property fails to format, skip it
                    continue

            formatted.append(formatted_page)

        return formatted


# ============================================================================
# PUBLIC API
# ============================================================================


def execute_autonomous_operation(operation: Dict, user_id: str = None) -> Dict:
    """
    Main entry point for autonomous operations.

    Args:
        operation: Operation dict from Gemini
        user_id: Telegram user ID (for confirmations)

    Returns:
        Result dict with success, message, and optional data
    """
    # Cleanup expired confirmations on each call
    ConfirmationManager.cleanup_expired()

    # PRIORITIZE PENDING CONFIRMATIONS
    # If we have a pending operation and the user is calling a destructive function,
    # it's likely a confirmation attempt. We check this BEFORE validation because
    # the confirmation call might be missing details (like page_id) that are in the pending op.
    if user_id and "operation_type" in operation:
        pending = ConfirmationManager.get_pending(user_id)
        if pending:
            # Check if the current operation matches the pending one's type
            # (e.g. both are "delete"). This prevents executing a pending delete
            # if the user switched to "create".
            if operation["operation_type"] == pending["operation_type"]:
                # Execute the STORED (valid) operation, not the current (potentially incomplete) one
                result = SmartExecutor.execute(pending)
                ConfirmationManager.clear_pending(user_id)
                return result

    # Validate operation
    is_valid, error_msg = OperationValidator.validate(operation)
    if not is_valid:
        return {"success": False, "message": f"Invalid operation: {error_msg}"}

    # Check if this is a destructive operation requiring confirmation
    op_type = operation["operation_type"]
    if op_type in ["delete", "update"] and user_id:
        # No pending operation found (already checked above), so this is a NEW request
        # Store for confirmation
        ConfirmationManager.store_pending(user_id, operation)
        return {
            "success": False,
            "requires_confirmation": True,
            "message": f"This will {op_type} data. Reply 'yes' to confirm.",
            "operation_details": operation.get("reasoning", ""),
        }

    # Execute operation
    return SmartExecutor.execute(operation)
