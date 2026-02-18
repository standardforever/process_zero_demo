from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models.rules import TransformRules

RULES_FILE = Path(__file__).resolve().parents[1] / "data" / "rules.json"


class RuleNotFoundError(ValueError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_rules() -> TransformRules:
    with RULES_FILE.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return TransformRules(**payload)


def load_rules_dict() -> dict[str, Any]:
    return load_rules().model_dump(by_alias=True)


def save_rules(payload: dict[str, Any] | TransformRules) -> TransformRules:
    if isinstance(payload, TransformRules):
        candidate = payload.model_dump(by_alias=True)
    else:
        candidate = payload

    candidate["lastUpdated"] = _utc_now_iso()
    validated = TransformRules(**candidate)

    with RULES_FILE.open("w", encoding="utf-8") as file:
        json.dump(validated.model_dump(by_alias=True), file, indent=2)
        file.write("\n")

    return validated


def get_rule_type(rule_type: str) -> Any:
    rules = load_rules_dict()
    if rule_type not in rules:
        raise RuleNotFoundError(f"Unknown rule type: {rule_type}")
    return rules[rule_type]


def update_rule_type(rule_type: str, value: Any) -> TransformRules:
    rules = load_rules_dict()
    if rule_type not in rules:
        raise RuleNotFoundError(f"Unknown rule type: {rule_type}")

    rules[rule_type] = value
    return save_rules(rules)
