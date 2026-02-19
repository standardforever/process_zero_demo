from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models.schema_store import ERPSchemaColumn, PostTransformationAction, SchemaStore, SchemaStoreMetadata

SCHEMA_STORE_FILE = Path(__file__).resolve().parents[1] / "data" / "schema_store.json"


class SchemaStoreValidationError(ValueError):
    pass


class SchemaStoreNotFoundError(ValueError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_schema_store() -> SchemaStore:
    return SchemaStore(
        erp_schema={},
        post_transformation_actions={
            "log_note": PostTransformationAction(
                enabled=True,
                action="add_note",
                target="invoice_record",
                section="Log Notes",
                content="AI Agent: This sales invoice record has been created through an autonomous process.",
            ),
            "scheduled_activity": PostTransformationAction(
                enabled=True,
                action="create_activity",
                activity_type="To Do",
                subject="Invoice Review: Please check and supervise this AI-generated invoice.",
                button_sequence=["Activity", "Scheduled Activity", "To Do", "Save"],
            ),
        },
        metadata=SchemaStoreMetadata(
            crm_columns=[],
            notification_emails=[],
            erp_system="Odoo",
            version="1.0.0",
            last_updated=_utc_now_iso(),
        ),
    )


def _normalize_column_name(name: str) -> str:
    cleaned = str(name).strip()
    if not cleaned:
        raise SchemaStoreValidationError("Column name cannot be empty")

    # Convert PascalCase/camelCase to snake_case first.
    with_word_boundaries = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", cleaned)
    # Replace spaces and symbols with underscores.
    snake = re.sub(r"[^A-Za-z0-9]+", "_", with_word_boundaries)
    snake = re.sub(r"_+", "_", snake).strip("_").lower()

    if not snake:
        raise SchemaStoreValidationError("Column name cannot be empty")
    return snake


def _normalize_email(email: str) -> str:
    cleaned = str(email).strip().lower()
    if not cleaned:
        raise SchemaStoreValidationError("Email cannot be empty")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", cleaned):
        raise SchemaStoreValidationError(f"Invalid email address: {cleaned}")
    return cleaned


def _normalize_store_for_save(store: SchemaStore) -> SchemaStore:
    normalized_erp_schema: dict[str, ERPSchemaColumn] = {}
    for key, value in store.erp_schema.items():
        normalized_erp_schema[_normalize_column_name(key)] = value
    store.erp_schema = normalized_erp_schema

    normalized_crm_columns: list[str] = []
    seen: set[str] = set()
    for item in store.metadata.crm_columns:
        normalized = _normalize_column_name(item)
        if normalized not in seen:
            seen.add(normalized)
            normalized_crm_columns.append(normalized)
    store.metadata.crm_columns = normalized_crm_columns

    normalized_notification_emails: list[str] = []
    seen_emails: set[str] = set()
    for item in store.metadata.notification_emails:
        normalized_email = _normalize_email(item)
        if normalized_email not in seen_emails:
            seen_emails.add(normalized_email)
            normalized_notification_emails.append(normalized_email)

    # Current product rule: keep exactly one notification email max.
    store.metadata.notification_emails = normalized_notification_emails[:1]
    return store


def _ensure_store_file() -> None:
    if SCHEMA_STORE_FILE.exists():
        return

    SCHEMA_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    default_store = _default_schema_store()
    with SCHEMA_STORE_FILE.open("w", encoding="utf-8") as file:
        json.dump(default_store.model_dump(), file, indent=2)
        file.write("\n")


def load_schema_store() -> SchemaStore:
    _ensure_store_file()

    with SCHEMA_STORE_FILE.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    store = SchemaStore(**payload)
    store_dump_before = store.model_dump()

    normalized = _normalize_store_for_save(store.model_copy(deep=True))
    store_dump_after = normalized.model_dump()

    # One-time migration path: if legacy payload has non-snake-case keys, rewrite on load.
    if store_dump_after != store_dump_before:
        normalized.metadata.last_updated = _utc_now_iso()
        with SCHEMA_STORE_FILE.open("w", encoding="utf-8") as file:
            json.dump(normalized.model_dump(), file, indent=2)
            file.write("\n")
        return normalized

    if not normalized.metadata.last_updated:
        normalized.metadata.last_updated = _utc_now_iso()
    return normalized


def save_schema_store(payload: dict[str, Any] | SchemaStore) -> SchemaStore:
    if isinstance(payload, SchemaStore):
        candidate = payload
    else:
        candidate = SchemaStore(**payload)

    candidate = _normalize_store_for_save(candidate)
    candidate.metadata.last_updated = _utc_now_iso()
    with SCHEMA_STORE_FILE.open("w", encoding="utf-8") as file:
        json.dump(candidate.model_dump(), file, indent=2)
        file.write("\n")

    return candidate


def get_schema_store_status(store: SchemaStore | None = None) -> dict[str, Any]:
    schema_store = store or load_schema_store()
    erp_count = len(schema_store.erp_schema)
    crm_count = len([item for item in schema_store.metadata.crm_columns if isinstance(item, str) and item.strip()])
    email_count = len(
        [item for item in schema_store.metadata.notification_emails if isinstance(item, str) and item.strip()]
    )
    return {
        "erp_columns_count": erp_count,
        "crm_columns_count": crm_count,
        "notification_emails_count": email_count,
        "has_erp_columns": erp_count > 0,
        "has_crm_columns": crm_count > 0,
        "has_notification_emails": email_count > 0,
        "can_use_chat": erp_count > 0 and crm_count > 0 and email_count > 0,
    }


def upsert_erp_schema_column(column_name: str, data: dict[str, Any] | ERPSchemaColumn) -> SchemaStore:
    name = _normalize_column_name(column_name)
    store = load_schema_store()
    column = data if isinstance(data, ERPSchemaColumn) else ERPSchemaColumn(**data)
    store.erp_schema[name] = column
    return save_schema_store(store)


def delete_erp_schema_column(column_name: str) -> SchemaStore:
    name = _normalize_column_name(column_name)
    store = load_schema_store()
    if name not in store.erp_schema:
        raise SchemaStoreNotFoundError(f"ERP column not found: {name}")
    del store.erp_schema[name]
    return save_schema_store(store)


def add_crm_column(column_name: str) -> SchemaStore:
    name = _normalize_column_name(column_name)
    store = load_schema_store()
    existing = {item.strip().lower() for item in store.metadata.crm_columns}
    if name.lower() not in existing:
        store.metadata.crm_columns.append(name)
    return save_schema_store(store)


def rename_crm_column(column_name: str, new_name: str) -> SchemaStore:
    old = _normalize_column_name(column_name)
    new = _normalize_column_name(new_name)
    store = load_schema_store()

    for index, item in enumerate(store.metadata.crm_columns):
        if item == old:
            store.metadata.crm_columns[index] = new
            return save_schema_store(store)

    raise SchemaStoreNotFoundError(f"CRM column not found: {old}")


def delete_crm_column(column_name: str) -> SchemaStore:
    name = _normalize_column_name(column_name)
    store = load_schema_store()
    try:
        store.metadata.crm_columns.remove(name)
    except ValueError as exc:
        raise SchemaStoreNotFoundError(f"CRM column not found: {name}") from exc

    return save_schema_store(store)


def add_notification_email(email: str) -> SchemaStore:
    normalized = _normalize_email(email)
    store = load_schema_store()
    existing = [item.strip().lower() for item in store.metadata.notification_emails if str(item).strip()]
    if existing and existing[0] != normalized:
        raise SchemaStoreValidationError(
            "Only one notification email is allowed. Edit or delete the existing email first."
        )
    store.metadata.notification_emails = [normalized]
    return save_schema_store(store)


def rename_notification_email(current_email: str, new_email: str) -> SchemaStore:
    current = _normalize_email(current_email)
    new = _normalize_email(new_email)
    store = load_schema_store()

    for index, item in enumerate(store.metadata.notification_emails):
        if item.strip().lower() == current:
            store.metadata.notification_emails[index] = new
            return save_schema_store(store)

    raise SchemaStoreNotFoundError(f"Notification email not found: {current}")


def delete_notification_email(email: str) -> SchemaStore:
    normalized = _normalize_email(email)
    store = load_schema_store()

    for index, item in enumerate(store.metadata.notification_emails):
        if item.strip().lower() == normalized:
            del store.metadata.notification_emails[index]
            return save_schema_store(store)

    raise SchemaStoreNotFoundError(f"Notification email not found: {normalized}")
