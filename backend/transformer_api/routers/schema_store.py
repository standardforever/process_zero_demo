from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..models.schema_store import ERPSchemaColumn, SchemaStore
from ..services.schema_store_service import (
    SchemaStoreNotFoundError,
    SchemaStoreValidationError,
    add_crm_column,
    add_notification_email,
    delete_crm_column,
    delete_erp_schema_column,
    delete_notification_email,
    get_schema_store_status,
    load_schema_store,
    rename_notification_email,
    rename_crm_column,
    save_schema_store,
    upsert_erp_schema_column,
)

router = APIRouter(prefix="/schema-store", tags=["schema-store"])


class CRMColumnRequest(BaseModel):
    column_name: str = Field(min_length=1)


class CRMColumnRenameRequest(BaseModel):
    new_name: str = Field(min_length=1)


class NotificationEmailRequest(BaseModel):
    email: str = Field(min_length=3)


class NotificationEmailRenameRequest(BaseModel):
    new_email: str = Field(min_length=3)


@router.get("")
def get_schema_store() -> dict[str, Any]:
    return load_schema_store().model_dump()


@router.get("/status")
def get_schema_status() -> dict[str, Any]:
    return get_schema_store_status()


@router.put("")
def put_schema_store(payload: SchemaStore) -> dict[str, Any]:
    try:
        saved = save_schema_store(payload)
        return saved.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid schema store payload: {exc}") from exc


@router.put("/erp/{column_name}")
def put_erp_column(column_name: str, payload: ERPSchemaColumn) -> dict[str, Any]:
    try:
        return upsert_erp_schema_column(column_name, payload).model_dump()
    except SchemaStoreValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid ERP schema payload: {exc}") from exc


@router.delete("/erp/{column_name}")
def remove_erp_column(column_name: str) -> dict[str, Any]:
    try:
        return delete_erp_schema_column(column_name).model_dump()
    except SchemaStoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SchemaStoreValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/crm")
def create_crm_column(payload: CRMColumnRequest) -> dict[str, Any]:
    try:
        return add_crm_column(payload.column_name).model_dump()
    except SchemaStoreValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/crm/{column_name}")
def put_crm_column(column_name: str, payload: CRMColumnRenameRequest) -> dict[str, Any]:
    try:
        return rename_crm_column(column_name, payload.new_name).model_dump()
    except SchemaStoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SchemaStoreValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/crm/{column_name}")
def remove_crm_column(column_name: str) -> dict[str, Any]:
    try:
        return delete_crm_column(column_name).model_dump()
    except SchemaStoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SchemaStoreValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/notifications/email")
def create_notification_email(payload: NotificationEmailRequest) -> dict[str, Any]:
    try:
        return add_notification_email(payload.email).model_dump()
    except SchemaStoreValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/notifications/email/{email}")
def put_notification_email(email: str, payload: NotificationEmailRenameRequest) -> dict[str, Any]:
    try:
        return rename_notification_email(email, payload.new_email).model_dump()
    except SchemaStoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SchemaStoreValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/notifications/email/{email}")
def remove_notification_email(email: str) -> dict[str, Any]:
    try:
        return delete_notification_email(email).model_dump()
    except SchemaStoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SchemaStoreValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
