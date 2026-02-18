from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..transformer import create_llm_manager

RULES_FILE = Path(__file__).resolve().parents[1] / "data" / "schema_store.json"

_manager = None


def _get_manager():
    global _manager
    if _manager is None:
        _manager = create_llm_manager(rules_file=str(RULES_FILE))
    return _manager


def process_chat_message(message: str) -> dict[str, Any]:
    text = message.strip()
    if not text:
        raise ValueError("Message is required")

    manager = _get_manager()
    return manager.process_request(text)


def format_chat_response(result: dict[str, Any]) -> str:
    status = str(result.get("status", "")).strip()
    message = str(result.get("message", "")).strip()

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
                    label = f"{erp_column}.{rule_name}" if erp_column and rule_name else rule_name or erp_column or "rule"
                    lines.append(f"{index}. {label} - {prompt}")
                return "Created rules:\n" + "\n".join(lines)
            return "No created rules found."

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
            erp_column = result.get("erp_column")
            return f"No created rules found for '{erp_column}'."

        if "summary" in result and isinstance(result.get("summary"), dict):
            return f"Summary:\n{json.dumps(result.get('summary'), indent=2, ensure_ascii=False)}"

        if "rule" in result and isinstance(result.get("rule"), dict):
            rule_name = result.get("rule_name", "rule")
            return f"{rule_name}:\n{json.dumps(result.get('rule'), indent=2, ensure_ascii=False)}"

        if "results" in result and isinstance(result.get("results"), dict):
            return f"Search results:\n{json.dumps(result.get('results'), indent=2, ensure_ascii=False)}"

        return json.dumps(result, indent=2, ensure_ascii=False)

    return "Request processed."


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
