# nodes/processing/process_invoice_rows_node.py

from utils.workflow_graph_state import WorkflowGraphState


async def process_invoice_rows_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Process invoice rows (PLACEHOLDER)
    
    TODO: Implement actual invoice creation logic
    - Loop through extracted rows
    - Switch between Odoo and Spreadsheet tabs
    - Create invoice in Odoo
    - Update status in Spreadsheet
    
    For now: Just marks processing as complete
    """
    
    print("\n" + "="*60)
    print("INVOICE PROCESSING (PLACEHOLDER)")
    print("="*60)
    
    extracted_rows = state.get("extracted_rows", [])
    total_rows = state.get("total_rows", 0)
    
    print(f"\n  📊 Rows to process: {total_rows}")
    
    if total_rows == 0:
        print(f"  ⚠️  No rows to process")
        
        return {
            **state,
            "processing_complete": True,
            "rows_processed": 0,
            "rows_failed": 0
        }
    
    # ============================================
    # PLACEHOLDER - Just mark as complete
    # ============================================
    
    print(f"\n  ⏭️  Processing not yet implemented")
    print(f"  ℹ️  This is a placeholder node")
    
    print(f"\n  📝 Would process:")
    for idx, row in enumerate(extracted_rows[:5]):  # Show first 5
        sales_ref = row.get('sales_request_ref', 'N/A')
        customer = row.get('customer_company', 'N/A')
        print(f"    [{idx + 1}] {sales_ref} - {customer}")
    
    if total_rows > 5:
        print(f"    ... and {total_rows - 5} more")
    
    # ============================================
    # MARK AS COMPLETE
    # ============================================
    
    return {
        **state,
        "processing_complete": True,
        "rows_processed": 0,  # Will be actual count later
        "rows_failed": 0,
        "processing_results": [],
        "current_step": "processing_complete"
    }
# ```

# **Simple and clean! Output:**
# ```
# ============================================================
# INVOICE PROCESSING (PLACEHOLDER)
# ============================================================

#   📊 Rows to process: 4

#   ⏭️  Processing not yet implemented
#   ℹ️  This is a placeholder node

#   📝 Would process:
#     [1] SO10016 - Universal Supplies
#     [2] SO10017 - Wrath Trading
#     [3] SO10018 - Ekho IT services
#     [4] SO10019 - Red Internet