from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models.crm_record import CRMRecord
from ..services.data_service import get_record_by_sales_ref, get_records
from ..services.transform_service import get_saved_output, save_batch_output, transform_batch, transform_record

router = APIRouter(prefix="/transform", tags=["transform"])


class PreviewTransformRequest(BaseModel):
    sales_request_ref: str | None = None
    record: CRMRecord | None = None


class BatchTransformRequest(BaseModel):
    sales_request_refs: list[str] | None = None


@router.post("/preview")
def preview_transform(payload: PreviewTransformRequest) -> dict:
    if payload.record is not None:
        invoice = transform_record(payload.record)
        return {"original": payload.record.model_dump(), "transformed": invoice.model_dump()}

    if payload.sales_request_ref:
        record = get_record_by_sales_ref(payload.sales_request_ref)
        if record is None:
            raise HTTPException(status_code=404, detail="Sales request ref not found")

        invoice = transform_record(record)
        return {"original": record.model_dump(), "transformed": invoice.model_dump()}

    raise HTTPException(status_code=400, detail="Provide either record or sales_request_ref")


@router.post("/batch")
def batch_transform(payload: BatchTransformRequest) -> dict:
    refs = payload.sales_request_refs or []

    if refs:
        records = []
        missing = []
        for ref in refs:
            record = get_record_by_sales_ref(ref)
            if record is None:
                missing.append(ref)
            else:
                records.append(record)

        if not records:
            raise HTTPException(status_code=404, detail="No provided sales refs were found")
    else:
        records = get_records()
        missing = []

    invoices = transform_batch(records)
    output = save_batch_output(invoices)

    return {
        "count": output["count"],
        "missing_sales_request_refs": missing,
        "invoices": output["invoices"],
    }


@router.get("/output")
def transform_output() -> dict:
    return get_saved_output()
