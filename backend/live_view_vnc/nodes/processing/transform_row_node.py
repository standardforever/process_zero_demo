# nodes/processing/transform_row_node.py

from utils.workflow_graph_state import WorkflowGraphState
from service.llm_client import LLMClient
import os
from dotenv import load_dotenv

load_dotenv()

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import json
import re
from pathlib import Path

from openai import OpenAI


class CRMPreprocessor:
    """
    Pre-processes raw CRM data into a normalized format
    suitable for transformation rules.
    """

    def normalize(self, raw_crm: Dict) -> Dict:
        """Transform flat CRM structure into nested/normalized structure."""
        normalized = raw_crm.copy()
        del normalized["row_index"]
   
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

            if product_key not in crm or not crm.get(product_key):
                break

            product_raw = crm.get(product_key, "")
            quantity    = crm.get(quantity_key, "0")
            price       = crm.get(price_key, "0")

            if not product_raw.strip():
                i += 1
                continue

            code, description = self._parse_product(product_raw)
            discount_percent = float(crm.get("sales_discount_percent", 0))

            products.append({
                "product_code":      code,
                "description":       description,
                "quantity":          quantity,
                "unit_price":        price,
                "discount_percent":  discount_percent,
                "tax":               None
            })

            i += 1

        return products

    def _parse_product(self, product_str: str) -> tuple:
        """Parse 'CHR100 - Black Office Chairs' into ('CHR100', 'Black Office Chairs')"""
        if " - " in product_str:
            parts = product_str.split(" - ", 1)
            return parts[0].strip(), parts[1].strip()
        return product_str.strip(), ""


class TransformationEngine:
    def __init__(self, rules_file: str,  api_key: str, model: str = "gpt-4o"):
        self.rules_file = Path(rules_file)
        self.schema   = self._load_schema()
        self.preprocessor  = CRMPreprocessor()
        self.client        = OpenAI(api_key=api_key)
        self.model         = model

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
            
    def _crm_value_to_rule_key(self, value: str) -> str:
        """Convert a CRM value to its expected rule key"""
        return re.sub(r'[^a-z0-9]', '_', str(value).lower()).strip('_')

    def _extract_candidate_rules(self, crm_data: Dict) -> tuple[Dict, List[str]]:
        """Extract candidate rules by matching CRM values to rule keys."""
        candidates = {}
        errors     = []

        # Build lookup keys from all CRM values
        crm_lookup_keys = {}
        for col, value in crm_data.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float)):
                key = self._crm_value_to_rule_key(value)
                crm_lookup_keys[key] = {"crm_column": col, "original_value": value}
        for erp_column, column_config in self.schema["erp_schema"].items():
            default_value = column_config.get("default_value")
            data_type     = column_config.get("data_type")
            description   = column_config.get("description", "")
            rules         = column_config.get("rules", {})
            matched_rules = {}

            # Fast O(1) lookup
            for rule_key in crm_lookup_keys:
                if rule_key in rules:
                    matched_rules[rule_key] = rules[rule_key]     

            # Handle not_null / is_null
            for rule_name, rule_data in rules.items():
                if rule_name in matched_rules:
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

            if not has_coverage and data_type != "array":
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

#     def _build_llm_prompt(self, crm_data: Dict, candidates: Dict) -> str:
#         """Build generic prompt that tells LLM to follow the provided rules"""

#         return f"""You are a CRM to ERP data transformation engine.

# Transform the CRM record into an ERP invoice by applying the transformation rules provided.

# ---
# **CRM Input:**
# {json.dumps(crm_data, indent=2)}

# ---
# **Transformation Rules (by ERP column):**
# {json.dumps(candidates, indent=2)}

# ---
# **Instructions:**

# For each ERP column in the transformation rules:

# 1. If `matched_rules` is not empty:
#    - Read the conditions and transformation from the matched rule
#    - Apply the transformation based on the action type:
#      * `set_value`: Use the specified value
#      * `copy_value`: Copy from source_crm_column
#      * `calculate`: Evaluate the formula using CRM data
#      * `concat`: Concatenate the specified values

# 2. If `matched_rules` is empty and `default_value` exists:
#    - Use the default_value

# 3. If `matched_rules` is empty and `default_value` is null:
#    - Set the field to null

# 4. For the `products` array:
#    - Transform the products_normalized array from CRM
#    - For each product, copy: product_code, description, quantity, unit_price, discount_percent
#    - Apply tax rules based on the matched_rules for the customer
#    - Tax should be a string with percentage (e.g., "20%", "0%", "Exempt")

# Respond ONLY with valid JSON in this exact format:
# {{
#   "invoice_reference": "...",
#   "customer_name": "...",
#   "invoice_date": "YYYY-MM-DD",
#   "terms_and_conditions": "...",
#   "payment_method": "...",
#   "products": [
#     {{
#       "product_code": "...",
#       "description": "...",
#       "quantity": 0,
#       "unit_price": 0.0,
#       "discount_percent": 0.0,
#       "tax": "..."
#     }}
#   ],
#   "delivery_address": "...",
#   "notes": "..."
# }}"""


    def _build_llm_prompt(self, crm_data: Dict, candidates: Dict) -> str:
        """Build generic prompt that tells LLM to follow the provided rules"""
        
        # Define the fixed structure for known fields
        fixed_structure = {
            "invoice_reference": "...",
            "customer_name": "...",
            "invoice_date": "YYYY-MM-DD",
            "terms_and_conditions": "...",
            "payment_method": "...",
            "products": [
                {
                    "product_code": "...",
                    "description": "...",
                    "quantity": 0,
                    "unit_price": 0.0,
                    "discount_percent": 0.0,
                    "tax": "..."
                }
            ],
            "delivery_address": "...",
            "notes": "..."
        }
        
        # Add any additional ERP columns not in the fixed structure
        for erp_column, config in candidates.items():
            if erp_column not in fixed_structure:
                data_type = config.get("data_type")
                
                if data_type == "array":
                    fixed_structure[erp_column] = []
                elif data_type == "number":
                    fixed_structure[erp_column] = 0
                elif data_type == "date":
                    fixed_structure[erp_column] = "YYYY-MM-DD"
                elif data_type == "boolean":
                    fixed_structure[erp_column] = False
                else:  # string, object, etc.
                    fixed_structure[erp_column] = "..."
        
        # Format as JSON structure for the prompt
        response_structure = json.dumps(fixed_structure, indent=2)
        
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
    - For each product, include: product_code, description, quantity, unit_price, discount_percent
    - Apply tax transformation rules to set the tax field for each product
    - Tax should be a string with percentage (e.g., "20%", "0%", "Exempt")

    5. For date fields:
    - Format dates as YYYY-MM-DD
    - Evaluate any date calculation formulas (e.g., invoice_date + timedelta(days=21))

    6. For number fields:
    - Return as numeric value, not string

    Respond ONLY with valid JSON matching this exact structure:
    {response_structure}

    CRITICAL: 
    - Include ALL fields in your response
    - Follow the exact structure shown above
    - Use null for fields with no value
    """

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
            
            print(erp_invoice)
            print("\n\n\n\n")

            return {
                "status":         "success",
                "invoice":        erp_invoice,  # Clean invoice data only
                "crm_input":      raw_crm_data,
                "normalized_crm": normalized_crm
            }

        except Exception as e:
            return {
                "status":    "error",
                "message":   f"LLM transformation failed: {str(e)}",
                "crm_input": raw_crm_data
            }


async def transform_row_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Transform raw spreadsheet row into structured invoice data using LLM
    
    Handles two outcomes:
    1. SUCCESS: Row transformed → proceeds to fill_invoice
    2. FAILURE: Row cannot be transformed → stored in failed_transformations
    """
    
    print("\n" + "="*60)
    print("ROW TRANSFORMATION (LLM)")
    print("="*60)
    
    # ============================================
    # FIND SPREADSHEET WORKFLOW
    # ============================================
    
    workflows = state.get("workflows", [])
    spreadsheet_workflow = None
    spreadsheet_index = -1
    
    for idx, wf in enumerate(workflows):
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "spreadsheet_tab" or wf.get("name") == "sharepoint_crm_navigation":
            spreadsheet_workflow = wf
            spreadsheet_index = idx
            break
    
    if not spreadsheet_workflow:
        print("  ✗ Spreadsheet workflow not found in state")
        return {
            **state,
            "error_message": "Spreadsheet workflow not found",
            "current_step": "transformation_failed"
        }
    
    # ============================================
    # GET CURRENT ROW
    # ============================================
    
    current_row = spreadsheet_workflow.get("current_row")
    current_row_index = spreadsheet_workflow.get("current_row_index", 0)
    rows_failed = spreadsheet_workflow.get("rows_failed", 0)
    failed_transformations = spreadsheet_workflow.get("failed_transformations", [])
    
    if not current_row:
        print("  ✗ No current row to transform")
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "error": "No current row to transform"
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": "No current row to transform",
            "current_step": "transformation_failed"
        }
    
    sales_ref = current_row.get("sales_request_ref", f"Row_{current_row_index}")
    
    # ============================================
    # DISPLAY RAW DATA
    # ============================================
    
    print(f"\n  📥 Raw Spreadsheet Data:")
    print(f"    Sales Ref: {sales_ref}")
    print(f"    Customer: {current_row.get('customer_company', 'N/A')}")
    print(f"    Contact: {current_row.get('customer_contact', 'N/A')}")
    print(f"    Discount: {current_row.get('sales_discount_percent', '0')}%")
    
    # ============================================
    # PRE-VALIDATION: CHECK REQUIRED FIELDS
    # ============================================
    
    required_raw_fields = ["customer_company", "customer_contact"]
    missing_raw_fields = [f for f in required_raw_fields if not current_row.get(f)]
    
    if missing_raw_fields:
        failure_reason = f"Missing required fields: {', '.join(missing_raw_fields)}"
        print(f"\n  ⚠️  {failure_reason}")
        
        failed_transformations.append({
            "sales_ref": sales_ref,
            "row_index": current_row_index,
            "reason": failure_reason,
            "raw_data": current_row
        })
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "transformed_row": None,
            "rows_failed": rows_failed + 1,
            "failed_transformations": failed_transformations,
            "current_row_index": current_row_index + 1,
            "transformation_skipped": True
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "current_step": "transformation_skipped"
        }
    
    # Check if at least one product exists
    has_product = any([
        current_row.get("product_1"),
        current_row.get("product_2"),
        current_row.get("product_3")
    ])
    
    if not has_product:
        failure_reason = "No products found in order"
        print(f"\n  ⚠️  {failure_reason}")
        
        failed_transformations.append({
            "sales_ref": sales_ref,
            "row_index": current_row_index,
            "reason": failure_reason,
            "raw_data": current_row
        })
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "transformed_row": None,
            "rows_failed": rows_failed + 1,
            "failed_transformations": failed_transformations,
            "current_row_index": current_row_index + 1,
            "transformation_skipped": True
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "current_step": "transformation_skipped"
        }
    
    # ============================================
    # INITIALIZE TRANSFORMATION ENGINE
    # ============================================
    
    try:
       
        transformer = TransformationEngine(
            rules_file="transformation_rules.json",
            api_key=os.getenv("OPENAI_API_KEY", '')
        )
        
        print(f"\n  🤖 Calling transformation engine...")
        
        # ============================================
        # CALL TRANSFORMATION ENGINE
        # ============================================
        
        result = transformer.transform(current_row)
        
        # ============================================
        # CHECK TRANSFORMATION STATUS
        # ============================================
        
        if result.get("status") == "error":
            # Transformation failed
            failure_reason = result.get("message", "Unknown transformation error")
            errors = result.get("errors", [])
            
            if errors:
                failure_reason += f" | Errors: {', '.join(errors)}"
            
            print(f"\n  ⚠️  Transformation Failed: {failure_reason}")
            
            failed_transformations.append({
                "sales_ref": sales_ref,
                "row_index": current_row_index,
                "reason": failure_reason,
                "raw_data": current_row
            })
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "transformed_row": None,
                "rows_failed": rows_failed + 1,
                "failed_transformations": failed_transformations,
                "current_row_index": current_row_index + 1,
                "transformation_skipped": True
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "current_step": "transformation_skipped"
            }
        
        # ============================================
        # EXTRACT INVOICE DATA
        # ============================================
        
        invoice_data = result.get("invoice", {})
        
        if not invoice_data:
            failure_reason = "No invoice data in transformation result"
            print(f"\n  ⚠️  {failure_reason}")
            
            failed_transformations.append({
                "sales_ref": sales_ref,
                "row_index": current_row_index,
                "reason": failure_reason,
                "raw_data": current_row
            })
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "transformed_row": None,
                "rows_failed": rows_failed + 1,
                "failed_transformations": failed_transformations,
                "current_row_index": current_row_index + 1,
                "transformation_skipped": True
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "current_step": "transformation_skipped"
            }
        
        # ============================================
        # VALIDATE INVOICE DATA
        # ============================================
        
        required_fields = ["invoice_reference", "customer_name", "products"]
        missing_fields = [f for f in required_fields if f not in invoice_data]
        
        if missing_fields:
            failure_reason = f"Missing required fields in invoice: {', '.join(missing_fields)}"
            print(f"\n  ⚠️  {failure_reason}")
            
            failed_transformations.append({
                "sales_ref": sales_ref,
                "row_index": current_row_index,
                "reason": failure_reason,
                "raw_data": current_row,
                "invoice_data": invoice_data
            })
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "transformed_row": None,
                "rows_failed": rows_failed + 1,
                "failed_transformations": failed_transformations,
                "current_row_index": current_row_index + 1,
                "transformation_skipped": True
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "current_step": "transformation_skipped"
            }
        
        if not invoice_data.get("products") or len(invoice_data["products"]) == 0:
            failure_reason = "No products in transformed invoice"
            print(f"\n  ⚠️  {failure_reason}")
            
            failed_transformations.append({
                "sales_ref": sales_ref,
                "row_index": current_row_index,
                "reason": failure_reason,
                "raw_data": current_row,
                "invoice_data": invoice_data
            })
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "transformed_row": None,
                "rows_failed": rows_failed + 1,
                "failed_transformations": failed_transformations,
                "current_row_index": current_row_index + 1,
                "transformation_skipped": True
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "current_step": "transformation_skipped"
            }
        
        # ============================================
        # DISPLAY TRANSFORMED DATA
        # ============================================
        print('\n\n\n *****')
        print(invoice_data)
        print('\n\n\n *****')
        print(f"\n  ✅ Transformation successful!")
        print(f"\n  📤 Transformed Invoice Data:")
        print(f"    Invoice Ref: {invoice_data.get('invoice_reference')}")
        print(f"    Customer: {invoice_data.get('customer_name')}")
        print(f"    Products: {len(invoice_data.get('products', []))}")
        
        print(f"\n  📦 Products:")
        for idx, product in enumerate(invoice_data.get('products', []), 1):
            print(f"    [{idx}] {product.get('product_code')} - {product.get('description')}")
            print(f"        Qty: {product.get('quantity')} × £{product.get('unit_price', 0):.2f}")
        
        # ============================================
        # UPDATE WORKFLOW WITH TRANSFORMED DATA
        # ============================================
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "transformed_row": invoice_data,  # ✅ Store only the invoice dict
            "failed_transformations": failed_transformations,
            "transformation_skipped": False,
            "error": None
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "current_step": "transformation_complete"
        }
    
    except Exception as e:
        failure_reason = f"Unexpected error: {str(e)}"
        print(f"\n  ⚠️  {failure_reason}")
        import traceback
        traceback.print_exc()
        
        failed_transformations.append({
            "sales_ref": sales_ref,
            "row_index": current_row_index,
            "reason": failure_reason,
            "raw_data": current_row
        })
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "transformed_row": None,
            "rows_failed": rows_failed + 1,
            "failed_transformations": failed_transformations,
            "current_row_index": current_row_index + 1,
            "transformation_skipped": True
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "current_step": "transformation_skipped"
        }