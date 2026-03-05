"""
config.py
---------
Central configuration for the IARMS application.
"""

import os

# Database
DB_NAME = "iarms.db"
BACKUP_DIR = "backups"
EXPORT_DIR = "exports"

# Application
APP_NAME = "IARMS - Inventory & Accounts Receivable Management System"
COMPANY_NAME = "Prapti Seva LLP"
VERSION = "2.0.0"

# Invoice defaults
DEFAULT_PAYMENT_TERMS_DAYS = 30
DEFAULT_GST_RATE = 18.0

# ABC Classification thresholds
ABC_CLASS_A_THRESHOLD = 80  # top 80% of value
ABC_CLASS_B_THRESHOLD = 95  # next 15% of value

# Alerts
LOW_STOCK_CRITICAL_MULTIPLIER = 0  # at 0 = out of stock
OVERDUE_WARNING_DAYS = 30
OVERDUE_CRITICAL_DAYS = 60

# Ensure directories exist
for d in [BACKUP_DIR, EXPORT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)