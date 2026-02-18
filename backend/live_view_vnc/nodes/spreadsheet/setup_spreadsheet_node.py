# nodes/spreadsheet/setup_spreadsheet_node.py

from typing import Dict, Any
from utils.workflow_graph_state import WorkflowGraphState
from nodes.execute_workflow_step_node import execute_workflow_step_node


async def setup_spreadsheet_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Setup Spreadsheet workflow node
    
    Goal: Navigate to SharePoint Sales Pipeline CRM and authenticate
    Target URL: https://pivotaluksolutionsltd-my.sharepoint.com/.../Sales%20Pipeline%20CRM/AllItems.aspx
    
    Smart navigation with page detection:
    - Every validation failure checks current location
    - Jumps to appropriate step based on where we are
    - Handles Microsoft login flow (email → password → MFA → CRM)
    - Unknown location → restart from beginning
    """
    
    print("\n" + "="*60)
    print("SHAREPOINT SETUP NODE")
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
            "current_step": "spreadsheet_setup_failed"
        }
    
    page = spreadsheet_workflow.get("page_instance")
    tab_id = spreadsheet_workflow.get("tab_id")
    variables = spreadsheet_workflow.get("variables", {})
    
    if not page:
        print("  ✗ Spreadsheet page instance not found")
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "page_valid": False,
            "setup_complete": False,
            "error": "Page instance not found"
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": "Spreadsheet page instance not found",
            "current_step": "spreadsheet_setup_failed"
        }
    
    # ============================================
    # SMART VALIDATION CHECK
    # ============================================
    
    SMART_RECOVERY_CHECKS = [
        {
            "condition": "url_contains",
            "value": "Sales%20Pipeline%20CRM",
            "then": {
                "action": "goto",
                "target_step": "verify_crm_loaded"
            }
        },
        {
            "condition": "text_visible",
            "value": "Stay signed in",
            "then": {
                "action": "goto",
                "target_step": "handle_stay_signed_in"
            }
        },
        {
            "condition": "text_visible",
            "value": "Enter password",
            "then": {
                "action": "goto",
                "target_step": "enter_password"
            }
        },
        {
            "condition": "text_visible",
            "value": "Verify your identity",
            "then": {
                "action": "goto",
                "target_step": "handle_mfa_check"
            }
        },
        {
            "condition": "url_contains",
            "value": "login.microsoftonline.com",
            "then": {
                "action": "goto",
                "target_step": "enter_email"
            }
        },
        {
            "condition": "url_contains",
            "value": "sharepoint.com",
            "then": {
                "action": "goto",
                "target_step": "wait_for_sharepoint_load"
            }
        },
        {
            "condition": "default",
            "then": {
                "action": "goto",
                "target_step": "navigate_to_sharepoint"
            }
        }
    ]
    
    # ============================================
    # STEP DEFINITIONS
    # ============================================
    
    STEPS = [
        {
            "name": "navigate_to_sharepoint",
            "description": "Navigate to SharePoint Sales Pipeline CRM",
            "validators": {},
            "actions": [
                {
                    "action_type": "navigate",
                    "parameters": {
                        "url": "https://pivotaluksolutionsltd-my.sharepoint.com/personal/martin_clickbuy_ai/Lists/Sales%20Pipeline%20CRM/AllItems.aspx",
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
            "name": "wait_for_page_load",
            "description": "Wait for initial page load",
            "validators": {},
            "actions": [
                {
                    "action_type": "wait",
                    "parameters": {"seconds": 10}
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "next"
                }
            }
        },
        {
            "name": "enter_email",
            "description": "Enter email address on Microsoft login page",
            "validators": {
                "url_contains": "login.microsoftonline.com",
                "text_visible": "Sign in"
            },
            "actions": [
                {
                    "action_type": "input",
                    "parameters": {
                        "text": variables.get("email", "yusuf@clickbuy.ai"),
                        "clear": True,
                        "input_type": "email",
                        "input_name": "loginfmt"
                    },
                    "description": "Enter email address"
                },
                {
                    "action_type": "click",
                    "parameters": {
                        "text": "Next",
                        "role": "button"
                    },
                    "description": "Click Next button"
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
            "name": "wait_for_password_page",
            "description": "Wait for password page to load",
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
            "name": "enter_password",
            "description": "Enter password on Microsoft login page",
            "validators": {
                "text_visible": "Enter password"
            },
            "actions": [
                {
                    "action_type": "input",
                    "parameters": {
                        "text": variables.get("password", "Engr@Bash#123m"),
                        "clear": True,
                        "input_type": "password",
                        "input_name": "passwd"
                    },
                    "description": "Enter password"
                },
                {
                    "action_type": "click",
                    "parameters": {
                        "text": "Sign in",
                        "role": "button"
                    },
                    "description": "Click Sign in button"
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
                    "action": "check",
                    "checks": [
                        {
                            "condition": "text_visible",
                            "value": "incorrect",
                            "then": {
                                "action": "goto",
                                "target_step": "handle_incorrect_password"
                            }
                        },
                        {
                            "condition": "text_visible",
                            "value": "locked",
                            "then": {
                                "action": "goto",
                                "target_step": "handle_account_locked"
                            }
                        },
                        {
                            "condition": "default",
                            "then": {
                                "action": "retry",
                                "max_retries": 2,
                                "retry_wait_seconds": 3
                            }
                        }
                    ]
                }
            }
        },
        {
            "name": "wait_after_signin",
            "description": "Wait for post-login redirect",
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
            "name": "handle_stay_signed_in",
            "description": "Handle 'Stay signed in?' prompt",
            "validators": {
                "text_visible": "Stay signed in"
            },
            "actions": [
                {
                    "action_type": "click",
                    "parameters": {
                        "text": "Yes",
                        "role": "button"
                    },
                    "description": "Click Yes to stay signed in"
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
                    "action": "next"
                }
            }
        },
        {
            "name": "wait_for_sharepoint_load",
            "description": "Wait for SharePoint page to fully load",
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
            "name": "handle_mfa_check",
            "description": "Check if MFA/2FA is required",
            "validators": {},
            "actions": [
                {
                    "action_type": "screenshot",
                    "parameters": {},
                    "description": "Capture page state for MFA check"
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "check",
                    "checks": [
                        {
                            "condition": "text_visible",
                            "value": "Verify your identity",
                            "then": {
                                "action": "pause",
                                "reason": "MFA required - please complete verification and resume"
                            }
                        },
                        {
                            "condition": "text_visible",
                            "value": "two-step verification",
                            "then": {
                                "action": "pause",
                                "reason": "2FA required - please complete verification and resume"
                            }
                        },
                        {
                            "condition": "text_visible",
                            "value": "Approve sign in",
                            "then": {
                                "action": "pause",
                                "reason": "Authenticator app approval required - please approve and resume"
                            }
                        },
                        {
                            "condition": "url_contains",
                            "value": "Sales%20Pipeline%20CRM",
                            "then": {
                                "action": "next"
                            }
                        },
                        {
                            "condition": "default",
                            "then": {
                                "action": "next"
                            }
                        }
                    ]
                }
            }
        },
        {
            "name": "verify_crm_loaded",
            "description": "Verify Sales Pipeline CRM list loaded successfully",
            "validators": {
                "url_contains": "Sales%20Pipeline%20CRM",
                "text_visible": "Sales Request Ref"
            },
            "actions": [
                {
                    "action_type": "screenshot",
                    "parameters": {},
                    "description": "Capture CRM page state"
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "skip"
                },
                "on_validation_fail": {
                    "action": "check",
                    "checks": [
                        {
                            "condition": "text_visible",
                            "value": "Access Denied",
                            "then": {
                                "action": "goto",
                                "target_step": "handle_access_denied"
                            }
                        },
                        {
                            "condition": "text_visible",
                            "value": "You don't have access",
                            "then": {
                                "action": "goto",
                                "target_step": "handle_access_denied"
                            }
                        },
                        {
                            "condition": "default",
                            "then": {
                                "action": "check",
                                "checks": SMART_RECOVERY_CHECKS
                            }
                        }
                    ]
                }
            }
        },
        {
            "name": "handle_incorrect_password",
            "description": "Handle incorrect password error",
            "validators": {},
            "actions": [
                {
                    "action_type": "screenshot",
                    "parameters": {}
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "pause",
                    "reason": "Incorrect password - please update credentials and resume"
                }
            }
        },
        {
            "name": "handle_account_locked",
            "description": "Handle locked account error",
            "validators": {},
            "actions": [
                {
                    "action_type": "screenshot",
                    "parameters": {}
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "pause",
                    "reason": "Account locked - please unlock account and resume"
                }
            }
        },
        {
            "name": "handle_access_denied",
            "description": "Handle access denied to SharePoint list",
            "validators": {},
            "actions": [
                {
                    "action_type": "screenshot",
                    "parameters": {}
                }
            ],
            "conditions": {
                "on_success": {
                    "action": "pause",
                    "reason": "Access denied to Sales Pipeline CRM - verify permissions"
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
        
        print(f"\n  📍 Current URL: {current_url[:80]}...")
        
        # Check if already at target
        TARGET_URL_PART = "Sales%20Pipeline%20CRM"
        if TARGET_URL_PART in current_url:
            print(f"  ✅ Already at target page!")
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "page_valid": True,
                "setup_complete": True
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "current_step": "spreadsheet_setup_complete"
            }
        
        # Use smart recovery to find starting point
        print(f"  🔍 Analyzing current location...")
        
        from nodes.execute_workflow_step_node import evaluate_checks
        
        # Create fake dom_state for check evaluation
        dom_state = {"url": current_url, "dom_representation": ""}
        
        recovery_action = evaluate_checks(SMART_RECOVERY_CHECKS, dom_state)
        target_step = recovery_action.get("target_step", "navigate_to_sharepoint")
        
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
                workflow=spreadsheet_workflow,
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
                print(f"      ⏭️  Setup complete")
                break
            
            elif action == "pause":
                print(f"      ⏸️  Paused: {next_action.get('reason')}")
                
                updated_workflows = workflows.copy()
                updated_workflows[spreadsheet_index] = {
                    **spreadsheet_workflow,
                    "page_valid": False,
                    "paused": True,
                    "pause_reason": next_action.get("reason")
                }
                
                return {
                    **state,
                    "workflows": updated_workflows,
                    "execution_paused": True,
                    "pause_reason": next_action.get("reason"),
                    "current_step": "spreadsheet_setup_paused"
                }
            
            elif action == "stop":
                print(f"      🛑 Stopped")
                
                updated_workflows = workflows.copy()
                updated_workflows[spreadsheet_index] = {
                    **spreadsheet_workflow,
                    "page_valid": False,
                    "setup_complete": False,
                    "error": result.get("error", "Step failed")
                }
                
                return {
                    **state,
                    "workflows": updated_workflows,
                    "error_message": result.get("error", "Step failed"),
                    "current_step": "spreadsheet_setup_stopped"
                }
            
            elif not result.get("success"):
                print(f"      ✗ Failed: {result.get('error')}")
                
                updated_workflows = workflows.copy()
                updated_workflows[spreadsheet_index] = {
                    **spreadsheet_workflow,
                    "page_valid": False,
                    "setup_complete": False,
                    "error": result.get("error")
                }
                
                return {
                    **state,
                    "workflows": updated_workflows,
                    "error_message": result.get("error"),
                    "current_step": "spreadsheet_setup_failed"
                }
        
        # ============================================
        # VERIFY FINAL STATE
        # ============================================
        
        final_info = await page.get_target_info()
        final_url = final_info.url if hasattr(final_info, 'url') else final_info.get("url", "")
        
        print(f"\n  📍 Final URL: {final_url[:80]}...")
        
        if TARGET_URL_PART in final_url:
            print(f"  ✅ Successfully reached Sales Pipeline CRM!")
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "page_valid": True,
                "setup_complete": True,
                "error": None
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "current_step": "spreadsheet_setup_complete"
            }
        else:
            print(f"  ⚠️  Not at target page")
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "page_valid": False,
                "setup_complete": False,
                "error": f"Expected '{TARGET_URL_PART}' in URL, got: {final_url}"
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": f"Expected '{TARGET_URL_PART}' in URL, got: {final_url}",
                "current_step": "spreadsheet_setup_failed"
            }
    
    except Exception as e:
        print(f"\n  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "page_valid": False,
            "setup_complete": False,
            "error": str(e)
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": str(e),
            "current_step": "spreadsheet_setup_failed"
        }