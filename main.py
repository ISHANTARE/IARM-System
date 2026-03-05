"""
Entry point for IARMS.
Boots up the database and launches the desktop GUI.

Default login: admin / admin123
"""

from database import initialize_database
from gui.app import IARMSApp
from config import APP_NAME, COMPANY_NAME, VERSION


def main():
    print("=" * 60)
    print(f"  {APP_NAME}")
    print(f"  {COMPANY_NAME}  —  v{VERSION}")
    print("=" * 60)
    print()

    initialize_database()
    print("[startup] Launching the GUI...")

    app = IARMSApp()
    app.mainloop()


if __name__ == "__main__":
    main()