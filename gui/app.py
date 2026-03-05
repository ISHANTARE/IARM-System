"""
gui/app.py
----------
REDESIGNED GUI with:
- Invoice shows product details (what was bought, quantities)
- 3 action buttons per invoice: Dispatch | Payment Done | Cancel
- Enhanced dashboard with dispatch/payment pending counts
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

from database import initialize_database
from modules.admin import authenticate_user, check_permission
from modules.invoice import update_overdue_invoices
from utils.helpers import format_currency, validate_date


class IARMSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IARMS - Prapti Seva LLP")
        self.geometry("1400x800")
        self.minsize(1100, 650)
        self.current_user = None
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._styles()
        self.show_login()

    def _styles(self):
        s = self.style
        s.configure('Title.TLabel', font=('Segoe UI', 18, 'bold'), foreground='#2c3e50')
        s.configure('Subtitle.TLabel', font=('Segoe UI', 12), foreground='#7f8c8d')
        s.configure('Header.TLabel', font=('Segoe UI', 14, 'bold'), foreground='#2c3e50')
        s.configure('KPI.TLabel', font=('Segoe UI', 22, 'bold'), foreground='#27ae60')
        s.configure('KPITitle.TLabel', font=('Segoe UI', 10), foreground='#95a5a6')
        s.configure('Nav.TButton', font=('Segoe UI', 11), padding=10)
        s.configure('Action.TButton', font=('Segoe UI', 10, 'bold'), padding=8)
        s.configure('Dispatch.TButton', font=('Segoe UI', 9, 'bold'), padding=5)
        s.configure('Payment.TButton', font=('Segoe UI', 9, 'bold'), padding=5)
        s.configure('Cancel.TButton', font=('Segoe UI', 9, 'bold'), padding=5)
        s.configure('Save.TButton', font=('Segoe UI', 12, 'bold'), padding=12)
        s.configure('Treeview', font=('Segoe UI', 10), rowheight=28)
        s.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))

    # ─── LOGIN ───
    def show_login(self):
        for w in self.winfo_children(): w.destroy()
        f = ttk.Frame(self, padding=40)
        f.place(relx=0.5, rely=0.5, anchor='center')

        ttk.Label(f, text="IARMS", style='Title.TLabel').pack(pady=(0,5))
        ttk.Label(f, text="Inventory & Accounts Receivable Management",
                  style='Subtitle.TLabel').pack(pady=(0,5))
        ttk.Label(f, text="Prapti Seva LLP", style='Subtitle.TLabel').pack(pady=(0,30))

        ttk.Label(f, text="Username:", font=('Segoe UI',11)).pack(anchor='w')
        self.uv = tk.StringVar()
        ue = ttk.Entry(f, textvariable=self.uv, width=30, font=('Segoe UI',11))
        ue.pack(pady=(0,15), ipady=4)
        ue.focus()

        ttk.Label(f, text="Password:", font=('Segoe UI',11)).pack(anchor='w')
        self.pv = tk.StringVar()
        pe = ttk.Entry(f, textvariable=self.pv, show="•", width=30, font=('Segoe UI',11))
        pe.pack(pady=(0,25), ipady=4)

        ttk.Button(f, text="Login", style='Action.TButton',
                   command=self._login).pack(fill='x', ipady=5)
        self.login_msg = ttk.Label(f, text="", foreground='red')
        self.login_msg.pack(pady=10)
        ttk.Label(f, text="Default: admin / admin123",
                  font=('Segoe UI',9), foreground='#bdc3c7').pack()

        pe.bind('<Return>', lambda e: self._login())
        ue.bind('<Return>', lambda e: pe.focus())

    def _login(self):
        u, p = self.uv.get().strip(), self.pv.get().strip()
        if not u or not p:
            self.login_msg.config(text="Enter both fields.")
            return
        user = authenticate_user(u, p)
        if user:
            self.current_user = user
            update_overdue_invoices()
            self._main_ui()
        else:
            self.login_msg.config(text="Invalid credentials.")

    def _main_ui(self):
        for w in self.winfo_children(): w.destroy()

        # Top bar
        top = ttk.Frame(self, padding=5)
        top.pack(fill='x', side='top')
        ttk.Label(top, text="IARMS - Prapti Seva LLP",
                  font=('Segoe UI',12,'bold'), foreground='#2c3e50').pack(side='left', padx=10)
        rf = ttk.Frame(top)
        rf.pack(side='right')
        ttk.Label(rf, text=f"{self.current_user['full_name']} ({self.current_user['role']})",
                  font=('Segoe UI',10), foreground='#7f8c8d').pack(side='left', padx=10)
        ttk.Button(rf, text="Logout", command=lambda: (
            setattr(self, 'current_user', None), self.show_login()
        )).pack(side='left', padx=5)

        ttk.Separator(self, orient='horizontal').pack(fill='x')

        main = ttk.Frame(self)
        main.pack(fill='both', expand=True)

        # Sidebar
        sb = ttk.Frame(main, width=200, padding=10)
        sb.pack(fill='y', side='left')
        sb.pack_propagate(False)
        ttk.Label(sb, text="Navigation", style='Header.TLabel').pack(pady=(0,15), anchor='w')

        navs = [
            ("📊 Dashboard", self.show_dashboard),
            ("📦 Inventory", self.show_inventory),
            ("👥 Customers", self.show_customers),
            ("🧾 Invoices", self.show_invoices),
            ("💰 Payments", self.show_payments),
            ("📈 Reports", self.show_reports),
            ("⚠️ Alerts", self.show_alerts),
        ]
        if check_permission(self.current_user['role'], 'admin'):
            navs.append(("⚙️ Admin", self.show_admin))

        for text, cmd in navs:
            ttk.Button(sb, text=text, style='Nav.TButton', command=cmd).pack(fill='x', pady=3)

        ttk.Separator(main, orient='vertical').pack(fill='y', side='left')

        self.content = ttk.Frame(main, padding=15)
        self.content.pack(fill='both', expand=True, side='left')
        self.show_dashboard()

    def _clear(self):
        for w in self.content.winfo_children(): w.destroy()

    # ─── DASHBOARD ───
    def show_dashboard(self):
        self._clear()
        from modules.reporting import get_dashboard_kpis
        from utils.alerts import get_all_alerts

        ttk.Label(self.content, text="Executive Dashboard",
                  style='Title.TLabel').pack(anchor='w', pady=(0,20))

        kpis = get_dashboard_kpis()

        # Row 1: Sales KPIs
        r1 = ttk.Frame(self.content)
        r1.pack(fill='x', pady=5)
        for title, val, sub in [
            ("Today's Sales", format_currency(kpis['daily'].get('today_revenue',0)),
             f"{kpis['daily'].get('today_invoices',0)} invoices"),
            ("Monthly Revenue", format_currency(kpis['monthly'].get('month_revenue',0)),
             f"{kpis['monthly'].get('month_invoices',0)} invoices"),
            ("Outstanding", format_currency(kpis['sales'].get('total_outstanding',0)),
             f"{kpis['sales'].get('overdue_count',0)} overdue"),
            ("DSO", f"{kpis.get('dso',0)} days", "Days Sales Outstanding"),
        ]:
            c = ttk.LabelFrame(r1, text=title, padding=15)
            c.pack(side='left', fill='both', expand=True, padx=5)
            ttk.Label(c, text=val, style='KPI.TLabel').pack()
            ttk.Label(c, text=sub, style='KPITitle.TLabel').pack()

        # Row 2: Dispatch/Inventory KPIs
        r2 = ttk.Frame(self.content)
        r2.pack(fill='x', pady=5)

        pending_dispatch = kpis['sales'].get('pending_dispatch', 0)
        dispatched_unpaid = kpis['sales'].get('dispatched_unpaid', 0)

        for title, val, sub, color in [
            ("Pending Dispatch", str(pending_dispatch),
             "Invoices awaiting dispatch",
             '#e74c3c' if pending_dispatch > 0 else '#27ae60'),
            ("Dispatched Unpaid", str(dispatched_unpaid),
             "Awaiting payment",
             '#f39c12' if dispatched_unpaid > 0 else '#27ae60'),
            ("Low Stock", str(kpis['inventory'].get('low_stock_count',0)),
             "Need reorder",
             '#e74c3c' if kpis['inventory'].get('low_stock_count',0) > 0 else '#27ae60'),
            ("Inventory Value", format_currency(kpis['inventory'].get('total_inventory_value',0)),
             f"{kpis['inventory'].get('total_products',0)} products", '#2c3e50'),
        ]:
            c = ttk.LabelFrame(r2, text=title, padding=15)
            c.pack(side='left', fill='both', expand=True, padx=5)
            ttk.Label(c, text=val, font=('Segoe UI',22,'bold'), foreground=color).pack()
            ttk.Label(c, text=sub, style='KPITitle.TLabel').pack()

        # Alerts
        ttk.Label(self.content, text="Recent Alerts",
                  style='Header.TLabel').pack(anchor='w', pady=(20,10))
        alerts = get_all_alerts()
        af = ttk.Frame(self.content)
        af.pack(fill='both', expand=True)
        if alerts:
            for a in alerts[:10]:
                icon = "🔴" if a['severity'] == 'critical' else "🟡"
                fg = '#e74c3c' if a['severity'] == 'critical' else '#f39c12'
                ttk.Label(af, text=f" {icon} [{a['type']}] {a['message']}",
                          foreground=fg, font=('Segoe UI',10)).pack(anchor='w', pady=2)
        else:
            ttk.Label(af, text="✅ All clear!", foreground='#27ae60',
                      font=('Segoe UI',11)).pack(anchor='w')

    # ─── INVENTORY (same as before, abbreviated for space) ───
    def show_inventory(self):
        self._clear()
        from modules.inventory import (get_all_products, search_products,
            calculate_abc_classification, export_products_csv, import_products_csv)

        ttk.Label(self.content, text="Inventory Management",
                  style='Title.TLabel').pack(anchor='w', pady=(0,15))

        tb = ttk.Frame(self.content)
        tb.pack(fill='x', pady=(0,10))
        ttk.Button(tb, text="➕ Add Product", style='Action.TButton',
                   command=self._add_product_dlg).pack(side='left', padx=5)
        ttk.Button(tb, text="🔄 ABC Recalc", style='Action.TButton',
                   command=lambda: (calculate_abc_classification(), self.show_inventory())
                   ).pack(side='left', padx=5)
        ttk.Button(tb, text="📥 Purchase", style='Action.TButton',
                   command=self._purchase_dlg).pack(side='left', padx=5)

        ttk.Label(tb, text="Search:").pack(side='left', padx=(20,5))
        sv = tk.StringVar()
        ttk.Entry(tb, textvariable=sv, width=25).pack(side='left')

        cols = ('code','name','cat','stock','reorder','buy','sell','margin','abc')
        tf = ttk.Frame(self.content)
        tf.pack(fill='both', expand=True)
        tree = ttk.Treeview(tf, columns=cols, show='headings', height=20)
        for c, h, w in [('code','Code',80),('name','Name',180),('cat','Category',110),
                         ('stock','Stock',70),('reorder','Reorder',65),
                         ('buy','Buy ₹',90),('sell','Sell ₹',90),
                         ('margin','Margin%',70),('abc','ABC',45)]:
            tree.heading(c, text=h)
            tree.column(c, width=w)
        sbar = ttk.Scrollbar(tf, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sbar.set)
        tree.pack(side='left', fill='both', expand=True)
        sbar.pack(side='right', fill='y')

        def pop(*a):
            tree.delete(*tree.get_children())
            t = sv.get().strip()
            prods = search_products(t) if t else get_all_products()
            for p in prods:
                tag = 'out' if p['current_stock'] <= 0 else ('low' if p['current_stock'] <= p['reorder_level'] else '')
                tree.insert('', 'end', iid=p['product_id'], values=(
                    p['product_code'], p['product_name'], p.get('category_name',''),
                    p['current_stock'], p['reorder_level'],
                    f"₹{p['purchase_price']:,.2f}", f"₹{p['selling_price']:,.2f}",
                    f"{p.get('margin_percent',0) or 0}%", p['abc_class']
                ), tags=(tag,))
            tree.tag_configure('low', background='#ffeaa7')
            tree.tag_configure('out', background='#fab1a0')

        sv.trace_add('write', pop)
        pop()

    def _add_product_dlg(self):
        from modules.inventory import add_product, get_all_categories
        d = tk.Toplevel(self); d.title("Add Product"); d.geometry("450x560")
        d.transient(self); d.grab_set()
        f = ttk.Frame(d, padding=20); f.pack(fill='both', expand=True)
        ttk.Label(f, text="Add Product", style='Header.TLabel').grid(row=0, column=0, columnspan=2, pady=(0,15), sticky='w')

        fields = {}
        for i, (k, l, v) in enumerate([
            ('product_code','Code*:',''), ('product_name','Name*:',''),
            ('unit','Unit:','pcs'), ('purchase_price','Buy Price:','0'),
            ('selling_price','Sell Price:','0'), ('gst_rate','GST%:','18'),
            ('current_stock','Stock:','0'), ('reorder_level','Reorder:','10')
        ], start=1):
            ttk.Label(f, text=l).grid(row=i, column=0, sticky='w', pady=5)
            var = tk.StringVar(value=v)
            ttk.Entry(f, textvariable=var, width=25).grid(row=i, column=1, sticky='w', pady=5, padx=(10,0))
            fields[k] = var

        cats = get_all_categories()
        r = len(fields) + 1
        ttk.Label(f, text="Category:").grid(row=r, column=0, sticky='w', pady=5)
        cv = tk.StringVar(value=cats[0]['category_name'] if cats else '')
        ttk.Combobox(f, textvariable=cv, values=[c['category_name'] for c in cats],
                     state='readonly', width=22).grid(row=r, column=1, sticky='w', pady=5, padx=(10,0))

        def save():
            code, name = fields['product_code'].get().strip(), fields['product_name'].get().strip()
            if not code or not name:
                messagebox.showerror("Error", "Code and name required."); return
            try:
                cid = next((c['category_id'] for c in cats if c['category_name'] == cv.get()), None)
                add_product(code, name, cid, fields['unit'].get(),
                    float(fields['purchase_price'].get() or 0),
                    float(fields['selling_price'].get() or 0),
                    float(fields['gst_rate'].get() or 18),
                    float(fields['current_stock'].get() or 0),
                    float(fields['reorder_level'].get() or 10),
                    self.current_user['user_id'])
                messagebox.showinfo("✅", "Product added!"); d.destroy(); self.show_inventory()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(f, text="💾 Save", style='Action.TButton', command=save).grid(
            row=r+1, column=0, columnspan=2, pady=20, sticky='ew')

    def _purchase_dlg(self):
        from modules.inventory import get_all_products, record_stock_transaction
        d = tk.Toplevel(self); d.title("Record Purchase"); d.geometry("450x300")
        d.transient(self); d.grab_set()
        f = ttk.Frame(d, padding=20); f.pack(fill='both', expand=True)

        prods = get_all_products()
        pm = {f"{p['product_code']} - {p['product_name']}": p['product_id'] for p in prods}

        ttk.Label(f, text="Product:").grid(row=0, column=0, sticky='w', pady=5)
        pv = tk.StringVar()
        ttk.Combobox(f, textvariable=pv, values=list(pm.keys()), state='readonly', width=30).grid(
            row=0, column=1, sticky='w', padx=10, pady=5)

        qv, prv, rv = tk.StringVar(value='0'), tk.StringVar(value='0'), tk.StringVar()
        for i, (l, v) in enumerate([("Qty:", qv), ("Price:", prv), ("Ref:", rv)], start=1):
            ttk.Label(f, text=l).grid(row=i, column=0, sticky='w', pady=5)
            ttk.Entry(f, textvariable=v, width=15).grid(row=i, column=1, sticky='w', padx=10, pady=5)

        def save():
            pid = pm.get(pv.get())
            if not pid: messagebox.showerror("Error", "Select product."); return
            try:
                q = float(qv.get())
                if q <= 0: raise ValueError("Qty must be positive")
                record_stock_transaction(pid, 'purchase', q, float(prv.get()),
                    rv.get(), 'Manual purchase', self.current_user['user_id'])
                messagebox.showinfo("✅", "Purchase recorded!"); d.destroy(); self.show_inventory()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(f, text="💾 Save", style='Action.TButton', command=save).grid(
            row=4, column=0, columnspan=2, pady=20, sticky='ew')

    # ─── CUSTOMERS ───
    def show_customers(self):
        self._clear()
        from modules.invoice import get_all_customers, search_customers, get_customer_outstanding

        ttk.Label(self.content, text="Customer Management",
                  style='Title.TLabel').pack(anchor='w', pady=(0,15))
        tb = ttk.Frame(self.content); tb.pack(fill='x', pady=(0,10))
        ttk.Button(tb, text="➕ Add Customer", style='Action.TButton',
                   command=self._add_cust_dlg).pack(side='left', padx=5)
        ttk.Label(tb, text="Search:").pack(side='left', padx=(20,5))
        sv = tk.StringVar()
        ttk.Entry(tb, textvariable=sv, width=25).pack(side='left')

        cols = ('id','name','type','phone','credit','disc','outstanding')
        tf = ttk.Frame(self.content); tf.pack(fill='both', expand=True)
        tree = ttk.Treeview(tf, columns=cols, show='headings', height=18)
        for c, h, w in [('id','ID',40),('name','Name',200),('type','Type',80),
                         ('phone','Phone',120),('credit','Credit Limit',100),
                         ('disc','Discount%',80),('outstanding','Outstanding',120)]:
            tree.heading(c, text=h); tree.column(c, width=w)
        tree.pack(fill='both', expand=True)

        def pop(*a):
            tree.delete(*tree.get_children())
            t = sv.get().strip()
            custs = search_customers(t) if t else get_all_customers()
            for c in custs:
                o = get_customer_outstanding(c['customer_id'])
                tree.insert('','end', iid=c['customer_id'], values=(
                    c['customer_id'], c['customer_name'], c['customer_type'],
                    c.get('phone',''), format_currency(c['credit_limit']),
                    f"{c['discount_rate']}%", format_currency(o)))
        sv.trace_add('write', pop); pop()

    def _add_cust_dlg(self):
        from modules.invoice import add_customer
        d = tk.Toplevel(self); d.title("Add Customer"); d.geometry("450x500")
        d.transient(self); d.grab_set()
        f = ttk.Frame(d, padding=20); f.pack(fill='both', expand=True)
        ttk.Label(f, text="Add Customer", style='Header.TLabel').grid(
            row=0, column=0, columnspan=2, pady=(0,15), sticky='w')

        fields = {}
        for i, (k, l, v) in enumerate([
            ('customer_name','Name*:',''), ('phone','Phone:',''),
            ('email','Email:',''), ('address','Address:',''),
            ('gst_number','GST:',''), ('credit_limit','Credit Limit:','0'),
            ('discount_rate','Discount%:','0'), ('payment_terms_days','Terms (days):','30')
        ], start=1):
            ttk.Label(f, text=l).grid(row=i, column=0, sticky='w', pady=5)
            var = tk.StringVar(value=v)
            ttk.Entry(f, textvariable=var, width=25).grid(row=i, column=1, sticky='w', pady=5, padx=(10,0))
            fields[k] = var

        r = len(fields) + 1
        ttk.Label(f, text="Type:").grid(row=r, column=0, sticky='w')
        tv = tk.StringVar(value='retail')
        ttk.Combobox(f, textvariable=tv, values=['retail','wholesale'],
                     state='readonly', width=22).grid(row=r, column=1, sticky='w', padx=(10,0))

        def save():
            name = fields['customer_name'].get().strip()
            if not name: messagebox.showerror("Error", "Name required."); return
            try:
                add_customer(name, tv.get(), fields['phone'].get(), fields['email'].get(),
                    fields['address'].get(), fields['gst_number'].get(),
                    float(fields['credit_limit'].get() or 0),
                    float(fields['discount_rate'].get() or 0),
                    int(fields['payment_terms_days'].get() or 30))
                messagebox.showinfo("✅", "Customer added!"); d.destroy(); self.show_customers()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(f, text="💾 Save", style='Action.TButton', command=save).grid(
            row=r+1, column=0, columnspan=2, pady=20, sticky='ew')

    # ══════════════════════════════════════════════════════════════════
    #  INVOICES — COMPLETELY REDESIGNED WITH 3 BUTTONS + ITEM DETAILS
    # ══════════════════════════════════════════════════════════════════

    def show_invoices(self):
        """Invoice management with item details and 3 action buttons."""
        self._clear()
        from modules.invoice import get_all_invoices

        ttk.Label(self.content, text="Invoice Management",
                  style='Title.TLabel').pack(anchor='w', pady=(0,10))

        # Toolbar
        tb = ttk.Frame(self.content); tb.pack(fill='x', pady=(0,10))
        ttk.Button(tb, text="➕ Create Invoice", style='Action.TButton',
                   command=self._create_invoice_dlg).pack(side='left', padx=5)

        ttk.Label(tb, text="Filter:").pack(side='left', padx=(20,5))
        fv = tk.StringVar(value='all')
        fc = ttk.Combobox(tb, textvariable=fv,
                          values=['all','created','dispatched','paid','overdue','cancelled'],
                          state='readonly', width=12)
        fc.pack(side='left')

        # ── Legend ──
        legend = ttk.Frame(tb)
        legend.pack(side='right', padx=10)
        for text, bg in [("Created","#dfe6e9"), ("Dispatched","#74b9ff"),
                          ("Paid","#a8e6cf"), ("Overdue","#fab1a0"),
                          ("Cancelled","#b2bec3")]:
            lf = tk.Frame(legend, bg=bg, padx=6, pady=2)
            lf.pack(side='left', padx=2)
            tk.Label(lf, text=text, bg=bg, font=('Segoe UI',8)).pack()

        # ── Main Invoice List (scrollable) ──
        canvas_frame = ttk.Frame(self.content)
        canvas_frame.pack(fill='both', expand=True)

        canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient='vertical', command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Mouse wheel scroll
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        def populate(*args):
            for w in scroll_frame.winfo_children(): w.destroy()
            invoices = get_all_invoices(status_filter=fv.get())

            if not invoices:
                ttk.Label(scroll_frame, text="No invoices found.",
                          font=('Segoe UI',12), foreground='#7f8c8d').pack(pady=30)
                return

            for inv in invoices:
                self._render_invoice_card(scroll_frame, inv)

        fc.bind('<<ComboboxSelected>>', populate)
        populate()

    def _render_invoice_card(self, parent, inv):
        """Render a single invoice card with item details and 3 buttons."""
        from modules.invoice import dispatch_invoice, mark_payment_done, cancel_invoice

        # Color coding
        status = inv['status']
        colors = {
            'created': '#dfe6e9', 'dispatched': '#74b9ff',
            'paid': '#a8e6cf', 'overdue': '#fab1a0',
            'cancelled': '#b2bec3'
        }
        bg = colors.get(status, '#dfe6e9')

        # Card frame
        card = tk.Frame(parent, bg=bg, bd=1, relief='solid', padx=12, pady=8)
        card.pack(fill='x', padx=5, pady=4)

        # ── Row 1: Invoice header ──
        header = tk.Frame(card, bg=bg)
        header.pack(fill='x')

        # Left side: Invoice info
        left = tk.Frame(header, bg=bg)
        left.pack(side='left', fill='x', expand=True)

        tk.Label(left, text=inv['invoice_number'],
                 font=('Segoe UI', 12, 'bold'), bg=bg).pack(side='left')

        tk.Label(left, text=f"  │  {inv['customer_name']}",
                 font=('Segoe UI', 11), bg=bg).pack(side='left')

        tk.Label(left, text=f"  │  Date: {inv['invoice_date']}",
                 font=('Segoe UI', 10), bg=bg, fg='#636e72').pack(side='left')

        tk.Label(left, text=f"  │  Due: {inv['due_date']}",
                 font=('Segoe UI', 10), bg=bg, fg='#636e72').pack(side='left')

        # Right side: Status badge + total
        right = tk.Frame(header, bg=bg)
        right.pack(side='right')

        status_colors = {
            'created': '#2d3436', 'dispatched': '#0984e3',
            'paid': '#00b894', 'overdue': '#d63031', 'cancelled': '#636e72'
        }
        status_icons = {
            'created': '📋', 'dispatched': '🚚',
            'paid': '✅', 'overdue': '⚠️', 'cancelled': '❌'
        }

        tk.Label(right, text=f"{status_icons.get(status,'')} {status.upper()}",
                 font=('Segoe UI', 10, 'bold'), bg=bg,
                 fg=status_colors.get(status, '#2d3436')).pack(side='left', padx=10)

        tk.Label(right, text=format_currency(inv['total_amount']),
                 font=('Segoe UI', 13, 'bold'), bg=bg).pack(side='left')

        # ── Row 2: Item details ──
        items_text = inv.get('items_summary', '')
        if items_text:
            items_frame = tk.Frame(card, bg=bg)
            items_frame.pack(fill='x', pady=(4, 0))

            tk.Label(items_frame,
                     text=f"📦 Items ({inv.get('items_count', 0)}): {items_text}",
                     font=('Segoe UI', 9), bg=bg, fg='#2d3436',
                     wraplength=700, justify='left').pack(side='left')

        # ── Row 3: Payment info + Action Buttons ──
        bottom = tk.Frame(card, bg=bg)
        bottom.pack(fill='x', pady=(6, 0))

        # Payment info
        info = tk.Frame(bottom, bg=bg)
        info.pack(side='left')

        if inv['balance_due'] > 0 and status != 'cancelled':
            tk.Label(info,
                     text=f"Balance: {format_currency(inv['balance_due'])}",
                     font=('Segoe UI', 10, 'bold'), bg=bg,
                     fg='#d63031').pack(side='left')
        elif status == 'paid':
            tk.Label(info, text="Fully Paid ✅",
                     font=('Segoe UI', 10), bg=bg,
                     fg='#00b894').pack(side='left')

        # ── 3 ACTION BUTTONS ──
        btns = tk.Frame(bottom, bg=bg)
        btns.pack(side='right')

        inv_id = inv['invoice_id']
        is_dispatched = inv.get('is_dispatched', 0)
        is_paid = inv.get('is_paid', 0)

        # BUTTON 1: DISPATCH
        if status not in ('cancelled', 'paid') and not is_dispatched:
            dispatch_btn = tk.Button(
                btns, text="🚚 Dispatch",
                font=('Segoe UI', 9, 'bold'),
                bg='#0984e3', fg='white', bd=0,
                padx=12, pady=4, cursor='hand2',
                command=lambda iid=inv_id: self._do_dispatch(iid)
            )
            dispatch_btn.pack(side='left', padx=3)

        # BUTTON 2: PAYMENT DONE
        if is_dispatched and not is_paid and status != 'cancelled':
            pay_btn = tk.Button(
                btns, text="💰 Payment Done",
                font=('Segoe UI', 9, 'bold'),
                bg='#00b894', fg='white', bd=0,
                padx=12, pady=4, cursor='hand2',
                command=lambda iid=inv_id: self._do_payment(iid)
            )
            pay_btn.pack(side='left', padx=3)

        # BUTTON 3: CANCEL
        if status not in ('cancelled', 'paid'):
            cancel_btn = tk.Button(
                btns, text="❌ Cancel",
                font=('Segoe UI', 9, 'bold'),
                bg='#d63031', fg='white', bd=0,
                padx=12, pady=4, cursor='hand2',
                command=lambda iid=inv_id: self._do_cancel(iid)
            )
            cancel_btn.pack(side='left', padx=3)

        # VIEW DETAILS button (always available)
        view_btn = tk.Button(
            btns, text="📋 Details",
            font=('Segoe UI', 9),
            bg='#636e72', fg='white', bd=0,
            padx=12, pady=4, cursor='hand2',
            command=lambda iid=inv_id: self._view_invoice(iid)
        )
        view_btn.pack(side='left', padx=3)

    # ─── BUTTON ACTIONS ───

    def _do_dispatch(self, invoice_id):
        """Handle Dispatch button click."""
        from modules.invoice import dispatch_invoice

        if not messagebox.askyesno(
            "Confirm Dispatch",
            "Mark this invoice as dispatched?\n\n"
            "This will DEDUCT stock from inventory."
        ):
            return

        ok, msg = dispatch_invoice(invoice_id, self.current_user['user_id'])

        if ok:
            messagebox.showinfo("✅ Dispatched", msg)
        else:
            messagebox.showerror("❌ Dispatch Failed", msg)

        self.show_invoices()

    def _do_payment(self, invoice_id):
        """Handle Payment Done button click — with method selection."""
        from modules.invoice import mark_payment_done, get_invoice

        inv = get_invoice(invoice_id)

        # Quick payment method dialog
        d = tk.Toplevel(self)
        d.title("Payment Method")
        d.geometry("350x250")
        d.transient(self)
        d.grab_set()

        f = ttk.Frame(d, padding=20)
        f.pack(fill='both', expand=True)

        ttk.Label(f, text=f"Payment for {inv['invoice_number']}",
                  style='Header.TLabel').pack(anchor='w', pady=(0,10))

        ttk.Label(f, text=f"Amount: {format_currency(inv['balance_due'])}",
                  font=('Segoe UI', 14, 'bold')).pack(anchor='w', pady=(0,15))

        ttk.Label(f, text="Payment Method:").pack(anchor='w')
        mv = tk.StringVar(value='cash')
        ttk.Combobox(f, textvariable=mv,
                     values=['cash','upi','bank_transfer','cheque','card','other'],
                     state='readonly', width=20).pack(anchor='w', pady=5)

        ttk.Label(f, text="Reference No (optional):").pack(anchor='w')
        rv = tk.StringVar()
        ttk.Entry(f, textvariable=rv, width=25).pack(anchor='w', pady=5)

        def confirm():
            ok, msg = mark_payment_done(
                invoice_id, mv.get(), rv.get(),
                self.current_user['user_id']
            )
            if ok:
                messagebox.showinfo("✅ Payment Recorded", msg)
            else:
                messagebox.showerror("❌ Payment Failed", msg)
            d.destroy()
            self.show_invoices()

        ttk.Button(f, text="✅ Confirm Payment", style='Action.TButton',
                   command=confirm).pack(fill='x', pady=15, ipady=5)

    def _do_cancel(self, invoice_id):
        """Handle Cancel button click."""
        from modules.invoice import cancel_invoice

        reason = tk.simpledialog.askstring(
            "Cancel Reason",
            "Why is this invoice being cancelled?\n(Leave blank if just for reference)",
            parent=self
        ) if hasattr(tk, 'simpledialog') else ''

        # Fallback if simpledialog not available
        if reason is None:
            # Simple confirmation instead
            if not messagebox.askyesno(
                "Cancel Invoice",
                "Cancel this invoice?\n"
                "Stock will be reversed if dispatched."
            ):
                return
            reason = ""

        ok, msg = cancel_invoice(invoice_id, reason or '',
                                 self.current_user['user_id'])
        if ok:
            messagebox.showinfo("✅ Cancelled", msg)
        else:
            messagebox.showerror("❌ Cancel Failed", msg)

        self.show_invoices()

    def _view_invoice(self, invoice_id):
        """View full invoice details."""
        from modules.invoice import get_invoice

        inv = get_invoice(invoice_id)
        if not inv: return

        d = tk.Toplevel(self)
        d.title(f"Invoice {inv['invoice_number']}")
        d.geometry("750x650")
        d.transient(self)

        # Scrollable content
        canvas = tk.Canvas(d); scrollbar = ttk.Scrollbar(d, orient='vertical', command=canvas.yview)
        frame = ttk.Frame(canvas, padding=20)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Header
        ttk.Label(frame, text=f"Invoice: {inv['invoice_number']}",
                  style='Title.TLabel').pack(anchor='w')

        status = inv['status']
        status_icon = {'created':'📋','dispatched':'🚚','paid':'✅','overdue':'⚠️','cancelled':'❌'}
        ttk.Label(frame, text=f"Status: {status_icon.get(status,'')} {status.upper()}",
                  font=('Segoe UI',12,'bold')).pack(anchor='w', pady=(5,0))

        # Customer & dates
        info_text = (
            f"Customer: {inv['customer_name']}\n"
            f"Phone: {inv.get('phone','N/A')} | Address: {inv.get('address','N/A')}\n"
            f"Invoice Date: {inv['invoice_date']} | Due Date: {inv['due_date']}\n"
            f"Created by: {inv.get('created_by_name','N/A')}"
        )
        if inv['is_dispatched']:
            info_text += f"\nDispatched: {inv.get('dispatched_date','')[:10]} by {inv.get('dispatched_by_name','N/A')}"
        if inv['is_paid']:
            info_text += f"\nPaid: {inv.get('paid_date','')[:10]} by {inv.get('paid_by_name','N/A')} via {inv.get('payment_method','N/A')}"
        if status == 'cancelled':
            info_text += f"\nCancelled: {inv.get('cancelled_date','')[:10]} by {inv.get('cancelled_by_name','N/A')}"
            if inv.get('cancel_reason'):
                info_text += f"\nReason: {inv['cancel_reason']}"

        ttk.Label(frame, text=info_text, font=('Segoe UI',10),
                  foreground='#636e72', justify='left').pack(anchor='w', pady=(5,15))

        # Items table
        ttk.Label(frame, text="📦 Items:", style='Header.TLabel').pack(anchor='w', pady=(0,5))

        cols = ('code','product','qty','unit','price','disc','gst','total')
        tree = ttk.Treeview(frame, columns=cols, show='headings', height=min(len(inv['items'])+1, 10))
        for c, h, w in [('code','Code',70),('product','Product',200),('qty','Qty',50),
                         ('unit','Unit',50),('price','Price',90),('disc','Disc%',50),
                         ('gst','GST%',50),('total','Total',100)]:
            tree.heading(c, text=h); tree.column(c, width=w)

        for item in inv['items']:
            tree.insert('','end', values=(
                item.get('product_code',''), item.get('product_name',''),
                item['quantity'], item.get('unit',''),
                format_currency(item['unit_price']),
                f"{item['discount_percent']}%", f"{item['gst_rate']}%",
                format_currency(item['line_total'])
            ))
        tree.pack(fill='x', pady=5)

        # Totals
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)
        tf = ttk.Frame(frame); tf.pack(fill='x')
        for l, v, bold in [
            ("Subtotal:", format_currency(inv['subtotal']), False),
            ("Discount:", f"-{format_currency(inv['discount_amount'])}", False),
            ("GST:", format_currency(inv['gst_amount']), False),
            ("TOTAL:", format_currency(inv['total_amount']), True),
            ("Paid:", format_currency(inv['amount_paid']), False),
            ("BALANCE:", format_currency(inv['balance_due']), True),
        ]:
            r = ttk.Frame(tf); r.pack(fill='x')
            ttk.Label(r, text=l, font=('Segoe UI',10,'bold' if bold else 'normal'),
                      width=15).pack(side='left', anchor='e')
            ttk.Label(r, text=v, font=('Segoe UI',10,'bold' if bold else 'normal')).pack(
                side='left', padx=10)

        # Payment history
        if inv['payments']:
            ttk.Label(frame, text="💰 Payment History:", style='Header.TLabel').pack(
                anchor='w', pady=(15,5))
            for p in inv['payments']:
                auto = " (auto)" if p.get('is_auto') else ""
                ttk.Label(frame,
                    text=f"  {p['payment_date']} | {format_currency(p['amount'])} | "
                         f"{p['payment_method']}{auto} | Ref: {p.get('reference_no','N/A')}",
                    font=('Segoe UI',10)).pack(anchor='w')

    # ─── CREATE INVOICE (same as before but NO stock deduction) ───

    def _create_invoice_dlg(self):
        from modules.invoice import get_all_customers, create_invoice, check_credit_limit
        from modules.inventory import get_all_products

        d = tk.Toplevel(self); d.title("Create Invoice"); d.geometry("900x700")
        d.minsize(800,600); d.transient(self); d.grab_set()
        d.grid_rowconfigure(1, weight=1); d.grid_columnconfigure(0, weight=1)

        # Header
        hf = ttk.LabelFrame(d, text="Invoice Details", padding=10)
        hf.grid(row=0, column=0, sticky='ew', padx=10, pady=(10,5))

        custs = get_all_customers()
        cm = {c['customer_name']: c for c in custs}

        ttk.Label(hf, text="Customer*:").grid(row=0, column=0, sticky='w')
        cv = tk.StringVar()
        cc = ttk.Combobox(hf, textvariable=cv, values=list(cm.keys()), state='readonly', width=30)
        cc.grid(row=0, column=1, padx=10, pady=5)

        today = datetime.now().strftime('%Y-%m-%d')
        due = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

        ttk.Label(hf, text="Date*:").grid(row=0, column=2, padx=10)
        dv = tk.StringVar(value=today); ttk.Entry(hf, textvariable=dv, width=12).grid(row=0, column=3)
        ttk.Label(hf, text="Due*:").grid(row=1, column=2, padx=10)
        duv = tk.StringVar(value=due); ttk.Entry(hf, textvariable=duv, width=12).grid(row=1, column=3)

        credit_lbl = tk.StringVar()
        ttk.Label(hf, textvariable=credit_lbl, foreground='#e67e22', font=('Segoe UI',9)).grid(
            row=1, column=0, columnspan=2, sticky='w')

        def on_cust(*a):
            c = cm.get(cv.get())
            if c:
                terms = c.get('payment_terms_days', 30) or 30
                try:
                    nd = datetime.strptime(dv.get(), '%Y-%m-%d') + timedelta(days=terms)
                    duv.set(nd.strftime('%Y-%m-%d'))
                except: pass
        cc.bind('<<ComboboxSelected>>', on_cust)

        # Items section
        isf = ttk.LabelFrame(d, text="Line Items", padding=10)
        isf.grid(row=1, column=0, sticky='nsew', padx=10, pady=5)
        isf.grid_rowconfigure(1, weight=1); isf.grid_columnconfigure(0, weight=1)

        # Add item form
        af = ttk.Frame(isf); af.grid(row=0, column=0, sticky='ew', pady=(0,5))
        prods = get_all_products()
        pm = {f"{p['product_code']} - {p['product_name']}": p for p in prods}

        pv, qv, prv, discv = tk.StringVar(), tk.StringVar(value='1'), tk.StringVar(value='0'), tk.StringVar(value='0')
        ttk.Label(af, text="Product:").grid(row=0, column=0)
        pc = ttk.Combobox(af, textvariable=pv, values=list(pm.keys()), state='readonly', width=30)
        pc.grid(row=0, column=1, padx=5)

        stock_lbl = ttk.Label(af, text="", foreground='#7f8c8d', font=('Segoe UI',9))
        stock_lbl.grid(row=1, column=1, sticky='w', padx=5)

        def on_prod(*a):
            p = pm.get(pv.get())
            if p:
                prv.set(str(p['selling_price']))
                stock_lbl.config(text=f"Stock: {p['current_stock']} {p['unit']}")
        pc.bind('<<ComboboxSelected>>', on_prod)

        for i, (l, v, w) in enumerate(
            [("Qty:",qv,6),("Price:",prv,10),("Disc%:",discv,5)], start=2):
            ttk.Label(af, text=l).grid(row=0, column=i*2)
            ttk.Entry(af, textvariable=v, width=w).grid(row=0, column=i*2+1, padx=3)

        items_list = []
        item_cols = ('product','qty','price','disc','gst','total')
        itree = ttk.Treeview(isf, columns=item_cols, show='headings', height=8)
        for c, h, w in [('product','Product',280),('qty','Qty',60),('price','Price',100),
                         ('disc','Disc%',60),('gst','GST%',60),('total','Total',120)]:
            itree.heading(c, text=h); itree.column(c, width=w)
        itree.grid(row=1, column=0, sticky='nsew')

        total_var = tk.StringVar(value="Total: ₹0.00")

        def refresh():
            gt = sum(i['line_total'] for i in items_list)
            total_var.set(f"Total: {format_currency(gt)}")

        def add_item():
            p = pm.get(pv.get())
            if not p: messagebox.showerror("Error", "Select product."); return
            try:
                qty = float(qv.get()); price = float(prv.get()); disc = float(discv.get())
                if qty <= 0: raise ValueError("Qty must be positive")

                # Note: we don't block based on stock — stock is checked at DISPATCH
                # But we warn the user
                existing = sum(i['quantity'] for i in items_list if i['product_id'] == p['product_id'])
                if existing + qty > p['current_stock']:
                    messagebox.showwarning("⚠️ Stock Warning",
                        f"Current stock: {p['current_stock']} {p['unit']}\n"
                        f"This invoice will need: {existing + qty}\n\n"
                        f"You can still create the invoice,\n"
                        f"but dispatch will fail unless stock is replenished.")

                gst = p['gst_rate']; gross = qty * price
                discount = gross * (disc/100); taxable = gross - discount
                gst_amt = taxable * (gst/100); total = taxable + gst_amt

                item = {'product_id': p['product_id'],
                    'product_name': f"{p['product_code']} - {p['product_name']}",
                    'quantity': qty, 'unit_price': price,
                    'discount_percent': disc, 'gst_rate': gst, 'line_total': round(total, 2)}
                items_list.append(item)
                itree.insert('','end', values=(item['product_name'], qty,
                    format_currency(price), f"{disc}%", f"{gst}%", format_currency(total)))
                refresh()
            except ValueError as e:
                messagebox.showerror("Error", str(e))

        def remove_item():
            sel = itree.selection()
            if not sel: return
            idx = itree.index(sel[0]); itree.delete(sel[0]); items_list.pop(idx); refresh()

        ttk.Button(af, text="➕ Add", command=add_item).grid(row=0, column=8, padx=5)
        ttk.Button(af, text="🗑️ Remove", command=remove_item).grid(row=0, column=9, padx=5)

        # Footer
        footer = ttk.Frame(d, padding=10)
        footer.grid(row=2, column=0, sticky='ew', padx=10, pady=5)
        ttk.Label(footer, textvariable=total_var, font=('Segoe UI',16,'bold')).pack(side='left')

        def save():
            if not cv.get(): messagebox.showerror("Error", "Select customer."); return
            if not items_list: messagebox.showerror("Error", "Add items."); return
            if not validate_date(dv.get()) or not validate_date(duv.get()):
                messagebox.showerror("Error", "Invalid date (YYYY-MM-DD)."); return

            cust = cm[cv.get()]
            gt = sum(i['line_total'] for i in items_list)

            if not messagebox.askyesno("Confirm",
                f"Create invoice for {cust['customer_name']}?\n"
                f"Items: {len(items_list)} | Total: {format_currency(gt)}\n\n"
                f"Note: Stock will be deducted only when dispatched."):
                return

            try:
                iid, inum = create_invoice(
                    cust['customer_id'], dv.get(), duv.get(),
                    items_list, '', self.current_user['user_id'])
                messagebox.showinfo("✅ Created",
                    f"Invoice {inum} created!\nTotal: {format_currency(gt)}\n\n"
                    f"Click 'Dispatch' when goods are ready to ship.")
                d.destroy(); self.show_invoices()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(footer, text="💾  CREATE INVOICE  💾", style='Save.TButton',
                   command=save).pack(side='right', ipadx=20, ipady=5)

    # ─── PAYMENTS ───
        # ─── PAYMENTS PAGE — FIXED WITH PROPER LIST VIEW ───
    def show_payments(self):
        """Payment records page showing all payments in a detailed list."""
        self._clear()
        from database import get_connection

        ttk.Label(self.content, text="Payment Records",
                  style='Title.TLabel').pack(anchor='w', pady=(0, 10))

        # ── Filters ──
        filter_frame = ttk.Frame(self.content)
        filter_frame.pack(fill='x', pady=(0, 10))

        # Date range filter
        ttk.Label(filter_frame, text="From:").pack(side='left', padx=(0, 5))
        from_var = tk.StringVar(value=(datetime.now().replace(day=1)).strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=from_var, width=12).pack(side='left')

        ttk.Label(filter_frame, text="To:").pack(side='left', padx=(10, 5))
        to_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=to_var, width=12).pack(side='left')

        # Method filter
        ttk.Label(filter_frame, text="Method:").pack(side='left', padx=(15, 5))
        method_var = tk.StringVar(value='all')
        ttk.Combobox(filter_frame, textvariable=method_var,
                     values=['all', 'cash', 'upi', 'bank_transfer',
                             'cheque', 'card', 'other'],
                     state='readonly', width=14).pack(side='left')

        # Search by customer/invoice
        ttk.Label(filter_frame, text="Search:").pack(side='left', padx=(15, 5))
        search_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=search_var, width=20).pack(side='left')

        # ── Summary Cards ──
        summary_frame = ttk.Frame(self.content)
        summary_frame.pack(fill='x', pady=(0, 10))

        total_card = ttk.LabelFrame(summary_frame, text="Total Collected", padding=10)
        total_card.pack(side='left', fill='both', expand=True, padx=3)
        total_amount_var = tk.StringVar(value="₹0.00")
        ttk.Label(total_card, textvariable=total_amount_var,
                  font=('Segoe UI', 18, 'bold'), foreground='#27ae60').pack()

        count_card = ttk.LabelFrame(summary_frame, text="Payment Count", padding=10)
        count_card.pack(side='left', fill='both', expand=True, padx=3)
        count_var = tk.StringVar(value="0")
        ttk.Label(count_card, textvariable=count_var,
                  font=('Segoe UI', 18, 'bold'), foreground='#2c3e50').pack()

        cash_card = ttk.LabelFrame(summary_frame, text="Cash", padding=10)
        cash_card.pack(side='left', fill='both', expand=True, padx=3)
        cash_var = tk.StringVar(value="₹0.00")
        ttk.Label(cash_card, textvariable=cash_var,
                  font=('Segoe UI', 18, 'bold'), foreground='#2c3e50').pack()

        upi_card = ttk.LabelFrame(summary_frame, text="UPI/Digital", padding=10)
        upi_card.pack(side='left', fill='both', expand=True, padx=3)
        upi_var = tk.StringVar(value="₹0.00")
        ttk.Label(upi_card, textvariable=upi_var,
                  font=('Segoe UI', 18, 'bold'), foreground='#0984e3').pack()

        bank_card = ttk.LabelFrame(summary_frame, text="Bank/Cheque/Card", padding=10)
        bank_card.pack(side='left', fill='both', expand=True, padx=3)
        bank_var = tk.StringVar(value="₹0.00")
        ttk.Label(bank_card, textvariable=bank_var,
                  font=('Segoe UI', 18, 'bold'), foreground='#6c5ce7').pack()

        # ── Payment Records Table ──
        table_frame = ttk.Frame(self.content)
        table_frame.pack(fill='both', expand=True)

        columns = ('sr', 'date', 'invoice', 'customer', 'amount',
                   'method', 'reference', 'type', 'recorded_by', 'time')

        tree = ttk.Treeview(table_frame, columns=columns,
                            show='headings', height=20)

        # Column configurations
        col_config = [
            ('sr', '#', 40, 'center'),
            ('date', 'Payment Date', 100, 'center'),
            ('invoice', 'Invoice #', 130, 'w'),
            ('customer', 'Customer', 180, 'w'),
            ('amount', 'Amount', 120, 'e'),
            ('method', 'Method', 100, 'center'),
            ('reference', 'Reference No.', 150, 'w'),
            ('type', 'Type', 70, 'center'),
            ('recorded_by', 'Recorded By', 120, 'w'),
            ('time', 'Timestamp', 140, 'w'),
        ]

        for col_id, heading, width, anchor in col_config:
            tree.heading(col_id, text=heading,
                         command=lambda c=col_id: self._sort_payment_tree(tree, c, False))
            tree.column(col_id, width=width, anchor=anchor)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # ── Status bar ──
        status_var = tk.StringVar(value="")
        ttk.Label(self.content, textvariable=status_var,
                  font=('Segoe UI', 9), foreground='#7f8c8d').pack(
            anchor='w', pady=(5, 0))

        # ── Populate function ──
        def populate(*args):
            # Clear existing rows
            tree.delete(*tree.get_children())

            conn = get_connection()

            # Build query with filters
            query = """
                SELECT p.payment_id,
                       p.payment_date,
                       p.amount,
                       p.payment_method,
                       p.reference_no,
                       p.remarks,
                       p.is_auto,
                       p.created_at,
                       i.invoice_number,
                       i.total_amount as invoice_total,
                       c.customer_name,
                       c.phone as customer_phone,
                       u.full_name as recorded_by
                FROM payments p
                JOIN invoices i ON p.invoice_id = i.invoice_id
                JOIN customers c ON i.customer_id = c.customer_id
                LEFT JOIN users u ON p.created_by = u.user_id
                WHERE 1=1
            """
            params = []

            # Date filter
            date_from = from_var.get().strip()
            date_to = to_var.get().strip()
            if validate_date(date_from):
                query += " AND p.payment_date >= ?"
                params.append(date_from)
            if validate_date(date_to):
                query += " AND p.payment_date <= ?"
                params.append(date_to)

            # Method filter
            method = method_var.get()
            if method and method != 'all':
                query += " AND p.payment_method = ?"
                params.append(method)

            # Search filter
            search = search_var.get().strip()
            if search:
                query += " AND (c.customer_name LIKE ? OR i.invoice_number LIKE ? OR p.reference_no LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

            query += " ORDER BY p.payment_date DESC, p.created_at DESC"

            rows = conn.execute(query, params).fetchall()
            conn.close()

            # Calculate summaries
            total = 0
            cash_total = 0
            upi_total = 0
            bank_total = 0

            for idx, r in enumerate(rows, start=1):
                amount = r['amount']
                total += amount
                method_val = r['payment_method']

                if method_val == 'cash':
                    cash_total += amount
                elif method_val in ('upi',):
                    upi_total += amount
                else:
                    bank_total += amount

                # Determine type label
                pay_type = "Auto" if r['is_auto'] else "Manual"

                # Color-code by method
                if method_val == 'cash':
                    tag = 'cash'
                elif method_val == 'upi':
                    tag = 'upi'
                elif method_val in ('bank_transfer', 'cheque'):
                    tag = 'bank'
                elif method_val == 'card':
                    tag = 'card'
                else:
                    tag = 'other'

                # Format method display
                method_display = {
                    'cash': '💵 Cash',
                    'upi': '📱 UPI',
                    'bank_transfer': '🏦 Bank Transfer',
                    'cheque': '📝 Cheque',
                    'card': '💳 Card',
                    'other': '📋 Other'
                }.get(method_val, method_val)

                tree.insert('', 'end', values=(
                    idx,
                    r['payment_date'],
                    r['invoice_number'],
                    r['customer_name'],
                    format_currency(amount),
                    method_display,
                    r['reference_no'] or '—',
                    pay_type,
                    r['recorded_by'] or 'System',
                    r['created_at'][:19] if r['created_at'] else '—',
                ), tags=(tag,))

            # Apply tag colors
            tree.tag_configure('cash', background='#ffeaa7')
            tree.tag_configure('upi', background='#dfe6e9')
            tree.tag_configure('bank', background='#b2f2bb')
            tree.tag_configure('card', background='#c3aed6')
            tree.tag_configure('other', background='#ffffff')

            # Update summary cards
            total_amount_var.set(format_currency(total))
            count_var.set(str(len(rows)))
            cash_var.set(format_currency(cash_total))
            upi_var.set(format_currency(upi_total))
            bank_var.set(format_currency(bank_total))

            # Update status bar
            status_var.set(
                f"Showing {len(rows)} payment records  │  "
                f"Period: {date_from} to {date_to}  │  "
                f"Total: {format_currency(total)}"
            )

        # ── Apply Filter Button ──
        ttk.Button(filter_frame, text="🔍 Apply",
                   style='Action.TButton',
                   command=populate).pack(side='left', padx=10)

        # Auto-filter on search typing (with delay)
        search_timer = [None]

        def on_search_change(*args):
            if search_timer[0]:
                self.after_cancel(search_timer[0])
            search_timer[0] = self.after(500, populate)

        search_var.trace_add('write', on_search_change)
        method_var.trace_add('write', lambda *a: populate())

        # ── Context Menu ──
        ctx_menu = tk.Menu(self, tearoff=0)
        ctx_menu.add_command(
            label="📋 View Invoice",
            command=lambda: self._view_payment_invoice(tree)
        )
        ctx_menu.add_command(
            label="📄 Copy Reference",
            command=lambda: self._copy_payment_ref(tree)
        )

        def show_ctx(event):
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
                ctx_menu.post(event.x_root, event.y_root)

        tree.bind('<Button-3>', show_ctx)
        tree.bind('<Double-1>', lambda e: self._view_payment_invoice(tree))

        # Initial load
        populate()

    def _sort_payment_tree(self, tree, col, reverse):
        """Sort treeview by column."""
        data = [(tree.set(child, col), child)
                for child in tree.get_children('')]

        # Try numeric sort for amount column
        if col == 'amount':
            try:
                data.sort(key=lambda t: float(
                    t[0].replace('₹', '').replace(',', '')),
                    reverse=reverse)
            except ValueError:
                data.sort(reverse=reverse)
        elif col == 'sr':
            data.sort(key=lambda t: int(t[0]), reverse=reverse)
        else:
            data.sort(reverse=reverse)

        for index, (val, child) in enumerate(data):
            tree.move(child, '', index)

        # Toggle sort direction for next click
        tree.heading(col, command=lambda: self._sort_payment_tree(
            tree, col, not reverse))

    def _view_payment_invoice(self, tree):
        """Open invoice detail from payment record."""
        sel = tree.selection()
        if not sel:
            return

        # Get invoice number from the selected row
        invoice_number = tree.set(sel[0], 'invoice')

        # Find invoice ID from invoice number
        from database import get_connection
        conn = get_connection()
        row = conn.execute(
            "SELECT invoice_id FROM invoices WHERE invoice_number=?",
            (invoice_number,)).fetchone()
        conn.close()

        if row:
            self._view_invoice(row['invoice_id'])

    def _copy_payment_ref(self, tree):
        """Copy payment reference to clipboard."""
        sel = tree.selection()
        if not sel:
            return
        ref = tree.set(sel[0], 'reference')
        if ref and ref != '—':
            self.clipboard_clear()
            self.clipboard_append(ref)
            messagebox.showinfo("Copied", f"Reference '{ref}' copied to clipboard.")

    # ─── REPORTS (abbreviated — same structure as before) ───
    def show_reports(self):
        self._clear()
        ttk.Label(self.content, text="Reports & Analytics", style='Title.TLabel').pack(anchor='w', pady=(0,15))
        rf = ttk.Frame(self.content); rf.pack(fill='x', pady=10)
        for text, cmd in [("📊 Aged Receivables", self._aged_report),
                          ("📈 DSO", self._dso_report),
                          ("🏆 Top Debtors", self._debtors_report),
                          ("📦 ABC", self._abc_report),
                          ("⚠️ Low Stock", self._stock_report),
                          ("📅 Monthly", self._monthly_report)]:
            ttk.Button(rf, text=text, style='Action.TButton', command=cmd).pack(side='left', padx=4)
        self.rpt = ttk.Frame(self.content); self.rpt.pack(fill='both', expand=True, pady=10)
        self._aged_report()

    def _cr(self):
        for w in self.rpt.winfo_children(): w.destroy()

    def _aged_report(self):
        self._cr()
        from modules.reporting import get_aged_receivables
        aged = get_aged_receivables()
        sf = ttk.Frame(self.rpt); sf.pack(fill='x', pady=5)
        for l, k in [("0-30",'current'),("31-60",'31_60'),("61-90",'61_90'),
                      ("90+",'over_90'),("Total",'grand_total')]:
            c = ttk.LabelFrame(sf, text=l, padding=10)
            c.pack(side='left', fill='both', expand=True, padx=3)
            ttk.Label(c, text=format_currency(aged['totals'][k]),
                      font=('Segoe UI',14,'bold')).pack()

    def _dso_report(self):
        self._cr()
        from modules.reporting import calculate_dso
        sf = ttk.Frame(self.rpt); sf.pack(fill='x', pady=10)
        for p, data in [("30-Day",calculate_dso(30)),("60-Day",calculate_dso(60)),
                         ("90-Day",calculate_dso(90))]:
            c = ttk.LabelFrame(sf, text=f"{p} DSO", padding=15)
            c.pack(side='left', fill='both', expand=True, padx=5)
            ttk.Label(c, text=f"{data['dso']} days", font=('Segoe UI',22,'bold')).pack()

    def _debtors_report(self):
        self._cr()
        from modules.reporting import get_top_customers_by_outstanding
        data = get_top_customers_by_outstanding(15)
        cols = ('name','inv','outstanding')
        tree = ttk.Treeview(self.rpt, columns=cols, show='headings', height=15)
        for c, h, w in [('name','Customer',250),('inv','Invoices',80),('outstanding','Outstanding',150)]:
            tree.heading(c, text=h); tree.column(c, width=w)
        for d in data:
            tree.insert('','end', values=(d['customer_name'], d['invoice_count'],
                format_currency(d['total_outstanding'])))
        tree.pack(fill='both', expand=True)

    def _abc_report(self):
        self._cr()
        from modules.inventory import get_abc_summary
        sf = ttk.Frame(self.rpt); sf.pack(fill='x', pady=10)
        for s in get_abc_summary():
            c = ttk.LabelFrame(sf, text=f"Class {s['abc_class']}", padding=15)
            c.pack(side='left', fill='both', expand=True, padx=5)
            ttk.Label(c, text=str(s['product_count']), font=('Segoe UI',22,'bold')).pack()
            ttk.Label(c, text=f"Value: {format_currency(s.get('total_value',0))}").pack()

    def _stock_report(self):
        self._cr()
        from modules.inventory import get_low_stock_products
        low = get_low_stock_products()
        cols = ('code','name','stock','reorder','status')
        tree = ttk.Treeview(self.rpt, columns=cols, show='headings', height=15)
        for c, h, w in [('code','Code',80),('name','Product',250),('stock','Stock',80),
                         ('reorder','Reorder',80),('status','Status',100)]:
            tree.heading(c, text=h); tree.column(c, width=w)
        for p in low:
            st = "OUT" if p['current_stock'] <= 0 else "LOW"
            tag = 'out' if st == 'OUT' else 'low'
            tree.insert('','end', values=(p['product_code'], p['product_name'],
                p['current_stock'], p['reorder_level'], st), tags=(tag,))
        tree.tag_configure('out', background='#fab1a0')
        tree.tag_configure('low', background='#ffeaa7')
        tree.pack(fill='both', expand=True)

    def _monthly_report(self):
        self._cr()
        from modules.reporting import get_monthly_sales_trend
        data = get_monthly_sales_trend(12)
        cols = ('month','inv','rev','col','out')
        tree = ttk.Treeview(self.rpt, columns=cols, show='headings', height=15)
        for c, h, w in [('month','Month',100),('inv','Invoices',80),('rev','Revenue',150),
                         ('col','Collected',150),('out','Outstanding',150)]:
            tree.heading(c, text=h); tree.column(c, width=w)
        for d in data:
            tree.insert('','end', values=(d['month'], d['invoice_count'],
                format_currency(d['revenue']), format_currency(d['collected']),
                format_currency(d['outstanding'])))
        tree.pack(fill='both', expand=True)

    # ─── ALERTS ───
    def show_alerts(self):
        self._clear()
        from utils.alerts import get_all_alerts
        ttk.Label(self.content, text="Alerts", style='Title.TLabel').pack(anchor='w', pady=(0,15))
        alerts = get_all_alerts()
        if not alerts:
            ttk.Label(self.content, text="✅ All clear!", foreground='#27ae60',
                      font=('Segoe UI',14)).pack(pady=40); return
        for a in alerts:
            icon = "🔴" if a['severity'] == 'critical' else "🟡"
            fg = '#e74c3c' if a['severity'] == 'critical' else '#f39c12'
            ttk.Label(self.content, text=f"{icon} [{a['type']}] {a['message']}",
                      foreground=fg, font=('Segoe UI',10)).pack(anchor='w', pady=2)

    # ─── ADMIN ───
    def show_admin(self):
        self._clear()
        from modules.admin import get_all_users, get_audit_log, perform_backup
        ttk.Label(self.content, text="Administration", style='Title.TLabel').pack(anchor='w', pady=(0,15))

        tb = ttk.Frame(self.content); tb.pack(fill='x', pady=(0,10))
        ttk.Button(tb, text="➕ Add User", style='Action.TButton',
                   command=self._add_user_dlg).pack(side='left', padx=5)
        ttk.Button(tb, text="💾 Backup", style='Action.TButton',
                   command=lambda: messagebox.showinfo("✅",
                       f"Backup: {perform_backup(self.current_user['user_id'])}")).pack(side='left', padx=5)

        nb = ttk.Notebook(self.content); nb.pack(fill='both', expand=True)

        uf = ttk.Frame(nb, padding=10); nb.add(uf, text="Users")
        for u in get_all_users():
            ttk.Label(uf, text=f"{u['username']} | {u['full_name']} | {u['role']} | "
                f"Active: {'Yes' if u['is_active'] else 'No'}").pack(anchor='w', pady=2)

        af = ttk.Frame(nb, padding=10); nb.add(af, text="Audit Log")
        cols = ('time','user','action')
        at = ttk.Treeview(af, columns=cols, show='headings', height=15)
        for c, h, w in [('time','Time',150),('user','User',120),('action','Action',300)]:
            at.heading(c, text=h); at.column(c, width=w)
        for l in get_audit_log(200):
            at.insert('','end', values=(l['timestamp'], l.get('full_name','System'), l['action']))
        at.pack(fill='both', expand=True)

    def _add_user_dlg(self):
        from modules.admin import create_user
        d = tk.Toplevel(self); d.title("Add User"); d.geometry("400x380")
        d.transient(self); d.grab_set()
        f = ttk.Frame(d, padding=20); f.pack(fill='both', expand=True)
        fields = {}
        for i, (k, l) in enumerate([('username','Username*:'),('password','Password*:'),
                                      ('full_name','Full Name*:'),('email','Email:')], start=1):
            ttk.Label(f, text=l).grid(row=i, column=0, sticky='w', pady=5)
            var = tk.StringVar()
            ttk.Entry(f, textvariable=var, width=25,
                      show='•' if k == 'password' else '').grid(row=i, column=1, padx=10, pady=5)
            fields[k] = var
        rv = tk.StringVar(value='staff')
        ttk.Label(f, text="Role:").grid(row=5, column=0, sticky='w')
        ttk.Combobox(f, textvariable=rv, values=['staff','manager','admin'],
                     state='readonly', width=22).grid(row=5, column=1, padx=10)
        def save():
            u, p, n = (fields['username'].get().strip(), fields['password'].get().strip(),
                       fields['full_name'].get().strip())
            if not all([u,p,n]): messagebox.showerror("Error", "Fill required fields."); return
            try:
                create_user(u, p, n, rv.get(), fields['email'].get(), self.current_user['user_id'])
                messagebox.showinfo("✅", "User created!"); d.destroy(); self.show_admin()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(f, text="💾 Create", style='Action.TButton', command=save).grid(
            row=6, column=0, columnspan=2, pady=20, sticky='ew')