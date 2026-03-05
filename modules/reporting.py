"""
Reporting — dashboard KPIs, aged receivables, DSO trends, profits, etc.
"""

from database import get_connection
from datetime import datetime, timedelta
import csv
import os


def get_aged_receivables():
    """
    Bucket all unpaid invoices into aging brackets:
    current (0-30 days), 31-60, 61-90, and 90+.
    """
    conn = get_connection()
    today = datetime.now()
    invoices = conn.execute("""
        SELECT i.*, c.customer_name FROM invoices i
        JOIN customers c ON i.customer_id=c.customer_id
        WHERE i.balance_due>0 AND i.status NOT IN ('cancelled','paid')
        ORDER BY i.invoice_date
    """).fetchall()
    conn.close()

    aged = {
        'current': [], '31_60': [], '61_90': [], 'over_90': [],
        'totals': {'current': 0, '31_60': 0, '61_90': 0,
                   'over_90': 0, 'grand_total': 0},
    }

    for inv in invoices:
        entry = dict(inv)
        age = (today - datetime.strptime(inv['invoice_date'], '%Y-%m-%d')).days
        entry['age_days'] = age

        if age <= 30:
            bucket = 'current'
        elif age <= 60:
            bucket = '31_60'
        elif age <= 90:
            bucket = '61_90'
        else:
            bucket = 'over_90'

        aged[bucket].append(entry)
        aged['totals'][bucket] += inv['balance_due']

    aged['totals']['grand_total'] = sum(
        aged['totals'][k] for k in ['current', '31_60', '61_90', 'over_90'])
    return aged


def calculate_dso(period_days=30):
    """
    Days Sales Outstanding — how many days, on average, it takes to collect
    payment. Lower is better.
    """
    conn = get_connection()
    end = datetime.now()
    start = end - timedelta(days=period_days)

    total_receivable = conn.execute("""
        SELECT COALESCE(SUM(balance_due),0) as v FROM invoices
        WHERE status NOT IN ('cancelled','paid') AND balance_due>0
    """).fetchone()['v']

    total_sales = conn.execute("""
        SELECT COALESCE(SUM(total_amount),0) as v FROM invoices
        WHERE invoice_date BETWEEN ? AND ? AND status!='cancelled'
    """, (start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))).fetchone()['v']

    conn.close()

    dso = (total_receivable / total_sales * period_days) if total_sales > 0 else 0
    return {
        'dso': round(dso, 1),
        'total_receivable': round(total_receivable, 2),
        'total_sales': round(total_sales, 2),
        'period_days': period_days,
    }


def get_dso_trend(months=6):
    """
    DSO calculated month-by-month for the last N months.
    Uses a single connection instead of opening one per iteration.
    """
    trend = []
    today = datetime.now()
    conn = get_connection()

    for i in range(months - 1, -1, -1):
        month_end = today - timedelta(days=30 * i)
        month_start = month_end - timedelta(days=30)

        receivable = conn.execute("""
            SELECT COALESCE(SUM(balance_due),0) as v FROM invoices
            WHERE invoice_date<=? AND status NOT IN ('cancelled','paid')
        """, (month_end.strftime('%Y-%m-%d'),)).fetchone()['v']

        sales = conn.execute("""
            SELECT COALESCE(SUM(total_amount),0) as v FROM invoices
            WHERE invoice_date BETWEEN ? AND ? AND status!='cancelled'
        """, (month_start.strftime('%Y-%m-%d'),
              month_end.strftime('%Y-%m-%d'))).fetchone()['v']

        dso = (receivable / sales * 30) if sales > 0 else 0
        trend.append({
            'month': month_end.strftime('%b %Y'),
            'dso': round(dso, 1),
            'receivable': round(receivable, 2),
            'sales': round(sales, 2),
        })

    conn.close()
    return trend


def get_top_customers_by_outstanding(limit=10):
    """Customers who owe us the most, sorted by outstanding amount."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT c.customer_id, c.customer_name, c.phone,
            c.customer_type, c.credit_limit,
            COUNT(i.invoice_id) as invoice_count,
            SUM(i.total_amount) as total_billed,
            SUM(i.balance_due) as total_outstanding,
            AVG(i.payment_delay_days) as avg_delay
        FROM customers c
        JOIN invoices i ON c.customer_id=i.customer_id
        WHERE i.status NOT IN ('cancelled') AND i.balance_due>0
        GROUP BY c.customer_id ORDER BY total_outstanding DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_customer_payment_profile(customer_id):
    """
    Build a payment profile for a customer — totals, averages, and a
    reliability rating based on how often they pay late.
    """
    conn = get_connection()

    stats = conn.execute("""
        SELECT COUNT(*) as total_invoices,
            COALESCE(SUM(total_amount),0) as total_billed,
            COALESCE(SUM(amount_paid),0) as total_paid,
            COALESCE(SUM(balance_due),0) as total_outstanding,
            COALESCE(AVG(payment_delay_days),0) as avg_delay,
            SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END) as paid_count,
            SUM(CASE WHEN status='overdue' THEN 1 ELSE 0 END) as overdue_count,
            SUM(CASE WHEN payment_delay_days>0 THEN 1 ELSE 0 END) as late_count
        FROM invoices WHERE customer_id=? AND status!='cancelled'
    """, (customer_id,)).fetchone()

    recent = conn.execute("""
        SELECT invoice_number, invoice_date, due_date, total_amount,
            amount_paid, balance_due, status, payment_delay_days,
            is_dispatched, is_paid
        FROM invoices WHERE customer_id=? AND status!='cancelled'
        ORDER BY invoice_date DESC LIMIT 20
    """, (customer_id,)).fetchall()

    conn.close()

    profile = dict(stats) if stats else {}
    profile['recent_invoices'] = [dict(r) for r in recent]

    total_invoices = profile.get('total_invoices', 0)
    if total_invoices > 0:
        late_pct = ((profile.get('late_count', 0) or 0) / total_invoices) * 100
        if late_pct <= 10:
            profile['rating'] = 'Excellent'
        elif late_pct <= 25:
            profile['rating'] = 'Good'
        elif late_pct <= 50:
            profile['rating'] = 'Average'
        else:
            profile['rating'] = 'Poor'
    else:
        profile['rating'] = 'New Customer'

    return profile


def get_dashboard_kpis():
    """Pull all the numbers needed for the main dashboard in one go."""
    conn = get_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')

    # Inventory stats
    inv_stats = conn.execute("""
        SELECT COUNT(*) as total_products,
            SUM(CASE WHEN current_stock<=reorder_level THEN 1 ELSE 0 END) as low_stock_count,
            SUM(CASE WHEN current_stock<=0 THEN 1 ELSE 0 END) as out_of_stock_count,
            COALESCE(SUM(current_stock*selling_price),0) as total_inventory_value
        FROM products WHERE is_active=1
    """).fetchone()

    # Overall sales stats
    sales_stats = conn.execute("""
        SELECT COUNT(*) as total_invoices,
            COALESCE(SUM(total_amount),0) as total_revenue,
            COALESCE(SUM(balance_due),0) as total_outstanding,
            COALESCE(SUM(amount_paid),0) as total_collected,
            SUM(CASE WHEN status='overdue' THEN 1 ELSE 0 END) as overdue_count,
            SUM(CASE WHEN is_dispatched=1 AND is_paid=0 AND status!='cancelled'
                THEN 1 ELSE 0 END) as dispatched_unpaid,
            SUM(CASE WHEN is_dispatched=0 AND status NOT IN ('cancelled','paid')
                THEN 1 ELSE 0 END) as pending_dispatch
        FROM invoices WHERE status!='cancelled'
    """).fetchone()

    # This month
    monthly = conn.execute("""
        SELECT COUNT(*) as month_invoices,
            COALESCE(SUM(total_amount),0) as month_revenue,
            COALESCE(SUM(amount_paid),0) as month_collected
        FROM invoices WHERE invoice_date>=? AND status!='cancelled'
    """, (month_start,)).fetchone()

    # Today
    daily = conn.execute("""
        SELECT COUNT(*) as today_invoices,
            COALESCE(SUM(total_amount),0) as today_revenue
        FROM invoices WHERE invoice_date=? AND status!='cancelled'
    """, (today,)).fetchone()

    customer_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM customers WHERE is_active=1"
    ).fetchone()

    conn.close()

    dso = calculate_dso(30)

    return {
        'inventory': dict(inv_stats) if inv_stats else {},
        'sales': dict(sales_stats) if sales_stats else {},
        'monthly': dict(monthly) if monthly else {},
        'daily': dict(daily) if daily else {},
        'customer_count': customer_count['cnt'] if customer_count else 0,
        'dso': dso['dso'],
    }


def get_monthly_sales_trend(months=12):
    """Revenue, collection, and outstanding by month for the last N months."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT strftime('%Y-%m', invoice_date) as month,
            COUNT(*) as invoice_count,
            COALESCE(SUM(total_amount),0) as revenue,
            COALESCE(SUM(amount_paid),0) as collected,
            COALESCE(SUM(balance_due),0) as outstanding
        FROM invoices WHERE status!='cancelled'
            AND invoice_date>=date('now', ? || ' months')
        GROUP BY strftime('%Y-%m', invoice_date) ORDER BY month
    """, (f"-{months}",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_profit_report(date_from=None, date_to=None):
    """Per-product profit breakdown for a date range."""
    conn = get_connection()
    query = """
        SELECT p.product_code, p.product_name,
            SUM(ii.quantity) as total_qty_sold,
            SUM(ii.quantity*ii.unit_price) as total_revenue,
            SUM(ii.quantity*p.purchase_price) as total_cost,
            SUM(ii.quantity*(ii.unit_price-p.purchase_price)) as total_profit
        FROM invoice_items ii
        JOIN invoices i ON ii.invoice_id=i.invoice_id
        JOIN products p ON ii.product_id=p.product_id
        WHERE i.status NOT IN ('cancelled')
    """
    params = []
    if date_from:
        query += " AND i.invoice_date>=?"
        params.append(date_from)
    if date_to:
        query += " AND i.invoice_date<=?"
        params.append(date_to)
    query += " GROUP BY p.product_id ORDER BY total_profit DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def export_aged_receivables_csv():
    """Dump the aged receivables report to a CSV file."""
    aged = get_aged_receivables()
    path = os.path.join("exports",
                        f"aged_receivables_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    items = []
    for bucket_label, bucket_key in [('0-30', 'current'), ('31-60', '31_60'),
                                      ('61-90', '61_90'), ('90+', 'over_90')]:
        for inv in aged[bucket_key]:
            items.append({
                'Bucket': bucket_label,
                'Invoice': inv['invoice_number'],
                'Customer': inv['customer_name'],
                'Date': inv['invoice_date'],
                'Total': inv['total_amount'],
                'Balance': inv['balance_due'],
                'Age': inv['age_days'],
            })
    if items:
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=items[0].keys())
            writer.writeheader()
            writer.writerows(items)
    return path