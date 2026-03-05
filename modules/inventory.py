"""
Inventory management — products, stock movements, ABC classification, CSV I/O.

Important: stock is only deducted when an invoice is dispatched, NOT when it's created.
"""

from database import get_connection, log_audit
from datetime import datetime, timedelta
import csv


# -----------------------------------------------------------------------
#  Product CRUD
# -----------------------------------------------------------------------

def add_product(product_code, product_name, category_id, unit,
                purchase_price, selling_price, gst_rate, current_stock,
                reorder_level, user_id=None):
    """Insert a new product. If there's initial stock, log a purchase transaction too."""
    conn = get_connection()
    try:
        cursor = conn.execute("""
            INSERT INTO products
            (product_code,product_name,category_id,unit,purchase_price,
             selling_price,gst_rate,current_stock,reorder_level)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (product_code, product_name, category_id, unit, purchase_price,
              selling_price, gst_rate, current_stock, reorder_level))
        pid = cursor.lastrowid

        # If they're adding a product with stock already on hand, record it
        if current_stock > 0:
            _record_stock_txn(conn, pid, 'purchase', current_stock,
                              purchase_price, 'INIT', 'Initial stock', user_id)

        log_audit(user_id, 'ADD_PRODUCT', 'products', pid,
                  None, {'code': product_code}, conn)
        conn.commit()
        return pid
    except Exception as err:
        conn.rollback()
        raise err
    finally:
        conn.close()


def update_product(product_id, user_id=None, **kwargs):
    """Update whichever product fields are passed in via kwargs."""
    conn = get_connection()
    allowed = ['product_name', 'category_id', 'unit', 'purchase_price',
               'selling_price', 'gst_rate', 'reorder_level', 'is_active']
    clauses, vals = [], []
    for key, val in kwargs.items():
        if key in allowed:
            clauses.append(f"{key}=?")
            vals.append(val)

    if not clauses:
        conn.close()
        return False

    clauses.append("updated_at=?")
    vals.extend([datetime.now().isoformat(), product_id])
    conn.execute(
        f"UPDATE products SET {','.join(clauses)} WHERE product_id=?", vals)

    log_audit(user_id, 'UPDATE_PRODUCT', 'products', product_id,
              None, kwargs, conn)
    conn.commit()
    conn.close()
    return True


def get_product(product_id):
    """Fetch a single product by ID, including its category name."""
    conn = get_connection()
    row = conn.execute("""
        SELECT p.*, c.category_name FROM products p
        LEFT JOIN categories c ON p.category_id=c.category_id
        WHERE p.product_id=?
    """, (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_products(active_only=True):
    """Get all products with calculated profit margin."""
    conn = get_connection()
    query = """
        SELECT p.*, c.category_name,
            (p.selling_price - p.purchase_price) as profit_margin,
            CASE WHEN p.purchase_price > 0
                THEN ROUND(((p.selling_price-p.purchase_price)
                    /p.purchase_price)*100, 1)
                ELSE 0 END as margin_percent
        FROM products p
        LEFT JOIN categories c ON p.category_id=c.category_id
    """
    if active_only:
        query += " WHERE p.is_active=1"
    query += " ORDER BY p.product_name"

    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_products(term):
    """Search products by name, code, or category."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.*, c.category_name FROM products p
        LEFT JOIN categories c ON p.category_id=c.category_id
        WHERE (p.product_name LIKE ? OR p.product_code LIKE ?
               OR c.category_name LIKE ?) AND p.is_active=1
        ORDER BY p.product_name
    """, (f"%{term}%", f"%{term}%", f"%{term}%")).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_product(product_id, user_id=None):
    """Soft-delete — just sets is_active to 0 so history is preserved."""
    conn = get_connection()
    conn.execute("UPDATE products SET is_active=0, updated_at=? WHERE product_id=?",
                 (datetime.now().isoformat(), product_id))
    log_audit(user_id, 'DELETE_PRODUCT', 'products', product_id, None, None, conn)
    conn.commit()
    conn.close()


# -----------------------------------------------------------------------
#  Stock movements
# -----------------------------------------------------------------------

def _record_stock_txn(conn, product_id, txn_type, quantity,
                      unit_price=0, ref='', remarks='', user_id=None):
    """
    Internal helper — writes a stock transaction row and adjusts the
    product's current_stock accordingly. Does NOT commit (caller handles that).
    """
    total = quantity * unit_price
    conn.execute("""
        INSERT INTO stock_transactions
        (product_id,transaction_type,quantity,unit_price,
         total_amount,reference_no,remarks,created_by)
        VALUES (?,?,?,?,?,?,?,?)
    """, (product_id, txn_type, quantity, unit_price, total, ref, remarks, user_id))

    # Inbound types add stock, outbound types subtract
    if txn_type in ('purchase', 'adjustment_in', 'return_in'):
        conn.execute("""
            UPDATE products SET current_stock=current_stock+?, updated_at=?
            WHERE product_id=?
        """, (quantity, datetime.now().isoformat(), product_id))
    elif txn_type in ('sale', 'adjustment_out', 'return_out', 'dispatch'):
        conn.execute("""
            UPDATE products SET current_stock=current_stock-?, updated_at=?
            WHERE product_id=?
        """, (quantity, datetime.now().isoformat(), product_id))


def record_stock_transaction(product_id, txn_type, quantity,
                              unit_price=0, ref='', remarks='',
                              user_id=None, conn=None):
    """Public wrapper — records a stock movement, optionally on an existing connection."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    try:
        _record_stock_txn(conn, product_id, txn_type, quantity,
                          unit_price, ref, remarks, user_id)
        if should_close:
            conn.commit()
        return True
    except Exception as err:
        if should_close:
            conn.rollback()
        raise err
    finally:
        if should_close:
            conn.close()


def check_stock_availability(product_id, required_qty):
    """
    Quick stock check. Returns a tuple of (is_enough, current_stock, shortage).
    Shortage is 0 if there's plenty.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT current_stock FROM products WHERE product_id=?",
        (product_id,)).fetchone()
    conn.close()
    if not row:
        return False, 0, required_qty
    current = row['current_stock']
    return (current >= required_qty, current, max(0, required_qty - current))


def get_stock_history(product_id, limit=100):
    """Get the recent stock transaction log for a particular product."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT st.*, u.full_name as created_by_name
        FROM stock_transactions st
        LEFT JOIN users u ON st.created_by=u.user_id
        WHERE st.product_id=?
        ORDER BY st.transaction_date DESC LIMIT ?
    """, (product_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# -----------------------------------------------------------------------
#  ABC classification
# -----------------------------------------------------------------------

def calculate_abc_classification():
    """
    Run ABC analysis on all active products based on the last 12 months
    of sales/dispatch value. A = top 80%, B = next 15%, C = bottom 5%.
    """
    conn = get_connection()
    one_year_ago = (datetime.now() - timedelta(days=365)).isoformat()

    rows = conn.execute("""
        SELECT p.product_id, COALESCE(SUM(st.total_amount),0) as annual_value
        FROM products p
        LEFT JOIN stock_transactions st ON p.product_id=st.product_id
            AND st.transaction_type IN ('sale','dispatch')
            AND st.transaction_date>=?
        WHERE p.is_active=1
        GROUP BY p.product_id ORDER BY annual_value DESC
    """, (one_year_ago,)).fetchall()

    products = [dict(r) for r in rows]
    grand_total = sum(p['annual_value'] for p in products)

    if grand_total == 0:
        # No sales data — everything stays as class C
        conn.execute("UPDATE products SET abc_class='C', annual_consumption_value=0")
        conn.commit()
        conn.close()
        return

    running_total = 0
    for p in products:
        running_total += p['annual_value']
        pct = (running_total / grand_total) * 100
        abc = 'A' if pct <= 80 else ('B' if pct <= 95 else 'C')
        conn.execute("""
            UPDATE products SET abc_class=?, annual_consumption_value=?, updated_at=?
            WHERE product_id=?
        """, (abc, p['annual_value'], datetime.now().isoformat(), p['product_id']))

    conn.commit()
    conn.close()


def get_abc_summary():
    """Get a quick breakdown of how many products fall into each ABC class."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT abc_class, COUNT(*) as product_count,
            COALESCE(SUM(annual_consumption_value),0) as total_value,
            COALESCE(SUM(current_stock*selling_price),0) as stock_value
        FROM products WHERE is_active=1
        GROUP BY abc_class ORDER BY abc_class
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_low_stock_products():
    """Products sitting at or below their reorder level."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.*, c.category_name FROM products p
        LEFT JOIN categories c ON p.category_id=c.category_id
        WHERE p.current_stock<=p.reorder_level AND p.is_active=1
        ORDER BY (p.current_stock-p.reorder_level) ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_categories():
    """All product categories, alphabetically."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM categories ORDER BY category_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_category(name, desc=""):
    """Create a new category."""
    conn = get_connection()
    cid = conn.execute(
        "INSERT INTO categories (category_name,description) VALUES (?,?)",
        (name, desc)).lastrowid
    conn.commit()
    conn.close()
    return cid


# -----------------------------------------------------------------------
#  CSV import/export
# -----------------------------------------------------------------------

def export_products_csv(filepath):
    """Dump all products to a CSV file."""
    products = get_all_products(active_only=False)
    if not products:
        return False
    fields = ['product_code', 'product_name', 'category_name', 'unit',
              'purchase_price', 'selling_price', 'gst_rate',
              'current_stock', 'reorder_level', 'abc_class']
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(products)
    return True


def import_products_csv(filepath, user_id=None):
    """
    Import products from a CSV file. Creates categories on-the-fly if needed.
    Returns (success_count, error_count, error_details).
    """
    categories = {c['category_name']: c['category_id']
                  for c in get_all_categories()}
    success, errors = 0, []

    with open(filepath, 'r', encoding='utf-8') as f:
        for row_num, row in enumerate(csv.DictReader(f), start=2):
            try:
                cat_name = row.get('category_name', 'General')
                cid = categories.get(cat_name)
                if not cid:
                    cid = add_category(cat_name)
                    categories[cat_name] = cid

                add_product(
                    row['product_code'], row['product_name'], cid,
                    row.get('unit', 'pcs'),
                    float(row.get('purchase_price', 0)),
                    float(row.get('selling_price', 0)),
                    float(row.get('gst_rate', 18)),
                    float(row.get('current_stock', 0)),
                    float(row.get('reorder_level', 10)),
                    user_id
                )
                success += 1
            except Exception as err:
                errors.append(f"Row {row_num}: {err}")

    return success, len(errors), errors