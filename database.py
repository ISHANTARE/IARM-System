"""
database.py
-----------
Complete database layer with dispatch tracking support.
"""

import sqlite3
import os
import shutil
import hashlib
from datetime import datetime

DB_NAME = "iarms.db"
BACKUP_DIR = "backups"
EXPORT_DIR = "exports"

for d in [BACKUP_DIR, EXPORT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)


def get_connection():
    """Return a new connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def initialize_database():
    """Create all tables and seed data."""
    conn = get_connection()
    cursor = conn.cursor()

    # ── Users ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','manager','staff')),
            email TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            last_login TEXT
        )
    """)

    # ── Categories ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT UNIQUE NOT NULL,
            description TEXT
        )
    """)

    # ── Products ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT UNIQUE NOT NULL,
            product_name TEXT NOT NULL,
            category_id INTEGER,
            unit TEXT DEFAULT 'pcs',
            purchase_price REAL DEFAULT 0,
            selling_price REAL DEFAULT 0,
            gst_rate REAL DEFAULT 18.0,
            current_stock REAL DEFAULT 0,
            reorder_level REAL DEFAULT 10,
            abc_class TEXT DEFAULT 'C' CHECK(abc_class IN ('A','B','C')),
            annual_consumption_value REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (category_id) REFERENCES categories(category_id)
        )
    """)

    # ── Stock Transactions ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL CHECK(
                transaction_type IN ('purchase','sale','adjustment_in',
                    'adjustment_out','return_in','return_out','dispatch')
            ),
            quantity REAL NOT NULL,
            unit_price REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            reference_no TEXT,
            remarks TEXT,
            transaction_date TEXT DEFAULT (datetime('now')),
            created_by INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(product_id),
            FOREIGN KEY (created_by) REFERENCES users(user_id)
        )
    """)

    # ── Customers ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            customer_type TEXT DEFAULT 'retail' CHECK(
                customer_type IN ('retail','wholesale')
            ),
            phone TEXT,
            email TEXT,
            address TEXT,
            gst_number TEXT,
            credit_limit REAL DEFAULT 0,
            discount_rate REAL DEFAULT 0,
            payment_terms_days INTEGER DEFAULT 30,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Invoices (REDESIGNED with dispatch tracking) ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            invoice_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            subtotal REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            gst_amount REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            amount_paid REAL DEFAULT 0,
            balance_due REAL DEFAULT 0,
            status TEXT DEFAULT 'created' CHECK(
                status IN ('created','dispatched','paid','cancelled','overdue')
            ),
            is_dispatched INTEGER DEFAULT 0,
            dispatched_date TEXT,
            dispatched_by INTEGER,
            is_paid INTEGER DEFAULT 0,
            paid_date TEXT,
            paid_by INTEGER,
            payment_method TEXT,
            payment_reference TEXT,
            cancelled_date TEXT,
            cancelled_by INTEGER,
            cancel_reason TEXT,
            payment_delay_days INTEGER DEFAULT 0,
            remarks TEXT,
            created_by INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (created_by) REFERENCES users(user_id),
            FOREIGN KEY (dispatched_by) REFERENCES users(user_id),
            FOREIGN KEY (paid_by) REFERENCES users(user_id),
            FOREIGN KEY (cancelled_by) REFERENCES users(user_id)
        )
    """)

    # ── Invoice Line Items ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            discount_percent REAL DEFAULT 0,
            gst_rate REAL DEFAULT 18.0,
            gst_amount REAL DEFAULT 0,
            line_total REAL DEFAULT 0,
            FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
                ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
    """)

    # ── Payments ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            payment_date TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT DEFAULT 'cash' CHECK(
                payment_method IN ('cash','upi','bank_transfer',
                    'cheque','card','other')
            ),
            reference_no TEXT,
            remarks TEXT,
            is_auto INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id),
            FOREIGN KEY (created_by) REFERENCES users(user_id)
        )
    """)

    # ── Audit Log ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            table_name TEXT,
            record_id INTEGER,
            old_values TEXT,
            new_values TEXT,
            timestamp TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # ── Seed Data ──
    cursor.execute("SELECT COUNT(*) as cnt FROM users")
    if cursor.fetchone()['cnt'] == 0:
        hashed = hash_password('admin123')
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, email)
            VALUES ('admin', ?, 'System Administrator', 'admin',
                    'admin@praptiseva.com')
        """, (hashed,))
    else:
        _migrate_passwords(cursor)

    cursor.execute("SELECT COUNT(*) as cnt FROM categories")
    if cursor.fetchone()['cnt'] == 0:
        cursor.executemany(
            "INSERT INTO categories (category_name, description) VALUES (?,?)",
            [
                ('Household Goods', 'Kitchen, cleaning, home essentials'),
                ('Personal Care', 'Soaps, shampoos, skincare'),
                ('Construction Equipment', 'Tools, machinery, materials'),
                ('General', 'Uncategorized')
            ]
        )

    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")


def _migrate_passwords(cursor):
    """Detect and migrate plain-text passwords to SHA-256."""
    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [col['name'] for col in cursor.fetchall()]

        if 'password' in columns and 'password_hash' not in columns:
            cursor.execute("""
                CREATE TABLE users_new (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','manager','staff')),
                    email TEXT, is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    last_login TEXT
                )
            """)
            cursor.execute("""
                INSERT INTO users_new
                    (user_id,username,password_hash,full_name,role,
                     email,is_active,created_at,last_login)
                SELECT user_id,username,password,full_name,role,
                       email,is_active,created_at,last_login
                FROM users
            """)
            cursor.execute("DROP TABLE users")
            cursor.execute("ALTER TABLE users_new RENAME TO users")

        cursor.execute("SELECT user_id, username, password_hash FROM users")
        for user in cursor.fetchall():
            pwd = user['password_hash']
            is_hashed = (len(pwd) == 64 and
                         all(c in '0123456789abcdef' for c in pwd.lower()))
            if not is_hashed:
                cursor.execute(
                    "UPDATE users SET password_hash=? WHERE user_id=?",
                    (hash_password(pwd), user['user_id'])
                )
    except Exception as e:
        print(f"[DB] Migration: {e}")
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO users
                    (user_id,username,password_hash,full_name,role,email)
                VALUES (1,'admin',?,'System Administrator','admin',
                        'admin@praptiseva.com')
            """, (hash_password('admin123'),))
        except Exception:
            pass


def backup_database():
    """Create timestamped backup."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(BACKUP_DIR, f"iarms_backup_{ts}.db")
    shutil.copy2(DB_NAME, path)
    return path


def log_audit(user_id, action, table_name=None, record_id=None,
              old_values=None, new_values=None, conn=None):
    """Write audit log entry."""
    close = False
    if conn is None:
        conn = get_connection()
        close = True
    try:
        conn.execute("""
            INSERT INTO audit_log
                (user_id,action,table_name,record_id,old_values,new_values)
            VALUES (?,?,?,?,?,?)
        """, (user_id, action, table_name, record_id,
              str(old_values) if old_values else None,
              str(new_values) if new_values else None))
        if close:
            conn.commit()
    except Exception as e:
        print(f"[AUDIT] {e}")
    finally:
        if close:
            conn.close()