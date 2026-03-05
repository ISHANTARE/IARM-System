"""
Invoice lifecycle — create → dispatch → payment → done (or cancel at any point).

Key design decision:
  Stock is NOT touched when an invoice is created. It only gets deducted
  when someone clicks "Dispatch". This way you can draft invoices freely
  without messing up inventory numbers.
"""

from database import get_connection, log_audit
from datetime import datetime, timedelta


# -----------------------------------------------------------------------
#  Customer management (lives here because customers are tightly coupled
#  with invoices in this app's workflow)
# -----------------------------------------------------------------------

def add_customer(customer_name, customer_type='retail', phone='', email='',
                 address='', gst_number='', credit_limit=0, discount_rate=0,
                 payment_terms_days=30):
    """Add a new customer record."""
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
    """Update only the fields that were actually passed in."""
    conn = get_connection()
    allowed = ['customer_name', 'customer_type', 'phone', 'email',
               'address', 'gst_number', 'credit_limit', 'discount_rate',
               'payment_terms_days', 'is_active']
    clauses, vals = [], []
    for key, val in kwargs.items():
        if key in allowed:
            clauses.append(f"{key}=?")
            vals.append(val)
    if not clauses:
        conn.close()
        return False
    vals.append(customer_id)
    conn.execute(f"UPDATE customers SET {','.join(clauses)} WHERE customer_id=?", vals)
    conn.commit()
    conn.close()
    return True


def get_all_customers(active_only=True):
    """All customers, optionally filtered to active ones only."""
    conn = get_connection()
    query = "SELECT * FROM customers"
    if active_only:
        query += " WHERE is_active=1"
    query += " ORDER BY customer_name"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_customer(customer_id):
    """Fetch one customer by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM customers WHERE customer_id=?",
                       (customer_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def search_customers(term):
    """Quick search by name or phone number."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM customers
        WHERE (customer_name LIKE ? OR phone LIKE ?) AND is_active=1
        ORDER BY customer_name
    """, (f"%{term}%", f"%{term}%")).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_customer_outstanding(customer_id):
    """How much does this customer owe us across all open invoices?"""
    conn = get_connection()
    row = conn.execute("""
        SELECT COALESCE(SUM(balance_due),0) as total
        FROM invoices WHERE customer_id=? AND status NOT IN ('cancelled','paid')
    """, (customer_id,)).fetchone()
    conn.close()
    return row['total'] if row else 0


# -----------------------------------------------------------------------
#  Invoice creation — no stock changes happen here
# -----------------------------------------------------------------------

def _gen_invoice_number(conn):
    """
    Generate the next sequential invoice number like INV-2026-00001.
    Uses the current year as a prefix so numbering resets each year.
    """
    year = datetime.now().year
    prefix = f"INV-{year}-"
    row = conn.execute(
        "SELECT invoice_number FROM invoices WHERE invoice_number LIKE ? "
        "ORDER BY invoice_id DESC LIMIT 1", (f"{prefix}%",)).fetchone()
    seq = int(row['invoice_number'].split('-')[-1]) + 1 if row else 1
    return f"{prefix}{seq:05d}"


def create_invoice(customer_id, invoice_date, due_date, items,
                   remarks='', user_id=None):
    """
    Create an invoice with line items. Stock is left alone at this stage —
    that happens later when dispatch is triggered.

    items: list of dicts, each with product_id, product_name, quantity,
           unit_price, discount_percent, gst_rate

    Returns: (invoice_id, invoice_number)
    """
    conn = get_connection()
    try:
        inv_num = _gen_invoice_number(conn)

        # Grab customer-level discount if any
        cust = conn.execute(
            "SELECT discount_rate FROM customers WHERE customer_id=?",
            (customer_id,)).fetchone()
        cust_discount = cust['discount_rate'] if cust else 0

        subtotal = 0
        total_discount = 0
        total_gst = 0
        calculated_items = []

        for item in items:
            qty = item['quantity']
            price = item['unit_price']
            disc = item.get('discount_percent', cust_discount)
            gst_rate = item.get('gst_rate', 18.0)

            gross = qty * price
            discount = gross * (disc / 100)
            taxable = gross - discount
            gst = taxable * (gst_rate / 100)
            line_total = taxable + gst

            subtotal += gross
            total_discount += discount
            total_gst += gst

            calculated_items.append({
                'product_id': item['product_id'],
                'quantity': qty,
                'unit_price': price,
                'discount_percent': disc,
                'gst_rate': gst_rate,
                'gst_amount': round(gst, 2),
                'line_total': round(line_total, 2),
            })

        total_amount = round(subtotal - total_discount + total_gst, 2)

        # Insert the invoice header — status starts as 'created'
        cursor = conn.execute("""
            INSERT INTO invoices
            (invoice_number,customer_id,invoice_date,due_date,
             subtotal,discount_amount,gst_amount,total_amount,
             amount_paid,balance_due,status,
             is_dispatched,is_paid,remarks,created_by)
            VALUES (?,?,?,?,?,?,?,?,0,?,'created',0,0,?,?)
        """, (inv_num, customer_id, invoice_date, due_date,
              round(subtotal, 2), round(total_discount, 2),
              round(total_gst, 2), total_amount, total_amount,
              remarks, user_id))

        inv_id = cursor.lastrowid

        # Insert line items (just recording what was ordered, no stock changes)
        for item in calculated_items:
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

    except Exception as err:
        conn.rollback()
        raise err
    finally:
        conn.close()


# -----------------------------------------------------------------------
#  Dispatch — this is where stock actually gets deducted
# -----------------------------------------------------------------------

def dispatch_invoice(invoice_id, user_id=None):
    """
    Mark an invoice as dispatched and DEDUCT stock for every line item.
    Checks stock availability for ALL items first — if anything is short,
    the whole dispatch is rejected (no partial shipments).

    Returns (success, message).
    """
    conn = get_connection()
    try:
        inv = conn.execute(
            "SELECT * FROM invoices WHERE invoice_id=?",
            (invoice_id,)).fetchone()

        if not inv:
            return False, "Invoice not found"
        if inv['is_dispatched'] == 1:
            return False, "Already dispatched"
        if inv['status'] == 'cancelled':
            return False, "Can't dispatch a cancelled invoice"

        # Pull all line items with current stock levels
        items = conn.execute(
            "SELECT ii.*, p.product_name, p.product_code, p.current_stock, p.unit "
            "FROM invoice_items ii "
            "JOIN products p ON ii.product_id=p.product_id "
            "WHERE ii.invoice_id=?", (invoice_id,)).fetchall()

        # Check if we have enough of everything before touching anything
        shortages = []
        for item in items:
            if item['current_stock'] < item['quantity']:
                shortages.append(
                    f"{item['product_code']} {item['product_name']}: "
                    f"need {item['quantity']} {item['unit']}, "
                    f"only have {item['current_stock']}"
                )

        if shortages:
            return False, "Not enough stock:\n" + "\n".join(shortages)

        # All good — deduct stock for each item
        from modules.inventory import _record_stock_txn
        for item in items:
            _record_stock_txn(
                conn, item['product_id'], 'dispatch', item['quantity'],
                item['unit_price'], inv['invoice_number'],
                f"Dispatched for {inv['invoice_number']}", user_id
            )

        # Update the invoice header
        now = datetime.now().isoformat()
        conn.execute("""
            UPDATE invoices SET
                status='dispatched',
                is_dispatched=1,
                dispatched_date=?,
                dispatched_by=?,
                updated_at=?
            WHERE invoice_id=?
        """, (now, user_id, now, invoice_id))

        log_audit(user_id, 'DISPATCH_INVOICE', 'invoices', invoice_id,
                  {'status': 'created'},
                  {'status': 'dispatched'}, conn)

        conn.commit()
        return True, f"Invoice {inv['invoice_number']} dispatched!"

    except Exception as err:
        conn.rollback()
        return False, str(err)
    finally:
        conn.close()


# -----------------------------------------------------------------------
#  Payment — one-click "mark as paid"
# -----------------------------------------------------------------------

def mark_payment_done(invoice_id, payment_method='cash',
                      payment_reference='', user_id=None):
    """
    Full-payment shortcut — records a payment for the entire outstanding
    balance and marks the invoice as paid. Goods must be dispatched first.

    Returns (success, message).
    """
    conn = get_connection()
    try:
        inv = conn.execute(
            "SELECT * FROM invoices WHERE invoice_id=?",
            (invoice_id,)).fetchone()

        if not inv:
            return False, "Invoice not found"
        if inv['status'] == 'cancelled':
            return False, "Can't pay a cancelled invoice"
        if inv['is_paid'] == 1:
            return False, "Already paid"
        if inv['is_dispatched'] == 0:
            return False, "Dispatch the goods before recording payment"

        pay_amount = inv['balance_due']
        pay_date = datetime.now().strftime('%Y-%m-%d')

        # How many days late was the payment (0 if on time)?
        due_date = datetime.strptime(inv['due_date'], '%Y-%m-%d')
        delay = max(0, (datetime.now() - due_date).days)

        # Create the payment record
        conn.execute("""
            INSERT INTO payments
            (invoice_id,payment_date,amount,payment_method,
             reference_no,remarks,is_auto,created_by)
            VALUES (?,?,?,?,?,?,1,?)
        """, (invoice_id, pay_date, pay_amount, payment_method,
              payment_reference,
              f"Full payment for {inv['invoice_number']}",
              user_id))

        # Close out the invoice
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

    except Exception as err:
        conn.rollback()
        return False, str(err)
    finally:
        conn.close()


# -----------------------------------------------------------------------
#  Cancellation — undoes everything
# -----------------------------------------------------------------------

def cancel_invoice(invoice_id, reason='', user_id=None):
    """
    Cancel an invoice. If it was already dispatched, this reverses the
    stock deductions. Can't cancel a paid invoice (you'd need a refund).

    Returns (success, message).
    """
    conn = get_connection()
    try:
        inv = conn.execute(
            "SELECT * FROM invoices WHERE invoice_id=?",
            (invoice_id,)).fetchone()

        if not inv:
            return False, "Invoice not found"
        if inv['status'] == 'cancelled':
            return False, "Already cancelled"
        if inv['is_paid'] == 1:
            return False, ("Can't cancel a paid invoice. "
                           "You'll need to issue a credit note / refund first.")

        # If goods were dispatched, put the stock back
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

        now = datetime.now().isoformat()
        conn.execute("""
            UPDATE invoices SET
                status='cancelled',
                cancelled_date=?,
                cancelled_by=?,
                cancel_reason=?,
                updated_at=?
            WHERE invoice_id=?
        """, (now, user_id, reason, now, invoice_id))

        stock_note = " Stock has been reversed." if inv['is_dispatched'] else ""
        log_audit(user_id, 'CANCEL_INVOICE', 'invoices', invoice_id,
                  {'status': inv['status']},
                  {'status': 'cancelled', 'reason': reason}, conn)

        conn.commit()
        return True, f"Invoice {inv['invoice_number']} cancelled.{stock_note}"

    except Exception as err:
        conn.rollback()
        return False, str(err)
    finally:
        conn.close()


# -----------------------------------------------------------------------
#  Invoice queries
# -----------------------------------------------------------------------

def get_invoice(invoice_id):
    """Get the full invoice with line items, payments, and user names."""
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

    # Line items
    items = conn.execute("""
        SELECT ii.*, p.product_name, p.product_code, p.unit
        FROM invoice_items ii
        JOIN products p ON ii.product_id=p.product_id
        WHERE ii.invoice_id=?
    """, (invoice_id,)).fetchall()
    invoice['items'] = [dict(i) for i in items]

    # Payment records
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
    """Get an invoice with a short text summary of its items (for list views)."""
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
    """
    All invoices for the list view. Each row includes a comma-separated
    summary of items so you can see what was ordered at a glance.
    """
    conn = get_connection()
    query = """
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
        query += " AND i.status=?"
        params.append(status_filter)
    if customer_id:
        query += " AND i.customer_id=?"
        params.append(customer_id)

    query += " GROUP BY i.invoice_id ORDER BY i.invoice_date DESC, i.invoice_id DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_invoices_detailed():
    """All invoices with full item details (for detailed/expanded views)."""
    conn = get_connection()
    invoices = conn.execute("""
        SELECT i.*, c.customer_name
        FROM invoices i
        JOIN customers c ON i.customer_id=c.customer_id
        ORDER BY i.invoice_date DESC, i.invoice_id DESC
    """).fetchall()

    result = []
    for inv in invoices:
        entry = dict(inv)
        items = conn.execute("""
            SELECT p.product_code, p.product_name, ii.quantity, p.unit,
                ii.unit_price, ii.line_total
            FROM invoice_items ii
            JOIN products p ON ii.product_id=p.product_id
            WHERE ii.invoice_id=?
        """, (inv['invoice_id'],)).fetchall()
        entry['items'] = [dict(i) for i in items]
        result.append(entry)

    conn.close()
    return result


def update_overdue_invoices():
    """Sweep through open invoices and mark any past-due ones as overdue."""
    conn = get_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    count = conn.execute("""
        UPDATE invoices SET status='overdue', updated_at=?
        WHERE due_date<? AND status IN ('created','dispatched')
          AND balance_due>0 AND is_paid=0
    """, (datetime.now().isoformat(), today)).rowcount
    conn.commit()
    conn.close()
    return count


def check_credit_limit(customer_id, new_amount):
    """
    Check whether a new invoice would push the customer past their credit limit.
    Returns (within_limit, current_outstanding, limit).
    """
    cust = get_customer(customer_id)
    if not cust or cust['credit_limit'] <= 0:
        return True, 0, 0
    outstanding = get_customer_outstanding(customer_id)
    return (outstanding + new_amount <= cust['credit_limit'],
            outstanding, cust['credit_limit'])