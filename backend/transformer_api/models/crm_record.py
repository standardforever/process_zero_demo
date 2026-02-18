from __future__ import annotations

from pydantic import BaseModel


class CRMRecord(BaseModel):
    sales_request_ref: str
    crm_source_system_id: str | None = None
    date_raised: str
    sales_person: str
    status: str
    customer_company: str
    customer_contact: str
    trading_address: str
    delivery_address: str
    sales_discount_percent: str
    product_1: str | None = None
    product_1_quantity: str | None = None
    product_1_price_per_unit: str | None = None
    product_2: str | None = None
    product_2_quantity: str | None = None
    product_2_price_per_unit: str | None = None
    product_3: str | None = None
    product_3_quantity: str | None = None
    product_3_price_per_unit: str | None = None
