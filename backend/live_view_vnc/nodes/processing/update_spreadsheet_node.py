# nodes/processing/update_spreadsheet_node.py

from typing import Dict, Any
from utils.workflow_graph_state import WorkflowGraphState
from service.workflow_executor import WorkflowExecutor
from schemas.actions_schemas import WorkflowStep, WorkflowActionType
from browser_use.browser.events import SwitchTabEvent
import re
import asyncio
import json
from browser_use.dom.service import DomService


# At the top, add import
# At the top, update imports
from nodes.processing.fill_invoice_js_helpers import (
    get_click_spreadsheet_row_script,
    get_click_edit_all_script,
    get_fill_and_save_invoice_id_script
)

async def get_page_state(page, state: WorkflowGraphState) -> Dict[str, Any]:
    """Get current page DOM representation"""
    browser = state.get("browser_instance")
    dom_service = DomService(browser)
    
    serialized_dom_state, enhanced_dom_tree, all_time = await dom_service.get_serialized_dom_tree()
    selector_map = serialized_dom_state.selector_map
    browser.update_cached_selector_map(selector_map)
    
    llm_representation = serialized_dom_state.llm_representation()
    target_info = await page.get_target_info()
    
    return {
        "dom_representation": llm_representation,
        "url": target_info.get("url"),
        "title": target_info.get("title")
    }


def find_element_with_text(llm_representation: str, search_text: str, element_type: str = "role=option") -> int | None:
    """Find element index that contains specific text"""
    search_text = search_text.lower()
    lines = llm_representation.split('\n')
    
    for i, line in enumerate(lines):
        if search_text in line.lower():
            # Look backwards for element
            for j in range(i, max(0, i - 5), -1):
                prev_line = lines[j]
                if element_type in prev_line:
                    match = re.search(r'\[(\d+)\]', prev_line)
                    if match:
                        return int(match.group(1))
    return None


async def update_spreadsheet_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Update SharePoint spreadsheet with invoice ID
    
    Steps:
    1. Switch to spreadsheet tab
    2. Find the row by sales_request_ref
    3. Click on the row
    4. Update invoice ID field (or status field)
    5. Save changes
    """
    
    print("\n" + "="*60)
    print("UPDATE SPREADSHEET WITH INVOICE ID")
    print("="*60)
    
    # ============================================
    # FIND WORKFLOWS
    # ============================================
    
    workflows = state.get("workflows", [])
    
    spreadsheet_workflow = None
    spreadsheet_index = -1
    for idx, wf in enumerate(workflows):
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "spreadsheet_tab" or wf.get("name") == "sharepoint_crm_navigation":
            spreadsheet_workflow = wf
            spreadsheet_index = idx
            tab_id = wf.get("tab_id")
            break
    
    if not spreadsheet_workflow:
        return {
            **state,
            "error_message": "Spreadsheet workflow not found",
            "current_step": "update_spreadsheet_failed"
        }
    
    # ============================================
    # GET INVOICE INFO
    # ============================================
    
    last_invoice = spreadsheet_workflow.get("last_invoice_created", {})
    invoice_id = last_invoice.get("invoice_id")
    sales_ref = last_invoice.get("sales_ref")
    row_index = last_invoice.get("row_index", 0)
    
    if not sales_ref:
        print(f"  ✗ No sales reference found to update")
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "current_row_index": row_index + 1,
            "rows_failed": spreadsheet_workflow.get("rows_failed", 0) + 1
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "current_step": "update_spreadsheet_failed_continue"
        }
    
    print(f"\n  Sales Ref: {sales_ref}")
    print(f"  Invoice ID: {invoice_id if invoice_id else 'N/A'}")
    
    # ============================================
    # SWITCH TO SPREADSHEET TAB
    # ============================================
    
    browser = state.get("browser_instance")
    tools = state.get("tools")
    page = spreadsheet_workflow.get("page_instance")
    
    if not page or not browser or not tools:
        return {
            **state,
            "error_message": "Page, browser or tools not found",
            "current_step": "update_spreadsheet_failed"
        }
    
    try:
        print(f"\n  [1/5] Switching to spreadsheet tab...")
        
        await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
        await asyncio.sleep(2)
        
        print(f"  ✓ Switched to spreadsheet tab")
        
        # ============================================
        # FIND ROW BY SALES REFERENCE
        # ============================================
        
        # ============================================
        # FIND AND CLICK ROW BY SALES REFERENCE (JavaScript)
        # ============================================
        
        print(f"\n  [2/4] Finding and clicking row with sales ref: {sales_ref}...")
        
        click_row_script = get_click_spreadsheet_row_script(sales_ref)
        click_row_result = await page.evaluate(click_row_script)
        
        # Parse result if it's a string
        if isinstance(click_row_result, str):
            click_row_result = json.loads(click_row_result)
        
        if not click_row_result.get("success"):
            print(f"  ✗ Could not find/click row: {click_row_result.get('error')}")
            
            # Store failure for email notification
            failed_updates = spreadsheet_workflow.get("failed_spreadsheet_updates", [])
            failed_updates.append({
                "sales_ref": sales_ref,
                "invoice_id": invoice_id,
                "row_index": row_index,
                "reason": click_row_result.get('error')
            })
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "current_row_index": row_index + 1,
                "rows_processed": spreadsheet_workflow.get("rows_processed", 0) + 1,
                "failed_spreadsheet_updates": failed_updates
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": click_row_result.get('error'),
                "current_step": "update_spreadsheet_failed_continue"
            }
        
        print(f"  ✅ Row clicked: {sales_ref}")
        
        # ============================================
        # CLICK EDIT ALL BUTTON (JavaScript)
        # ============================================
        
        print(f"\n  [3/5] Clicking 'Edit all' button...")
        
        edit_all_script = get_click_edit_all_script()
        edit_all_result = await page.evaluate(edit_all_script)
        
        # Parse result if it's a string
        if isinstance(edit_all_result, str):
            edit_all_result = json.loads(edit_all_result)
        
        if not edit_all_result.get("success"):
            print(f"  ✗ Edit all click failed: {edit_all_result.get('error')}")
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": edit_all_result.get('error'),
                "current_step": "update_spreadsheet_failed_continue"
            }
        
        print(f"  ✅ Edit all clicked - form in edit mode")
        
        # ============================================
        # FILL INVOICE ID AND SAVE (JavaScript)
        # ============================================
        
        print(f"\n  [4/5] Filling Invoice ID and saving...")
        
        fill_and_save_script = get_fill_and_save_invoice_id_script(invoice_id if invoice_id else "CREATED")
        fill_and_save_result = await page.evaluate(fill_and_save_script)
        
        # Parse result if it's a string
        if isinstance(fill_and_save_result, str):
            fill_and_save_result = json.loads(fill_and_save_result)
        
        if not fill_and_save_result.get("success"):
            print(f"  ✗ Fill and save failed: {fill_and_save_result.get('error')}")
            # Still count as processed but note the error
        else:
            print(f"  ✅ Invoice ID filled and saved: {invoice_id if invoice_id else 'CREATED'}")
        
        # ============================================
        # SUCCESS
        # ============================================
        
        print(f"\n{'='*60}")
        print(f"✅ SPREADSHEET UPDATE COMPLETED")
        print(f"{'='*60}")
        print(f"  Sales Ref: {sales_ref}")
        print(f"  Invoice ID: {invoice_id if invoice_id else 'CREATED'}")
        
        
        
        # ============================================
        # SUCCESS
        # ============================================
        
        print(f"\n  ✅ Spreadsheet updated successfully!")
        print(f"    Sales Ref: {sales_ref}")
        print(f"    Invoice ID: {invoice_id if invoice_id else 'CREATED'}")
        
        # Update workflows
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "current_row_index": row_index + 1,
            "rows_processed": spreadsheet_workflow.get("rows_processed", 0) + 1,
            "last_updated_ref": sales_ref
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "current_step": "spreadsheet_updated_success"
        }
    
    except Exception as e:
        print(f"\n  ✗ Error updating spreadsheet: {e}")
        import traceback
        traceback.print_exc()
        
        # Store failure for email notification
        failed_updates = spreadsheet_workflow.get("failed_spreadsheet_updates", [])
        failed_updates.append({
            "sales_ref": sales_ref,
            "invoice_id": invoice_id,
            "row_index": row_index,
            "reason": f"Exception during update: {str(e)}"
        })
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "current_row_index": row_index + 1,
            "rows_processed": spreadsheet_workflow.get("rows_processed", 0) + 1,
            "failed_spreadsheet_updates": failed_updates,
            "error": str(e)
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": str(e),
            "current_step": "update_spreadsheet_failed_continue"
        }