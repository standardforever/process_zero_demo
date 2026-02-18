from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..services.rules_service import RuleNotFoundError, get_rule_type, load_rules, save_rules, update_rule_type

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("")
def get_rules() -> dict[str, Any]:
    return load_rules().model_dump(by_alias=True)


@router.put("")
async def put_rules(request: Request) -> dict[str, Any]:
    payload = await _read_json_object(request)
    try:
        updated = save_rules(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid rules payload: {exc}") from exc
    return updated.model_dump(by_alias=True)


@router.get("/{rule_type}")
def get_single_rule(rule_type: str) -> dict[str, Any]:
    try:
        data = get_rule_type(rule_type)
    except RuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"type": rule_type, "data": data}


@router.put("/{rule_type}")
async def put_single_rule(rule_type: str, request: Request) -> dict[str, Any]:
    payload = await _read_json_object(request)
    try:
        updated = update_rule_type(rule_type, payload)
    except RuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid rule payload: {exc}") from exc

    return {"type": rule_type, "data": updated.model_dump(by_alias=True).get(rule_type)}


async def _read_json_object(request: Request) -> dict[str, Any]:
    body = await request.body()
    if not body:
        return {}

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc.msg}") from exc

    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Rule payload must be a JSON object")

    return payload
