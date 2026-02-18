# nodes/execute_workflow_step_node.py
import asyncio
import json
from typing import Dict, Any, List
# from browser_use import Page
from browser_use.dom.service import DomService
from browser_use.dom.serializer.serializer import DOMTreeSerializer
from browser_use.browser.events import SwitchTabEvent

from utils.workflow_graph_state import WorkflowGraphState
from service.workflow_executor import WorkflowExecutor
from schemas.actions_schemas import WorkflowStep, WorkflowActionType
from service.llm_client import call_llm


# ============================================================
# CONDITION SCOPE
# ============================================================
#
# TRIGGERS (when conditions get evaluated):
#   on_success          → step completed successfully
#   on_validation_fail  → LLM validation failed
#   on_error            → action execution failed (after all retries exhausted)
#
# ACTIONS (what happens when a condition triggers):
#   next    → proceed to next sequential step (default on success)
#   goto    → jump to a specific named step (requires target_step)
#   retry   → retry from a step (requires retry_step, or current step if None)
#   skip    → end workflow gracefully (no error)
#   stop    → stop workflow immediately (error state)
#   pause   → pause for human intervention (requires reason)
#   check   → evaluate sub-checks to decide which action to take
#
# CHECK CONDITIONS (used inside "check" action):
#   text_visible    → text exists somewhere in page DOM
#   element_exists  → element matching selector exists in DOM
#   url_contains    → current URL contains a string
#   default         → always matches (use as fallback, must be last)
#
# RETRY BEHAVIOR:
#   - Configured via on_error.max_retries (default 0 = no retry)
#   - Configured via on_error.retry_wait_seconds (default 2)
#   - Each retry: wait → rescrape → re-validate → re-execute
#   - Applies to BOTH validation failures and execution failures
#   - After all retries exhausted → condition evaluation runs
#
# ============================================================


# ============================================================
# CONDITION EVALUATION
# ============================================================

def evaluate_checks(
    checks: List[Dict],
    dom_state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluate a list of checks against current page state.
    First matching check wins → returns that check's 'then' action.
    
    Example checks:
    [
        {"condition": "text_visible", "value": "Invalid credentials", "then": {"action": "goto", "target_step": "handle_invalid"}},
        {"condition": "url_contains", "value": "/error", "then": {"action": "goto", "target_step": "handle_error"}},
        {"condition": "default", "then": {"action": "stop"}}
    ]
    """
    url = dom_state.get("url", "")
    dom_text = dom_state.get("dom_representation", "")
    
    for check in checks:
        condition = check.get("condition")
        value = check.get("value", "")
        matched = False
        
        if condition == "text_visible":
            matched = value.lower() in dom_text.lower()
        
        elif condition == "element_exists":
            matched = value in dom_text
        
        elif condition == "url_contains":
            matched = value in url
        
        elif condition == "default":
            matched = True
        
        if matched:
            print(f"      📌 Check matched: {condition} = '{value}'")
            return check.get("then", {"action": "next"})
    
    # No check matched at all → default to next
    return {"action": "next"}


def resolve_condition(
    trigger: str,
    step: Dict[str, Any],
    dom_state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Resolve what to do next based on trigger + step conditions.
    
    Args:
        trigger: "on_success" | "on_validation_fail" | "on_error"
        step: Step definition containing conditions
        dom_state: Current page state for check evaluation
    
    Returns:
        {
            "action": "next" | "goto" | "skip" | "stop" | "pause",
            "target_step": str | None,   # for goto
            "reason": str | None,        # for pause
        }
    """
    conditions = step.get("conditions", {})
    trigger_config = conditions.get(trigger)
    
    # --- No condition configured → use defaults ---
    if not trigger_config:
        if trigger == "on_success":
            return {"action": "next"}
        else:
            # on_validation_fail or on_error with no config → stop
            return {"action": "stop"}
    
    action = trigger_config.get("action")
    
    # --- "check" → evaluate sub-checks ---
    if action == "check":
        resolved = evaluate_checks(
            checks=trigger_config.get("checks", []),
            dom_state=dom_state
        )
        # If check resolves to "retry" → convert to goto
        if resolved.get("action") == "retry":
            return {
                "action": "goto",
                "target_step": resolved.get("retry_step")  # None = current step
            }
        return resolved
    
    # --- "retry" in condition → convert to goto ---
    # Retry as a condition outcome means "go back to step X and re-run"
    # The parent loop handles the actual re-execution
    if action == "retry":
        return {
            "action": "goto",
            "target_step": trigger_config.get("retry_step")  # None = current step
        }
    
    # --- All other actions (next, goto, skip, stop, pause) → return directly ---
    return trigger_config


# ============================================================
# RETRY + EXECUTION
# ============================================================

async def execute_with_retry(
    workflow: Dict[str, Any],
    step: Dict[str, Any],
    step_index: int,
    state: WorkflowGraphState,
    max_retries: int = 0,
    retry_wait_seconds: int = 2
) -> Dict[str, Any]:
    """
    Execute step with built-in retry on failure.
    
    Each retry cycle:
    1. Wait retry_wait_seconds
    2. Rescrape page
    3. Re-validate (if validators exist)
    4. Re-execute actions
    
    After all retries exhausted → returns with appropriate trigger
    for condition evaluation.
    """
    
    step_name = step.get("name", f"step_{step_index}")
    actions = step.get("actions", [])
    validators = step.get("validators", {})
    
    page = workflow.get("page_instance")
    tab_id = workflow.get("tab_id", "")
    
    dom_state = None
    
    for attempt in range(max_retries + 1):
        is_retry = attempt > 0
        
        if is_retry:
            print(f"      🔄 Retry {attempt}/{max_retries} (waiting {retry_wait_seconds}s)...")
            await asyncio.sleep(retry_wait_seconds)
        
        # ============================================
        # VALIDATE + POPULATE INDICES
        # ============================================
        populated_actions = actions.copy()
        
        if validators:
            print(f"      🔍 Validating page state...")
            
            validation_result = await validate_and_populate_actions(
                page=page,
                tab_id=tab_id,
                step=step,
                actions=actions,
                state=state
            )
            
            dom_state = validation_result.get("dom_state")
            
            if not validation_result.get("valid", False):
                print(f"      ✗ Validation failed: {validation_result.get('reason')}")
                
                if attempt < max_retries:
                    continue  # Retry → wait → rescrape → re-validate
                
                # All retries exhausted on validation
                return {
                    "success": False,
                    "validation_passed": False,
                    "error": validation_result.get("reason"),
                    "step_name": step_name,
                    "dom_state": dom_state,
                    "trigger": "on_validation_fail"
                }
            
            print(f"      ✓ Validation passed")
            populated_actions = validation_result.get("populated_actions", actions)
            
            # await save_populated_actions(
            #     workflow=workflow,
            #     step_index=step_index,
            #     populated_actions=populated_actions,
            #     state=state
            # )
        
        # ============================================
        # EXECUTE ACTIONS
        # ============================================
        print(f"      ⚙️  Executing {len(populated_actions)} action(s)...")
        
        action_results = []
        execution_failed = False
        
        for action_idx, action in enumerate(populated_actions):
            action_type = action.get("action_type")
            parameters = action.get("parameters", {})
            action_desc = action.get("description", action_type)
            
            print(f"        [{action_idx + 1}/{len(populated_actions)}] {action_desc}...")
            
            execution_result = await execute_action(
                page=page,
                action_type=action_type,
                parameters=parameters,
                state=state,
                tab_id=tab_id,
                variables=workflow.get("variables", {})  # Pass workflow variables
            )
            
            if not execution_result.get("success", False):
                print(f"        ✗ Action failed: {execution_result.get('error')}")
                execution_failed = True
                
                if attempt < max_retries:
                    break  # Break action loop → retry whole step
                
                # All retries exhausted on execution
                # Scrape page for condition evaluation if we don't have dom_state
                if dom_state is None:
                    dom_state = await get_page_state(page, tab_id, state)
                
                return {
                    "success": False,
                    "validation_passed": bool(validators),
                    "error": execution_result.get("error"),
                    "step_name": step_name,
                    "failed_action_index": action_idx,
                    "dom_state": dom_state,
                    "trigger": "on_error"
                }
            
            action_results.append(execution_result)
            print(f"        ✓ Done")
            
            if action_idx < len(populated_actions) - 1:
                await asyncio.sleep(0.5)
        
        if execution_failed:
            continue  # Retry whole step
        
        # ============================================
        # ALL ACTIONS SUCCEEDED
        # ============================================
        print(f"      ✓ All actions completed")
        
        return {
            "success": True,
            "validation_passed": bool(validators),
            "step_name": step_name,
            "action_results": action_results,
            "populated_actions": populated_actions,
            "dom_state": dom_state,
            "trigger": "on_success"
        }
    
    # Fallback (should not normally reach here)
    return {
        "success": False,
        "error": "Max retries exhausted",
        "step_name": step_name,
        "dom_state": dom_state,
        "trigger": "on_error"
    }


# ============================================================
# MAIN NODE
# ============================================================

async def execute_workflow_step_node(
    workflow: Dict[str, Any],
    step: Dict[str, Any],
    step_index: int,
    state: WorkflowGraphState
) -> Dict[str, Any]:
    """
    Main step execution node.
    
    Flow:
    1. Switch to correct tab
    2. Determine retry config from conditions
    3. Execute with retry (validate → execute → retry if needed)
    4. Evaluate conditions based on outcome
    5. Return result with next_action for the parent loop
    
    Returns:
        {
            "success": bool,
            "step_name": str,
            "trigger": "on_success" | "on_validation_fail" | "on_error",
            "next_action": {
                "action": "next" | "goto" | "skip" | "stop" | "pause",
                "target_step": str | None,
                "reason": str | None
            }
        }
    """
    
    step_name = step.get("name", f"step_{step_index}")
    conditions = step.get("conditions", {})
    browser = state.get("browser_instance")
    tab_id = workflow.get("tab_id", "")
    
    # --- Switch to correct tab ---
    await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
    
    print(f"\n    [{step_index + 1}] {step_name}")
    print(f"      Actions: {len(step.get('actions', []))}")
    
    # --- Determine retry config ---
    on_error_config = conditions.get("on_error", {})
    max_retries = on_error_config.get("max_retries", 0)
    retry_wait = on_error_config.get("retry_wait_seconds", 2)
    
    # --- Execute with retry ---
    result = await execute_with_retry(
        workflow=workflow,
        step=step,
        step_index=step_index,
        state=state,
        max_retries=max_retries,
        retry_wait_seconds=retry_wait
    )
    
    # --- Resolve condition based on outcome ---
    trigger = result.get("trigger", "on_success")
    dom_state = result.get("dom_state") or {}
    
    next_action = resolve_condition(
        trigger=trigger,
        step=step,
        dom_state=dom_state
    )
    
    # If goto with no target_step → means retry current step
    if next_action.get("action") == "goto" and next_action.get("target_step") is None:
        next_action["target_step"] = step_name
    
    result["next_action"] = next_action
    
    # --- Log next action ---
    action = next_action.get("action")
    if action == "next":
        print(f"      ➡️  Next step")
    elif action == "goto":
        print(f"      ⏭️  Jump to: {next_action.get('target_step')}")
    elif action == "pause":
        print(f"      ⏸️  Paused: {next_action.get('reason', 'No reason given')}")
    elif action == "skip":
        print(f"      ⏭️  Skipping remaining steps")
    elif action == "stop":
        print(f"      🛑 Stopping workflow")
    
    return result


# ============================================================
# EXECUTE SINGLE ACTION
# ============================================================

async def execute_action(
    page: Any,
    action_type: str,
    parameters: Dict[str, Any],
    state: WorkflowGraphState,
    tab_id: str,
    variables: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Execute a single action. No validation, no retry. Just runs it."""
    
    tools = state.get("tools")
    browser = state.get("browser_instance")
    
    try:
        executor = WorkflowExecutor(tools=tools, browser_session=browser)
        
        workflow_step = WorkflowStep(
            name="current_action",
            action_type=WorkflowActionType(action_type),
            parameters=parameters
        )
        
        result = await executor.execute_step(
            step=workflow_step,
            variables=variables
        )
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# VALIDATE + POPULATE INDICES (Single LLM Call)
# ============================================================

async def validate_and_populate_actions(
    page: Any,
    tab_id: str,
    step: Dict[str, Any],
    actions: List[Dict[str, Any]],
    state: WorkflowGraphState
) -> Dict[str, Any]:
    """
    Validate page + populate indices for all actions needing them.
    Single LLM call for everything.
    
    Returns dom_state alongside results (needed for condition evaluation).
    """
    
    # Get page state
    dom_state = await get_page_state(page, tab_id, state)
    
    validators = step.get("validators", {})
    
    # Determine which actions need indices
    actions_needing_indices = []
    for idx, action in enumerate(actions):
        action_type = action.get("action_type")
        parameters = action.get("parameters", {})
        
        needs_index = action_type in ["click", "input", "select_dropdown", "upload_file", "get_dropdown_options", "scroll"]
        # has_index = "index" in parameters
        has_index = False
        
        if needs_index and not has_index:
            actions_needing_indices.append({
                "action_index": idx,
                "action": action
            })
    
    # Build prompt
    prompt = build_validation_prompt(
        dom_state=dom_state,
        step=step,
        validators=validators,
        actions_needing_indices=actions_needing_indices
    )
    
    needs_indices_text = f" + finding {len(actions_needing_indices)} indices" if actions_needing_indices else ""
    print(f"      🤖 Calling LLM for validation{needs_indices_text}...")
    
    # Call LLM
    llm_result = await call_llm(prompt)
    llm_response = llm_result["response"]
    usage = llm_result["usage"]
    
    print(f"      📊 Tokens: {usage['input_tokens']} in, {usage['output_tokens']} out, {usage['total_tokens']} total")
    
    # Populate actions with indices from LLM
    populated_actions = actions.copy()
    for index_info in llm_response.get("action_indices", []):
        action_idx = index_info["action_index"]
        populated_actions[action_idx]["parameters"]["index"] = index_info["index"]
        populated_actions[action_idx]["parameters"]["_element_info"] = index_info["element_info"]
    
    llm_response["populated_actions"] = populated_actions
    llm_response["token_usage"] = usage
    llm_response["dom_state"] = dom_state  # Pass through for condition evaluation
    
    return llm_response


# ============================================================
# GET PAGE STATE
# ============================================================

async def get_page_state(page, tab_id: str, state: WorkflowGraphState) -> Dict[str, Any]:
    """Scrape current page → return DOM + URL + title"""
    
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


# ============================================================
# SAVE POPULATED ACTIONS
# ============================================================

async def save_populated_actions(
    workflow: Dict[str, Any],
    step_index: int,
    populated_actions: List[Dict[str, Any]],
    state: WorkflowGraphState
) -> None:
    """Save populated indices to config file for future runs"""
    
    config_file_path = state.get("config_file_path")
    full_config = state.get("full_config", {})
    
    if not full_config or not config_file_path:
        return
    
    workflows = state.get("workflows", [])
    workflow_idx = workflows.index(workflow)
    
    # Update in-memory
    workflows[workflow_idx]["steps"][step_index]["actions"] = populated_actions
    full_config["workflows"][workflow_idx]["steps"][step_index]["actions"] = populated_actions
    
    # Save to file
    try:
        with open(config_file_path, 'w') as f:
            json.dump(full_config, f, indent=2)
        
        populated_count = sum(1 for a in populated_actions if "index" in a.get("parameters", {}))
        if populated_count > 0:
            print(f"      📝 Saved {populated_count} index/indices to config")
    except Exception as e:
        print(f"      ⚠️  Could not save config: {e}")


# ============================================================
# BUILD VALIDATION PROMPT
# ============================================================

def build_validation_prompt(
    dom_state: Dict[str, Any],
    step: Dict[str, Any],
    validators: Dict[str, Any],
    actions_needing_indices: List[Dict[str, Any]]
) -> str:
    """Build LLM prompt for validation + index detection"""
    
    prompt = f"""You are validating a workflow step execution.

RESPONSE FORMAT:
- Return ONLY valid JSON
- Do NOT wrap in markdown code blocks
- Start directly with {{ and end with }}

STEP INFORMATION:
-----------------
Step Name: {step.get('name')}
Description: {step.get('description')}

CURRENT PAGE STATE:
-------------------
URL: {dom_state.get('url')}
Title: {dom_state.get('title')}

DOM Elements:
{dom_state.get('dom_representation')}

TASK 1 - VALIDATE PAGE:
------------------------
Check if the page satisfies these validators:
{json.dumps(validators, indent=2)}

For each validator, verify if the condition is met in the DOM above.
"""

    if actions_needing_indices:
        prompt += f"""
TASK 2 - FIND ELEMENT INDICES FOR ACTIONS:
-------------------------------------------
This step has {len(actions_needing_indices)} action(s) that need element indices.
For each action below, find the correct element index from the DOM.

"""
        for item in actions_needing_indices:
            action = item["action"]
            action_idx = item["action_index"]
            action_type = action.get("action_type")
            params = action.get("parameters", {})
            action_desc = action.get("description", action_type)
            
            prompt += f"""
ACTION {action_idx + 1}:
  Type: {action_type}
  Description: {action_desc}
"""
            element_criteria = extract_element_criteria(action_type, params)
            if element_criteria:
                prompt += f"""  Find element matching:
{json.dumps(element_criteria, indent=4)}
"""
            if action_type == "click":
                prompt += """  Look for: clickable element (button, link), exact or partial text match, role/type, ARIA labels
"""
            elif action_type == "input":
                prompt += """  Look for: input field, associated label, placeholder, name/id, input type
"""
            elif action_type == "select_dropdown":
                prompt += """  Look for: select/dropdown, associated label, name/id
"""
        
        prompt += """
IMPORTANT:
- Index is shown in square brackets like [123] before each element
- Match elements as precisely as possible
- Consider element hierarchy and context
- Verify elements are interactive/visible
"""

    # Return format
    if actions_needing_indices:
        prompt += """
RETURN JSON FORMAT:
{
    "valid": true/false,
    "reason": "explanation",
    "validator_results": {
        "validator_name": {"passed": true/false, "details": "..."}
    },
    "action_indices": [
        {
            "action_index": 0,
            "index": <number>,
            "element_info": {
                "text": "element text",
                "type": "element type",
                "confidence": 0.0-1.0,
                "reasoning": "why this element"
            }
        }
    ]
}
"""
    else:
        prompt += """
RETURN JSON FORMAT:
{
    "valid": true/false,
    "reason": "explanation",
    "validator_results": {
        "validator_name": {"passed": true/false, "details": "..."}
    }
}
"""
    return prompt


# ============================================================
# EXTRACT ELEMENT CRITERIA
# ============================================================

def extract_element_criteria(action_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Extract element identification criteria from action parameters"""
    
    criteria = {}
    
    identification_fields = [
        'button_text', 'link_text', 'text', 'text_contains', 'text_exact',
        'label', 'aria_label', 'placeholder', 'title',
        'name', 'id', 'class', 'role', 'type',
        'value', 'alt', 'href_contains',
        'input_label', 'input_name', 'input_placeholder', 'input_type',
        'dropdown_label', 'dropdown_name'
    ]
    
    for field in identification_fields:
        if field in params:
            criteria[field] = params[field]
    
    if '_descriptive' in params:
        descriptive = params['_descriptive']
        if isinstance(descriptive, dict):
            criteria.update(descriptive)
    
    return criteria