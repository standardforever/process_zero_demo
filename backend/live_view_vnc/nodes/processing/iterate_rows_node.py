# nodes/processing/iterate_rows_node.py

from utils.workflow_graph_state import WorkflowGraphState


async def iterate_rows_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Iterate through extracted spreadsheet rows
    
    Controller node that:
    1. Gets next unprocessed row from extracted data
    2. Sets current_row for downstream processing
    3. Increments row index
    4. Determines if processing is complete
    
    State tracking per workflow:
    - extracted_rows: List of all rows to process
    - current_row_index: Index of current row being processed
    - current_row: The actual row data for processing
    - total_rows: Total number of rows
    - rows_processed: Count of successfully processed rows
    - rows_failed: Count of failed rows
    - processing_complete: Boolean flag
    """
    
    print("\n" + "="*60)
    print("ROW ITERATOR")
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
            "current_step": "iteration_failed"
        }
    
    # ============================================
    # GET ITERATION STATE
    # ============================================
    
    extracted_rows = spreadsheet_workflow.get("extracted_rows", [])
    current_row_index = spreadsheet_workflow.get("current_row_index", 0)
    total_rows = spreadsheet_workflow.get("total_rows", 0)
    rows_processed = spreadsheet_workflow.get("rows_processed", 0)
    rows_failed = spreadsheet_workflow.get("rows_failed", 0)
    
    print(f"\n  📊 Processing Status:")
    print(f"    Total Rows: {total_rows}")
    print(f"    Processed: {rows_processed}")
    print(f"    Failed: {rows_failed}")
    print(f"    Current Index: {current_row_index}")
    
    # ============================================
    # CHECK IF EXTRACTION COMPLETED
    # ============================================
    
    if not extracted_rows or len(extracted_rows) == 0:
        print(f"\n  ⚠️  No rows extracted - cannot process")
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "processing_complete": True,
            "current_row": None,
            "error": "No rows to process"
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": "No rows to process",
            "current_step": "processing_complete"
        }
    
    # ============================================
    # CHECK IF ALL ROWS PROCESSED
    # ============================================
    
    if current_row_index >= len(extracted_rows):
        print(f"\n  ✅ All rows processed!")
        print(f"    Successfully Processed: {rows_processed}/{total_rows}")
        print(f"    Failed: {rows_failed}/{total_rows}")
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "processing_complete": True,
            "current_row": None,
            "current_row_index": current_row_index
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "current_step": "processing_complete"
        }
    
    # ============================================
    # GET CURRENT ROW
    # ============================================
    
    current_row = extracted_rows[current_row_index]
    
    sales_ref = current_row.get("sales_request_ref", "N/A")
    customer = current_row.get("customer_company", "N/A")
    
    print(f"\n  🔄 Processing Row [{current_row_index + 1}/{total_rows}]:")
    print(f"    Sales Ref: {sales_ref}")
    print(f"    Customer: {customer}")
    
    # ============================================
    # UPDATE WORKFLOW WITH CURRENT ROW
    # ============================================
    
    updated_workflows = workflows.copy()
    updated_workflows[spreadsheet_index] = {
        **spreadsheet_workflow,
        "current_row": current_row,
        "current_row_index": current_row_index,
        "processing_complete": False,
        "error": None
    }
    
    return {
        **state,
        "workflows": updated_workflows,
        "current_step": "row_ready_for_processing"
    }