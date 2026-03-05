from __future__ import annotations

import json
import re
from typing import Any

from .rules_ai_service import copilot_assist, explain_rules_for_situation
from .rules_service import get_rule_type, load_rules_dict

HELP_TEXT = (
    "Hello. I can help you create, update, explain, list, and delete transformation rules.\n\n"
    "Try prompts like:\n"
    "1. Add a sales tax rule for ACME set to 10%\n"
    "2. Show me all available rules\n"
    "3. Explain which rules apply for Sony Entertainment\n"
    "4. Update payment terms for ABC Trading to 21 Days\n"
    "5. Delete the rule for customer Red Internet"
)

GREETING_PATTERN = re.compile(
    r"^\s*(hi|hello|hey|yo|good morning|good afternoon|good evening)\b[!. ]*$",
    re.IGNORECASE,
)
HELP_PATTERN = re.compile(
    r"\b(help|how do i use|what can you do|guide me|how can you help)\b",
    re.IGNORECASE,
)
LIST_ALL_PATTERN = re.compile(
    r"\b(list|show|display|get)\b.*\b(all|available)?\s*rules\b|\bwhat rules\b|\bwhat rule types\b",
    re.IGNORECASE,
)
EXPLAIN_PATTERN = re.compile(
    r"\b(explain|which rules apply|what applies|what happens for|summarize rules for)\b",
    re.IGNORECASE,
)
MUTATION_PATTERN = re.compile(
    r"\b(add|create|update|change|set|delete|remove)\b",
    re.IGNORECASE,
)


def _normalize_messages(messages: list[dict[str, str]] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in messages or []:
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized[-20:]


def _extract_latest_user_message(messages: list[dict[str, str]]) -> str:
    for item in reversed(messages):
        if item["role"] == "user":
            return item["content"]
    return ""


def _extract_known_rule_type(text: str) -> str | None:
    rules = load_rules_dict()
    for rule_type in rules.keys():
        if rule_type in {"version", "lastUpdated"}:
            continue
        if rule_type.lower() in text.lower():
            return rule_type
    return None


def _format_rule_types_summary() -> str:
    rules = load_rules_dict()
    items = [key for key in rules.keys() if key not in {"version", "lastUpdated"}]
    if not items:
        return "No rule types are available."
    lines = [f"{index}. {item}" for index, item in enumerate(items, start=1)]
    return "Available rule types:\n" + "\n".join(lines)


def process_chat_message(message: str) -> dict[str, Any]:
    text = message.strip()
    if not text:
        raise ValueError("Message is required")
    return process_chat_messages([{"role": "user", "content": text}])


def process_chat_messages(messages: list[dict[str, str]]) -> dict[str, Any]:
    normalized_messages = _normalize_messages(messages)
    if not normalized_messages:
        raise ValueError("Message is required")

    latest_user_message = _extract_latest_user_message(normalized_messages).strip()
    if not latest_user_message:
        raise ValueError("Message is required")

    if GREETING_PATTERN.match(latest_user_message):
        return {"status": "success", "message": "Hello. How can I help you with your transformation rules today?"}

    if HELP_PATTERN.search(latest_user_message):
        return {"status": "success", "message": HELP_TEXT}

    if LIST_ALL_PATTERN.search(latest_user_message):
        return {"status": "success", "message": _format_rule_types_summary()}

    rule_type = _extract_known_rule_type(latest_user_message)
    if rule_type and re.search(r"\b(show|view|get|display)\b", latest_user_message, re.IGNORECASE):
        return {
            "status": "success",
            "message": f"{rule_type}:\n{json.dumps(get_rule_type(rule_type), indent=2, ensure_ascii=False)}",
        }

    if EXPLAIN_PATTERN.search(latest_user_message):
        explanation = explain_rules_for_situation(latest_user_message)
        return {
            "status": "success",
            "message": _format_explain_response(explanation),
        }

    copilot_preview = copilot_assist(normalized_messages, apply=False)
    if copilot_preview.get("mode") == "proposal" and MUTATION_PATTERN.search(latest_user_message):
        applied = copilot_assist(normalized_messages, apply=True)
        return {
            "status": "success",
            "message": _format_copilot_response(applied),
            "payload": applied,
        }

    return {
        "status": "success",
        "message": _format_copilot_response(copilot_preview),
        "payload": copilot_preview,
    }


def format_chat_response(result: dict[str, Any]) -> str:
    message = str(result.get("message", "")).strip()
    if message:
        return message

    payload = result.get("payload")
    if isinstance(payload, dict):
        if "reply" in payload:
            return _format_copilot_response(payload)
        if "summary" in payload and "applicable_rules" in payload:
            return _format_explain_response(payload)

    status = str(result.get("status", "")).strip()
    if status == "error":
        return "I could not process that request."

    return "Request processed."


def _format_copilot_response(payload: dict[str, Any]) -> str:
    reply = str(payload.get("reply", "")).strip() or "I reviewed your request."
    questions_raw = payload.get("questions", [])
    questions = [str(item).strip() for item in questions_raw if str(item).strip()] if isinstance(questions_raw, list) else []
    if not questions:
        return reply

    lines = [reply, "", "Follow-up Questions"]
    for index, question in enumerate(questions, start=1):
        lines.append(f"{index}. {question}")
    return "\n".join(lines)


def _format_explain_response(payload: dict[str, Any]) -> str:
    summary = str(payload.get("summary", "")).strip() or "Rules explanation generated."
    applicable = payload.get("applicable_rules", [])
    if not isinstance(applicable, list) or not applicable:
        return summary

    lines = [summary, "", "Applicable Rules"]
    for index, item in enumerate(applicable, start=1):
        if not isinstance(item, dict):
            continue
        rule_type = str(item.get("rule_type", "rule")).strip()
        match_type = str(item.get("match_type", "")).strip()
        matched_key = item.get("matched_key")
        resolved_value = item.get("resolved_value")
        reason = str(item.get("reason", "")).strip()
        key_part = f" for {matched_key}" if matched_key else ""
        lines.append(f"{index}. {rule_type}{key_part} -> {resolved_value!r} ({match_type})")
        if reason:
            lines.append(f"   {reason}")
    return "\n".join(lines)
