from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, model_validator


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ERPSchemaColumn(BaseModel):
    default_value: Any = None
    data_type: str = "string"
    description: str = ""
    required: bool = False
    rules: dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "extra": "allow",
    }


class PostTransformationAction(BaseModel):
    enabled: bool = True
    action: str
    target: str | None = None
    section: str | None = None
    content: str | None = None
    activity_type: str | None = None
    subject: str | None = None
    button_sequence: list[str] = Field(default_factory=list)

    model_config = {
        "extra": "allow",
    }


class SchemaStoreMetadata(BaseModel):
    crm_columns: list[str] = Field(default_factory=list)
    notification_email: str = ""
    erp_system: str = "Odoo"
    version: str = "1.0.0"
    last_updated: str = Field(default_factory=_utc_now_iso)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_notification_emails(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        canonical = str(data.get("notification_email", "")).strip()
        if not canonical:
            legacy = data.get("notification_emails")
            if isinstance(legacy, list):
                for item in legacy:
                    candidate = str(item).strip()
                    if candidate:
                        canonical = candidate
                        break
            elif isinstance(legacy, str):
                canonical = legacy.strip()
            if canonical:
                data["notification_email"] = canonical

        data.pop("notification_emails", None)
        return data

    model_config = {
        "extra": "allow",
    }


class SchemaStore(BaseModel):
    erp_schema: dict[str, ERPSchemaColumn] = Field(default_factory=dict)
    post_transformation_actions: dict[str, PostTransformationAction] = Field(default_factory=dict)
    metadata: SchemaStoreMetadata = Field(default_factory=SchemaStoreMetadata)

    model_config = {
        "extra": "forbid",
    }
