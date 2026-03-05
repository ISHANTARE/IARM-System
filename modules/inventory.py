"""
modules/inventory.py
--------------------
Inventory Management Module.
KEY CHANGE: Stock is deducted only on DISPATCH, not on invoice creation.
"""

from database import get_connection, log_audit
from datetime import datetime, timedelta
import csv


# ═══════════════════════════════════════════
#  PRODUCT CRUD
# ═══════════════════════════════════════════

def add_product(product_code, product_name, category_id, unit,
                purchase_price, selling_price, gst_rate, current_stock,
                reorder_level, user_id=None):
    """Add a new product."""
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

        if current_stock > 0:
            _record_stock_txn(conn, pid, 'purchase', current_stock,
                              purchase_price, 'INIT', 'Initial stock', user_id)

        log_audit(user_id, 'ADD_PRODUCT', 'products', pid,
                  None, {'code': product_code}, conn)
        conn.commit()
        return pid
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def update_product(product_id, user_id=None, **kwargs):
    """Update product fields."""
    conn = get_connection()
    allowed = ['product_name', 'category_id', 'unit', 'purchase_price',
               'selling_price', 'gst_rate', 'reorder_level', 'is_active']
    clauses, vals = [], []
    for k, v in kwargs.items():
        if k in allowed:
            clauses.append(f"{k}=?")
            vals.append(v)
    if not clauses:
        conn.close()
        return False
    clauses.append("updated_at=?")
    vals.extend([datetime.now().isoformat(), product_id])
    conn.execute(
        f"UPDATE products SET {','.join(clauses)} WHERE product_id=?", vals)
    conn.commit()
    conn.close()
    return True


def get_product(product_id):
    """Get single product."""
    conn = get_connection()
    row = conn.execute("""
        SELECT p.*, c.category_name FROM products p
        LEFT JOIN categories c ON p.category_id=c.category_id
        WHERE p.product_id=?
    """, (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_products(active_only=True):
    """Get all products with margin calculation."""
    conn = get_connection()
    q = """
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
        q += " WHERE p.is_active=1"
    q += " ORDER BY p.product_name"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_products(term):
    """Search products by name/code/category."""
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
    """Soft-delete product."""
    conn = get_connection()
    conn.execute("UPDATE products SET is_active=0, updated_at=? WHERE product_id=?",
                 (datetime.now().isoformat(), product_id))
    log_audit(user_id, 'DELETE_PRODUCT', 'products', product_id, None, None, conn)
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════
#  STOCK TRANSACTIONS
# ═══════════════════════════════════════════

def _record_stock_txn(conn, product_id, txn_type, quantity,
                      unit_price=0, ref='', remarks='', user_id=None):
    """INTERNAL: Record stock movement on existing connection. No commit."""
    total = quantity * unit_price
    conn.execute("""
        INSERT INTO stock_transactions
        (product_id,transaction_type,quantity,unit_price,
         total_amount,reference_no,remarks,created_by)
        VALUES (?,?,?,?,?,?,?,?)
    """, (product_id, txn_type, quantity, unit_price, total, ref, remarks, user_id))

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
    """PUBLIC: Record stock movement."""
    close = False
    if conn is None:
        conn = get_connection()
        close = True
    try:
        _record_stock_txn(conn, product_id, txn_type, quantity,
                          unit_price, ref, remarks, user_id)
        if close:
            conn.commit()
        return True
    except Exception as e:
        if close:
            conn.rollback()
        raise e
    finally:
        if close:
            conn.close()


def check_stock_availability(product_id, required_qty):
    """Check if enough stock available. Returns (ok, current, shortage)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT current_stock FROM products WHERE product_id=?",
        (product_id,)).fetchone()
    conn.close()
    if not row:
        return False, 0, required_qty
    cur = row['current_stock']
    return (cur >= required_qty, cur, max(0, required_qty - cur))


def get_stock_history(product_id, limit=100):
    """Get stock history for a product."""
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


# ═══════════════════════════════════════════
#  ABC CLASSIFICATION
# ═══════════════════════════════════════════

def calculate_abc_classification():
    """ABC analysis based on annual consumption value."""
    conn = get_connection()
    ago = (datetime.now() - timedelta(days=365)).isoformat()
    rows = conn.execute("""
        SELECT p.product_id, COALESCE(SUM(st.total_amount),0) as av
        FROM products p
        LEFT JOIN stock_transactions st ON p.product_id=st.product_id
            AND st.transaction_type IN ('sale','dispatch')
            AND st.transaction_date>=?
        WHERE p.is_active=1
        GROUP BY p.product_id ORDER BY av DESC
    """, (ago,)).fetchall()

    products = [dict(r) for r in rows]
    total = sum(p['av'] for p in products)

    if total == 0:
        conn.execute("UPDATE products SET abc_class='C', annual_consumption_value=0")
        conn.commit()
        conn.close()
        return

    cumulative = 0
    for p in products:
        cumulative += p['av']
        pct = (cumulative / total) * 100
        cls = 'A' if pct <= 80 else ('B' if pct <= 95 else 'C')
        conn.execute("""
            UPDATE products SET abc_class=?, annual_consumption_value=?, updated_at=?
            WHERE product_id=?
        """, (cls, p['av'], datetime.now().isoformat(), p['product_id']))

    conn.commit()
    conn.close()


def get_abc_summary():
    """ABC class summary."""
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
    """Products at or below reorder level."""
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
    """All categories."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM categories ORDER BY category_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_category(name, desc=""):
    """Add category."""
    conn = get_connection()
    cid = conn.execute(
        "INSERT INTO categories (category_name,description) VALUES (?,?)",
        (name, desc)).lastrowid
    conn.commit()
    conn.close()
    return cid


def export_products_csv(filepath):
    """Export products to CSV."""
    products = get_all_products(active_only=False)
    if not products:
        return False
    fields = ['product_code', 'product_name', 'category_name', 'unit',
              'purchase_price', 'selling_price', 'gst_rate',
              'current_stock', 'reorder_level', 'abc_class']
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(products)
    return True


def import_products_csv(filepath, user_id=None):
    """Import products from CSV."""
    categories = {c['category_name']: c['category_id']
                  for c in get_all_categories()}
    success, errors = 0, []
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            try:
                cat = row.get('category_name', 'General')
                cid = categories.get(cat)
                if not cid:
                    cid = add_category(cat)
                    categories[cat] = cid
                add_product(row['product_code'], row['product_name'], cid,
                            row.get('unit', 'pcs'),
                            float(row.get('purchase_price', 0)),
                            float(row.get('selling_price', 0)),
                            float(row.get('gst_rate', 18)),
                            float(row.get('current_stock', 0)),
                            float(row.get('reorder_level', 10)), user_id)
                success += 1
            except Exception as e:
                errors.append(f"Row {i}: {e}")
    return success, len(errors), errors