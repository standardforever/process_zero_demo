from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schema_store_service import get_schema_store_status
from ..transformer import create_llm_manager

RULES_FILE = Path(__file__).resolve().parents[1] / "data" / "schema_store.json"
SCHEMA_SETUP_PATH = "/transformer/schema"

_manager = None


def _get_manager():
    global _manager
    if _manager is None:
        _manager = create_llm_manager(rules_file=str(RULES_FILE))
    return _manager


def _is_greeting(text: str) -> bool:
    normalized = re.sub(r"[^\w\s]", "", text.lower()).strip()
    return normalized in {
        "hi",
        "hello",
        "hey",
        "yo",
        "good morning",
        "good afternoon",
        "good evening",
    }


def _is_help_request(text: str) -> bool:
    text_lc = text.lower()
    help_patterns = [
        r"\bhow\b.*\bcreate\b.*\brule\b",
        r"\bcreate\b.*\bnew\b.*\brule\b",
        r"\bguide\b.*\brule\b",
        r"\bhelp\b",
        r"\bwhat can you do\b",
    ]
    return any(re.search(pattern, text_lc) for pattern in help_patterns)


def _is_continue_message(text: str) -> bool:
    normalized = re.sub(r"[^\w\s]", "", text.lower()).strip()
    return normalized in {"continue", "im done", "i am done", "done", "lets continue"}


def _schema_required_response() -> dict[str, Any]:
    status = get_schema_store_status()
    missing: list[str] = []
    if not status.get("has_erp_columns"):
        missing.append("at least one ERP column")
    if not status.get("has_crm_columns"):
        missing.append("at least one CRM column")
    if not status.get("has_notification_emails"):
        missing.append("one notification email")

    missing_text = ", ".join(missing) if missing else "required schema setup items"
    message = (
        "Schema setup is not complete yet. Please add "
        f"{missing_text} first.\n"
        f"Open Schema Setup: {SCHEMA_SETUP_PATH}\n"
        "When done, send: Continue"
    )
    return {
        "status": "schema_required",
        "message": message,
        "schema_status": status,
        "schema_url": SCHEMA_SETUP_PATH,
    }


def _help_message() -> str:
    return (
        "Hello. I can help you create, update, delete, and list transformation rules.\n"
        "Before rule operations, ensure schema setup is complete:\n"
        f"- Add ERP column(s)\n- Add CRM column(s)\n- Add one notification email\n"
        f"Open Schema Setup: {SCHEMA_SETUP_PATH}\n\n"
        "Example:\n"
        "Add a rule in sales_tax_rate: if customer_name equals \"ACME\", set value to \"10%\""
    )


def process_chat_message(message: str) -> dict[str, Any]:
    text = message.strip()
    if not text:
        raise ValueError("Message is required")

    if _is_greeting(text):
        return {
            "status": "assistant",
            "message": "Hello. How can I help you with your rule mappings today?",
        }

    if _is_help_request(text):
        return {
            "status": "assistant",
            "message": _help_message(),
        }

    status = get_schema_store_status()
    if not status.get("can_use_chat"):
        return _schema_required_response()

    if _is_continue_message(text):
        return {
            "status": "assistant",
            "message": (
                "Great. Schema is ready. Share your rule instruction and I will apply it.\n"
                "Example: Add a rule in sales_tax_rate: if customer_name equals \"ACME\", set value to \"10%\""
            ),
        }

    manager = _get_manager()
    return manager.process_request(text)


def format_chat_response(result: dict[str, Any]) -> str:
    status = str(result.get("status", "")).strip()
    message = str(result.get("message", "")).strip()

    if status in {"assistant", "schema_required"}:
        return message or "Request processed."

    if status == "error":
        return message or "I could not process that request."

    if status == "not_allowed":
        return message or "That action is not allowed."

    if message:
        return message

    if status == "success":
        if "rules_by_column" in result:
            created_rule_prompts = result.get("created_rule_prompts") or []
            if isinstance(created_rule_prompts, list) and created_rule_prompts:
                lines: list[str] = []
                for index, item in enumerate(created_rule_prompts, start=1):
                    erp_column = str(item.get("erp_column", "")).strip()
                    rule_name = str(item.get("rule_name", "")).strip()
                    prompt = str(item.get("prompt", "")).strip()
                    label = (
                        f"{erp_column}.{rule_name}"
                        if erp_column and rule_name
                        else rule_name or erp_column or "rule"
                    )
                    lines.append(f"{index}. {label} - {prompt}")
                return "Created rules:\n" + "\n".join(lines)
            return _format_rules_by_column(result)

        if "rules" in result and "erp_column" in result:
            created_rule_prompts = result.get("created_rule_prompts") or []
            if isinstance(created_rule_prompts, list) and created_rule_prompts:
                lines = []
                for index, item in enumerate(created_rule_prompts, start=1):
                    rule_name = str(item.get("rule_name", "")).strip() or "rule"
                    prompt = str(item.get("prompt", "")).strip()
                    lines.append(f"{index}. {rule_name} - {prompt}")
                erp_column = str(result.get("erp_column", "")).strip()
                return f"Created rules for '{erp_column}':\n" + "\n".join(lines)
            return _format_rules_for_column(result)

        if "summary" in result and isinstance(result.get("summary"), dict):
            return f"Summary:\n{json.dumps(result.get('summary'), indent=2, ensure_ascii=False)}"

        if "rule" in result and isinstance(result.get("rule"), dict):
            rule_name = result.get("rule_name", "rule")
            return f"{rule_name}:\n{json.dumps(result.get('rule'), indent=2, ensure_ascii=False)}"

        if "results" in result and isinstance(result.get("results"), dict):
            return f"Search results:\n{json.dumps(result.get('results'), indent=2, ensure_ascii=False)}"

        return json.dumps(result, indent=2, ensure_ascii=False)

    return "Request processed."


def _format_rules_by_column(result: dict[str, Any]) -> str:
    rules_by_column = result.get("rules_by_column")
    if not isinstance(rules_by_column, dict) or not rules_by_column:
        return "No rules found."

    lines: list[str] = []
    counter = 1
    for column_name, rules in sorted(rules_by_column.items()):
        if not isinstance(rules, dict):
            continue
        for rule_name, rule_data in sorted(rules.items()):
            lines.append(f"{counter}. {column_name}.{rule_name} - {_summarize_rule(rule_data)}")
            counter += 1

    return "\n".join(lines) if lines else "No rules found."


def _format_rules_for_column(result: dict[str, Any]) -> str:
    erp_column = str(result.get("erp_column", "")).strip() or "column"
    rules = result.get("rules")
    if not isinstance(rules, dict) or not rules:
        return f"No rules found for '{erp_column}'."

    lines: list[str] = []
    for index, (rule_name, rule_data) in enumerate(sorted(rules.items()), start=1):
        lines.append(f"{index}. {erp_column}.{rule_name} - {_summarize_rule(rule_data)}")
    return "\n".join(lines)


def _summarize_rule(rule_data: Any) -> str:
    if not isinstance(rule_data, dict):
        return "rule configured"

    conditions = rule_data.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        return "rule configured"

    first = conditions[0] if isinstance(conditions[0], dict) else {}
    crm_column = str(first.get("crm_column", "")).strip() or "field"
    operator = str(first.get("operator", "")).strip() or "matches"
    value = first.get("value")
    transformation = first.get("transformation") if isinstance(first.get("transformation"), dict) else {}
    action = str(transformation.get("action", "")).strip() or "transform"
    target_value = transformation.get("value")
    return f"if {crm_column} {operator} {value!r} -> {action} {target_value!r}"
