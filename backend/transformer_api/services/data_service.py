from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models.crm_record import CRMRecord

ROOT_DIR = Path(__file__).resolve().parents[2]
VISIBLE_ROWS_FILE = ROOT_DIR / "visible_rows.json"


def _load_visible_rows() -> list[dict[str, Any]]:
    with VISIBLE_ROWS_FILE.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return payload.get("rows", [])


def _normalize_row(row: dict[str, Any]) -> CRMRecord:
    return CRMRecord(
        sales_request_ref=str(row.get("Sales Request Ref", "")).strip(),
        crm_source_system_id=_nullable_string(row.get("CRM Source System ID")),
        date_raised=str(row.get("Date Raised", "")).strip(),
        sales_person=str(row.get("Sales Person", "")).strip(),
        status=str(row.get("Status", "")).strip(),
        customer_company=str(row.get("Customer Company", "")).strip(),
        customer_contact=str(row.get("Customer Contact", "")).strip(),
        trading_address=str(row.get("Trading Address", "")).strip(),
        delivery_address=str(row.get("Delivery Address", "")).strip(),
        sales_discount_percent=str(row.get("Sales Discount %", "0")).strip(),
        product_1=_nullable_string(row.get("Product 1")),
        product_1_quantity=_nullable_string(row.get("Product 1 Quantity")),
        product_1_price_per_unit=_nullable_string(row.get("Product 1 Price Per Unit")),
        product_2=_nullable_string(row.get("Product 2")),
        product_2_quantity=_nullable_string(row.get("Product 2 Quantity")),
        product_2_price_per_unit=_nullable_string(row.get("Product 2 Price Per Unit")),
        product_3=_nullable_string(row.get("Product 3")),
        product_3_quantity=_nullable_string(row.get("Product 3 Quantity")),
        product_3_price_per_unit=_nullable_string(row.get("Product 3 Price Per Unit")),
    )


def _nullable_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def get_records(search: str | None = None) -> list[CRMRecord]:
    normalized = [_normalize_row(row) for row in _load_visible_rows()]
    if not search:
        return normalized

    query = search.strip().lower()
    return [
        record
        for record in normalized
        if query in record.customer_company.lower() or query in record.sales_request_ref.lower()
    ]


def get_paginated_records(page: int = 1, limit: int = 10, search: str | None = None) -> dict[str, Any]:
    records = get_records(search=search)
    total = len(records)
    total_pages = max(1, (total + limit - 1) // limit)
    safe_page = max(1, min(page, total_pages))

    start = (safe_page - 1) * limit
    end = start + limit
    items = records[start:end]

    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "page": safe_page,
        "limit": limit,
        "total_pages": total_pages,
    }


def get_record_by_sales_ref(sales_request_ref: str) -> CRMRecord | None:
    target = sales_request_ref.strip().lower()
    for record in get_records():
        if record.sales_request_ref.lower() == target:
            return record
    return None


def get_unique_customers() -> list[str]:
    customers = {record.customer_company for record in get_records() if record.customer_company}
    return sorted(customers)


def get_stats() -> dict[str, int | str | None]:
    records = get_records()
    active_count = sum(1 for record in records if record.status.lower() == "active")
    return {
        "total_records": len(records),
        "active_records": active_count,
        "customer_count": len(get_unique_customers()),
        "latest_sales_request_ref": records[0].sales_request_ref if records else None,
    }
