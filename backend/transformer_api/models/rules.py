from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator


class ConditionalStringRule(BaseModel):
    default: str = Field(alias="_default")
    conditions: dict[str, str] = Field(default_factory=dict)

    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
    }


class ConditionalIntRule(BaseModel):
    default: int = Field(alias="_default")
    conditions: dict[str, int] = Field(default_factory=dict)

    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
    }


class CustomerReferenceRule(BaseModel):
    customerNamePrefixLength: int = 3
    includeYear: bool = True
    invoiceIdSource: str = "sales_request_ref"
    invoiceIdPrefix: str = "INV"
    invoiceIdPadLength: int = 4

    model_config = {
        "extra": "forbid",
    }


class PaymentReferenceRule(BaseModel):
    customerNamePrefixLength: int = 5
    crmSourceIdField: str = "crm_source_system_id"
    fallbackSourceIdField: str = "sales_request_ref"
    useInvoiceTotalWithoutDecimals: bool = True

    model_config = {
        "extra": "forbid",
    }


class TransformRules(BaseModel):
    version: str
    lastUpdated: str
    customerNameMapping: dict[str, str] = Field(default_factory=dict)
    customerCountry: ConditionalStringRule
    salesTaxRate: ConditionalStringRule
    termsAndConditions: ConditionalStringRule
    paymentTerms: ConditionalStringRule
    paymentMethod: ConditionalStringRule
    deliveryDays: ConditionalIntRule
    customerReference: CustomerReferenceRule = Field(default_factory=CustomerReferenceRule)
    paymentReference: PaymentReferenceRule = Field(default_factory=PaymentReferenceRule)
    notificationEmail: str | None = None

    @field_validator("notificationEmail")
    @classmethod
    def validate_notification_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        email = value.strip()
        if not email:
            return None
        if "," in email or ";" in email:
            raise ValueError("notificationEmail must be a single email address")
        if not re.fullmatch(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            raise ValueError("notificationEmail must be a valid email address")
        return email

    model_config = {
        # Allow arbitrary top-level rule names so users can create new rules dynamically.
        "extra": "allow",
    }


class RuleTypeUpdate(BaseModel):
    data: dict
