from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.chat_service import format_chat_response, process_chat_message
from ..services.schema_store_service import get_schema_store_status

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatStreamRequest(BaseModel):
    message: str


def _sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chunk_text(text: str, size: int = 24) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def _ensure_chat_access() -> None:
    status = get_schema_store_status()
    if not status["can_use_chat"]:
        raise HTTPException(
            status_code=403,
            detail="AI chat is locked. Add at least one ERP column and one CRM column in schema setup first.",
        )


@router.post("/stream")
async def stream_chat(payload: ChatStreamRequest) -> StreamingResponse:
    _ensure_chat_access()
    text = payload.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is required")

    async def event_stream() -> AsyncIterator[str]:
        yield _sse_event({"type": "start"})
        try:
            result = await asyncio.to_thread(process_chat_message, text)
            response_text = format_chat_response(result)
            for chunk in _chunk_text(response_text):
                yield _sse_event({"type": "chunk", "content": chunk})
                await asyncio.sleep(0.01)
            yield _sse_event({"type": "done", "result": result})
        except Exception as exc:
            yield _sse_event({"type": "error", "error": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
