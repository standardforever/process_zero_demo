from utils.workflow_graph_state import WorkflowGraphState


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
    current_step = state.get("current_step")
    
    spreadsheet_workflow = None
    for wf in workflows:
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "spreadsheet_tab" or wf.get("name") == "sharepoint_crm_navigation":
            spreadsheet_workflow = wf
            break
    
    if not spreadsheet_workflow:
        print("\n  ❌ Spreadsheet workflow missing - routing to email_failure")
        return "email"
    
    transformation_skipped = spreadsheet_workflow.get("transformation_skipped", False)
    
    if transformation_skipped or current_step == "transformation_failed":
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

















