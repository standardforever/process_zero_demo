import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import re


class RuleEngine:
    def __init__(self, rules_file: str = "transformation_rules.json"):
        self.rules_file = Path(rules_file)
        self.schema = self._load_schema()

    def _load_schema(self) -> Dict:
        """Load the transformation schema from file"""
        try:
            with open(self.rules_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "erp_schema": {},
                "post_transformation_actions": {},
                "metadata": {
                    "crm_columns": [],
                    "erp_system": "Odoo",
                    "version": "1.0.0",
                    "last_updated": datetime.utcnow().isoformat()
                }
            }

    def _save_schema(self):
        """Save the schema to file"""
        self.schema["metadata"]["last_updated"] = datetime.utcnow().isoformat()
        with open(self.rules_file, 'w') as f:
            json.dump(self.schema, f, indent=2)

    def _generate_rule_name(self, erp_column: str, base_name: str) -> str:
        """Generate a unique rule name within the column"""
        sanitized = re.sub(r'[^a-z0-9_]', '_', base_name.lower())
        existing_rules = self.schema["erp_schema"].get(erp_column, {}).get("rules", {})

        if sanitized not in existing_rules:
            return sanitized

        counter = 1
        while f"{sanitized}_{counter}" in existing_rules:
            counter += 1
        return f"{sanitized}_{counter}"

    # ==================== Rule Management ====================

    def _conditions_are_duplicate(self, existing_conditions: list, new_conditions: list) -> bool:
        """
        Check if two condition lists are functionally the same
        by comparing crm_column + operator + value for each condition
        """
        if len(existing_conditions) != len(new_conditions):
            return False

        for ec, nc in zip(existing_conditions, new_conditions):
            if (
                ec.get("crm_column") != nc.get("crm_column") or
                ec.get("operator")   != nc.get("operator")   or
                ec.get("value")      != nc.get("value")
            ):
                return False
        return True

    def add_rule(self, erp_column: str, rule_name: str, rule_data: Dict) -> Dict:
        """
        Add a new rule or update existing if same conditions already exist.
        Rule name is used exactly as provided - no modification.
        """

        # 1. ERP column must exist
        if erp_column not in self.schema["erp_schema"]:
            return {
                "status": "error",
                "message": f"ERP column '{erp_column}' does not exist. "
                        f"Available columns: {list(self.schema['erp_schema'].keys())}"
            }

        # 2. Validate required fields
        for field in ["conditions", ]:
            if field not in rule_data:
                return {
                    "status": "error",
                    "message": f"Missing required field: {field}"
                }

        # 3. Validate each condition has its own transformation
        for i, condition in enumerate(rule_data["conditions"]):
            if "transformation" not in condition:
                return {
                    "status": "error",
                    "message": f"Condition at index {i} is missing its 'transformation' block"
                }

        new_conditions = rule_data["conditions"]
        existing_rules = self.schema["erp_schema"][erp_column]["rules"]

        # 4. Check for duplicate conditions across existing rules
        for existing_rule_name, existing_rule_data in existing_rules.items():
            if self._conditions_are_duplicate(
                existing_rule_data.get("conditions", []),
                new_conditions
            ):
                # Same conditions found — update instead of creating duplicate
                existing_rule_data["conditions"] = new_conditions
                existing_rule_data["priority"]   = rule_data.get("priority", existing_rule_data.get("priority", 1))
                existing_rule_data["enabled"]    = rule_data.get("enabled", existing_rule_data.get("enabled", True))
                existing_rule_data["notes"]      = rule_data.get("notes", existing_rule_data.get("notes", ""))
                existing_rule_data["updated_at"] = datetime.utcnow().isoformat()

                self._save_schema()
                return {
                    "status": "updated",
                    "message": f"Rule with same conditions already existed under '{existing_rule_name}' — updated instead of creating duplicate",
                    "erp_column": erp_column,
                    "rule_name": existing_rule_name
                }

        # 5. Check if rule name already exists (different conditions) — block it, don't suffix
        if rule_name in existing_rules:
            return {
                "status": "error",
                "message": f"Rule name '{rule_name}' already exists in '{erp_column}' with different conditions. "
                        f"Please use a different name or update the existing rule explicitly."
            }

        # 6. Add the new rule using the exact name provided
        rule = {
            "priority":   rule_data.get("priority", 1),
            "enabled":    rule_data.get("enabled", True),
            "conditions": new_conditions,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        if "notes" in rule_data:
            rule["notes"] = rule_data["notes"]

        existing_rules[rule_name] = rule
        self._save_schema()

        return {
            "status": "success",
            "message": f"Rule '{rule_name}' added to '{erp_column}'",
            "erp_column": erp_column,
            "rule_name": rule_name
        }


    def get_rule(self, erp_column: str, rule_name: str) -> Dict:
        """Get a specific rule"""
        if erp_column not in self.schema["erp_schema"]:
            return {
                "status": "error",
                "message": f"ERP column '{erp_column}' not found"
            }

        rules = self.schema["erp_schema"][erp_column].get("rules", {})
        if rule_name not in rules:
            return {
                "status": "error",
                "message": f"Rule '{rule_name}' not found in column '{erp_column}'"
            }

        return {
            "status": "success",
            "erp_column": erp_column,
            "rule_name": rule_name,
            "rule": rules[rule_name]
        }


    def update_rule(self, erp_column: str, rule_name: str, updates: Dict) -> Dict:
        """Update an existing rule"""
        if erp_column not in self.schema["erp_schema"]:
            return {
                "status": "error",
                "message": f"ERP column '{erp_column}' not found"
            }

        rules = self.schema["erp_schema"][erp_column].get("rules", {})
        if rule_name not in rules:
            return {
                "status": "error",
                "message": f"Rule '{rule_name}' not found in '{erp_column}'. "
                        f"Available rules: {list(rules.keys())}"
            }

        rule = rules[rule_name]

        # Update top-level fields
        for key in ["priority", "enabled", "notes"]:
            if key in updates:
                rule[key] = updates[key]

        # Update conditions (each must still have its own transformation)
        if "conditions" in updates:
            for i, condition in enumerate(updates["conditions"]):
                if "transformation" not in condition:
                    return {
                        "status": "error",
                        "message": f"Condition at index {i} is missing its 'transformation' block"
                    }
            rule["conditions"] = updates["conditions"]

        rule["updated_at"] = datetime.utcnow().isoformat()
        self._save_schema()

        return {
            "status": "success",
            "message": f"Rule '{rule_name}' in '{erp_column}' updated successfully",
            "erp_column": erp_column,
            "rule_name": rule_name
        }

    def delete_rule(self, erp_column: str, rule_name: str) -> Dict:
        """Delete a rule"""
        if erp_column not in self.schema["erp_schema"]:
            return {
                "status": "error",
                "message": f"ERP column '{erp_column}' not found"
            }

        rules = self.schema["erp_schema"][erp_column].get("rules", {})
        if rule_name not in rules:
            return {
                "status": "error",
                "message": f"Rule '{rule_name}' not found in column '{erp_column}'"
            }

        del rules[rule_name]
        self._save_schema()

        return {
            "status": "success",
            "message": f"Rule '{rule_name}' deleted from '{erp_column}'",
            "erp_column": erp_column,
            "rule_name": rule_name
        }

    def list_rules(self, erp_column: Optional[str] = None, enabled_only: bool = False) -> Dict:
        """List rules for a specific column or all columns"""
        if erp_column:
            if erp_column not in self.schema["erp_schema"]:
                return {
                    "status": "error",
                    "message": f"ERP column '{erp_column}' not found"
                }

            rules = self.schema["erp_schema"][erp_column].get("rules", {})
            if enabled_only:
                rules = {k: v for k, v in rules.items() if v.get("enabled", True)}

            sorted_rules = dict(sorted(rules.items(), key=lambda x: x[1].get("priority", 999)))

            return {
                "status": "success",
                "erp_column": erp_column,
                "rules": sorted_rules,
                "count": len(sorted_rules)
            }
        else:
            all_rules = {}
            for col_name, col_data in self.schema["erp_schema"].items():
                rules = col_data.get("rules", {})
                if enabled_only:
                    rules = {k: v for k, v in rules.items() if v.get("enabled", True)}
                if rules:
                    all_rules[col_name] = dict(sorted(rules.items(), key=lambda x: x[1].get("priority", 999)))

            return {
                "status": "success",
                "rules_by_column": all_rules,
                "total_columns": len(all_rules),
                "total_rules": sum(len(r) for r in all_rules.values())
            }

    def search_rules(self, search_term: str, search_in: List[str] = None) -> Dict:
        """Search for rules by name, conditions, or transformation values"""
        if search_in is None:
            search_in = ["rule_name", "conditions", "transformation"]

        search_term_lower = search_term.lower()
        results = {}

        for col_name, col_data in self.schema["erp_schema"].items():
            matching_rules = {}
            for rule_name, rule_data in col_data.get("rules", {}).items():
                match = False

                if "rule_name" in search_in and search_term_lower in rule_name.lower():
                    match = True

                if "conditions" in search_in:
                    for condition in rule_data.get("conditions", []):
                        if (search_term_lower in str(condition.get("crm_column", "")).lower() or
                                search_term_lower in str(condition.get("value", "")).lower()):
                            match = True
                            break

                if "transformation" in search_in:
                    transform = rule_data.get("transformation", {})
                    if (search_term_lower in str(transform.get("value", "")).lower() or
                            search_term_lower in str(transform.get("formula", "")).lower()):
                        match = True

                if match:
                    matching_rules[rule_name] = rule_data

            if matching_rules:
                results[col_name] = matching_rules

        return {
            "status": "success",
            "search_term": search_term,
            "results": results,
            "total_matches": sum(len(r) for r in results.values())
        }

    # ==================== Utility Methods ====================

    def get_summary(self) -> Dict:
        """Get a summary of the entire transformation schema"""
        total_rules = 0
        enabled_rules = 0
        columns_with_rules = 0

        for col_data in self.schema["erp_schema"].values():
            rules = col_data.get("rules", {})
            if rules:
                columns_with_rules += 1
                total_rules += len(rules)
                enabled_rules += sum(1 for r in rules.values() if r.get("enabled", True))

        return {
            "status": "success",
            "summary": {
                "total_erp_columns": len(self.schema["erp_schema"]),
                "columns_with_rules": columns_with_rules,
                "total_rules": total_rules,
                "enabled_rules": enabled_rules,
                "disabled_rules": total_rules - enabled_rules,
                "crm_columns_available": len(self.schema["metadata"].get("crm_columns", [])),
                "erp_system": self.schema["metadata"].get("erp_system", "Unknown"),
                "version": self.schema["metadata"].get("version", "1.0.0"),
                "last_updated": self.schema["metadata"].get("last_updated")
            }
        }

    def validate_schema(self) -> Dict:
        """Validate the entire schema for consistency"""
        errors = []
        warnings = []

        for col_name, col_data in self.schema["erp_schema"].items():
            if "default_value" not in col_data:
                errors.append(f"Column '{col_name}' missing default_value")
            if "data_type" not in col_data:
                errors.append(f"Column '{col_name}' missing data_type")

            crm_columns = self.schema["metadata"].get("crm_columns", [])
            for rule_name, rule_data in col_data.get("rules", {}).items():
                if "conditions" not in rule_data:
                    errors.append(f"Rule '{col_name}.{rule_name}' missing conditions")
                if "transformation" not in rule_data:
                    errors.append(f"Rule '{col_name}.{rule_name}' missing transformation")

                for condition in rule_data.get("conditions", []):
                    crm_col = condition.get("crm_column")
                    if crm_col and crm_col not in crm_columns:
                        warnings.append(
                            f"Rule '{col_name}.{rule_name}' references unknown CRM column '{crm_col}'"
                        )

        return {
            "status": "success" if not errors else "error",
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def export_rules_for_column(self, erp_column: str) -> Dict:
        """Export all rules for a specific column in a readable format"""
        if erp_column not in self.schema["erp_schema"]:
            return {
                "status": "error",
                "message": f"ERP column '{erp_column}' not found"
            }

        column_data = self.schema["erp_schema"][erp_column]

        return {
            "status": "success",
            "erp_column": erp_column,
            "export": {
                "default_value": column_data.get("default_value"),
                "data_type": column_data.get("data_type"),
                "description": column_data.get("description", ""),
                "rules": column_data.get("rules", {})
            }
        }


   
from openai import OpenAI
import json
from typing import Dict, List


class LLMRuleManager:
    def __init__(self, rule_engine: RuleEngine, api_key: str, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.rule_engine = rule_engine

    def _get_system_context(self) -> str:
        """Get current system context for the LLM"""
        metadata = self.rule_engine.schema.get("metadata", {})
        erp_columns = list(self.rule_engine.schema.get("erp_schema", {}).keys())
        crm_columns = metadata.get("crm_columns", [])

        return f"""You are an expert transformation rule management assistant for an ERP system.

**Current System Context:**
- ERP System: {metadata.get('erp_system', 'Unknown')}
- Available CRM Columns: {', '.join(crm_columns)}
- Available ERP Columns: {', '.join(erp_columns)}

**Your Role:** You ONLY manage transformation rules inside existing ERP columns.
You CANNOT create, edit, or delete ERP columns or CRM columns - those are system-defined.
If a user asks to create/modify columns, politely inform them this is not allowed via chat.

**Supported Operators:**
- equals, not_equals, greater_than, less_than, greater_equal, less_equal
- contains, not_contains, in, not_in, starts_with, ends_with
- is_null, not_null

**Supported Transformation Actions:**
- set_value: Set a fixed value
- copy_value: Copy directly from a CRM column
- calculate: Use a formula (arithmetic and string operations)
- concat: Concatenate multiple values

**Logical Operators for Conditions:**
- AND: All conditions must be true
- OR: At least one condition must be true"""

    
    def _get_crud_prompt(self, user_input: str) -> str:
        return f"""Analyze this user request and respond with a JSON object describing the operation.

    **User Request:** "{user_input}"

    Respond ONLY with JSON in this exact format:

    {{
    "operation": "add_rule|update_rule|delete_rule|view_rule|list_rules|search_rules|get_summary|not_allowed",
    "intent_summary": "Brief description of what user wants",
    "erp_column": "target_erp_column_name",
    "rule_name": "descriptive_rule_name_in_snake_case",
    "rule_data": {{
        "priority": 1,
        "enabled": true,
        "conditions": [
        {{
            "crm_column": "column_name",
            "operator": "equals",
            "value": "value_to_check",
            "logical_operator": "AND|OR",
            "transformation": {{
            "action": "set_value|copy_value|calculate|concat",
            "value": "static_value",
            "source_crm_column": "",
            "formula": ""
            }}
        }}
        ],
        "notes": "optional explanation"
    }},
    "updates": {{
        "conditions": [
        {{
            "crm_column": "column_name",
            "operator": "equals",
            "value": "value_to_check",
            "logical_operator": "",
            "transformation": {{
            "action": "set_value|copy_value|calculate|concat",
            "value": "static_value",
            "source_crm_column": "",
            "formula": ""
            }}
        }}
        ]
    }},
    "search_term": "",
    "not_allowed_reason": ""
    }}

    **CRITICAL STRUCTURE RULE:**
    - The `transformation` block MUST always be INSIDE each condition object, NOT at the rule level
    - Every single condition must have its own `transformation` block
    - There is NO top-level transformation — only per-condition transformations
    - logical_operator is only needed for the 2nd+ condition, leave as "" for the first condition

    **Important Rules:**
    1. ONLY use columns from the available lists above
    2. Extract ALL conditions mentioned by the user
    3. For multiple conditions, set logical_operator ("AND" or "OR") on the 2nd+ condition only
    4. rule_name MUST be the exact CRM column value from the condition, converted to snake_case (spaces to underscores only) — do NOT shorten, abbreviate, translate or append anything to it.
        Examples:
        - condition value "Inner Mongolias"  → rule_name = "inner_mongolias"
        - condition value "united kingdom"   → rule_name = "united_kingdom"
        - condition value "ACME Trading"     → rule_name = "acme_trading"
        - condition value "ABC Trading"      → rule_name = "abc_trading"
        NEVER do: "inner_mongolias_tax", "uk_standard", "acme_trading_corp" — no extra words, no abbreviations
    5. For updates/deletes, identify the exact erp_column and rule_name
    6. If user tries to create/edit/delete a column, set operation to "not_allowed"

    **Examples:**

    User: "Add a rule: if customer_name is 'Inner Mongolia', set sales_tax_rate to 0"
    {{
    "operation": "add_rule",
    "erp_column": "sales_tax_rate",
    "rule_name": "inner_mongolia",
    "rule_data": {{
        "priority": 1,
        "enabled": true,
        "conditions": [
        {{
            "crm_column": "customer_name",
            "operator": "equals",
            "value": "Inner Mongolia",
            "logical_operator": "",
            "transformation": {{
            "action": "set_value",
            "value": 0,
            "source_crm_column": "",
            "formula": ""
            }}
        }}
        ],
        "notes": "Export - No VAT"
    }}
    }}

    User: "Add a rule: if customer_name is 'James' AND has_contract is false, set sales_tax_rate to 25"
    {{
    "operation": "add_rule",
    "erp_column": "sales_tax_rate",
    "rule_name": "james",
    "rule_data": {{
        "priority": 1,
        "enabled": true,
        "conditions": [
        {{
            "crm_column": "customer_name",
            "operator": "equals",
            "value": "James",
            "logical_operator": "",
            "transformation": {{
            "action": "set_value",
            "value": 25,
            "source_crm_column": "",
            "formula": ""
            }}
        }},
        {{
            "crm_column": "has_contract",
            "operator": "equals",
            "value": false,
            "logical_operator": "AND",
            "transformation": {{
            "action": "set_value",
            "value": 25,
            "source_crm_column": "",
            "formula": ""
            }}
        }}
        ],
        "notes": "25% tax for James with no contract"
    }}
    }}

    User: "Update the inner_mongolia rule in sales_tax_rate to 5%"
    {{
    "operation": "update_rule",
    "erp_column": "sales_tax_rate",
    "rule_name": "inner_mongolia",
    "updates": {{
        "conditions": [
        {{
            "crm_column": "customer_name",
            "operator": "equals",
            "value": "Inner Mongolia",
            "logical_operator": "",
            "transformation": {{
            "action": "set_value",
            "value": 5,
            "source_crm_column": "",
            "formula": ""
            }}
        }}
        ]
    }}
    }}

    User: "Delete the james rule from sales_tax_rate"
    {{
    "operation": "delete_rule",
    "erp_column": "sales_tax_rate",
    "rule_name": "james"
    }}

    User: "Show me all rules for payment_terms"
    {{
    "operation": "list_rules",
    "erp_column": "payment_terms"
    }}

    User: "Create a new ERP column called discount"
    {{
    "operation": "not_allowed",
    "not_allowed_reason": "ERP columns are system-defined and cannot be created via chat."
    }}"""


    def process_request(self, user_input: str) -> Dict:
        """Process a natural language CRUD request"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_context()},
                    {"role": "user", "content": self._get_crud_prompt(user_input)}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            llm_response = json.loads(response.choices[0].message.content)
            

            return self._execute_operation(llm_response, user_input)

        except Exception as e:
            return {
                "status": "error",
                "message": f"LLM processing error: {str(e)}",
                "user_input": user_input
            }

    def _execute_operation(self, llm_response: Dict, original_input: str) -> Dict:
        """Execute the CRUD operation based on LLM interpretation"""
        operation = llm_response.get("operation")

        try:
            if operation == "add_rule":
                return self.rule_engine.add_rule(
                    erp_column=llm_response.get("erp_column"),
                    rule_name=llm_response.get("rule_name"),
                    rule_data=llm_response.get("rule_data", {})
                )

            elif operation == "update_rule":
                return self.rule_engine.update_rule(
                    erp_column=llm_response.get("erp_column"),
                    rule_name=llm_response.get("rule_name"),
                    updates=llm_response.get("updates", {})
                )

            elif operation == "delete_rule":
                return self.rule_engine.delete_rule(
                    erp_column=llm_response.get("erp_column"),
                    rule_name=llm_response.get("rule_name")
                )

            elif operation == "view_rule":
                return self.rule_engine.get_rule(
                    erp_column=llm_response.get("erp_column"),
                    rule_name=llm_response.get("rule_name")
                )

            elif operation == "list_rules":
                return self.rule_engine.list_rules(
                    erp_column=llm_response.get("erp_column")
                )

            elif operation == "search_rules":
                return self.rule_engine.search_rules(
                    search_term=llm_response.get("search_term", "")
                )

            elif operation == "get_summary":
                return self.rule_engine.get_summary()

            elif operation == "not_allowed":
                return {
                    "status": "not_allowed",
                    "message": llm_response.get(
                        "not_allowed_reason",
                        "This operation is not permitted via chat. Columns are system-defined."
                    )
                }

            else:
                return {
                    "status": "error",
                    "message": f"Unknown operation: {operation}",
                    "llm_interpretation": llm_response
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Execution error: {str(e)}",
                "operation": operation,
                "original_input": original_input
            }

    def batch_process(self, requests: List[str]) -> List[Dict]:
        """Process multiple requests in batch"""
        results = []
        for request in requests:
            result = self.process_request(request)
            result["original_request"] = request
            results.append(result)
        return results

    
# Initialize the system
rule_engine = RuleEngine("transformation_rules.json")
llm_manager = LLMRuleManager(rule_engine, api_key=os.getenv("OPENAI_API_KEY", ""))


# Set up CRM columns in metadata
rule_engine.schema["metadata"]["crm_columns"] = [
    "customer_name", "country", "invoice_date", "invoice_id", 
    "crm_source_id", "invoice_total"
]
rule_engine._save_schema()

# Example 1: Add ERP columns and rules using natural language
requests =  [
    # # Customer Name Mapping

    # "add rule for acme trading customer name set tax to 20%"
    # "Add a rule acme_trading_corporation_limited: if customer_name equals 'ACME Trading Corporation Limited' set customer to 'ACME Trading Corporation LTD'",
    # "Add a rule abc_trading: if customer_name equals 'ABC Trading' set customer to 'ABC Trading Limited'",
    # "Add a rule sony_entertainment: if customer_name equals 'Sony Entertainment' set customer to 'Sony Entertainment Incorporated'",
    # "Add a rule echo_it_services: if customer_name equals 'Echo IT Services' set customer to 'EKHO IT Services'",
    # "Add a rule inner_mongolia: if customer_name equals 'Inner Mongolia' set customer to 'Inner Mongolia Autonomous Region Test'",
    # "Add a rule munaray: if customer_name equals 'Munaray' set customer to 'MUNARAY'",
    # "Add a rule red_internet: if customer_name equals 'Red Internet' set customer to 'Red Internet Co. Limited'",
    # "Add a rule trade_direct: if customer_name equals 'Trade Direct' set customer to 'Trading Direct Limited'",
    # "Add a rule universal_studios: if customer_name equals 'Universal Studios' set customer to 'Universal Supplies Limited'",
    # "Add a rule wraith_trading: if customer_name equals 'Wraith Trading' set customer to 'Wraith Trading Limited'",
    # "Add a rule veterinary_solutions: if customer_name equals 'Veterinary Solutions' set customer to 'Veterinary Solutions Limited'",

    # # Sales Tax Rate
    # "Add a rule inner_mongolia: if customer_name equals 'Inner Mongolia' set taxes to 0",
    # "Add a rule munaray: if customer_name equals 'Munaray' set taxes to 0",
    # "Add a rule universal_studios: if customer_name equals 'Universal Studios' set taxes to 5",
    # "Add a rule veterinary_solutions: if customer_name equals 'Veterinary Solutions' set taxes to 'Exempt'",

    # # Terms and Conditions
    # "Add a rule inner_mongolia: if customer_name equals 'Inner Mongolia' set terms_and_conditions to 'China Customer'",
    # "Add a rule munaray: if customer_name equals 'Munaray' set terms_and_conditions to 'US Customer'",
    # "Add a rule sony_entertainment: if customer_name equals 'Sony Entertainment' set terms_and_conditions to 'VIP Customer'",
    # "Add a rule universal_studios: if customer_name equals 'Universal Studios' set terms_and_conditions to 'VIP Customer'",

    # # Customer Reference
    # "Add a rule customer_reference: if invoice_id is not null set customer_reference using formula erp_customer_name[:3].upper() + str(datetime.now().year) + invoice_id",

    # # Payment Reference
    # "Add a rule payment_reference: if crm_source_id is not null set payment_reference using formula erp_customer_name[:5].upper() + crm_source_id + str(int(invoice_total))",

    # # Delivery Date
    # "Add a rule inner_mongolia: if customer_name equals 'Inner Mongolia' set delivery_date using formula invoice_date + timedelta(days=21)",
    # "Add a rule munaray: if customer_name equals 'Munaray' set delivery_date using formula invoice_date + timedelta(days=14)",
    # "Add a rule acme_trading_corporation_limited: if customer_name equals 'ACME Trading Corporation Limited' set delivery_date using formula invoice_date + timedelta(days=3)",
    # "Add a rule universal_studios: if customer_name equals 'Universal Studios' set delivery_date using formula invoice_date + timedelta(days=5)",

    # # Payment Method
    # "Add a rule inner_mongolia: if customer_name equals 'Inner Mongolia' set payment_method to 'Manual Payment'",
    # "Add a rule munaray: if customer_name equals 'Munaray' set payment_method to 'Bank Deposit'",
    # "Add a rule abc_trading: if customer_name equals 'ABC Trading' set payment_method to 'BACS Direct Debit'",
    # "Add a rule red_internet: if customer_name equals 'Red Internet' set payment_method to 'BACS Direct Debit'",
    # "Add a rule echo_it_services: if customer_name equals 'Echo IT Services' set payment_method to 'Manual Payment'",

    # # Payment Terms
    # "Add a rule inner_mongolia: if customer_name equals 'Inner Mongolia' set payment_terms to '45 Days'",
    # "Add a rule munaray: if customer_name equals 'Munaray' set payment_terms to '45 Days'",
    # "Add a rule sony_entertainment: if customer_name equals 'Sony Entertainment' set payment_terms to '15 Days'",
    # "Add a rule universal_studios: if customer_name equals 'Universal Studios' set payment_terms to '15 Days'",
    # "Add a rule trade_direct: if customer_name equals 'Trade Direct' set payment_terms to '21 Days'",
    # "Add a rule veterinary_solutions: if customer_name equals 'Veterinary Solutions' set payment_terms to '21 Days'",
]

print("=== Processing Natural Language Requests ===\n")
for request in requests:
    print(f"📝 User: {request}")
    result = llm_manager.process_request(request)
    print(f"✅ Result: {result.get('message', result)}\n")
