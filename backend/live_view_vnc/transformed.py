from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import json
import os
import re

from rules import RuleEngine, OpenAI

from typing import Dict, List
from datetime import datetime
import re


class CRMPreprocessor:
    """
    Pre-processes raw CRM data into a normalized format
    suitable for transformation rules.
    """

    def normalize(self, raw_crm: Dict) -> Dict:
        """
        Transform flat CRM structure into nested/normalized structure.
        
        Example:
        {
          "product_1": "CHR100 - Black Office Chairs",
          "product_1_quantity": "123",
          "product_1_price_per_unit": "89.99"
        }
        
        Becomes:
        {
          "products_normalized": [
            {
              "product_code": "CHR100",
              "description": "Black Office Chairs",
              "quantity": 123,
              "unit_price": 89.99
            }
          ]
        }
        """
        normalized = raw_crm.copy()

        # Extract products
        products = self._extract_products(raw_crm)
        normalized["products_normalized"] = products

        # Clean up - remove original product_X fields to reduce noise
        keys_to_remove = [k for k in normalized.keys() if k.startswith("product_")]
        for key in keys_to_remove:
            del normalized[key]

        return normalized

    def _extract_products(self, crm: Dict) -> List[Dict]:
        """Extract product_1, product_2, product_3... into array"""
        products = []
        i = 1

        while True:
            product_key  = f"product_{i}"
            quantity_key = f"product_{i}_quantity"
            price_key    = f"product_{i}_price_per_unit"

            # Stop when we don't find the next product
            if product_key not in crm or not crm.get(product_key):
                break

            product_raw = crm.get(product_key, "")
            quantity    = crm.get(quantity_key, "0")
            price       = crm.get(price_key, "0")

            # Skip empty products
            if not product_raw.strip():
                i += 1
                continue

            # Parse product code and description
            code, description = self._parse_product(product_raw)

            # Get global discount
            discount_percent = float(crm.get("sales_discount_percent", 0))

            products.append({
                "product_code":      code,
                "description":       description,
                "quantity":          quantity,
                "unit_price":        price,
                "discount_percent":  discount_percent,
                "tax":               None  # Will be set by transformation rules
            })

            i += 1

        return products

    def _parse_product(self, product_str: str) -> tuple:
        """
        Parse 'CHR100 - Black Office Chairs' into ('CHR100', 'Black Office Chairs')
        """
        if " - " in product_str:
            parts = product_str.split(" - ", 1)
            return parts[0].strip(), parts[1].strip()
        return product_str.strip(), ""


class TransformationEngine:
    def __init__(self, rule_engine: RuleEngine, api_key: str, model: str = "gpt-4o"):
        self.rule_engine   = rule_engine
        self.preprocessor  = CRMPreprocessor()
        self.client        = OpenAI(api_key=api_key)
        self.model         = model

    def _crm_value_to_rule_key(self, value: str) -> str:
        """Convert a CRM value to its expected rule key"""
        return re.sub(r'[^a-z0-9]', '_', str(value).lower()).strip('_')

    def _extract_candidate_rules(self, crm_data: Dict) -> tuple[Dict, List[str]]:
        """
        Extract candidate rules by matching CRM values to rule keys.
        Now supports both simple values and nested structures.
        """
        candidates = {}
        errors     = []

        # Build lookup keys from all CRM values (including nested)
        crm_lookup_keys = {}
        for col, value in crm_data.items():
            if value is None:
                continue
            # Only convert string/numeric values to rule keys
            if isinstance(value, (str, int, float)):
                key = self._crm_value_to_rule_key(value)
                crm_lookup_keys[key] = {"crm_column": col, "original_value": value}

        for erp_column, column_config in self.rule_engine.schema["erp_schema"].items():
            default_value = column_config.get("default_value")
            data_type     = column_config.get("data_type")
            description   = column_config.get("description", "")
            rules         = column_config.get("rules", {})
            matched_rules = {}

            # Fast O(1) lookup
            for rule_key in crm_lookup_keys:
                if rule_key in rules and rules[rule_key].get("enabled", True):
                    matched_rules[rule_key] = rules[rule_key]

            # Handle not_null / is_null
            for rule_name, rule_data in rules.items():
                if rule_name in matched_rules or not rule_data.get("enabled", True):
                    continue

                for condition in rule_data.get("conditions", []):
                    operator   = condition.get("operator", "")
                    crm_column = condition.get("crm_column", "")

                    if operator == "not_null" and crm_data.get(crm_column) is not None:
                        matched_rules[rule_name] = rule_data
                        break
                    if operator == "is_null" and crm_data.get(crm_column) is None:
                        matched_rules[rule_name] = rule_data
                        break

            has_coverage = bool(matched_rules) or default_value is not None

            if not has_coverage and data_type != "array":  # Arrays can default to []
                errors.append(
                    f"ERP column '{erp_column}' ({data_type}): "
                    f"No matching rule found and default_value is null"
                )

            candidates[erp_column] = {
                "description":   description,
                "data_type":     data_type,
                "default_value": default_value,
                "matched_rules": matched_rules,
                "has_coverage":  has_coverage
            }

        return candidates, errors

    def _build_llm_prompt(self, crm_data: Dict, candidates: Dict) -> str:
        """Build generic prompt that tells LLM to follow the provided rules"""
        return f"""You are a CRM to ERP data transformation engine.

    Transform the CRM record into an ERP invoice by applying the transformation rules provided.

    ---
    **CRM Input:**
    {json.dumps(crm_data, indent=2)}

    ---
    **Transformation Rules (by ERP column):**
    {json.dumps(candidates, indent=2)}

    ---
    **Instructions:**

    For each ERP column in the transformation rules:

    1. If `matched_rules` is not empty:
    - Read the conditions and transformation from the matched rule
    - Apply the transformation based on the action type:
        * `set_value`: Use the specified value
        * `copy_value`: Copy from source_crm_column
        * `calculate`: Evaluate the formula using CRM data
        * `concat`: Concatenate the specified values

    2. If `matched_rules` is empty and `default_value` exists:
    - Use the default_value

    3. If `matched_rules` is empty and `default_value` is null:
    - Set the field to null

    4. For the `products` array:
    - Transform the products_normalized array from CRM
    - For each product, copy: product_code, description, quantity, unit_price, discount_percent
    - Apply tax rules based on the matched_rules for the customer
    - Tax should be a string with percentage (e.g., "20%", "0%", "Exempt")

    Respond ONLY with valid JSON in this exact format:
    {{
    "invoice_reference": "...",
    "customer_name": "...",
    "invoice_date": "YYYY-MM-DD",
    "terms_and_conditions": "...",
    "payment_method": "...",
    "products": [
        {{
        "product_code": "...",
        "description": "...",
        "quantity": 0,
        "unit_price": 0.0,
        "discount_percent": 0.0,
        "tax": "..."
        }}
    ],
    "delivery_address": "...",
    "notes": "..."
    }}"""

    def _call_llm(self, prompt: str) -> Dict:
        """Call LLM for transformation - returns the clean invoice data"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise ERP data transformation engine. "
                            "Always respond with valid JSON only matching the exact format requested."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0
        )
        return json.loads(response.choices[0].message.content)

    def transform(self, raw_crm_data: Dict) -> Dict:
        """Transform raw CRM data to ERP invoice format"""
        
        # Step 1: Normalize CRM data
        normalized_crm = self.preprocessor.normalize(raw_crm_data)

        # Step 2: Extract candidate rules
        candidates, errors = self._extract_candidate_rules(normalized_crm)

        # Step 3: Check for errors
        if errors:
            return {
                "status":    "error",
                "message":   "Missing required field coverage",
                "errors":    errors,
                "crm_input": raw_crm_data
            }

        # Step 4: Transform via LLM
        try:
            prompt         = self._build_llm_prompt(normalized_crm, candidates)
            erp_invoice    = self._call_llm(prompt)

            return {
                "status":        "success",
                "invoice":       erp_invoice,  # Clean invoice data only
                "crm_input":     raw_crm_data,
                "normalized_crm": normalized_crm
            }

        except Exception as e:
            return {
                "status":    "error",
                "message":   f"LLM transformation failed: {str(e)}",
                "crm_input": raw_crm_data
            }

    def transform_batch(self, crm_records: List[Dict]) -> List[Dict]:
        """Transform multiple records"""
        return [self.transform(record) for record in crm_records]
    
    
    

# Initialize
rule_engine = RuleEngine("transformation_rules.json")
transformer = TransformationEngine(rule_engine, api_key=os.getenv("OPENAI_API_KEY", ""))

# Raw CRM data
raw_crm = {
    'row_index': 1,
    'sales_request_ref': 'SO10017',
    'date_raised': '1/1/2026',
    'sales_person': 'Alan Smith',
    'status': 'Active',
    'customer_company': 'Sony Entertainmentss',
    'customer_contact': 'Joan Fillet',
    'trading_address': 'Units A&B, LEYTON MILLS, Marshall Rd, London E10 5NH',
    'delivery_address': 'Units A&B, LEYTON MILLS, Marshall Rd, London E10 5NH',
    'sales_discount_percent': '0',
    'product_1': 'CHR100 - Black Office Chairs',
    'product_1_quantity': '123',
    'product_1_price_per_unit': '89.99',
    'product_2': '',
    'product_2_quantity': '',
    'product_2_price_per_unit': '',
}

# Transform
result = transformer.transform(raw_crm)
print(result)
print(result["invoice"])

# print(json.dumps(result["erp_data"], indent=2))

# Output:
# {
#   "invoice_reference": "SO10017",
#   "customer_name": "Wraith Trading Limited",
#   "invoice_date": "2026-01-01",
#   "products": [
#     {
#       "product_code": "CHR100",
#       "description": "Black Office Chairs",
#       "quantity": 123,
#       "unit_price": 89.99,
#       "discount_percent": 0,
#       "discount_amount": 0.0,
#       "subtotal": 11068.77,
#       "line_total": 11068.77,
#       "tax": "20%"
#     }
#   ],
#   "total": 11068.77,
#   "delivery_address": "Units A&B, LEYTON MILLS, Marshall Rd, London E10 5NH",
#   "notes": "Sales Person: Alan Smith"
# }
