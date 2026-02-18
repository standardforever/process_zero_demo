import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from

from openai import OpenAI

STATE_FILE = "transformation_state.json"
DEFAULT_MODEL = "gpt-4o-mini"


def default_state() -> Dict[str, Any]:
    return {
        "crm_columns": {
            "lead_name": {"type": "string", "required": True},
            "crm_id": {"type": "string", "required": True},
            "total": {"type": "number", "required": True},
            "invoice_date": {"type": "date", "required": True},
            "invoice_id": {"type": "string", "required": True},
        },
        "erp_columns": {
            "partner_name": {"type": "string", "required": True},
            "external_ref": {"type": "string", "required": True},
            "amount_total": {"type": "number", "required": True},
            "invoice_date": {"type": "date", "required": True},
            "name": {"type": "string", "required": True},
        },
        "mapping": {
            "lead_name": {"erp_column": "partner_name", "transform": "strip"},
            "crm_id": {"erp_column": "external_ref"},
            "total": {"erp_column": "amount_total"},
            "invoice_date": {"erp_column": "invoice_date"},
            "invoice_id": {"erp_column": "name"},
        },
        "rules": {
            "name_mapping": {}
        },
        "crm_records": {},
    }


def load_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        state = default_state()
        save_state(state)
        return state
    with open(STATE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_state(state: Dict[str, Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)


@dataclass
class AgentResult:
    ok: bool
    action: str
    message: str
    data: Optional[Dict[str, Any]] = None


class ValidationError(Exception):
    pass


class TransformationEngine:
    def __init__(self, state: Dict[str, Any]):
        self.state = state

    def _validate_column_name(self, side: str, column_name: str) -> None:
        bucket = "crm_columns" if side == "crm" else "erp_columns"
        if column_name not in self.state[bucket]:
            raise ValidationError(f"Unknown {side.upper()} column: '{column_name}'")

    def _validate_mapping_integrity(self) -> None:
        for crm_col, config in self.state["mapping"].items():
            if crm_col not in self.state["crm_columns"]:
                raise ValidationError(
                    f"Mapping references unknown CRM column: '{crm_col}'"
                )
            erp_col = config.get("erp_column")
            if erp_col not in self.state["erp_columns"]:
                raise ValidationError(
                    f"Mapping for '{crm_col}' references unknown ERP column: '{erp_col}'"
                )

    def create_or_update_column(
        self, side: str, name: str, col_type: str = "string", required: bool = False
    ) -> AgentResult:
        if side not in {"crm", "erp"}:
            raise ValidationError("side must be 'crm' or 'erp'")
        key = "crm_columns" if side == "crm" else "erp_columns"
        self.state[key][name] = {"type": col_type, "required": bool(required)}
        return AgentResult(True, "column_upsert", f"{side.upper()} column '{name}' saved")

    def read_columns(self, side: str) -> AgentResult:
        key = "crm_columns" if side == "crm" else "erp_columns"
        return AgentResult(True, "column_read", f"{side.upper()} columns", self.state[key])

    def delete_column(self, side: str, name: str) -> AgentResult:
        key = "crm_columns" if side == "crm" else "erp_columns"
        if name not in self.state[key]:
            raise ValidationError(f"Column '{name}' does not exist in {side.upper()}")
        del self.state[key][name]

        if side == "crm" and name in self.state["mapping"]:
            del self.state["mapping"][name]
        if side == "erp":
            stale = [crm for crm, m in self.state["mapping"].items() if m["erp_column"] == name]
            for crm in stale:
                del self.state["mapping"][crm]

        return AgentResult(True, "column_delete", f"{side.upper()} column '{name}' deleted")

    def upsert_mapping(self, crm_column: str, erp_column: str, transform: Optional[str] = None) -> AgentResult:
        self._validate_column_name("crm", crm_column)
        self._validate_column_name("erp", erp_column)
        entry = {"erp_column": erp_column}
        if transform:
            entry["transform"] = transform
        self.state["mapping"][crm_column] = entry
        self._validate_mapping_integrity()
        return AgentResult(True, "mapping_upsert", f"Mapped '{crm_column}' -> '{erp_column}'")

    def read_mapping(self) -> AgentResult:
        self._validate_mapping_integrity()
        return AgentResult(True, "mapping_read", "CRM -> ERP mapping", self.state["mapping"])

    def delete_mapping(self, crm_column: str) -> AgentResult:
        if crm_column not in self.state["mapping"]:
            raise ValidationError(f"No mapping exists for CRM column '{crm_column}'")
        del self.state["mapping"][crm_column]
        return AgentResult(True, "mapping_delete", f"Mapping removed for '{crm_column}'")

    def upsert_rule(self, rule_name: str, key: str, value: Any) -> AgentResult:
        if rule_name not in self.state["rules"]:
            self.state["rules"][rule_name] = {}
        self.state["rules"][rule_name][key] = value
        return AgentResult(True, "rule_upsert", f"Rule '{rule_name}' updated for '{key}'")

    def delete_rule(self, rule_name: str, key: Optional[str] = None) -> AgentResult:
        if rule_name not in self.state["rules"]:
            raise ValidationError(f"Rule set '{rule_name}' does not exist")
        if key is None:
            del self.state["rules"][rule_name]
            return AgentResult(True, "rule_delete", f"Rule set '{rule_name}' deleted")
        if key not in self.state["rules"][rule_name]:
            raise ValidationError(f"Rule '{rule_name}' has no key '{key}'")
        del self.state["rules"][rule_name][key]
        return AgentResult(True, "rule_delete", f"Rule '{rule_name}:{key}' deleted")

    def create_or_update_crm_record(self, record_id: str, data: Dict[str, Any]) -> AgentResult:
        self._validate_crm_payload(data)
        self.state["crm_records"][record_id] = data
        return AgentResult(True, "crm_record_upsert", f"CRM record '{record_id}' saved")

    def read_crm_record(self, record_id: str) -> AgentResult:
        if record_id not in self.state["crm_records"]:
            raise ValidationError(f"CRM record '{record_id}' not found")
        return AgentResult(True, "crm_record_read", f"CRM record '{record_id}'", self.state["crm_records"][record_id])

    def delete_crm_record(self, record_id: str) -> AgentResult:
        if record_id not in self.state["crm_records"]:
            raise ValidationError(f"CRM record '{record_id}' not found")
        del self.state["crm_records"][record_id]
        return AgentResult(True, "crm_record_delete", f"CRM record '{record_id}' deleted")

    def transform_record(self, crm_payload: Dict[str, Any]) -> AgentResult:
        self._validate_crm_payload(crm_payload)
        self._validate_mapping_integrity()

        erp_payload: Dict[str, Any] = {}
        for crm_column, config in self.state["mapping"].items():
            if crm_column not in crm_payload:
                continue
            erp_col = config["erp_column"]
            value = crm_payload[crm_column]
            erp_payload[erp_col] = self._apply_transform(value, config.get("transform"))

        name_map = self.state.get("rules", {}).get("name_mapping", {})
        if "partner_name" in erp_payload and erp_payload["partner_name"] in name_map:
            erp_payload["partner_name"] = name_map[erp_payload["partner_name"]]

        missing_required_erp = [
            col
            for col, meta in self.state["erp_columns"].items()
            if meta.get("required") and col not in erp_payload
        ]
        if missing_required_erp:
            raise ValidationError(
                f"Missing required ERP columns after mapping: {missing_required_erp}"
            )

        return AgentResult(True, "transform", "ERP payload generated", {"erp_payload": erp_payload})

    def _validate_crm_payload(self, crm_payload: Dict[str, Any]) -> None:
        unknown_cols = [k for k in crm_payload if k not in self.state["crm_columns"]]
        if unknown_cols:
            raise ValidationError(
                f"Unknown CRM columns in payload: {unknown_cols}. "
                f"Allowed columns: {list(self.state['crm_columns'].keys())}"
            )

        missing_required = [
            col
            for col, meta in self.state["crm_columns"].items()
            if meta.get("required") and col not in crm_payload
        ]
        if missing_required:
            raise ValidationError(f"Missing required CRM columns: {missing_required}")

    @staticmethod
    def _apply_transform(value: Any, transform: Optional[str]) -> Any:
        if not transform:
            return value
        if transform == "strip" and isinstance(value, str):
            return value.strip()
        if transform == "upper" and isinstance(value, str):
            return value.upper()
        if transform == "lower" and isinstance(value, str):
            return value.lower()
        return value


class IntentParser:
    def __init__(self, client: OpenAI, model: str = DEFAULT_MODEL):
        self.client = client
        self.model = model

    def parse(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_prompt(user_input, state)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    @staticmethod
    def _build_prompt(user_input: str, state: Dict[str, Any]) -> str:
        crm_cols = sorted(state["crm_columns"].keys())
        erp_cols = sorted(state["erp_columns"].keys())
        return (
            "You are a request parser for a CRM->ERP transformation engine. "
            "Return JSON only. Minimize tokens. "
            "If unknown column names appear, include them in errors list. "
            "Do not invent fields.\n"
            f"Allowed CRM columns: {crm_cols}\n"
            f"Allowed ERP columns: {erp_cols}\n"
            "Output schema:\n"
            "{"
            "\"operation\":\"create|read|update|delete|transform|out_of_scope\","
            "\"target\":\"crm_column|erp_column|mapping|rule|crm_record|none\","
            "\"payload\":{},"
            "\"errors\":[]"
            "}"
        )


class TransformationAgent:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.state = load_state()
        self.engine = TransformationEngine(self.state)
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.intent_parser = IntentParser(self.client, model=model)

    def handle(self, user_input: str, crm_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            if crm_payload is not None:
                result = self.engine.transform_record(crm_payload)
                return self._persist_and_format(result)

            intent = self.intent_parser.parse(user_input, self.state)
            parser_errors = intent.get("errors", [])
            if parser_errors:
                return {"ok": False, "action": "validate", "message": "; ".join(parser_errors)}

            result = self._execute_intent(intent)
            return self._persist_and_format(result)

        except ValidationError as exc:
            return {"ok": False, "action": "validation_error", "message": str(exc)}
        except Exception as exc:
            return {"ok": False, "action": "runtime_error", "message": str(exc)}

    def _persist_and_format(self, result: AgentResult) -> Dict[str, Any]:
        save_state(self.state)
        response = {"ok": result.ok, "action": result.action, "message": result.message}
        if result.data is not None:
            response["data"] = result.data
        return response

    def _execute_intent(self, intent: Dict[str, Any]) -> AgentResult:
        operation = intent.get("operation")
        target = intent.get("target")
        payload = intent.get("payload", {})

        if operation == "transform":
            return self.engine.transform_record(payload.get("crm_payload", {}))

        if target == "crm_column":
            if operation in {"create", "update"}:
                return self.engine.create_or_update_column(
                    "crm",
                    payload["name"],
                    payload.get("type", "string"),
                    payload.get("required", False),
                )
            if operation == "read":
                return self.engine.read_columns("crm")
            if operation == "delete":
                return self.engine.delete_column("crm", payload["name"])

        if target == "erp_column":
            if operation in {"create", "update"}:
                return self.engine.create_or_update_column(
                    "erp",
                    payload["name"],
                    payload.get("type", "string"),
                    payload.get("required", False),
                )
            if operation == "read":
                return self.engine.read_columns("erp")
            if operation == "delete":
                return self.engine.delete_column("erp", payload["name"])

        if target == "mapping":
            if operation in {"create", "update"}:
                return self.engine.upsert_mapping(
                    payload["crm_column"],
                    payload["erp_column"],
                    payload.get("transform"),
                )
            if operation == "read":
                return self.engine.read_mapping()
            if operation == "delete":
                return self.engine.delete_mapping(payload["crm_column"])

        if target == "rule":
            if operation in {"create", "update"}:
                return self.engine.upsert_rule(
                    payload["rule_name"], payload["key"], payload["value"]
                )
            if operation == "delete":
                return self.engine.delete_rule(payload["rule_name"], payload.get("key"))

        if target == "crm_record":
            if operation in {"create", "update"}:
                return self.engine.create_or_update_crm_record(
                    payload["record_id"], payload["record"]
                )
            if operation == "read":
                return self.engine.read_crm_record(payload["record_id"])
            if operation == "delete":
                return self.engine.delete_crm_record(payload["record_id"])

        raise ValidationError(f"Unsupported intent: operation={operation}, target={target}")


if __name__ == "__main__":
    agent = TransformationAgent()

    print("\\n1) Transform explicit payload")
    sample_payload = {
        "lead_name": "ACME Trading Corporation Limited",
        "crm_id": "CRM_995",
        "total": 1500.00,
        "invoice_date": "2024-11-01",
        "invoice_id": "INV088",
    }
    print(json.dumps(agent.handle("transform", crm_payload=sample_payload), indent=2))

    print("\\n2) CRUD on mapping (chat intent -> python execution)")
    print(
        json.dumps(
            agent.handle("Map CRM column lead_name to ERP column partner_name using strip"),
            indent=2,
        )
    )

    print("\\n3) Error on extra CRM columns")
    bad_payload = {
        **sample_payload,
        "unexpected_col": "not allowed",
    }
    print(json.dumps(agent.handle("transform", crm_payload=bad_payload), indent=2))
