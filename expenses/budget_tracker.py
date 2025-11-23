"""
Budget Tracker - Handles budget calculations, spending analysis, and financial summaries.
"""

from datetime import datetime
from dateutil.relativedelta import relativedelta

from .notion_client import (
    get_database_id,
    query_database,
    find_page_by_name,
    extract_number_property,
)


def get_month_boundaries():
    """
    Calculate start and end dates for the current month.

    Returns:
        Tuple of (month_start_iso, month_end_iso, month_name)
    """
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = month_start + relativedelta(months=1)

    return (month_start.isoformat(), month_end.isoformat(), now.strftime("%B %Y"))


def get_category_budget(category_name):
    """
    Get the monthly budget for a specific category.
    Checks multiple possible property names for flexibility.

    Args:
        category_name: Name of the category

    Returns:
        Budget amount (float) or None if not found
    """
    category_db_id = get_database_id("categories")
    pages = query_database(category_db_id)

    category_name_lower = category_name.lower().strip()

    for page in pages:
        title_prop = page.get("properties", {}).get("Name", {})
        title_list = title_prop.get("title", [])

        if title_list:
            page_name = title_list[0].get("text", {}).get("content", "")

            if page_name.lower().strip() == category_name_lower:
                # Try different property names for budget
                for prop_name in ["Budget", "Monthly Budget", "Limit", "Monthly Cost"]:
                    budget = extract_number_property(page, prop_name)
                    if budget is not None:
                        return budget

    return None


def calculate_category_spending(category_id, month_start, month_end):
    """
    Calculate total spending for a category in a date range.

    Args:
        category_id: Category page ID
        month_start: Start date (ISO format)
        month_end: End date (ISO format)

    Returns:
        Total amount spent (float)
    """
    expense_db_id = get_database_id("expenses")

    filter_params = {
        "and": [
            {"property": "Date", "date": {"on_or_after": month_start}},
            {"property": "Date", "date": {"before": month_end}},
            {"property": "Categories", "relation": {"contains": category_id}},
        ]
    }

    expenses = query_database(expense_db_id, filter_params)

    total = sum(extract_number_property(expense, "Amount") or 0 for expense in expenses)

    return total


def calculate_total_income(month_start, month_end):
    """
    Calculate total income for a date range.

    Args:
        month_start: Start date (ISO format)
        month_end: End date (ISO format)

    Returns:
        Total income amount (float)
    """
    income_db_id = get_database_id("income")

    filter_params = {
        "and": [
            {"property": "Date", "date": {"on_or_after": month_start}},
            {"property": "Date", "date": {"before": month_end}},
        ]
    }

    income_entries = query_database(income_db_id, filter_params)

    total = sum(
        extract_number_property(entry, "Amount") or 0 for entry in income_entries
    )

    return total


def get_monthly_summary():
    """
    Generate comprehensive financial summary for current month.

    Returns:
        Dict containing:
        - month: Month name and year
        - total_income: Total income for the month
        - total_spent: Total expenses for the month
        - remaining: Income minus expenses
        - total_budget: Sum of all category budgets
        - categories: List of category summaries with spending and budgets
    """
    month_start, month_end, month_name = get_month_boundaries()

    category_db_id = get_database_id("categories")
    categories = query_database(category_db_id)

    category_summary = []
    total_spent = 0
    total_budget = 0

    for cat_page in categories:
        title_prop = cat_page.get("properties", {}).get("Name", {})
        title_list = title_prop.get("title", [])

        if title_list:
            cat_name = title_list[0].get("text", {}).get("content", "")
            cat_id = cat_page["id"]

            spent = calculate_category_spending(cat_id, month_start, month_end)

            # Only include categories with actual spending
            if spent > 0:
                budget = get_category_budget(cat_name)

                category_summary.append(
                    {"name": cat_name, "spent": spent, "budget": budget}
                )

                total_spent += spent
                if budget:
                    total_budget += budget

    total_income = calculate_total_income(month_start, month_end)

    return {
        "month": month_name,
        "total_income": total_income,
        "total_spent": total_spent,
        "remaining": total_income - total_spent,
        "total_budget": total_budget,
        "categories": category_summary,
    }


def check_budget_impact(category_name, additional_amount):
    """
    Simulate adding an expense and check budget impact.

    Args:
        category_name: Category to check
        additional_amount: Hypothetical expense amount

    Returns:
        Dict containing:
        - status: Budget status (safe, approaching_limit, close_to_limit, over_budget, no_budget, unknown)
        - message: User-friendly status message
        - current_spent: Current spending in category
        - projected_spent: Spending after adding the amount
        - budget: Category budget
        - remaining: Budget remaining after the expense
        - percentage: Percentage of budget used
    """
    month_start, month_end, _ = get_month_boundaries()

    category_db_id = get_database_id("categories")
    category_id = find_page_by_name(category_db_id, category_name)

    if not category_id:
        return {
            "status": "unknown",
            "message": f"Category '{category_name}' not found.",
        }

    current_spent = calculate_category_spending(category_id, month_start, month_end)
    budget = get_category_budget(category_name)

    if not budget:
        return {
            "status": "no_budget",
            "message": f"No budget set for '{category_name}'.",
            "current_spent": current_spent,
            "projected_spent": current_spent + additional_amount,
        }

    projected_spent = current_spent + additional_amount
    remaining = budget - projected_spent
    percentage = (projected_spent / budget) * 100

    # Determine status based on percentage thresholds
    if projected_spent > budget:
        status = "over_budget"
        message = "⚠️ You will go over budget!"
    elif percentage >= 90:
        status = "close_to_limit"
        message = "⚠️ You are close to your budget, be cautious!"
    elif percentage >= 75:
        status = "approaching_limit"
        message = "✅ You are within budget but approaching the limit."
    else:
        status = "safe"
        message = "✅ You are well within your budget!"

    return {
        "status": status,
        "message": message,
        "category": category_name,
        "current_spent": current_spent,
        "projected_spent": projected_spent,
        "budget": budget,
        "remaining": remaining,
        "percentage": percentage,
    }
