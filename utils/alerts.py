"""
Alert generation — checks for low stock, overdue invoices, and anything
else that needs attention.
"""

from modules.inventory import get_low_stock_products
from modules.invoice import update_overdue_invoices
from modules.reporting import get_aged_receivables
from datetime import datetime


def get_all_alerts():
    """
    Gather all system-wide alerts into one sorted list.
    Critical stuff floats to the top so you see it first.
    """
    alerts = []

    # -- Low stock warnings --
    for product in get_low_stock_products():
        severity = 'critical' if product['current_stock'] <= 0 else 'warning'
        alerts.append({
            'type': 'LOW_STOCK',
            'severity': severity,
            'message': (
                f"[{product['product_code']}] {product['product_name']}: "
                f"Stock={product['current_stock']}, "
                f"Reorder Level={product['reorder_level']}"
            ),
            'data': product,
            'timestamp': datetime.now().isoformat(),
        })

    # -- Overdue invoices --
    update_overdue_invoices()
    aged = get_aged_receivables()

    # 90+ days overdue is critical
    for inv in aged.get('over_90', []):
        alerts.append({
            'type': 'OVERDUE_90+',
            'severity': 'critical',
            'message': (
                f"Invoice {inv['invoice_number']} "
                f"({inv['customer_name']}): "
                f"₹{inv['balance_due']:,.2f} overdue by "
                f"{inv['age_days']} days"
            ),
            'data': inv,
            'timestamp': datetime.now().isoformat(),
        })

    # 61-90 days is a warning
    for inv in aged.get('61_90', []):
        alerts.append({
            'type': 'OVERDUE_61_90',
            'severity': 'warning',
            'message': (
                f"Invoice {inv['invoice_number']} "
                f"({inv['customer_name']}): "
                f"₹{inv['balance_due']:,.2f} overdue by "
                f"{inv['age_days']} days"
            ),
            'data': inv,
            'timestamp': datetime.now().isoformat(),
        })

    # Sort so critical alerts show up first
    severity_rank = {'critical': 0, 'warning': 1, 'info': 2}
    alerts.sort(key=lambda a: severity_rank.get(a['severity'], 3))

    return alerts