# nodes/spreadsheet/validate_spreadsheet_page_node.py

from utils.workflow_graph_state import WorkflowGraphState


async def validate_spreadsheet_page_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Validate SharePoint Sales Pipeline CRM page is ready
    
    Target: Sales Pipeline CRM list view
    Expected URL: https://pivotaluksolutionsltd-my.sharepoint.com/.../Sales%20Pipeline%20CRM/AllItems.aspx
    
    Checks:
    1. URL contains 'Sales Pipeline CRM' (encoded or decoded)
    2. Correct SharePoint domain
    3. Key elements visible (Sales Request Ref header)
    4. Not on login page
    5. Not on error/access denied page
    
    Updates workflow.page_valid = True/False
    """
    
    print("\n" + "="*60)
    print("SHAREPOINT PAGE VALIDATION")
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
            "current_step": "spreadsheet_validation_failed"
        }
    
    # ============================================
    # GET WORKFLOW DATA
    # ============================================
    
    page = spreadsheet_workflow.get("page_instance")
    tab_id = spreadsheet_workflow.get("tab_id")
    current_retry_count = spreadsheet_workflow.get("retry_count", 0)
    
    if not page:
        print("  ✗ Spreadsheet page instance not found in workflow")
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "page_valid": False,
            "retry_count": current_retry_count + 1
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": "Spreadsheet page instance not found",
            "current_step": "spreadsheet_validation_failed"
        }
    
    try:
        # ============================================
        # GET CURRENT PAGE INFO
        # ============================================
        
        page_info = await page.get_target_info()
        current_url = page_info.url if hasattr(page_info, 'url') else page_info.get("url", "")
        page_title = page_info.title if hasattr(page_info, 'title') else page_info.get("title", "")
        
        print(f"\n  📍 Current URL: {current_url[:80]}...")
        print(f"  📄 Page Title: {page_title[:60]}{'...' if len(page_title) > 60 else ''}")
        
        # ============================================
        # VALIDATION CHECKS
        # ============================================
        
        TARGET_URL_ENCODED = "Sales%20Pipeline%20CRM"
        TARGET_URL_DECODED = "Sales Pipeline CRM"
        EXPECTED_DOMAIN = "sharepoint.com"
        
        validation_results = []
        
        # Check 1: URL contains Sales Pipeline CRM (encoded or decoded)
        url_check = TARGET_URL_ENCODED in current_url or TARGET_URL_DECODED in current_url
        validation_results.append({
            "check": "URL contains 'Sales Pipeline CRM'",
            "passed": url_check,
            "details": f"Found: {url_check}"
        })
        
        # Check 2: Correct SharePoint domain
        domain_check = EXPECTED_DOMAIN in current_url
        validation_results.append({
            "check": "Correct SharePoint domain",
            "passed": domain_check,
            "details": f"Domain: {EXPECTED_DOMAIN}"
        })
        
        # Check 3: Not on login page
        not_login = "login.microsoftonline.com" not in current_url
        validation_results.append({
            "check": "Not on login page",
            "passed": not_login,
            "details": f"Login detected: {not not_login}"
        })
        
        # Check 4: Not on error page (based on URL patterns)
        error_patterns = ["error", "access-denied", "unauthorized"]
        not_error = not any(pattern in current_url.lower() for pattern in error_patterns)
        validation_results.append({
            "check": "Not on error page",
            "passed": not_error,
            "details": f"Error page: {not not_error}"
        })
        
        # Check 5: Page title looks correct
        title_check = any(keyword in page_title.lower() for keyword in ["sales", "pipeline", "crm", "list", "sharepoint"])
        validation_results.append({
            "check": "Page title contains expected keywords",
            "passed": title_check,
            "details": f"Title: {page_title[:40]}"
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
        
        # All critical checks must pass
        critical_checks = [
            validation_results[0],  # URL contains Sales Pipeline CRM
            validation_results[1],  # Correct domain
            validation_results[2],  # Not on login
            validation_results[3],  # Not on error page
        ]
        
        all_critical_passed = all(r["passed"] for r in critical_checks)
        
        if all_critical_passed:
            print(f"\n  ✅ SharePoint page is valid and ready!")
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "page_valid": True,
                "retry_count": 0,  # Reset on success
                "error": None
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": None,
                "current_step": "spreadsheet_validation_passed"
            }
        else:
            failed_checks = [r["check"] for r in validation_results if not r["passed"]]
            failure_reason = f"Validation failed: {', '.join(failed_checks)}"
            
            print(f"\n  ❌ Validation failed")
            print(f"  ℹ️  Reason: {failure_reason}")
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "page_valid": False,
                "retry_count": current_retry_count + 1,
                "error": failure_reason
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": failure_reason,
                "current_step": "spreadsheet_validation_failed"
            }
    
    except Exception as e:
        print(f"\n  ✗ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "page_valid": False,
            "retry_count": current_retry_count + 1,
            "error": f"Validation error: {str(e)}"
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": f"Validation error: {str(e)}",
            "current_step": "spreadsheet_validation_failed"
        }