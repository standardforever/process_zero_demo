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





class TransformationEngine:
    def __init__(self, rules_file: str):
        self.rules_file = Path(rules_file)
        self.schema = self._load_schema()

    def _load_schema(self) -> Dict:
        try:
            with open(self.rules_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _build_products(self, crm: Dict, tax: str, discount: float) -> List[Dict]:
        products = []
        for i in range(1, 4):
            raw = crm.get(f"product_{i}", "")
            if not raw:
                continue
            parts        = raw.split(" - ", 1)
            product_code = parts[0].strip()
            description  = parts[1].strip() if len(parts) > 1 else ""
            qty          = crm.get(f"product_{i}_quantity") or 0
            price        = crm.get(f"product_{i}_price_per_unit") or 0.0
            products.append({
                "product_code":     product_code,
                "description":      description,
                "quantity":         int(qty),
                "unit_price":       float(price),
                "discount_percent": discount,
                "tax":              tax,
            })
        return products

    def transform(self, raw_crm_data: Dict) -> Dict:
        crm          = raw_crm_data.copy()
        agent_rules  = self.schema.get("transformAgentRules", {})
        company_name = crm.get("customer_company", "").lower()

        # Match CRM company name to a rule key (case-insensitive)
        rule = next(
            (v for k, v in agent_rules.items() if k.lower() == company_name),
            None
        )

        if rule is None:
            message = f"No transformAgentRule found for company: '{crm.get('customer_company')}'"
            return {
                "status":    "error",
                "message":   message,
                "errors":    [message],
                "crm_input": raw_crm_data,
            }

        discount = float(crm.get("sales_discount_percent") or 0)
        products = self._build_products(crm, tax=rule.get("taxes", ""), discount=discount)

        invoice = {
            "invoice_reference":    rule.get("invoice_reference"),
            "customer_name":        rule.get("erp_customer_name"),
            "invoice_date":         rule.get("invoice_date"),
            "terms_and_conditions": rule.get("terms_and_conditions"),
            "payment_method":       rule.get("payment_method"),
            "sales_person":         rule.get("sales_person"),
            "payment_terms":        rule.get("payment_terms"),
            "payment_reference":    rule.get("payment_reference"),
            "customer_reference":   rule.get("customer_reference"),
            "delivery_address":     crm.get("delivery_address"),
            "notes":                None,
            "products":             products,
        }

        return {
            "status":         "success",
            "invoice":        invoice,
            "crm_input":      raw_crm_data,
            "normalized_crm": crm,
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
    # print(current_row)
    # print('\n\n\n\n\n\n')
    # exit()
    
    try:
        transformer = TransformationEngine(
            rules_file="transformation_agent.json",
            # api_key=os.getenv("OPENAI_API_KEY", '')
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