from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from dateutil import parser

from ..models.crm_record import CRMRecord
from ..models.erp_invoice import ERPInvoice, LineItem
from .rules_service import load_rules

TRANSFORMED_OUTPUT_FILE = Path(__file__).resolve().parents[1] / "data" / "transformed.json"


def _to_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    cleaned = value.replace(",", "").replace("%", "").strip()
    if not cleaned:
        return default
    try:
        return float(cleaned)
    except ValueError:
        return default


def _parse_tax_percent(tax_rate: str) -> float:
    normalized = tax_rate.strip().lower()
    if normalized == "exempt":
        return 0.0
    return _to_float(tax_rate, default=0.0)


def _split_product(value: str) -> tuple[str, str]:
    if " - " in value:
        code, description = value.split(" - ", 1)
        return code.strip(), description.strip()

    parts = value.split(maxsplit=1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return value.strip(), value.strip()


def _prefix_from_name(name: str, length: int, fallback: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9]", "", name).upper()
    return (compact[:length] or fallback).upper()


def _resolve_source_field(record: CRMRecord, field_name: str, fallback_field: str) -> str:
    primary = getattr(record, field_name, None)
    if primary is not None and str(primary).strip():
        return str(primary).strip()

    fallback = getattr(record, fallback_field, None)
    if fallback is not None and str(fallback).strip():
        return str(fallback).strip()

    return ""


def _build_invoice_id(source: str, prefix: str, pad_length: int) -> str:
    cleaned_source = str(source).strip()
    if not cleaned_source:
        cleaned_source = "0"

    digits = re.sub(r"[^0-9]", "", cleaned_source)
    suffix = digits if digits else re.sub(r"[^A-Za-z0-9]", "", cleaned_source).upper()
    if pad_length > 0 and suffix.isdigit():
        suffix = suffix.zfill(pad_length)

    normalized_prefix = re.sub(r"[^A-Za-z0-9]", "", prefix).upper()
    return f"{normalized_prefix}{suffix}"


def _build_line_items(record: CRMRecord) -> list[LineItem]:
    items: list[LineItem] = []

    for index in (1, 2, 3):
        product = getattr(record, f"product_{index}")
        quantity = getattr(record, f"product_{index}_quantity")
        unit_price = getattr(record, f"product_{index}_price_per_unit")

        if not product:
            continue

        code, description = _split_product(product)
        qty = _to_float(quantity, default=0.0)
        price = _to_float(unit_price, default=0.0)
        line_total = round(qty * price, 2)

        items.append(
            LineItem(
                product_code=code,
                description=description,
                quantity=qty,
                unit_price=price,
                line_total=line_total,
            )
        )

    return items


def transform_record(record: CRMRecord) -> ERPInvoice:
    rules = load_rules()
    # UK date format (DD/MM/YYYY)
    invoice_date = parser.parse(record.date_raised, dayfirst=True)

    mapped_customer = rules.customerNameMapping.get(record.customer_company, record.customer_company)
    country = rules.customerCountry.conditions.get(mapped_customer, rules.customerCountry.default)
    tax_rate = rules.salesTaxRate.conditions.get(mapped_customer, rules.salesTaxRate.default)
    terms = rules.termsAndConditions.conditions.get(mapped_customer, rules.termsAndConditions.default)
    payment_terms = rules.paymentTerms.conditions.get(mapped_customer, rules.paymentTerms.default)
    payment_method = rules.paymentMethod.conditions.get(mapped_customer, rules.paymentMethod.default)
    delivery_days = rules.deliveryDays.conditions.get(mapped_customer, rules.deliveryDays.default)

    delivery_date = invoice_date + timedelta(days=delivery_days)

    line_items = _build_line_items(record)
    subtotal_before_discount = sum(item.line_total for item in line_items)
    discount_percent = _to_float(record.sales_discount_percent, default=0.0)
    subtotal = round(subtotal_before_discount * (1 - discount_percent / 100), 2)
    tax_percent = _parse_tax_percent(tax_rate)
    tax_amount = round(subtotal * (tax_percent / 100), 2)
    total = round(subtotal + tax_amount, 2)

    customer_ref_rules = rules.customerReference
    payment_ref_rules = rules.paymentReference

    year = str(invoice_date.year)
    customer_ref_prefix = _prefix_from_name(
        mapped_customer,
        length=customer_ref_rules.customerNamePrefixLength,
        fallback="CUS",
    )
    invoice_source = _resolve_source_field(
        record,
        field_name=customer_ref_rules.invoiceIdSource,
        fallback_field="sales_request_ref",
    )
    invoice_id = _build_invoice_id(
        source=invoice_source,
        prefix=customer_ref_rules.invoiceIdPrefix,
        pad_length=customer_ref_rules.invoiceIdPadLength,
    )
    customer_reference = (
        f"{customer_ref_prefix}{year}{invoice_id}"
        if customer_ref_rules.includeYear
        else f"{customer_ref_prefix}{invoice_id}"
    )

    payment_ref_prefix = _prefix_from_name(
        mapped_customer,
        length=payment_ref_rules.customerNamePrefixLength,
        fallback="PAYME",
    )
    crm_source_id = _resolve_source_field(
        record,
        field_name=payment_ref_rules.crmSourceIdField,
        fallback_field=payment_ref_rules.fallbackSourceIdField,
    )
    crm_source_id = re.sub(r"[^A-Za-z0-9]", "", crm_source_id).upper() or record.sales_request_ref
    total_without_decimals = str(int(total)) if payment_ref_rules.useInvoiceTotalWithoutDecimals else str(total)
    payment_reference = f"{payment_ref_prefix}{crm_source_id}{total_without_decimals}"

    return ERPInvoice(
        sales_request_ref=record.sales_request_ref,
        invoice_date=invoice_date.date().isoformat(),
        sales_person=record.sales_person,
        customer_contact=record.customer_contact,
        trading_address=record.trading_address,
        delivery_address=record.delivery_address,
        discount_percent=discount_percent,
        customer_name=mapped_customer,
        country=country,
        tax_rate=tax_rate,
        terms_and_conditions=terms,
        payment_terms=payment_terms,
        payment_method=payment_method,
        delivery_date=delivery_date.date().isoformat(),
        customer_reference=customer_reference,
        payment_reference=payment_reference,
        line_items=line_items,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=total,
    )


def transform_batch(records: list[CRMRecord]) -> list[ERPInvoice]:
    return [transform_record(record) for record in records]


def save_batch_output(invoices: list[ERPInvoice]) -> dict[str, Any]:
    payload = {
        "count": len(invoices),
        "invoices": [invoice.model_dump() for invoice in invoices],
    }
    with TRANSFORMED_OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
        file.write("\n")
    return payload


def get_saved_output() -> dict[str, Any]:
    if not TRANSFORMED_OUTPUT_FILE.exists():
        return {"count": 0, "invoices": []}

    with TRANSFORMED_OUTPUT_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)
