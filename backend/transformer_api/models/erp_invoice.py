from __future__ import annotations

from pydantic import BaseModel


class LineItem(BaseModel):
    product_code: str
    description: str
    quantity: float
    unit_price: float
    line_total: float


class ERPInvoice(BaseModel):
    sales_request_ref: str
    invoice_date: str
    sales_person: str
    customer_contact: str
    trading_address: str
    delivery_address: str
    discount_percent: float

    customer_name: str
    country: str
    tax_rate: str
    terms_and_conditions: str
    payment_terms: str
    payment_method: str
    delivery_date: str
    customer_reference: str
    payment_reference: str

    line_items: list[LineItem]
    subtotal: float
    tax_amount: float
    total: float
