from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.rules_ai_service import copilot_assist, explain_rules_for_situation, preview_or_apply_rules_update
from ..services.schema_store_service import get_schema_store_status

router = APIRouter(prefix="/rules/ai", tags=["rules-ai"])


class RulesAIUpdateRequest(BaseModel):
    instruction: str
    apply: bool = False


class RulesAIExplainRequest(BaseModel):
    situation: str


class RulesAICopilotMessage(BaseModel):
    role: str
    content: str


class RulesAICopilotRequest(BaseModel):
    messages: list[RulesAICopilotMessage] = Field(default_factory=list)
    apply: bool = False
    include_records_limit: int = 40


def _ensure_chat_access() -> None:
    status = get_schema_store_status()
    if not status["can_use_chat"]:
        raise HTTPException(
            status_code=403,
            detail="AI chat is locked. Add at least one ERP column and one CRM column in schema setup first.",
        )


@router.post("/update")
def ai_update_rules(payload: RulesAIUpdateRequest) -> dict[str, Any]:
    _ensure_chat_access()
    try:
        return preview_or_apply_rules_update(payload.instruction, apply=payload.apply)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/explain")
def ai_explain_rules(payload: RulesAIExplainRequest) -> dict[str, Any]:
    _ensure_chat_access()
    try:
        return explain_rules_for_situation(payload.situation)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/copilot")
def ai_copilot(payload: RulesAICopilotRequest) -> dict[str, Any]:
    _ensure_chat_access()
    try:
        message_payload = [{"role": item.role, "content": item.content} for item in payload.messages]
        return copilot_assist(
            messages=message_payload,
            apply=payload.apply,
            include_records_limit=payload.include_records_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
