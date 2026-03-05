"""
Data models — plain dataclasses for the core business objects.
Nothing fancy, just structured containers for passing data around.
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Product:
    product_id: Optional[int] = None
    product_code: str = ""
    product_name: str = ""
    category_id: Optional[int] = None
    unit: str = "pcs"
    purchase_price: float = 0.0
    selling_price: float = 0.0
    gst_rate: float = 18.0
    current_stock: float = 0.0
    reorder_level: float = 10.0
    abc_class: str = "C"
    annual_consumption_value: float = 0.0
    is_active: bool = True


@dataclass
class Customer:
    customer_id: Optional[int] = None
    customer_name: str = ""
    customer_type: str = "retail"
    phone: str = ""
    email: str = ""
    address: str = ""
    gst_number: str = ""
    credit_limit: float = 0.0
    discount_rate: float = 0.0
    is_active: bool = True


@dataclass
class InvoiceItem:
    item_id: Optional[int] = None
    invoice_id: Optional[int] = None
    product_id: int = 0
    product_name: str = ""
    quantity: float = 0.0
    unit_price: float = 0.0
    discount_percent: float = 0.0
    gst_rate: float = 18.0
    line_total: float = 0.0


@dataclass
class Invoice:
    invoice_id: Optional[int] = None
    invoice_number: str = ""
    customer_id: int = 0
    customer_name: str = ""
    invoice_date: str = ""
    due_date: str = ""
    subtotal: float = 0.0
    discount_amount: float = 0.0
    gst_amount: float = 0.0
    total_amount: float = 0.0
    amount_paid: float = 0.0
    balance_due: float = 0.0
    status: str = "pending"
    payment_delay_days: int = 0
    items: List[InvoiceItem] = field(default_factory=list)


@dataclass
class Payment:
    payment_id: Optional[int] = None
    invoice_id: int = 0
    payment_date: str = ""
    amount: float = 0.0
    payment_method: str = "cash"
    reference_no: str = ""
    remarks: str = ""