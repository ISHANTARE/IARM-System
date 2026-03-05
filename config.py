"""
Central config — all app-wide constants live here so nothing is scattered.
"""

import os

# --- Paths ---
DB_NAME = "iarms.db"
BACKUP_DIR = "backups"
EXPORT_DIR = "exports"

# --- App identity ---
APP_NAME = "IARMS - Inventory & Accounts Receivable Management System"
COMPANY_NAME = "Prapti Seva LLP"
VERSION = "3.0.0"

# --- Invoice defaults ---
DEFAULT_PAYMENT_TERMS_DAYS = 30
DEFAULT_GST_RATE = 18.0

# --- ABC classification thresholds (cumulative % of total value) ---
ABC_CLASS_A_THRESHOLD = 80   # top 80% by value
ABC_CLASS_B_THRESHOLD = 95   # next 15% by value

# --- Alerts ---
LOW_STOCK_CRITICAL_MULTIPLIER = 0   # 0 means "out of stock"
OVERDUE_WARNING_DAYS = 30
OVERDUE_CRITICAL_DAYS = 60

# Make sure the output folders exist on import
for _dir in [BACKUP_DIR, EXPORT_DIR]:
    os.makedirs(_dir, exist_ok=True)