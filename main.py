"""
IARMS v3.0 — Redesigned Invoice System
Login: admin / admin123
"""

from database import initialize_database
from gui.app import IARMSApp

def main():
    print("=" * 60)
    print("  IARMS v3.0 - Prapti Seva LLP")
    print("  Inventory & Accounts Receivable Management System")
    print("=" * 60)
    print()

    # DELETE OLD DATABASE for clean start with new schema
    import os
    if os.path.exists("iarms.db"):
        print("[!] Detected old database. Backing up and recreating...")
        import shutil
        shutil.copy2("iarms.db", "iarms_old_backup.db")
        os.remove("iarms.db")

    initialize_database()
    print("[STARTUP] Launching...")
    app = IARMSApp()
    app.mainloop()

if __name__ == "__main__":
    main()