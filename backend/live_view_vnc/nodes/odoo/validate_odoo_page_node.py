# nodes/odoo/validate_odoo_page_node.py

from utils.workflow_graph_state import WorkflowGraphState


async def validate_odoo_page_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Validate Odoo page is at the correct location and ready
    
    Target: New invoice creation form
    Expected URL: https://process-zero.odoo.com/odoo/customer-invoices/new
    
    Checks:
    1. URL contains 'customer-invoices/new'
    2. Page is accessible
    3. Correct domain
    4. Not on login page
    
    Updates workflow.page_valid = True/False
    """
    
    print("\n" + "="*60)
    print("ODOO PAGE VALIDATION")
    print("="*60)
    
    # ============================================
    # FIND ODOO WORKFLOW
    # ============================================
    
    workflows = state.get("workflows", [])
    odoo_workflow = None
    odoo_index = -1
    
    for idx, wf in enumerate(workflows):
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "odoo_tab" or wf.get("name") == "odoo_invoice_creation":
            odoo_workflow = wf
            odoo_index = idx
            break
    
    if not odoo_workflow:
        print("  ✗ Odoo workflow not found in state")
        return {
            **state,
            "error_message": "Odoo workflow not found",
            "current_step": "odoo_validation_failed"
        }
    
    # ============================================
    # GET WORKFLOW DATA
    # ============================================
    
    page = odoo_workflow.get("page_instance")
    tab_id = odoo_workflow.get("tab_id")
    current_retry_count = odoo_workflow.get("retry_count", 0)
    
    if not page:
        print("  ✗ Odoo page instance not found in workflow")
        
        # UPDATE WORKFLOW - INCREMENT RETRY
        updated_workflows = workflows.copy()
        updated_workflows[odoo_index] = {
            **odoo_workflow,
            "page_valid": False,
            "retry_count": current_retry_count + 1
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": "Odoo page instance not found",
            "current_step": "odoo_validation_failed"
        }
    
    try:
        # ============================================
        # GET CURRENT PAGE INFO
        # ============================================
        
        page_info = await page.get_target_info()
        current_url = page_info.url if hasattr(page_info, 'url') else page_info.get("url", "")
        page_title = page_info.title if hasattr(page_info, 'title') else page_info.get("title", "")
        
        print(f"\n  📍 Current URL: {current_url}")
        print(f"  📄 Page Title: {page_title}")
        
        # ============================================
        # VALIDATION CHECKS
        # ============================================
        
        TARGET_URL_PART = "customer-invoices/new"
        EXPECTED_DOMAIN = "process-zero.odoo.com"
        
        validation_results = []
        
        # Check 1: URL contains target path
        url_check = TARGET_URL_PART in current_url
        validation_results.append({
            "check": "URL contains 'customer-invoices/new'",
            "passed": url_check,
            "details": f"Found: {TARGET_URL_PART in current_url}"
        })
        
        # Check 2: Correct domain
        domain_check = EXPECTED_DOMAIN in current_url
        validation_results.append({
            "check": "Correct Odoo domain",
            "passed": domain_check,
            "details": f"Domain: {EXPECTED_DOMAIN}"
        })
        
        # Check 3: Not on login page
        not_login = "/web/login" not in current_url
        validation_results.append({
            "check": "Not on login page",
            "passed": not_login,
            "details": f"Login detected: {'/web/login' in current_url}"
        })
        
        # ============================================
        # PRINT VALIDATION RESULTS
        # ============================================
        
        print(f"\n  🔍 Validation Results:")
        for result in validation_results:
            icon = "✅" if result["passed"] else "❌"
            print(f"    {icon} {result['check']}")
            if not result["passed"]:
                print(f"       → {result['details']}")
        
        # ============================================
        # DETERMINE OVERALL VALIDITY
        # ============================================
        
        all_passed = all(r["passed"] for r in validation_results)
        
        if all_passed:
            print(f"\n  ✅ Odoo page is valid and ready!")
            
            # UPDATE WORKFLOW - SUCCESS
            updated_workflows = workflows.copy()
            updated_workflows[odoo_index] = {
                **odoo_workflow,
                "page_valid": True,
                "retry_count": 0,  # Reset on success
                "error": None
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": None,
                "current_step": "odoo_validation_passed"
            }
        else:
            failed_checks = [r["check"] for r in validation_results if not r["passed"]]
            failure_reason = f"Validation failed: {', '.join(failed_checks)}"
            
            print(f"\n  ❌ Validation failed")
            print(f"  ℹ️  Reason: {failure_reason}")
            
            # UPDATE WORKFLOW - FAILURE
            updated_workflows = workflows.copy()
            updated_workflows[odoo_index] = {
                **odoo_workflow,
                "page_valid": False,
                "retry_count": current_retry_count + 1,
                "error": failure_reason
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": failure_reason,
                "current_step": "odoo_validation_failed"
            }
    
    except Exception as e:
        print(f"\n  ✗ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        
        # UPDATE WORKFLOW - EXCEPTION
        updated_workflows = workflows.copy()
        updated_workflows[odoo_index] = {
            **odoo_workflow,
            "page_valid": False,
            "retry_count": current_retry_count + 1,
            "error": f"Validation error: {str(e)}"
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": f"Validation error: {str(e)}",
            "current_step": "odoo_validation_failed"
        }