from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models.rules import TransformRules

RULES_FILE = Path(__file__).resolve().parents[2] / "live_view_vnc" / "transformation_agent.json"
LEGACY_RULES_FILE = Path(__file__).resolve().parents[1] / "data" / "rules.json"


class RuleNotFoundError(ValueError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_rules_file() -> None:
    if RULES_FILE.exists():
        return

    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LEGACY_RULES_FILE.exists():
        shutil.copy2(LEGACY_RULES_FILE, RULES_FILE)
        return

    # Fallback default only if neither file exists.
    default_rules = TransformRules(
        version="1.0",
        lastUpdated=_utc_now_iso(),
        customerNameMapping={},
        customerCountry={"_default": "United Kingdom", "conditions": {}},
        salesTaxRate={"_default": "20%", "conditions": {}},
        termsAndConditions={"_default": "Standard Terms & Conditions", "conditions": {}},
        paymentTerms={"_default": "30 Days", "conditions": {}},
        paymentMethod={"_default": "Bank Deposit", "conditions": {}},
        deliveryDays={"_default": 7, "conditions": {}},
    )
    with RULES_FILE.open("w", encoding="utf-8") as file:
        json.dump(default_rules.model_dump(by_alias=True), file, indent=2)
        file.write("\n")


def load_rules() -> TransformRules:
    _ensure_rules_file()
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
