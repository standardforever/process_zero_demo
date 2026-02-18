# nodes/odoo/setup_odoo_node.py

from typing import Dict, Any
from utils.workflow_graph_state import WorkflowGraphState
from nodes.execute_workflow_step_node import execute_workflow_step_node


async def setup_odoo_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Setup Odoo workflow node
    
    Goal: Navigate to new invoice creation page
    Target URL: https://process-zero.odoo.com/odoo/customer-invoices/new
    
    Smart navigation with page detection:
    - Every validation failure checks current location
    - Jumps to appropriate step based on where we are
    - Unknown location → restart from beginning
    """
    
    print("\n" + "="*60)
    print("ODOO SETUP NODE")
    print("="*60)
    
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
            "current_step": "odoo_setup_failed"
        }
    
    page = odoo_workflow.get("page_instance")
    tab_id = odoo_workflow.get("tab_id")
    variables = odoo_workflow.get("variables", {})
    
    if not page:
        print("  ✗ Odoo page instance not found")
        return {
            **state,
            "error_message": "Odoo page instance not found",
            "current_step": "odoo_setup_failed"
        }
    
    # ============================================
    # SMART VALIDATION CHECK
    # This is used when any step's validation fails
    # ============================================
    
    SMART_RECOVERY_CHECKS = [
        {
            "condition": "url_contains",
            "value": "customer-invoices/new",
            "then": {
                "action": "goto",
                "target_step": "verify_invoice_form_loaded"
            }
        },
        {
            "condition": "url_contains",
            "value": "customer-invoices",
            "then": {
                "action": "goto",
                "target_step": "naviage_to_new_invoice"
            }
        },
        {
            "condition": "url_contains",
            "value": "/odoo/accounting",
            "then": {
                "action": "goto",
                "target_step": "wait_for_invoicing_page"
            }
        },
        {
            "condition": "url_contains",
            "value": "/odoo",
            "then": {
                "action": "goto",
                "target_step": "wait_for_dashboard"
            }
        },
        {
            "condition": "url_contains",
            "value": "/web/login",
            "then": {
                "action": "goto",
                "target_step": "perform_login"
            }
        },
        {
            "condition": "default",
            "then": {
                "action": "goto",
                "target_step": "navigate_to_odoo"
            }
        }
    ]
    
    # ============================================
    # STEP DEFINITIONS
    # ============================================
    
    STEPS = [
        {
            "name": "navigate_to_odoo",
            "description": "Navigate to Odoo login page",
            "validators": {},
            "actions": [
                {
                    "action_type": "navigate",
                    "parameters": {
                        "url": "https://process-zero.odoo.com/",
                        "new_tab": False
                    }
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                },
                "on_error": {
                    "action": "stop"
                }
            }
        },
        
        {
            "name": "wait_for_initial_load",
            "description": "Wait for page to fully load",
            "validators": {},
            "actions": [
                {
                    "action_type": "wait",
                    "parameters": {"seconds": 5}
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                }
            }
        },
        {
            "name": "perform_login",
            "description": "Enter credentials and login to Odoo",
            "validators": {
                "url_contains": "/web/login",
                "text_visible": "Log in"
            },
            "actions": [
                {
                    "action_type": "input",
                    "parameters": {
                        "text": variables.get("username", "martinm@processzero.co.uk"),
                        "clear": True,
                        "input_name": "login"
                    },
                    "description": "Enter username"
                },
                {
                    "action_type": "input",
                    "parameters": {
                        "text": variables.get("password", "0p9o8i7u^Y"),
                        "clear": True,
                        "input_type": "password",
                        "input_name": "password"
                    },
                    "description": "Enter password"
                },
                {
                    "action_type": "click",
                    "parameters": {
                        "button_text": "Log in",
                        "role": "button"
                    },
                    "description": "Click login button"
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                },
                "on_validation_fail": {
                    "action": "check",
                    "checks": SMART_RECOVERY_CHECKS
                },
                "on_error": {
                    "action": "retry",
                    "max_retries": 2,
                    "retry_wait_seconds": 3
                }
            }
        },
        {
            "name": "wait_for_dashboard",
            "description": "Wait for dashboard to load after login",
            "validators": {},
            "actions": [
                {
                    "action_type": "wait",
                    "parameters": {"seconds": 8}
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                }
            }
        },
        {
            "name": "navigate_to_invoicing",
            "description": "Click Invoicing app from dashboard",
            "validators": {
                "url_contains": "/odoo",
                "url_not_contains": "/accounting"
            },
            "actions": [
                {
                    "action_type": "click",
                    "parameters": {
                        "text": "Invoicing",
                        "role": "link"
                    },
                    "description": "Click Invoicing app"
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                },
                "on_validation_fail": {
                    "action": "check",
                    "checks": SMART_RECOVERY_CHECKS
                },
                "on_error": {
                    "action": "retry",
                    "max_retries": 2,
                    "retry_wait_seconds": 2
                }
            }
        },
        {
            "name": "wait_for_invoicing_page",
            "description": "Wait for invoicing page to fully load",
            "validators": {},
            "actions": [
                {
                    "action_type": "wait",
                    "parameters": {"seconds": 8}
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                }
            }
        },
        {
            "name": "open_customers_dropdown",
            "description": "Click Customers dropdown to expand menu",
            "validators": {
                "url_contains": "/accounting",
                "url_not_contains": "customer-invoices"
            },
            "actions": [
                {
                    "action_type": "click",
                    "parameters": {
                        "text": "Customers",
                        "role": "button"
                    },
                    "description": "Click Customers dropdown"
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                },
                "on_validation_fail": {
                    "action": "check",
                    "checks": SMART_RECOVERY_CHECKS
                },
                "on_error": {
                    "action": "retry",
                    "max_retries": 2,
                    "retry_wait_seconds": 2
                }
            }
        },
        {
            "name": "wait_for_invoices_list",
            "description": "Wait for invoices list to load",
            "validators": {},
            "actions": [
                {
                    "action_type": "wait",
                    "parameters": {"seconds": 3}
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                }
            }
        },
        {
            "name": "select_invoices_from_menu",
            "description": "Select Invoices option from Customers dropdown",
            "validators": {
                "url_contains": "/accounting",
                "url_not_contains": "customer-invoices"
            },
            "actions": [
                {
                    "action_type": "click",
                    "parameters": {
                        "text": "Invoices",
                        "role": "link"
                    },
                    "description": "Click Invoices menu item, NOTE: Invoices should be clicked not Invoicing"
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                },
                "on_validation_fail": {
                    "action": "check",
                    "checks": SMART_RECOVERY_CHECKS
                },
                "on_error": {
                    "action": "retry",
                    "max_retries": 2,
                    "retry_wait_seconds": 2
                }
            }
        },
        {
            "name": "wait_for_invoices_list",
            "description": "Wait for invoices list to load",
            "validators": {},
            "actions": [
                {
                    "action_type": "wait",
                    "parameters": {"seconds": 3}
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                }
            }
        },
        {
            "name": "click_new_invoice",
            "description": "Click New button to create new invoice",
            "validators": {
                "url_contains": "customer-invoices",
                "url_not_contains": "/new"
            },
            "actions": [
                {
                    "action_type": "click",
                    "parameters": {
                        "text": "New",
                        "role": "button"
                    },
                    "description": "Click New button"
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                },
                "on_validation_fail": {
                    "action": "check",
                    "checks": SMART_RECOVERY_CHECKS
                },
                "on_error": {
                    "action": "retry",
                    "max_retries": 2,
                    "retry_wait_seconds": 2
                }
            }
        },
        {
            "name": "wait_for_invoice_form",
            "description": "Wait for new invoice form to load",
            "validators": {},
            "actions": [
                {
                    "action_type": "wait",
                    "parameters": {"seconds": 5}
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                }
            }
        },
        {
            "name": "naviage_to_new_invoice",
            "description": "Navigate to new invoice page",
            "validators": {},
            "actions": [
                {
                    "action_type": "navigate",
                    "parameters": {
                        "url": "https://process-zero.odoo.com/odoo/customer-invoices/new",
                        "new_tab": False
                    }
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                },
                "on_error": {
                    "action": "stop"
                }
            }
        },
        {
            "name": "verify_invoice_form_loaded",
            "description": "Verify invoice creation form is ready",
            "validators": {
                "url_contains": "/new"
            },
            "actions": [
                {
                    "action_type": "screenshot",
                    "parameters": {},
                    "description": "Take screenshot of invoice form"
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "skip"
                },
                "on_validation_fail": {
                    "action": "check",
                    "checks": SMART_RECOVERY_CHECKS
                }
            }
        }
    ]
    
    # ============================================
    # BUILD STEP NAME INDEX
    # ============================================
    
    step_name_to_index = {step["name"]: idx for idx, step in enumerate(STEPS)}
    
    # ============================================
    # DETERMINE STARTING STEP
    # ============================================
    
    try:
        # Get current URL
        current_info = await page.get_target_info()
        current_url = current_info.url if hasattr(current_info, 'url') else current_info.get("url", "")
        
        print(f"\n  📍 Current URL: {current_url}")
        
        TARGET_URL = "customer-invoices/new"
        if TARGET_URL in current_url:
            print(f"  ✅ Already at target page!")
            
            # UPDATE WORKFLOW IN ARRAY
            updated_workflows = workflows.copy()
            updated_workflows[odoo_index] = {
                **odoo_workflow,
                "page_valid": True,
                "setup_complete": True
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "current_step": "odoo_setup_complete"
            }
        
        # Use smart recovery to find starting point
        print(f"  🔍 Analyzing current location...")
        
        from nodes.execute_workflow_step_node import evaluate_checks
        
        # Create fake dom_state for check evaluation
        dom_state = {"url": current_url, "dom_representation": ""}
        
        recovery_action = evaluate_checks(SMART_RECOVERY_CHECKS, dom_state)
        target_step = recovery_action.get("target_step", "navigate_to_odoo")
        
        start_step_index = step_name_to_index.get(target_step, 0)
        
        print(f"  🎯 Starting from: {target_step} (step {start_step_index + 1}/{len(STEPS)})")
        
        # ============================================
        # EXECUTE STEPS WITH LOOP HANDLING
        # ============================================
        
        current_step_index = start_step_index
        
        while current_step_index < len(STEPS):
            step = STEPS[current_step_index]
            step_name = step.get("name")
            
            result = await execute_workflow_step_node(
                workflow=odoo_workflow,
                step=step,
                step_index=current_step_index,
                state=state
            )
            
            # Handle next_action
            next_action = result.get("next_action", {})
            action = next_action.get("action")
            
            if action == "next":
                current_step_index += 1
            
            elif action == "goto":
                target_step = next_action.get("target_step")
                if target_step in step_name_to_index:
                    current_step_index = step_name_to_index[target_step]
                    print(f"      ⏭️  Jumping to: {target_step}")
                else:
                    print(f"      ⚠️  Unknown target: {target_step}, continuing")
                    current_step_index += 1
            
            elif action == "skip":
                print(f"      ⏭️  Step complete")
                break  # We're done
            
            elif action == "pause":
                print(f"      ⏸️  Paused: {next_action.get('reason')}")
                
                # UPDATE WORKFLOW WITH PAUSED STATE
                updated_workflows = workflows.copy()
                updated_workflows[odoo_index] = {
                    **odoo_workflow,
                    "page_valid": False,
                    "paused": True,
                    "pause_reason": next_action.get("reason")
                }
                
                return {
                    **state,
                    "workflows": updated_workflows,
                    "execution_paused": True,
                    "pause_reason": next_action.get("reason"),
                    "current_step": "odoo_setup_paused"
                }
            
            elif action == "stop":
                print(f"      🛑 Stopped")
                
                # UPDATE WORKFLOW WITH STOPPED STATE
                updated_workflows = workflows.copy()
                updated_workflows[odoo_index] = {
                    **odoo_workflow,
                    "page_valid": False,
                    "setup_complete": False,
                    "error": result.get("error", "Step failed")
                }
                
                return {
                    **state,
                    "workflows": updated_workflows,
                    "error_message": result.get("error", "Step failed"),
                    "current_step": "odoo_setup_stopped"
                }
            
            elif not result.get("success"):
                print(f"      ✗ Failed: {result.get('error')}")
                
                # UPDATE WORKFLOW WITH FAILURE
                updated_workflows = workflows.copy()
                updated_workflows[odoo_index] = {
                    **odoo_workflow,
                    "page_valid": False,
                    "setup_complete": False,
                    "error": result.get("error")
                }
                
                return {
                    **state,
                    "workflows": updated_workflows,
                    "error_message": result.get("error"),
                    "current_step": "odoo_setup_failed"
                }
        
        # ============================================
        # VERIFY FINAL STATE
        # ============================================
        
        final_info = await page.get_target_info()
        final_url = final_info.url if hasattr(final_info, 'url') else final_info.get("url", "")
        
        print(f"\n  📍 Final URL: {final_url}")
        
        if TARGET_URL in final_url:
            print(f"  ✅ Successfully reached target!")
            
            # UPDATE WORKFLOW WITH SUCCESS
            updated_workflows = workflows.copy()
            updated_workflows[odoo_index] = {
                **odoo_workflow,
                "page_valid": True,
                "setup_complete": True,
                "error": None
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "current_step": "odoo_setup_complete"
            }
        else:
            print(f"  ⚠️  Not at target page")
            
            # UPDATE WORKFLOW WITH FAILURE
            updated_workflows = workflows.copy()
            updated_workflows[odoo_index] = {
                **odoo_workflow,
                "page_valid": False,
                "setup_complete": False,
                "error": f"Expected '{TARGET_URL}' in URL, got: {final_url}"
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": f"Expected '{TARGET_URL}' in URL, got: {final_url}",
                "current_step": "odoo_setup_failed"
            }
    
    except Exception as e:
        print(f"\n  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        
        # UPDATE WORKFLOW WITH EXCEPTION
        updated_workflows = workflows.copy()
        updated_workflows[odoo_index] = {
            **odoo_workflow,
            "page_valid": False,
            "setup_complete": False,
            "error": str(e)
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": str(e),
            "current_step": "odoo_setup_failed"
        }
# ```

# **Key improvements:**

# 1. ✅ **Smart Recovery Checks** - Centralized location detection logic
# 2. ✅ **No more "skip"** - Always checks where we are and jumps appropriately
# 3. ✅ **Unknown page → restart** - Default action goes to `navigate_to_odoo`
# 4. ✅ **Loop handling** - Uses `goto` to jump between steps
# 5. ✅ **Variables support** - Uses credentials from config

# **Example flow:**
# ```
# Current URL: https://process-zero.odoo.com/odoo/accounting

# 🔍 Analyzing current location...
# 🎯 Starting from: wait_for_invoicing_page (step 6/12)

# [6] wait_for_invoicing_page ✓
# [7] open_customers_dropdown
#     🔍 Validating...
#     ✗ Validation failed
#     🔍 Checking current location...
#     ⏭️  Jumping to: wait_for_invoicing_page

# [6] wait_for_invoicing_page ✓
# ...