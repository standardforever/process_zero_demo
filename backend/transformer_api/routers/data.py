from __future__ import annotations

from fastapi import APIRouter, Query

from ..services.data_service import get_paginated_records, get_stats, get_unique_customers

router = APIRouter(prefix="/data", tags=["data"])


@router.get("")
def list_data(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=200),
    search: str | None = Query(default=None),
) -> dict:
    return get_paginated_records(page=page, limit=limit, search=search)


@router.get("/customers")
def list_customers() -> dict[str, list[str]]:
    return {"customers": get_unique_customers()}


@router.get("/stats")
def data_stats() -> dict:
    return get_stats()
