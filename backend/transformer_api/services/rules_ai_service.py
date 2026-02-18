from __future__ import annotations

import json
import os
import re
from typing import Any

from ..models.rules import TransformRules
from .rules_service import load_rules, save_rules

UPDATE_SYSTEM_PROMPT = """
You are an expert rules editor for a CRM-to-ERP transformer.

You receive:
1) A natural-language instruction.
2) The current rules JSON object.

Your task:
- Produce a minimally changed, valid full rules object.
- Keep fields not mentioned by the user unchanged.
- Allow creating new top-level rule names when explicitly requested by the user.
- For new mapping-style rules, use this shape:
  { "_default": <value>, "conditions": { "<key>": <value> } }
- Keep `version` and `lastUpdated` valid strings.

Return JSON ONLY with this exact shape:
{
  "summary": "short plain-English summary of what changed",
  "updated_rules": { ... full rules object ... }
}
""".strip()

EXPLAIN_SYSTEM_PROMPT = """
You are an expert assistant for a CRM-to-ERP transformer rules engine.

You receive:
1) A user situation in natural language.
2) The current rules JSON.

Task:
- Explain which rules are relevant for this situation.
- If the situation implies a customer, include the condition match and resolved value.
- If no specific condition matches, explain that defaults apply.

Return JSON ONLY:
{
  "summary": "plain-English explanation",
  "applicable_rules": [
    {
      "rule_type": "paymentTerms",
      "match_type": "condition|default|mapping|config",
      "matched_key": "customer name or null",
      "resolved_value": "final value",
      "reason": "short reason"
    }
  ]
}
""".strip()

COPILOT_SYSTEM_PROMPT = """
You are a Rules Copilot for a CRM-to-ERP transformer.

You receive:
1) Conversation messages from the user.
2) Current rules JSON.

Objectives:
- Help users design rule mappings in valid schema shape.
- If user asks to create/update rules but details are missing, ask focused follow-up questions.
- For conditional rule mapping workflows, ask for:
  1) default value
  2) customer-specific mappings
  3) confirmation to apply
- When enough details are available, return a full `updated_rules` object.
- You may add a new top-level rule field when user explicitly asks to create one.
- For new mapping-style rules, use:
  { "_default": <value>, "conditions": { "<key>": <value> } }
- Keep the rules JSON schema valid.
- Keep changes minimal.

Return JSON ONLY:
{
  "mode": "answer|clarify|proposal",
  "reply": "assistant response for the UI",
  "questions": ["follow-up question 1", "follow-up question 2"],
  "updated_rules": { ... full rules object ... } | null
}
""".strip()

CONDITIONAL_RULE_TYPES = [
    "customerCountry",
    "salesTaxRate",
    "termsAndConditions",
    "paymentTerms",
    "paymentMethod",
    "deliveryDays",
]

ERP_TOP_LEVEL_FIELDS = [
    "sales_request_ref",
    "invoice_date",
    "sales_person",
    "customer_contact",
    "trading_address",
    "delivery_address",
    "discount_percent",
    "customer_name",
    "country",
    "tax_rate",
    "terms_and_conditions",
    "payment_terms",
    "payment_method",
    "delivery_date",
    "customer_reference",
    "payment_reference",
    "line_items",
    "subtotal",
    "tax_amount",
    "total",
]

ERP_LINE_ITEM_FIELDS = [
    "product_code",
    "description",
    "quantity",
    "unit_price",
    "line_total",
]

def preview_or_apply_rules_update(instruction: str, apply: bool = False) -> dict[str, Any]:
    text = instruction.strip()
    if not text:
        raise ValueError("Instruction is required")

    current_rules = load_rules().model_dump(by_alias=True)
    ai_response = _call_openai_json(
        UPDATE_SYSTEM_PROMPT,
        {
            "instruction": text,
            "current_rules": current_rules,
        },
    )

    summary = str(ai_response.get("summary", "")).strip() or "Rules updated by AI"
    updated_rules_payload = ai_response.get("updated_rules")
    if not isinstance(updated_rules_payload, dict):
        raise ValueError("AI response did not include a valid `updated_rules` object")

    validated = TransformRules(**updated_rules_payload)
    updated_rules = validated.model_dump(by_alias=True)
    changes = _diff_dict(current_rules, updated_rules)

    response: dict[str, Any] = {
        "applied": False,
        "summary": summary,
        "changes": changes,
        "updated_rules": updated_rules,
    }

    if apply:
        saved = save_rules(validated).model_dump(by_alias=True)
        response["applied"] = True
        response["updated_rules"] = saved
        response["changes"] = _diff_dict(current_rules, saved)

    return response


def explain_rules_for_situation(situation: str) -> dict[str, Any]:
    text = situation.strip()
    if not text:
        raise ValueError("Situation is required")

    rules = load_rules().model_dump(by_alias=True)

    try:
        ai_response = _call_openai_json(
            EXPLAIN_SYSTEM_PROMPT,
            {
                "situation": text,
                "rules": rules,
            },
        )
        summary = str(ai_response.get("summary", "")).strip() or "Rules explanation generated"
        applicable = ai_response.get("applicable_rules")
        if not isinstance(applicable, list):
            raise ValueError("AI response did not include a valid `applicable_rules` list")
        return {
            "summary": summary,
            "applicable_rules": applicable,
            "used_ai": True,
        }
    except RuntimeError:
        # Missing API key/package should be explicit for update, but explain has a deterministic fallback.
        return _deterministic_explain(rules, text)
    except Exception:
        return _deterministic_explain(rules, text)


def copilot_assist(
    messages: list[dict[str, str]],
    apply: bool = False,
    include_records_limit: int = 40,
) -> dict[str, Any]:
    normalized_messages = _normalize_messages(messages)
    if not normalized_messages:
        raise ValueError("At least one user message is required")

    # Demo mode: CRM context is intentionally commented out.
    _ = include_records_limit
    current_rules = load_rules().model_dump(by_alias=True)

    try:
        ai_response = _call_openai_json(
            COPILOT_SYSTEM_PROMPT,
            {
                "messages": normalized_messages,
                "rules": current_rules,
            },
        )
        return _build_copilot_response(ai_response, current_rules, apply=apply, used_ai=True)
    except RuntimeError:
        # No configured key/package: return deterministic guidance and CRM answer path.
        return _deterministic_copilot_response(normalized_messages, current_rules, apply=apply)
    except Exception:
        return _deterministic_copilot_response(normalized_messages, current_rules, apply=apply)


def _deterministic_explain(rules: dict[str, Any], situation: str) -> dict[str, Any]:
    situation_lc = situation.lower()
    customers = _collect_known_customers(rules)
    matched_customer = next((name for name in customers if name.lower() in situation_lc), None)

    applicable_rules: list[dict[str, Any]] = []

    if matched_customer:
        mapped = rules.get("customerNameMapping", {}).get(matched_customer, matched_customer)
        applicable_rules.append(
            {
                "rule_type": "customerNameMapping",
                "match_type": "mapping",
                "matched_key": matched_customer,
                "resolved_value": mapped,
                "reason": "Customer mapping resolves CRM name to target ERP customer name.",
            }
        )
        resolved_customer = mapped
    else:
        resolved_customer = None

    for rule_type in CONDITIONAL_RULE_TYPES:
        rule_data = rules.get(rule_type, {})
        default_value = rule_data.get("_default")
        conditions = rule_data.get("conditions", {})

        matched_key = None
        resolved_value = default_value
        match_type = "default"
        reason = "No customer-specific condition found; default applies."

        if resolved_customer and isinstance(conditions, dict) and resolved_customer in conditions:
            matched_key = resolved_customer
            resolved_value = conditions[resolved_customer]
            match_type = "condition"
            reason = "Customer-specific condition matched."

        applicable_rules.append(
            {
                "rule_type": rule_type,
                "match_type": match_type,
                "matched_key": matched_key,
                "resolved_value": resolved_value,
                "reason": reason,
            }
        )

    summary = (
        f"Evaluated rules for customer '{matched_customer}'."
        if matched_customer
        else "No explicit customer detected in the situation; defaults were used."
    )

    return {
        "summary": summary,
        "applicable_rules": applicable_rules,
        "used_ai": False,
    }


def _collect_known_customers(rules: dict[str, Any]) -> list[str]:
    result: set[str] = set()

    mapping = rules.get("customerNameMapping", {})
    if isinstance(mapping, dict):
        for crm_name, erp_name in mapping.items():
            if isinstance(crm_name, str) and crm_name.strip():
                result.add(crm_name.strip())
            if isinstance(erp_name, str) and erp_name.strip():
                result.add(erp_name.strip())

    for rule_type in CONDITIONAL_RULE_TYPES:
        rule_data = rules.get(rule_type, {})
        conditions = rule_data.get("conditions", {})
        if isinstance(conditions, dict):
            for key in conditions:
                if isinstance(key, str) and key.strip():
                    result.add(key.strip())

    return sorted(result)


def _normalize_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in messages[-20:]:
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def _build_copilot_response(
    ai_response: dict[str, Any],
    current_rules: dict[str, Any],
    apply: bool,
    used_ai: bool,
) -> dict[str, Any]:
    mode = str(ai_response.get("mode", "answer")).strip().lower()
    if mode not in {"answer", "clarify", "proposal"}:
        mode = "answer"

    reply = str(ai_response.get("reply", "")).strip() or "I reviewed your request."

    questions_raw = ai_response.get("questions", [])
    questions = []
    if isinstance(questions_raw, list):
        questions = [str(item).strip() for item in questions_raw if str(item).strip()]

    updated_rules_payload = ai_response.get("updated_rules")
    updated_rules: dict[str, Any] | None = None
    changes: list[dict[str, Any]] = []
    applied = False

    if isinstance(updated_rules_payload, dict):
        validated = TransformRules(**updated_rules_payload)
        updated_rules = validated.model_dump(by_alias=True)
        changes = _diff_dict(current_rules, updated_rules)

        if mode != "proposal":
            mode = "proposal"

        if apply:
            saved = save_rules(validated).model_dump(by_alias=True)
            updated_rules = saved
            changes = _diff_dict(current_rules, saved)
            applied = True
            if "applied" not in reply.lower() and "saved" not in reply.lower():
                reply = f"{reply}\n\nChanges have been applied and saved."
        else:
            if changes:
                if "apply" not in reply.lower():
                    reply = f"{reply}\n\nA proposal is ready. Click 'Apply Copilot Proposal' to save it."
            else:
                if "no changes" not in reply.lower():
                    reply = f"{reply}\n\nNo actual rule changes were detected."
    else:
        if mode == "answer" and any(word in reply.lower() for word in ("created", "updated", "added", "saved")):
            reply = (
                f"{reply}\n\nNo valid rule proposal was generated, so nothing was changed. "
                "Provide more details or ask for a proposal explicitly."
            )

    return {
        "mode": mode,
        "reply": reply,
        "questions": questions,
        "changes": changes,
        "updated_rules": updated_rules,
        "applied": applied,
        "used_ai": used_ai,
        # Explicitly indicate no server-side conversation memory.
        "state_persisted": False,
    }


def _deterministic_copilot_response(
    messages: list[dict[str, str]],
    current_rules: dict[str, Any],
    apply: bool = False,
) -> dict[str, Any]:
    user_messages = [item["content"] for item in messages if item.get("role") == "user"]
    last_user = user_messages[-1] if user_messages else ""
    combined_text = "\n".join(user_messages)
    text = last_user.lower()

    parsed_proposal = _build_rule_proposal_from_text(combined_text, current_rules)
    if parsed_proposal:
        updated_rules, rule_name = parsed_proposal
        changes = _diff_dict(current_rules, updated_rules)
        reply = (
            f"I prepared a proposal to create or update `{rule_name}`. "
            "Review the changes and click 'Apply Copilot Proposal' to save."
        )
        applied = False
        if apply:
            validated = TransformRules(**updated_rules)
            saved_rules = save_rules(validated).model_dump(by_alias=True)
            changes = _diff_dict(current_rules, saved_rules)
            updated_rules = saved_rules
            reply = f"Changes for `{rule_name}` have been applied and saved."
            applied = True
        return {
            "mode": "proposal",
            "reply": reply,
            "questions": [],
            "changes": changes,
            "updated_rules": updated_rules,
            "applied": applied,
            "used_ai": False,
            "state_persisted": False,
        }

    rule_intent = any(keyword in text for keyword in ("rule", "mapping", "default", "payment terms", "tax", "delivery"))
    detected_rule_name = _extract_rule_name_from_text(combined_text)
    is_column_label_request = _looks_like_column_label_mapping_request(combined_text)

    if rule_intent:
        if detected_rule_name:
            if is_column_label_request:
                reply = (
                    f"I detected rule name `{detected_rule_name}` and this looks like a column-label mapping request. "
                    "I can create it with top-level fields plus nested `line_items` labels."
                )
                questions = [
                    f"Should `{detected_rule_name}` be a plain mapping object like `invoice_date: Invoice Date`?",
                    "Should `line_items` be nested like `line_items: { product_code: Product Code }`?",
                    "For unknown/new columns, should label fallback be `Title Case` from snake_case?",
                ]
            else:
                reply = (
                    f"I detected rule name `{detected_rule_name}`. "
                    "I can create/update it once you provide default and specific mappings."
                )
                questions = [
                    f"What should be the `_default` value for `{detected_rule_name}`?",
                    f"Which specific keys should map to non-default values in `{detected_rule_name}`?",
                    "Confirm if I should prepare a proposal now.",
                ]
        else:
            reply = (
                "I can guide your rule mapping step by step. "
                "For mapping-style rules, define the `_default` first, then specific `conditions`."
            )
            questions = [
                "What rule name do you want to create or update?",
                "What should be the `_default` value for that rule?",
                "Which specific keys should map to non-default values, and what are those values?",
            ]
        return {
            "mode": "clarify",
            "reply": reply,
            "questions": questions,
            "changes": [],
            "updated_rules": None,
            "applied": False,
            "used_ai": False,
            "state_persisted": False,
        }

    return {
        "mode": "clarify",
        "reply": (
            "I can help with rule mapping and updates. "
            "Describe a rule change in natural language and I will guide you."
        ),
        "questions": [
            "If updating rules, which rule type and what default value do you want?",
        ],
        "changes": [],
        "updated_rules": None,
        "applied": False,
        "used_ai": False,
        "state_persisted": False,
    }


def _extract_rule_name_from_text(text: str) -> str | None:
    for pattern in [
        r"(?:create|add|new|update)\s+(?:a\s+)?(?:new\s+)?rule(?:\s+(?:called|named))?\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        r"rule\s+name\s+(?:is|will\s+be)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        r"name\s+of\s+the\s+rule\s+(?:is|will\s+be)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    ]:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _looks_like_column_label_mapping_request(text: str) -> bool:
    text_lc = text.lower()
    required_hints = ("snake case", "proper case")
    return all(hint in text_lc for hint in required_hints) or ("->" in text and "column" in text_lc)


def _build_rule_proposal_from_text(
    text: str,
    current_rules: dict[str, Any],
) -> tuple[dict[str, Any], str] | None:
    if not text.strip():
        return None

    rule_name = _extract_rule_name_from_text(text)
    if not rule_name:
        return None

    if _looks_like_column_label_mapping_request(text):
        column_mapping = _build_column_label_mapping_rule(text)
        if column_mapping:
            updated_rules = json.loads(json.dumps(current_rules))
            existing = updated_rules.get(rule_name)
            if isinstance(existing, dict):
                merged = json.loads(json.dumps(existing))
                merged = _merge_mapping_dicts(merged, column_mapping)
                updated_rules[rule_name] = merged
            else:
                updated_rules[rule_name] = column_mapping
            return updated_rules, rule_name

    default_match = re.search(
        r"default(?:\s+value)?\s*(?:is|to|=)?\s*(.+?)(?=(?:\s+(?:but|and)\s+for\b)|[,.;\n]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if not default_match:
        return None

    default_value = _coerce_rule_value(default_match.group(1))

    conditions: dict[str, Any] = {}
    for match in re.finditer(
        r"(?:for)\s+([a-zA-Z0-9 _\-.]+?)\s+(?:make(?:\s+it)?|set(?:\s+it)?|is|to|=)\s+(.+?)(?=(?:\s+and\s+for\b)|[,.;\n]|$)",
        text,
        flags=re.IGNORECASE,
    ):
        key = match.group(1).strip()
        value = _coerce_rule_value(match.group(2))
        if key:
            conditions[key] = value

    updated_rules = json.loads(json.dumps(current_rules))
    existing = updated_rules.get(rule_name)
    if isinstance(existing, dict):
        merged_conditions = {}
        if isinstance(existing.get("conditions"), dict):
            merged_conditions.update(existing["conditions"])
        merged_conditions.update(conditions)
        updated_rules[rule_name] = {
            "_default": default_value,
            "conditions": merged_conditions,
        }
    else:
        updated_rules[rule_name] = {
            "_default": default_value,
            "conditions": conditions,
        }

    return updated_rules, rule_name


def _build_column_label_mapping_rule(text: str) -> dict[str, Any]:
    explicit_pairs = _extract_explicit_column_label_pairs(text)
    use_full_erp_schema = _text_mentions_erp_schema(text)

    mapping: dict[str, Any] = {}
    line_items_mapping: dict[str, str] = {}

    if use_full_erp_schema:
        for field in ERP_TOP_LEVEL_FIELDS:
            if field == "line_items":
                continue
            mapping[field] = _snake_to_title_case(field)
        for subfield in ERP_LINE_ITEM_FIELDS:
            line_items_mapping[subfield] = _snake_to_title_case(subfield)

    for source_key, label in explicit_pairs.items():
        normalized_key = source_key.strip()
        if not normalized_key:
            continue
        if normalized_key.startswith("line_items."):
            subfield = normalized_key.split(".", 1)[1].strip()
            if subfield:
                line_items_mapping[subfield] = label
            continue
        if normalized_key == "line_items":
            continue
        mapping[normalized_key] = label

    if line_items_mapping:
        mapping["line_items"] = line_items_mapping

    return mapping


def _extract_explicit_column_label_pairs(text: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for match in re.finditer(
        r"([a-zA-Z_][a-zA-Z0-9_.]*)\s*->\s*([A-Za-z0-9 _\-/()]+?)(?=(?:[,;\n]|$))",
        text,
        flags=re.IGNORECASE,
    ):
        source_key = match.group(1).strip()
        label = match.group(2).strip()
        if source_key and label:
            pairs[source_key] = label
    return pairs


def _text_mentions_erp_schema(text: str) -> bool:
    text_lc = text.lower()
    return (
        "erp columns" in text_lc
        or "payload" in text_lc
        or "line_items contains" in text_lc
        or "line items contains" in text_lc
    )


def _snake_to_title_case(value: str) -> str:
    words = [part for part in value.strip().split("_") if part]
    return " ".join(word[:1].upper() + word[1:] for word in words)


def _merge_mapping_dicts(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _merge_mapping_dicts(base[key], value)
        else:
            base[key] = value
    return base


def _coerce_rule_value(raw_value: str) -> Any:
    value = raw_value.strip().strip("\"'")
    value_lc = value.lower()
    if value_lc in {"true", "false"}:
        return value_lc == "true"
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    if re.fullmatch(r"-?\d+\.\d+", value):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _call_openai_json(system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError("openai package is not installed") from exc

    model = os.getenv("RULES_AI_MODEL", "gpt-4.1-mini")
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )

    content = (response.choices[0].message.content or "").strip()
    parsed = _parse_json_object(content)
    if not isinstance(parsed, dict):
        raise ValueError("AI did not return a JSON object")
    return parsed


def _parse_json_object(text: str) -> dict[str, Any]:
    if not text:
        raise ValueError("Empty AI response")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("AI response did not contain JSON")

    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("AI response JSON is not an object")
    return parsed


def _diff_dict(before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    if isinstance(before, dict) and isinstance(after, dict):
        keys = sorted(set(before.keys()) | set(after.keys()))
        for key in keys:
            next_path = f"{path}.{key}" if path else str(key)
            if key not in before:
                changes.append({"path": next_path, "before": None, "after": after[key]})
                continue
            if key not in after:
                changes.append({"path": next_path, "before": before[key], "after": None})
                continue
            changes.extend(_diff_dict(before[key], after[key], next_path))
        return changes

    if before != after:
        changes.append({"path": path or "$", "before": before, "after": after})

    return changes
