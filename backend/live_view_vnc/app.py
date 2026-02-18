# workflow_graph.py

# Import all nodes



from langgraph.graph import StateGraph, START, END
from utils.workflow_graph_state import WorkflowGraphState
from nodes.load_config_node import load_config_node
from nodes.browser_connection_node import check_browser_connection_node
from nodes.create_workflow_tabs_node import create_workflow_tabs_node
# Import execute_workflows_node for resume
from nodes.execute_workflows_node import execute_workflows_node


from nodes.connect_browser_node import connect_browser_node
from nodes.create_workflow_tabs_node import create_workflow_tabs_node

# Odoo workflow nodes
from nodes.odoo.setup_odoo_node import setup_odoo_node
from nodes.odoo.validate_odoo_page_node import validate_odoo_page_node

# Spreadsheet workflow nodes
from nodes.spreadsheet.setup_spreadsheet_node import setup_spreadsheet_node
from nodes.spreadsheet.validate_spreadsheet_page_node import validate_spreadsheet_page_node
from nodes.spreadsheet.extract_spreadsheet_data_node import extract_spreadsheet_data_node

# Processing nodes
from nodes.processing.process_invoice_rows_node import process_invoice_rows_node
from nodes.processing.iterate_rows_node import iterate_rows_node
from nodes.processing.transform_row_node import transform_row_node
from nodes.processing.fill_invoice_node import fill_invoice_node
from nodes.processing.update_status_node import update_status_node
from nodes.processing.update_spreadsheet_node import update_spreadsheet_node




from nodes.email.email_config_fail import email_failure_node
from nodes.processing.process_complete_node import process_complete_node
# ============================================
# Conditional Edge Functions
# ============================================


# workflow_graph.py

def after_validate_odoo(state: WorkflowGraphState) -> str:
    """Route after Odoo validation - reads from workflow"""
    workflows = state.get("workflows", [])
    max_retries = state.get("global_settings", {}).get("max_retries", 3)
    
    # Find Odoo workflow
    odoo_workflow = None
    for wf in workflows:
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "odoo_tab" or wf.get("name") == "odoo_invoice_creation":
            odoo_workflow = wf
            break
    
    if not odoo_workflow:
        return "email"
    
    odoo_valid = odoo_workflow.get("page_valid", False)
    retry_count = odoo_workflow.get("retry_count", 0)
    
    if odoo_valid:
        print(f"\n  ✅ Odoo validation passed, continuing to spreadsheet...")
        return "setup_spreadsheet"
    
    if retry_count > max_retries:
        print(f"\n  ❌ Odoo validation failed after {max_retries} attempts")
        print(f"  🛑 Max retries exhausted, stopping workflow")
        return "email"
    
    print(f"\n  ⚠️  Odoo validation failed")
    print(f"  🔄 Retry {retry_count}/{max_retries} - looping back to setup_odoo")
    
    return "setup_odoo"


def after_validate_spreadsheet(state: WorkflowGraphState) -> str:
    """Route after Spreadsheet validation - reads from workflow"""
    workflows = state.get("workflows", [])
    max_retries = state.get("global_settings", {}).get("max_retries", 3)
    
    # Find Spreadsheet workflow
    spreadsheet_workflow = None
    for wf in workflows:
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "spreadsheet_tab" or wf.get("name") == "sharepoint_crm_navigation":
            spreadsheet_workflow = wf
            break
    
    if not spreadsheet_workflow:
        return "email"
    
    spreadsheet_valid = spreadsheet_workflow.get("page_valid", False)
    retry_count = spreadsheet_workflow.get("retry_count", 0)
    
    if spreadsheet_valid:
        print(f"\n  ✅ Spreadsheet validation passed, continuing to extraction...")
        return "extract_data"
    
    if retry_count > max_retries:
        print(f"\n  ❌ Spreadsheet validation failed after {max_retries} attempts")
        print(f"  🛑 Max retries exhausted, stopping workflow")
        return "email"
    
    print(f"\n  ⚠️  Spreadsheet validation failed")
    print(f"  🔄 Retry {retry_count}/{max_retries} - looping back to setup_spreadsheet")
    
    return "setup_spreadsheet"




# workflow_graph.py - Update conditional function

# def after_transform_row(state: WorkflowGraphState) -> str:
#     """Route after transformation - either fill invoice or skip to next row"""
#     workflows = state.get("workflows", [])
    
#     spreadsheet_workflow = None
#     for wf in workflows:
#         tab_ref = wf.get("tab_config", {}).get("tab_reference")
#         if tab_ref == "spreadsheet_tab" or wf.get("name") == "sharepoint_crm_navigation":
#             spreadsheet_workflow = wf
#             break
    
#     if not spreadsheet_workflow:
#         return "end"
    
#     transformation_skipped = spreadsheet_workflow.get("transformation_skipped", False)
    
#     if transformation_skipped:
#         print(f"\n  ⏭️  Transformation failed - skipping to next row")
#         return "iterate_rows"  # Skip back to iterator for next row
#     else:
#         print(f"\n  ➡️  Transformation successful - proceeding to fill invoice")
#         return "fill_invoice"
    
    
# workflow_graph.py - Add conditional function

def after_iterate_rows(state: WorkflowGraphState) -> str:
    """
    Route after iterating rows:
    - If global error → email
    - If complete → process_complete
    - If row available → transform_row
    - Otherwise → email (invalid state)
    """

    # Global failure check
    if state.get("error_message"):
        print("\n  ❌ Error detected - routing to email_failure")
        return "email"

    workflows = state.get("workflows", [])

    # Find Spreadsheet workflow
    spreadsheet_workflow = None
    for wf in workflows:
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "spreadsheet_tab" or wf.get("name") == "sharepoint_crm_navigation":
            spreadsheet_workflow = wf
            break

    if not spreadsheet_workflow:
        print("\n  ❌ Spreadsheet workflow missing - routing to email_failure")
        return "email"

    processing_complete = spreadsheet_workflow.get("processing_complete", False)
    current_row = spreadsheet_workflow.get("current_row")

    if processing_complete:
        print("\n  ✅ All rows processed")
        return "process_complete"

    if current_row:
        print("\n  ➡️ Row ready - proceeding to transform")
        return "transform_row"

    print("\n  ❌ Invalid state - no row and not complete")
    return "email"





def after_transform_row(state: WorkflowGraphState) -> str:
    """Route after transformation - either fill invoice or skip to next row"""
    workflows = state.get("workflows", [])
    
    spreadsheet_workflow = None
    for wf in workflows:
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "spreadsheet_tab" or wf.get("name") == "sharepoint_crm_navigation":
            spreadsheet_workflow = wf
            break
    
    if not spreadsheet_workflow:
        return "iterate_rows"
    
    transformation_skipped = spreadsheet_workflow.get("transformation_skipped", False)
    
    if transformation_skipped:
        print(f"\n  ⏭️  Transformation failed - skipping to next row")
        return "iterate_rows"
    else:
        print(f"\n  ➡️  Transformation successful - proceeding to fill invoice")
        return "fill_invoice"


def after_fill_invoice(state: WorkflowGraphState) -> str:
    """Route after invoice creation"""
    current_step = state.get("current_step")
    
    if current_step == "invoice_created_needs_spreadsheet_update":
        print(f"\n  ➡️  Invoice created - updating spreadsheet")
        return "update_spreadsheet"
    elif current_step == "fill_invoice_failed_continue" or current_step == "fill_invoice_failed":
        print(f"\n  ⏭️  Invoice creation failed - skipping to next row")
        return "iterate_rows"
    elif current_step == "setup_odoo":
        print(f"\n  🔄 Not on invoice page - going back to setup Odoo")
        return "setup_odoo"
    else:
        print(f"\n  ⚠️  Unexpected state: {current_step}")
        return "iterate_rows"

def after_update_spreadsheet(state: WorkflowGraphState) -> str:
    """Route after spreadsheet update - always continue to next row"""
    print(f"\n  ➡️  Continuing to next row")
    return "iterate_rows"





def after_load_config(state: WorkflowGraphState) -> str:
    if state.get("error_message"):
        return "email"
    return "check_browser"


def after_check_browser(state: WorkflowGraphState) -> str:
    if state.get("error_message"):
        return "email"
    return "connect_browser"


def after_connect_browser(state: WorkflowGraphState) -> str:
    if state.get("error_message"):
        return "email"
    return "create_tabs"

def after_create_tabs(state: WorkflowGraphState) -> str:
    if state.get("error_message"):
        return "email"
    return "setup_odoo"





def after_extract_data(state: WorkflowGraphState) -> str:
    """
    Route after extraction:
    - If success → iterate_rows
    - If failure → retry validation (max 3)
    - If retries exhausted → email
    """
    
    workflows = state.get("workflows", [])
    max_retries = state.get("global_settings", {}).get("max_retries", 3)

    # Find spreadsheet workflow
    spreadsheet_workflow = None
    for wf in workflows:
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "spreadsheet_tab" or wf.get("name") == "sharepoint_crm_navigation":
            spreadsheet_workflow = wf
            break

    if not spreadsheet_workflow:
        return "email"

    extraction_complete = spreadsheet_workflow.get("extraction_complete", False)
    retry_count = spreadsheet_workflow.get("extraction_retry_count", 0)

    if extraction_complete:
        print("\n  ✅ Extraction successful — moving to iteration")
        return "iterate_rows"

    if retry_count >= max_retries:
        print(f"\n  ❌ Extraction failed after {max_retries} attempts")
        print("  📧 Routing to email_failure")
        return "email"

    print(f"\n  ⚠️ Extraction failed")
    print(f"  🔄 Retry {retry_count}/{max_retries}")
    print("  ↩ Returning to validate_spreadsheet")

    return "validate_spreadsheet"


# ============================================
# Build Graph
# ============================================




def build_graph():
    graph = StateGraph(WorkflowGraphState)
    
    # ============================================
    # SETUP PHASE - Sequential
    # ============================================
    graph.add_node("load_config", load_config_node)
    graph.add_node("check_browser", check_browser_connection_node)
    graph.add_node("connect_browser", connect_browser_node)
    graph.add_node("create_tabs", create_workflow_tabs_node)
    
    # ============================================
    # ODOO WORKFLOW - Sequential Track 1
    # ============================================
    graph.add_node("setup_odoo", setup_odoo_node)
    graph.add_node("validate_odoo", validate_odoo_page_node)
    graph.add_node("process_complete", process_complete_node)


    
    # ============================================
    # SPREADSHEET WORKFLOW - Sequential Track 2
    # ============================================
    graph.add_node("setup_spreadsheet", setup_spreadsheet_node)
    graph.add_node("validate_spreadsheet", validate_spreadsheet_page_node)
    
    # ============================================
    # DATA EXTRACTION
    # ============================================
    graph.add_node("extract_data", extract_spreadsheet_data_node)
    
    # ============================================
    # PROCESSING LOOP
    # ============================================
    graph.add_node("iterate_rows", iterate_rows_node)
    graph.add_node("transform_row", transform_row_node)
    graph.add_node("fill_invoice", fill_invoice_node)
    graph.add_node("update_spreadsheet", update_spreadsheet_node)
    graph.add_node("email_failure", email_failure_node)

    
    # ============================================
    # EDGES - Setup Phase (Sequential)
    # ============================================
    graph.add_edge(START, "load_config")
    graph.add_conditional_edges(
        "load_config",
        after_load_config,
        {
            "check_browser": "check_browser",
            "email": "email_failure"
        }
    )
    
    
    graph.add_conditional_edges(
        "check_browser",
        after_check_browser,
        {
            "connect_browser": "connect_browser",
            "email": "email_failure"
        }
    )

    
    graph.add_conditional_edges(
        "connect_browser",
        after_connect_browser,
        {
            "create_tabs": "create_tabs",
            "email": "email_failure"
        }
    )

    # graph.add_edge("update_spreadsheet", END)
    
    # ============================================
    # EDGES - Sequential Execution
    # ============================================
    
    # After tabs created → setup Odoo first
    graph.add_edge("create_tabs", "setup_odoo")
    
    # Odoo setup → validate Odoo
    graph.add_edge("setup_odoo", "validate_odoo")
    
    # Validate Odoo → conditional (loop back or continue or stop)
    graph.add_conditional_edges(
        "validate_odoo",
        after_validate_odoo,
        {
            "setup_odoo": "setup_odoo",              # Loop back if invalid (retry available)
            "setup_spreadsheet": "setup_spreadsheet", # Continue if valid
            "email": "email_failure"                                # Stop if max retries exhausted
        }
    )
    
    # Spreadsheet setup → validate Spreadsheet
    graph.add_edge("setup_spreadsheet", "validate_spreadsheet")
    
    # Validate Spreadsheet → conditional (loop back or continue or stop)
    graph.add_conditional_edges(
        "validate_spreadsheet",
        after_validate_spreadsheet,
        {
            "setup_spreadsheet": "setup_spreadsheet", # Loop back if invalid (retry available)
            "extract_data": "extract_data",           # Continue if valid
            "email": "email_failure"                                 # Stop if max retries exhausted
        }
    )
    
    # ============================================
    # EDGES - Data Extraction & Processing Loop
    # ============================================
    
    # Extract data → Start iteration
    graph.add_edge("extract_data", "iterate_rows")
    
    graph.add_conditional_edges(
        "extract_data",
        after_extract_data,
        {
            "iterate_rows": "iterate_rows",
            "validate_spreadsheet": "validate_spreadsheet",
            "email": "email_failure"
        }
    )
        
    # Iterate rows → conditional (has rows or done)
    graph.add_conditional_edges(
        "iterate_rows",
        after_iterate_rows,
        {
            "transform_row": "transform_row",
            "process_complete": "process_complete",
            "email": "email_failure"
        }
    )

    # Transform row → conditional (success or skip)
    graph.add_conditional_edges(
        "transform_row",
        after_transform_row,
        {
            "fill_invoice": "fill_invoice",     # Transformation successful
            "iterate_rows": "iterate_rows"      # Transformation failed/skipped - next row
        }
    )
    
    # Fill invoice → conditional (success or failure)
    graph.add_conditional_edges(
        "fill_invoice",
        after_fill_invoice,
        {
            "update_spreadsheet": "update_spreadsheet",  # Invoice created - update sheet
            "iterate_rows": "iterate_rows",               # Invoice failed - next row
            "setup_odoo": "setup_odoo"
        }
    )
    
    # Update spreadsheet → always back to iterate
    graph.add_conditional_edges(
        "update_spreadsheet",
        after_update_spreadsheet,
        {
            "iterate_rows": "iterate_rows"  # Always continue to next row
        }
    )
    
    graph.add_edge("process_complete", END)
    return graph.compile()



# def build_graph():
#     graph = StateGraph(WorkflowGraphState)
    
#     # ============================================
#     # SETUP PHASE - Sequential
#     # ============================================
#     graph.add_node("load_config", load_config_node)
#     graph.add_node("check_browser", check_browser_connection_node)
#     graph.add_node("connect_browser", connect_browser_node)
#     graph.add_node("create_tabs", create_workflow_tabs_node)
    
#     # ============================================
#     # TEST NODE
#     # ============================================
#     graph.add_node("update_spreadsheet", update_spreadsheet_node)
    
#     # ============================================
#     # EDGES - Setup Phase (Sequential)
#     # ============================================
#     graph.add_edge(START, "load_config")
#     graph.add_edge("load_config", "check_browser")
#     graph.add_edge("check_browser", "connect_browser")
#     graph.add_edge("connect_browser", "create_tabs")
    
#     # ============================================
#     # TEST: Jump directly to update_spreadsheet
#     # ============================================
#     graph.add_edge("create_tabs", "update_spreadsheet")
#     graph.add_edge("update_spreadsheet", END)
    
#     return graph.compile()

# # run_graph.py
import asyncio
from browser_use import Tools



async def run_workflow(config_file_path: str = "config.json"):
    """Run the complete workflow graph from the beginning"""
    
    print("="*60)
    print("WORKFLOW EXECUTION ENGINE")
    print("="*60)
    
    # Build graph
    print("\n[1] Building graph...")
    graph = build_graph()
    print("✓ Graph built")
    
    # Initial state
    initial_state: WorkflowGraphState = {
        "odoo_retry_count": 2,
        "spreadsheet_retry_count": 2,
        "config_file_path": config_file_path,
        "full_config": None,
        "browser_connection_url": None,
        "browser_accessible": False,
        "browser_instance": None,
        "tools": Tools(),
        "workflows": None,
        "global_settings": None,
        "current_workflow_index": 0,
        "current_step_index": 0,
        "workflow_results": {},
        "execution_paused": False,
        "pause_reason": None,
        "resume_from_step": None,
        "requires_human_intervention": False,
        "intervention_data": None,
        "error_message": None,
        "current_step": "start",
        
    }
    
    # Run graph
    print(f"\n[2] Running graph with config: {config_file_path}\n")
    result = await graph.ainvoke(initial_state)
    
    # Print results
    return result


async def resume_workflow(paused_state: WorkflowGraphState, resume_from_step: int = None):
    """
    Resume a paused workflow
    
    Args:
        paused_state: The state that was paused
        resume_from_step: Optional step index to resume from (overrides current position)
    """
    
    print("="*60)
    print("RESUMING WORKFLOW")
    print("="*60)
    
    # Validate state
    if not paused_state.get("execution_paused"):
        print("⚠️  State is not paused. Use run_workflow() instead.")
        return paused_state
    
    # Set resume point if specified
    if resume_from_step is not None:
        paused_state["resume_from_step"] = resume_from_step
        print(f"▶️  Will resume from step index: {resume_from_step}")
    
    # Build graph and resume
    graph = build_graph()
    
    # Call execute_workflows_node directly since we're already setup
    result = await execute_workflows_node(paused_state)
    
    # Print results
    print_results(result)
    
    return result


def print_results(result: WorkflowGraphState):
    """Print execution results"""
    
    print("\n" + "="*60)
    print("EXECUTION RESULTS")
    print("="*60)
    
    print(f"\nFinal State: {result.get('current_step')}")
    print(f"Error: {result.get('error_message', 'None')}")
    
    if result.get("execution_paused"):
        print(f"\n⏸️  PAUSED")
        print(f"Reason: {result.get('pause_reason')}")
        if result.get("intervention_data"):
            intervention = result["intervention_data"]
            print(f"Workflow: {intervention.get('workflow_name')}")
            print(f"Step: {intervention.get('step_name')} (index {intervention.get('step_index')})")
            print(f"\n💡 To resume, call: await resume_workflow(result)")
            print(f"💡 To resume from different step: await resume_workflow(result, resume_from_step=5)")
    
    # Print workflow results
    workflow_results = result.get("workflow_results", {})
    if workflow_results:
        print(f"\n{'='*60}")
        print("WORKFLOW RESULTS")
        print("="*60)
        
        for workflow_name, workflow_result in workflow_results.items():
            status = workflow_result.get("status")
            status_icon = {
                "completed": "✅",
                "failed": "❌",
                "paused": "⏸️",
                "skipped": "⏭️",
                "running": "🔄"
            }.get(status, "❓")
            
            print(f"\n{status_icon} {workflow_name}")
            print(f"   Status: {status}")
            print(f"   Steps Completed: {workflow_result.get('steps_completed')}")
            print(f"   Steps Failed: {workflow_result.get('steps_failed')}")




# Run
if __name__ == "__main__":
    result = asyncio.run(run_workflow("config.json"))
    
    # If paused, can resume like this:
    # result = asyncio.run(resume_workflow(result))