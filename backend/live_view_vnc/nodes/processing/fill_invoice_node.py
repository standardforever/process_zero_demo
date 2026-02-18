
# nodes/processing/fill_invoice_node.py

from typing import Dict, Any
from utils.workflow_graph_state import WorkflowGraphState
from service.workflow_executor import WorkflowExecutor
from schemas.actions_schemas import WorkflowStep, WorkflowActionType
from browser_use.browser.events import SwitchTabEvent

import re
import asyncio
import json
from browser_use.dom.service import DomService

# Import JavaScript helper scripts
from nodes.processing.fill_invoice_js_helpers import (
    get_fill_customer_script,
    get_fill_invoice_date_script,
    get_fill_payment_terms_script,
    get_add_products_script,
    get_log_note_script,
    get_schedule_activity_script,
    get_configure_columns_script,
    get_click_other_info_tab_script,
    get_fill_customer_reference_script,
    get_click_confirm_button_script,      # Add this
    get_extract_invoice_id_script          # Add this
)


async def fill_invoice_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Fill Odoo invoice form using JavaScript execution
    """
    
    print("\n" + "="*60)
    print("FILL INVOICE - JAVASCRIPT AUTOMATION")
    print("="*60)
    
    # ============================================
    # FIND WORKFLOWS
    # ============================================
    
    workflows = state.get("workflows", [])
    
    odoo_workflow = None
    odoo_index = -1
    for idx, wf in enumerate(workflows):
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "odoo_tab" or wf.get("name") == "odoo_invoice_creation":
            odoo_workflow = wf
            odoo_index = idx
            tab_id = wf.get("tab_id")
            break
    
    spreadsheet_workflow = None
    spreadsheet_index = -1
    for idx, wf in enumerate(workflows):
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "spreadsheet_tab" or wf.get("name") == "sharepoint_crm_navigation":
            spreadsheet_workflow = wf
            spreadsheet_index = idx
            break
    
    if not odoo_workflow or not spreadsheet_workflow:
        return {
            **state,
            "error_message": "Workflows not found",
            "current_step": "fill_invoice_failed"
        }
    
    
    # --- Switch to correct tab ---
    browser = state.get("browser_instance")
    await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
    
    
    # ============================================
    # GET DATA
    # ============================================
    
    transformed_row = spreadsheet_workflow.get("transformed_row")
    if not transformed_row:
        return {
            **state,
            "error_message": "No transformed data",
            "current_step": "fill_invoice_failed"
        }
    
    customer_name = transformed_row.get("customer_name", "")
    invoice_ref = transformed_row.get("invoice_reference", "N/A")
    invoice_date = transformed_row.get("invoice_date", "")
    products = transformed_row.get("products", [])
    
    print(f"\n  Invoice: {invoice_ref}")
    print(f"  Customer: {customer_name}")
    print(f"  Products: {len(products)}")
    
    page = odoo_workflow.get("page_instance")
    
    if not page:
        return {
            **state,
            "error_message": "Page instance not found",
            "current_step": "fill_invoice_failed"
        }
    
    try:
        # ============================================
        # STEP 1: VERIFY ON INVOICE PAGE
        # ============================================
        
        print(f"\n  [1/7] Verifying invoice page...")
        
        page_info = await page.get_target_info()
        current_url = page_info.url if hasattr(page_info, 'url') else page_info.get("url", "")
        
        if "customer-invoices/new" not in current_url:
            print(f"  ✗ Not on invoice page!")
            
            updated_workflows = workflows.copy()
            updated_workflows[odoo_index] = {
                **odoo_workflow,
                "page_valid": False,
                "setup_complete": False
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": "Not on invoice page",
                "current_step": "setup_odoo"
            }
        
        print(f"  ✓ On invoice page")
        
        # ============================================
        # STEP 2: FILL CUSTOMER (JavaScript)
        # ============================================
        
        print(f"\n  [2/7] Filling customer: {customer_name}...")
        
        customer_script = get_fill_customer_script(customer_name)
        customer_result = await page.evaluate(customer_script)
        if isinstance(customer_result, str):
            customer_result = json.loads(customer_result)
        
        if not customer_result.get("success"):
            error = customer_result.get("error", "Unknown error")
            print(f"  ✗ Customer fill failed: {error}")
            
            # Add to failed transformations
            failed_transformations = spreadsheet_workflow.get("failed_transformations", [])
            failed_transformations.append({
                "sales_ref": invoice_ref,
                "row_index": spreadsheet_workflow.get("current_row_index", 0),
                "reason": f"Customer fill failed: {error}",
                "raw_data": spreadsheet_workflow.get("current_row")
            })
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "current_row_index": spreadsheet_workflow.get("current_row_index", 0) + 1,
                "rows_failed": spreadsheet_workflow.get("rows_failed", 0) + 1,
                "failed_transformations": failed_transformations
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": error,
                # "current_step": "customer_fill_failed",
                "current_step": "fill_invoice_failed_continue"
            }
        
        print(f"  ✅ Customer filled: {customer_name}")
        
        # ============================================
        # STEP 3: FILL INVOICE DATE (JavaScript)
        # ============================================
        
        if invoice_date:
            print(f"\n  [3/7] Filling invoice date: {invoice_date}...")
            
            date_script = get_fill_invoice_date_script(invoice_date)
            date_result = await page.evaluate(date_script)
            if isinstance(date_result, str):
                date_result = json.loads(date_result)
                
            if date_result.get("success"):
                print(f"  ✅ Invoice date filled: {invoice_date}")
            else:
                print(f"  ⚠️  Invoice date fill failed: {date_result.get('error')}, continuing...")
        else:
            print(f"\n  [3/7] No invoice date provided, skipping...")
        
        # ============================================
        # STEP 4: FILL PAYMENT TERMS (JavaScript)
        # ============================================
        
        print(f"\n  [4/7] Filling payment terms: 15 Days...")
        
        payment_script = get_fill_payment_terms_script("15 Days")
        payment_result = await page.evaluate(payment_script)
        if isinstance(payment_result, str):
            payment_result = json.loads(payment_result)
        
        if payment_result.get("success"):
            if payment_result.get("created"):
                print(f"  ✅ Payment terms created: 15 Days")
            else:
                print(f"  ✅ Payment terms filled: 15 Days")
        else:
            print(f"  ⚠️  Payment terms fill failed: {payment_result.get('error')}, continuing...")
            
        
        # ============================================
        # STEP 4.5: CONFIGURE INVOICE COLUMNS (JavaScript)
        # ============================================
        
        print(f"\n  [4.5/7] Configuring invoice columns...")
        
        configure_script = get_configure_columns_script()
        configure_result = await page.evaluate(configure_script)
        
        if isinstance(configure_result, str):
            configure_result = json.loads(configure_result)
        
        if configure_result.get("success"):
            columns_checked = configure_result.get("columns_checked", 0)
            if columns_checked > 0:
                print(f"  ✅ Configured {columns_checked} columns")
            else:
                print(f"  ✅ All columns already configured")
        else:
            print(f"  ⚠️  Column configuration failed: {configure_result.get('error')}, continuing...")
        
        
        # ============================================
        # STEP 5: ADD PRODUCTS (JavaScript)
        # ============================================
        
        if products:
            print(f"\n  [5/7] Adding {len(products)} product(s) to invoice...")
            
            products_script = get_add_products_script(products)
            products_result = await page.evaluate(products_script)
            
            if isinstance(products_result, str):
                products_result = json.loads(products_result)
            
            if products_result.get("success"):
                print(f"  ✅ All {products_result.get('productsAdded')} products added successfully")
            else:
                added = products_result.get("productsAdded", 0)
                total = products_result.get("totalProducts", len(products))
                print(f"  ⚠️  Products partially added: {added}/{total}")
                print(f"     Error: {products_result.get('error', 'Unknown')}")
        else:
            print(f"\n  [5/7] No products to add, skipping...")
        
        
        # ============================================
        # STEP 6: CLICK OTHER INFO TAB (JavaScript)
        # ============================================
        
        print(f"\n  [6/9] Clicking 'Other Info' tab...")
        
        other_info_script = get_click_other_info_tab_script()
        other_info_result = await page.evaluate(other_info_script)
        if isinstance(other_info_result, str):
            other_info_result = json.loads(other_info_result)
        
        if other_info_result.get("success"):
            if other_info_result.get("already_selected"):
                print(f"  ✅ Other Info tab already selected")
            else:
                print(f"  ✅ Other Info tab clicked")
        else:
            print(f"  ⚠️  Other Info tab click failed: {other_info_result.get('error')}, continuing...")
        
        # ============================================
        # STEP 7: FILL CUSTOMER REFERENCE (JavaScript)
        # ============================================
        
        print(f"\n  [7/9] Filling customer reference: {invoice_ref}...")
        
        ref_script = get_fill_customer_reference_script(invoice_ref)
        ref_result = await page.evaluate(ref_script)
        if isinstance(ref_result, str):
            ref_result = json.loads(ref_result)
        
        
        if ref_result.get("success"):
            print(f"  ✅ Customer reference filled: {invoice_ref}")
        else:
            print(f"  ⚠️  Customer reference fill failed: {ref_result.get('error')}, continuing...")
        
        # ============================================
        # STEP 6: LOG INTERNAL NOTE (JavaScript)
        # ============================================
        
        print(f"\n  [6/7] Logging internal note...")
        
        log_message = "This sales invoice record has been created through an autonomous process."
        log_script = get_log_note_script(log_message)
        log_result = await page.evaluate(log_script)
        
        if isinstance(log_result, str):
                log_result = json.loads(log_result)
        
        if log_result.get("success"):
            print(f"  ✅ Internal note logged")
        else:
            print(f"  ⚠️  Log note failed: {log_result.get('error')}, continuing...")
        
        # ============================================
        # STEP 7: SCHEDULE ACTIVITY (JavaScript)
        # ============================================
        
        print(f"\n  [7/7] Scheduling activity...")
        
        activity_summary = "Invoice Review: Please check and supervise this AI-generated invoice."
        activity_script = get_schedule_activity_script(activity_summary)
        activity_result = await page.evaluate(activity_script)
        
        if isinstance(activity_result, str):
            activity_result = json.loads(activity_result)
        
        if activity_result.get("success"):
            print(f"  ✅ Activity scheduled")
        else:
            print(f"  ⚠️  Activity scheduling failed: {activity_result.get('error')}, continuing...")
        
        # ============================================
        # STEP 10: CLICK CONFIRM BUTTON (JavaScript)
        # ============================================
        
        print(f"\n  [10/11] Clicking Confirm button...")
        
        confirm_script = get_click_confirm_button_script()
        confirm_result = await page.evaluate(confirm_script)
        if isinstance(confirm_result, str):
            confirm_result = json.loads(confirm_result)
        
        if not confirm_result.get("success"):
            print(f"  ✗ Confirm button click failed: {confirm_result.get('error')}")
            
            updated_workflows = workflows.copy()
            updated_workflows[odoo_index] = {
                **odoo_workflow,
                "invoice_filled": True,
                "confirmed": False,
                "confirm_error": confirm_result.get('error')
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": f"Failed to confirm invoice: {confirm_result.get('error')}",
                # "current_step": "invoice_confirm_failed"
                "current_step": "fill_invoice_failed_continue"
            }
        
        print(f"  ✅ Confirm button clicked")
        
        # ============================================
        # STEP 11: EXTRACT INVOICE ID (JavaScript)
        # ============================================
        
        print(f"\n  [11/11] Extracting invoice ID...")
        
        extract_script = get_extract_invoice_id_script()
        extract_result = await page.evaluate(extract_script)
        if isinstance(extract_result, str):
            extract_result = json.loads(extract_result)
        
        invoice_id = None
        
        if extract_result.get("success"):
            invoice_id = extract_result.get("invoice_id")
            print(f"  ✅ Invoice ID extracted: {invoice_id}")
        else:
            print(f"  ⚠️  Invoice ID extraction failed: {extract_result.get('error')}")
            # Not critical - we can continue without it
        
        # ============================================
        # SUCCESS - UPDATE STATE
        # ============================================
        
        print(f"\n{'='*60}")
        print(f"✅ INVOICE COMPLETED SUCCESSFULLY")
        print(f"{'='*60}")
        print(f"  Customer: {customer_name}")
        print(f"  Reference: {invoice_ref}")
        if invoice_id:
            print(f"  Invoice ID: {invoice_id}")
        print(f"  Products Added: {len(products)}")
        print(f"  Status: CONFIRMED")
        
        # Update workflows with invoice ID
        updated_workflows = workflows.copy()
        updated_workflows[odoo_index] = {
            **odoo_workflow,
            "invoice_filled": True,
            "confirmed": True,
            "last_invoice_id": invoice_id,
            "last_customer_reference": invoice_ref
        }
        
        # Update spreadsheet workflow - store invoice info for next node
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "last_invoice_created": {
                "invoice_id": invoice_id,
                "sales_ref": invoice_ref,
                "customer_name": customer_name,
                "row_index": spreadsheet_workflow.get("current_row_index", 0)
            }
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "current_step": "invoice_created_needs_spreadsheet_update"  # ← Route to update node
        }
    
    except Exception as e:
        print(f"\n  ✗ Error filling invoice: {e}")
        import traceback
        traceback.print_exc()
        
        # Mark row as failed
        failed_transformations = spreadsheet_workflow.get("failed_transformations", [])
        failed_transformations.append({
            "sales_ref": invoice_ref,
            "row_index": spreadsheet_workflow.get("current_row_index", 0),
            "reason": f"Exception during invoice creation: {str(e)}",
            "raw_data": spreadsheet_workflow.get("current_row")
        })
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "current_row_index": spreadsheet_workflow.get("current_row_index", 0) + 1,
            "rows_failed": spreadsheet_workflow.get("rows_failed", 0) + 1,
            "failed_transformations": failed_transformations,
            "error": str(e)
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": str(e),
            "current_step": "fill_invoice_failed_continue"  # ← Continue to next row
        }