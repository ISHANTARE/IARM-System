# IARMS — Inventory & Accounts Receivable Management System

A desktop application built to manage product inventory, customer invoicing, payment tracking, and financial reporting — all in one place.

Built with Python and Tkinter. Uses SQLite for local data storage. No external services or internet connection required.

---

## Features

- **Inventory Management** — Add, edit, search, and soft-delete products. Track stock levels with automatic reorder alerts.
- **ABC Classification** — Automatically classifies products into A/B/C categories based on annual sales value (Pareto analysis).
- **Customer Management** — Maintain a customer directory with credit limits, discount rates, and GST details.
- **Invoice Lifecycle** — Create invoices → Dispatch (deducts stock) → Record Payment → Done. Cancel at any stage with automatic stock reversal.
- **Payment Tracking** — Filterable payment records with summaries by method (cash, UPI, bank transfer, etc.).
- **Reports & Analytics** — Aged receivables, DSO trends, monthly sales, profit breakdowns, top debtors.
- **Alerts Dashboard** — Low stock warnings, overdue invoice notifications — all in one view.
- **User Roles** — Admin, Manager, Staff with role-based access control.
- **Audit Trail** — Every significant action is logged for accountability.
- **CSV Import/Export** — Bulk-load products or export data for spreadsheets.
- **Database Backups** — One-click backups from the admin panel.

---

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Tkinter (comes bundled with most Python installations)

No external packages are required — everything uses the Python standard library.

### Installation

```bash
git clone https://github.com/<your-username>/IARM-System.git
cd IARM-System
python main.py
```

### Default Login

| Username | Password   | Role  |
|----------|------------|-------|
| `admin`  | `admin123` | Admin |

> **Note:** Change the default password after first login via the Admin panel.

---

## Project Structure

```
IARMS/
├── main.py              # Entry point — boots up DB and launches the GUI
├── config.py            # App-wide constants (DB name, version, thresholds)
├── database.py          # SQLite schema, connections, migrations, auditing
├── models.py            # Dataclass definitions for Product, Customer, Invoice, etc.
│
├── gui/
│   └── app.py           # The entire Tkinter GUI (login, sidebar, all views)
│
├── modules/
│   ├── admin.py         # User authentication, permissions, audit log
│   ├── inventory.py     # Product CRUD, stock transactions, ABC analysis
│   ├── invoice.py       # Invoice lifecycle, customer CRUD, payment processing
│   └── reporting.py     # Dashboard KPIs, aged receivables, DSO, profit reports
│
├── utils/
│   ├── alerts.py        # Alert generation (low stock, overdue invoices)
│   └── helpers.py       # Date formatting, validation, currency display
│
├── backups/             # Auto-generated database backups
├── exports/             # CSV exports land here
├── requirements.txt     # Python version requirement
└── README.md            # This file
```

---

## How It Works

### Invoice Workflow

```
CREATE  →  DISPATCH  →  PAYMENT  →  DONE
  │           │           │
  │           │           └── Records payment, marks invoice as paid
  │           └── Validates stock, deducts inventory, marks as dispatched
  └── Saves invoice + line items (stock is NOT touched yet)

At any point before payment:
  CANCEL  →  Reverses stock if dispatched, marks as cancelled
```

Stock is only deducted when an invoice is **dispatched**, not when it's created. This lets you draft invoices without worrying about inventory numbers.

### ABC Classification

Products are classified based on annual sales value:
- **Class A** — Top 80% of total sales value (high priority)
- **Class B** — Next 15% (medium priority)
- **Class C** — Bottom 5% (low priority)

Recalculate anytime from the Inventory page.

---

## Tech Stack

| Component     | Technology         |
|---------------|--------------------|
| Language      | Python 3.8+        |
| GUI Framework | Tkinter (built-in) |
| Database      | SQLite3 (built-in) |
| Hashing       | SHA-256 (hashlib)  |

No external dependencies. Runs on Windows, macOS, and Linux.

---

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m "Add my feature"`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

