from utils.workflow_graph_state import WorkflowGraphState

async def process_complete_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Final success handler before ending workflow
    """
    print("\n" + "="*60)
    print("WORKFLOW COMPLETED SUCCESSFULLY")
    print("="*60)

    workflows = state.get("workflows", [])
    
    browser_instance = state.get('browser_instance')
    await browser_instance.stop()

    # Find spreadsheet workflow
    spreadsheet_workflow = None
    for wf in workflows:
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "spreadsheet_tab" or wf.get("name") == "sharepoint_crm_navigation":
            spreadsheet_workflow = wf
            break

    if spreadsheet_workflow:
        print(f"  ✅ Total Rows: {spreadsheet_workflow.get('total_rows', 0)}")
        print(f"  ✅ Rows Processed: {spreadsheet_workflow.get('rows_processed', 0)}")
        print(f"  ❌ Rows Failed: {spreadsheet_workflow.get('rows_failed', 0)}")

    return {
        **state,
        "current_step": "workflow_complete"
    }
