"""
utils/alerts.py
---------------
Alert generation for low stock and overdue invoices.
"""

from modules.inventory import get_low_stock_products
from modules.invoice import update_overdue_invoices
from modules.reporting import get_aged_receivables
from datetime import datetime


def get_all_alerts():
    """Consolidate all system alerts into a single list."""
    alerts = []

    # Low Stock Alerts
    low_stock = get_low_stock_products()
    for p in low_stock:
        severity = 'critical' if p['current_stock'] <= 0 else 'warning'
        alerts.append({
            'type': 'LOW_STOCK',
            'severity': severity,
            'message': (
                f"[{p['product_code']}] {p['product_name']}: "
                f"Stock={p['current_stock']}, "
                f"Reorder Level={p['reorder_level']}"
            ),
            'data': p,
            'timestamp': datetime.now().isoformat()
        })

    # Overdue Invoice Alerts
    update_overdue_invoices()
    aged = get_aged_receivables()

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
            'timestamp': datetime.now().isoformat()
        })

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
            'timestamp': datetime.now().isoformat()
        })

    severity_order = {'critical': 0, 'warning': 1, 'info': 2}
    alerts.sort(key=lambda a: severity_order.get(a['severity'], 3))

    return alerts