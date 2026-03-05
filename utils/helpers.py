"""
utils/helpers.py
----------------
Common helper functions.
"""

from datetime import datetime, timedelta


def format_currency(amount):
    """Format as Indian Rupee."""
    if amount is None:
        return "₹0.00"
    return f"₹{amount:,.2f}"


def format_date(date_str, input_fmt='%Y-%m-%d', output_fmt='%d-%b-%Y'):
    """Convert date string between formats."""
    if not date_str:
        return ""
    try:
        return datetime.strptime(date_str, input_fmt).strftime(output_fmt)
    except ValueError:
        return date_str


def validate_date(date_str, fmt='%Y-%m-%d'):
    """Validate a date string. Returns True if valid."""
    try:
        datetime.strptime(date_str, fmt)
        return True
    except ValueError:
        return False


def get_date_range(period='month'):
    """Return (start_date, end_date) strings."""
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
        qm = ((today.month - 1) // 3) * 3 + 1
        start = today.replace(month=qm, day=1)
        end = today
    elif period == 'year':
        start = today.replace(month=1, day=1)
        end = today
    else:
        start = end = today

    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def validate_required_fields(data, required):
    """Check all required fields are present and non-empty."""
    missing = []
    for field in required:
        val = data.get(field)
        if val is None or str(val).strip() == '':
            missing.append(field)
    return missing