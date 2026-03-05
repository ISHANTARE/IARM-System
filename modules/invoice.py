"""
modules/invoice.py
------------------
REDESIGNED Invoice System with 3-button lifecycle:
  1. DISPATCH  → deducts stock, marks as dispatched
  2. PAYMENT   → auto-records payment, marks as paid
  3. CANCEL    → reverses stock if dispatched, marks cancelled

KEY CHANGE: Stock is NOT deducted at invoice creation.
            Stock is deducted ONLY when dispatch button is clicked.
"""

from database import get_connection, log_audit
from datetime import datetime, timedelta


# ═══════════════════════════════════════════
#  CUSTOMER MANAGEMENT
# ═══════════════════════════════════════════

def add_customer(customer_name, customer_type='retail', phone='', email='',
                 address='', gst_number='', credit_limit=0, discount_rate=0,
                 payment_terms_days=30):
    conn = get_connection()
    cid = conn.execute("""
        INSERT INTO customers
        (customer_name,customer_type,phone,email,address,
         gst_number,credit_limit,discount_rate,payment_terms_days)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (customer_name, customer_type, phone, email, address,
          gst_number, credit_limit, discount_rate, payment_terms_days)).lastrowid
    conn.commit()
    conn.close()
    return cid


def update_customer(customer_id, **kwargs):
    conn = get_connection()
    allowed = ['customer_name', 'customer_type', 'phone', 'email',
               'address', 'gst_number', 'credit_limit', 'discount_rate',
               'payment_terms_days', 'is_active']
    clauses, vals = [], []
    for k, v in kwargs.items():
        if k in allowed:
            clauses.append(f"{k}=?")
            vals.append(v)
    if not clauses:
        conn.close()
        return False
    vals.append(customer_id)
    conn.execute(f"UPDATE customers SET {','.join(clauses)} WHERE customer_id=?", vals)
    conn.commit()
    conn.close()
    return True


def get_all_customers(active_only=True):
    conn = get_connection()
    q = "SELECT * FROM customers"
    if active_only:
        q += " WHERE is_active=1"
    q += " ORDER BY customer_name"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_customer(customer_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM customers WHERE customer_id=?",
                       (customer_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def search_customers(term):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM customers
        WHERE (customer_name LIKE ? OR phone LIKE ?) AND is_active=1
        ORDER BY customer_name
    """, (f"%{term}%", f"%{term}%")).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_customer_outstanding(customer_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT COALESCE(SUM(balance_due),0) as total
        FROM invoices WHERE customer_id=? AND status NOT IN ('cancelled','paid')
    """, (customer_id,)).fetchone()
    conn.close()
    return row['total'] if row else 0


# ═══════════════════════════════════════════
#  INVOICE CREATION (NO STOCK DEDUCTION!)
# ═══════════════════════════════════════════

def _gen_invoice_number(conn):
    """Generate sequential invoice number."""
    year = datetime.now().year
    prefix = f"INV-{year}-"
    row = conn.execute(
        "SELECT invoice_number FROM invoices WHERE invoice_number LIKE ? "
        "ORDER BY invoice_id DESC LIMIT 1", (f"{prefix}%",)).fetchone()
    num = int(row['invoice_number'].split('-')[-1]) + 1 if row else 1
    return f"{prefix}{num:05d}"


def create_invoice(customer_id, invoice_date, due_date, items,
                   remarks='', user_id=None):
    """
    Create invoice WITHOUT deducting stock.
    Stock is only deducted when dispatched.
    
    items: list of dicts with product_id, product_name, quantity,
           unit_price, discount_percent, gst_rate
    
    Returns: (invoice_id, invoice_number)
    """
    conn = get_connection()
    try:
        inv_num = _gen_invoice_number(conn)

        # Get customer discount
        cust = conn.execute(
            "SELECT discount_rate FROM customers WHERE customer_id=?",
            (customer_id,)).fetchone()
        cust_disc = cust['discount_rate'] if cust else 0

        subtotal = 0
        total_disc = 0
        total_gst = 0
        calc_items = []

        for item in items:
            qty = item['quantity']
            price = item['unit_price']
            disc = item.get('discount_percent', cust_disc)
            gst_rate = item.get('gst_rate', 18.0)

            gross = qty * price
            discount = gross * (disc / 100)
            taxable = gross - discount
            gst = taxable * (gst_rate / 100)
            line_total = taxable + gst

            subtotal += gross
            total_disc += discount
            total_gst += gst

            calc_items.append({
                'product_id': item['product_id'],
                'quantity': qty,
                'unit_price': price,
                'discount_percent': disc,
                'gst_rate': gst_rate,
                'gst_amount': round(gst, 2),
                'line_total': round(line_total, 2)
            })

        total_amount = round(subtotal - total_disc + total_gst, 2)

        # Insert invoice header — status='created', NOT dispatched
        cursor = conn.execute("""
            INSERT INTO invoices
            (invoice_number,customer_id,invoice_date,due_date,
             subtotal,discount_amount,gst_amount,total_amount,
             amount_paid,balance_due,status,
             is_dispatched,is_paid,remarks,created_by)
            VALUES (?,?,?,?,?,?,?,?,0,?,'created',0,0,?,?)
        """, (inv_num, customer_id, invoice_date, due_date,
              round(subtotal, 2), round(total_disc, 2),
              round(total_gst, 2), total_amount, total_amount,
              remarks, user_id))

        inv_id = cursor.lastrowid

        # Insert line items ONLY — no stock deduction
        for item in calc_items:
            conn.execute("""
                INSERT INTO invoice_items
                (invoice_id,product_id,quantity,unit_price,
                 discount_percent,gst_rate,gst_amount,line_total)
                VALUES (?,?,?,?,?,?,?,?)
            """, (inv_id, item['product_id'], item['quantity'],
                  item['unit_price'], item['discount_percent'],
                  item['gst_rate'], item['gst_amount'], item['line_total']))

        log_audit(user_id, 'CREATE_INVOICE', 'invoices', inv_id,
                  None, {'number': inv_num, 'total': total_amount}, conn)

        conn.commit()
        return inv_id, inv_num

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ═══════════════════════════════════════════════════
#  BUTTON 1: DISPATCH — Deducts stock from inventory
# ═══════════════════════════════════════════════════

def dispatch_invoice(invoice_id, user_id=None):
    """
    Mark invoice as dispatched and DEDUCT stock.
    This is when inventory actually gets reduced.
    
    Rules:
    - Cannot dispatch if already dispatched
    - Cannot dispatch if cancelled
    - Validates stock availability before dispatching
    
    Returns: (success, message)
    """
    conn = get_connection()
    try:
        inv = conn.execute(
            "SELECT * FROM invoices WHERE invoice_id=?",
            (invoice_id,)).fetchone()

        if not inv:
            return False, "Invoice not found"

        if inv['is_dispatched'] == 1:
            return False, "Invoice is already dispatched"

        if inv['status'] == 'cancelled':
            return False, "Cannot dispatch a cancelled invoice"

        # Get all line items
        items = conn.execute(
            "SELECT ii.*, p.product_name, p.product_code, p.current_stock, p.unit "
            "FROM invoice_items ii "
            "JOIN products p ON ii.product_id=p.product_id "
            "WHERE ii.invoice_id=?", (invoice_id,)).fetchall()

        # Validate stock for ALL items first
        stock_errors = []
        for item in items:
            if item['current_stock'] < item['quantity']:
                stock_errors.append(
                    f"{item['product_code']} {item['product_name']}: "
                    f"Need {item['quantity']} {item['unit']}, "
                    f"have {item['current_stock']}"
                )

        if stock_errors:
            return False, "Insufficient stock:\n" + "\n".join(stock_errors)

        # All stock OK — deduct for each item
        from modules.inventory import _record_stock_txn

        for item in items:
            _record_stock_txn(
                conn, item['product_id'], 'dispatch', item['quantity'],
                item['unit_price'], inv['invoice_number'],
                f"Dispatched via {inv['invoice_number']}", user_id
            )

        # Update invoice status
        conn.execute("""
            UPDATE invoices SET
                status='dispatched',
                is_dispatched=1,
                dispatched_date=?,
                dispatched_by=?,
                updated_at=?
            WHERE invoice_id=?
        """, (datetime.now().isoformat(), user_id,
              datetime.now().isoformat(), invoice_id))

        log_audit(user_id, 'DISPATCH_INVOICE', 'invoices', invoice_id,
                  {'status': 'created'},
                  {'status': 'dispatched'}, conn)

        conn.commit()
        return True, f"Invoice {inv['invoice_number']} dispatched successfully!"

    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


# ═══════════════════════════════════════════════════
#  BUTTON 2: PAYMENT DONE — Auto-records full payment
# ═══════════════════════════════════════════════════

def mark_payment_done(invoice_id, payment_method='cash',
                      payment_reference='', user_id=None):
    """
    One-click payment: marks invoice as fully paid.
    Auto-creates payment record — no manual entry needed.
    
    Rules:
    - Must be dispatched first (goods must be sent before payment)
    - Cannot pay cancelled invoices
    - Cannot pay already paid invoices
    
    Returns: (success, message)
    """
    conn = get_connection()
    try:
        inv = conn.execute(
            "SELECT * FROM invoices WHERE invoice_id=?",
            (invoice_id,)).fetchone()

        if not inv:
            return False, "Invoice not found"

        if inv['status'] == 'cancelled':
            return False, "Cannot pay a cancelled invoice"

        if inv['is_paid'] == 1:
            return False, "Invoice is already paid"

        if inv['is_dispatched'] == 0:
            return False, "Dispatch the goods before recording payment"

        pay_amount = inv['balance_due']
        pay_date = datetime.now().strftime('%Y-%m-%d')

        # Calculate payment delay
        due_date = datetime.strptime(inv['due_date'], '%Y-%m-%d')
        today = datetime.now()
        delay = max(0, (today - due_date).days)

        # Auto-create payment record
        conn.execute("""
            INSERT INTO payments
            (invoice_id,payment_date,amount,payment_method,
             reference_no,remarks,is_auto,created_by)
            VALUES (?,?,?,?,?,?,1,?)
        """, (invoice_id, pay_date, pay_amount, payment_method,
              payment_reference,
              f"Auto-payment for {inv['invoice_number']}",
              user_id))

        # Update invoice
        conn.execute("""
            UPDATE invoices SET
                status='paid',
                is_paid=1,
                amount_paid=total_amount,
                balance_due=0,
                paid_date=?,
                paid_by=?,
                payment_method=?,
                payment_reference=?,
                payment_delay_days=?,
                updated_at=?
            WHERE invoice_id=?
        """, (pay_date, user_id, payment_method, payment_reference,
              delay, datetime.now().isoformat(), invoice_id))

        log_audit(user_id, 'PAYMENT_DONE', 'invoices', invoice_id,
                  {'status': inv['status'], 'balance': inv['balance_due']},
                  {'status': 'paid', 'balance': 0, 'method': payment_method},
                  conn)

        conn.commit()
        return True, (f"Payment of ₹{pay_amount:,.2f} recorded for "
                       f"{inv['invoice_number']}")

    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


# ═══════════════════════════════════════════════════
#  BUTTON 3: CANCEL — Reverses everything
# ═══════════════════════════════════════════════════

def cancel_invoice(invoice_id, reason='', user_id=None):
    """
    Cancel an invoice.
    - If dispatched: reverses stock deductions
    - If paid: cannot cancel (must refund first)
    - If just created: simply marks as cancelled
    
    Returns: (success, message)
    """
    conn = get_connection()
    try:
        inv = conn.execute(
            "SELECT * FROM invoices WHERE invoice_id=?",
            (invoice_id,)).fetchone()

        if not inv:
            return False, "Invoice not found"

        if inv['status'] == 'cancelled':
            return False, "Invoice is already cancelled"

        if inv['is_paid'] == 1:
            return False, ("Cannot cancel a paid invoice. "
                           "Issue a credit note / refund first.")

        # If dispatched, reverse stock
        if inv['is_dispatched'] == 1:
            items = conn.execute(
                "SELECT * FROM invoice_items WHERE invoice_id=?",
                (invoice_id,)).fetchall()

            from modules.inventory import _record_stock_txn
            for item in items:
                _record_stock_txn(
                    conn, item['product_id'], 'return_in', item['quantity'],
                    item['unit_price'], inv['invoice_number'],
                    f"Cancelled: {inv['invoice_number']} - {reason}",
                    user_id
                )

        # Mark as cancelled
        conn.execute("""
            UPDATE invoices SET
                status='cancelled',
                cancelled_date=?,
                cancelled_by=?,
                cancel_reason=?,
                updated_at=?
            WHERE invoice_id=?
        """, (datetime.now().isoformat(), user_id, reason,
              datetime.now().isoformat(), invoice_id))

        stock_msg = " Stock has been reversed." if inv['is_dispatched'] else ""
        log_audit(user_id, 'CANCEL_INVOICE', 'invoices', invoice_id,
                  {'status': inv['status']},
                  {'status': 'cancelled', 'reason': reason}, conn)

        conn.commit()
        return True, f"Invoice {inv['invoice_number']} cancelled.{stock_msg}"

    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


# ═══════════════════════════════════════════
#  INVOICE QUERIES
# ═══════════════════════════════════════════

def get_invoice(invoice_id):
    """Get complete invoice with items and payments."""
    conn = get_connection()
    row = conn.execute("""
        SELECT i.*, c.customer_name, c.gst_number, c.address, c.phone,
            u1.full_name as created_by_name,
            u2.full_name as dispatched_by_name,
            u3.full_name as paid_by_name,
            u4.full_name as cancelled_by_name
        FROM invoices i
        JOIN customers c ON i.customer_id=c.customer_id
        LEFT JOIN users u1 ON i.created_by=u1.user_id
        LEFT JOIN users u2 ON i.dispatched_by=u2.user_id
        LEFT JOIN users u3 ON i.paid_by=u3.user_id
        LEFT JOIN users u4 ON i.cancelled_by=u4.user_id
        WHERE i.invoice_id=?
    """, (invoice_id,)).fetchone()

    if not row:
        conn.close()
        return None

    invoice = dict(row)

    # Line items with product details
    items = conn.execute("""
        SELECT ii.*, p.product_name, p.product_code, p.unit
        FROM invoice_items ii
        JOIN products p ON ii.product_id=p.product_id
        WHERE ii.invoice_id=?
    """, (invoice_id,)).fetchall()
    invoice['items'] = [dict(i) for i in items]

    # Payments
    payments = conn.execute("""
        SELECT p.*, u.full_name as recorded_by
        FROM payments p
        LEFT JOIN users u ON p.created_by=u.user_id
        WHERE p.invoice_id=?
        ORDER BY p.payment_date
    """, (invoice_id,)).fetchall()
    invoice['payments'] = [dict(p) for p in payments]

    conn.close()
    return invoice


def get_invoice_with_items_summary(invoice_id):
    """Get invoice with a text summary of items for list display."""
    conn = get_connection()
    row = conn.execute("""
        SELECT i.*, c.customer_name
        FROM invoices i
        JOIN customers c ON i.customer_id=c.customer_id
        WHERE i.invoice_id=?
    """, (invoice_id,)).fetchone()

    if not row:
        conn.close()
        return None

    inv = dict(row)

    # Build items summary
    items = conn.execute("""
        SELECT p.product_name, p.product_code, ii.quantity, p.unit,
            ii.unit_price, ii.line_total
        FROM invoice_items ii
        JOIN products p ON ii.product_id=p.product_id
        WHERE ii.invoice_id=?
    """, (invoice_id,)).fetchall()

    inv['items_list'] = [dict(i) for i in items]
    inv['items_summary'] = ", ".join(
        f"{i['product_name']} ×{i['quantity']}" for i in items
    )
    inv['items_count'] = len(items)

    conn.close()
    return inv


def get_all_invoices(status_filter=None, customer_id=None):
    """Get all invoices with item summaries for list display."""
    conn = get_connection()
    q = """
        SELECT i.*,
            c.customer_name,
            GROUP_CONCAT(
                p.product_name || ' ×' || ii.quantity, ', '
            ) as items_summary,
            COUNT(ii.item_id) as items_count
        FROM invoices i
        JOIN customers c ON i.customer_id=c.customer_id
        LEFT JOIN invoice_items ii ON i.invoice_id=ii.invoice_id
        LEFT JOIN products p ON ii.product_id=p.product_id
        WHERE 1=1
    """
    params = []

    if status_filter and status_filter != 'all':
        q += " AND i.status=?"
        params.append(status_filter)
    if customer_id:
        q += " AND i.customer_id=?"
        params.append(customer_id)

    q += " GROUP BY i.invoice_id ORDER BY i.invoice_date DESC, i.invoice_id DESC"

    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_invoices_detailed():
    """Get all invoices with full item details for expanded view."""
    conn = get_connection()
    invoices = conn.execute("""
        SELECT i.*, c.customer_name
        FROM invoices i
        JOIN customers c ON i.customer_id=c.customer_id
        ORDER BY i.invoice_date DESC, i.invoice_id DESC
    """).fetchall()

    result = []
    for inv in invoices:
        d = dict(inv)
        items = conn.execute("""
            SELECT p.product_code, p.product_name, ii.quantity, p.unit,
                ii.unit_price, ii.line_total
            FROM invoice_items ii
            JOIN products p ON ii.product_id=p.product_id
            WHERE ii.invoice_id=?
        """, (inv['invoice_id'],)).fetchall()
        d['items'] = [dict(i) for i in items]
        result.append(d)

    conn.close()
    return result


def update_overdue_invoices():
    """Mark overdue invoices."""
    conn = get_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    cnt = conn.execute("""
        UPDATE invoices SET status='overdue', updated_at=?
        WHERE due_date<? AND status IN ('created','dispatched')
          AND balance_due>0 AND is_paid=0
    """, (datetime.now().isoformat(), today)).rowcount
    conn.commit()
    conn.close()
    return cnt


def check_credit_limit(customer_id, new_amount):
    """Check credit limit."""
    cust = get_customer(customer_id)
    if not cust or cust['credit_limit'] <= 0:
        return True, 0, 0
    outstanding = get_customer_outstanding(customer_id)
    return (outstanding + new_amount <= cust['credit_limit'],
            outstanding, cust['credit_limit'])