"""
General-purpose helpers — date formatting, validation, currency display.
"""

from datetime import datetime, timedelta


def format_currency(amount):
    """Format a number as Indian Rupees (₹1,23,456.00 style)."""
    if amount is None:
        return "₹0.00"
    return f"₹{amount:,.2f}"


def format_date(date_str, input_fmt='%Y-%m-%d', output_fmt='%d-%b-%Y'):
    """Convert a date string from one format to another."""
    if not date_str:
        return ""
    try:
        return datetime.strptime(date_str, input_fmt).strftime(output_fmt)
    except ValueError:
        return date_str


def validate_date(date_str, fmt='%Y-%m-%d'):
    """Check if a string is a valid date in the given format."""
    try:
        datetime.strptime(date_str, fmt)
        return True
    except ValueError:
        return False


def get_date_range(period='month'):
    """
    Get start and end dates for common time periods.
    Returns a tuple of (start_date, end_date) as YYYY-MM-DD strings.
    """
    today = datetime.now()

    if period == 'today':
        start = end = today
    elif period == 'week':
        start = today - timedelta(days=today.weekday())
        end = today
    elif period == 'month':
        start = today.replace(day=1)
        end = today
    elif period == 'quarter':
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        start = today.replace(month=quarter_start_month, day=1)
        end = today
    elif period == 'year':
        start = today.replace(month=1, day=1)
        end = today
    else:
        start = end = today

    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def validate_required_fields(data, required):
    """
    Check that all required fields are present and non-empty.
    Returns a list of field names that are missing.
    """
    missing = []
    for field in required:
        val = data.get(field)
        if val is None or str(val).strip() == '':
            missing.append(field)
    return missing