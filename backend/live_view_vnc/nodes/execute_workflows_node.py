# nodes/execute_workflows_node.py
import asyncio
from typing import Dict, Any, List
from utils.workflow_graph_state import WorkflowGraphState
from nodes.execute_workflow_step_node import execute_workflow_step_node


async def execute_workflows_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Execute all workflows in the state.
    
    Handles:
    - Fresh execution (start from beginning)
    - Resume execution (continue from paused state)
    
    Returns updated state with execution results.
    """
    
    workflows = state.get("workflows", [])
  
    if not workflows:
        print("No workflows to execute")
        state["current_step"] = "no_workflows"
        return state
    
    # ============================================
    # RESUME LOGIC
    # ============================================
    start_workflow_index = 0
    start_step_index = 0
    is_resuming = False
    
    if state.get("execution_paused"):
        # We're resuming from a pause
        is_resuming = True
        start_workflow_index = state.get("current_workflow_index", 0)
        
        # Check if user specified a different step to resume from
        resume_from_step = state.get("resume_from_step")
        if resume_from_step is not None:
            start_step_index = resume_from_step
            print(f"\n🔄 Resuming from user-specified step index: {start_step_index}")
        else:
            # Resume from step after the one that paused
            start_step_index = state.get("current_step_index", 0)
            print(f"\n🔄 Resuming from step index: {start_step_index}")
        
        # Clear pause state
        state["execution_paused"] = False
        state["pause_reason"] = None
        state["resume_from_step"] = None
        state["requires_human_intervention"] = False
        state["intervention_data"] = None
    
    # ============================================
    # EXECUTION
    # ============================================
    print(f"\n{'='*60}")
    if is_resuming:
        print(f"RESUMING WORKFLOW EXECUTION")
    else:
        print(f"EXECUTING {len(workflows)} WORKFLOW(S)")
    print(f"{'='*60}")
    
    # Execute workflows starting from start_workflow_index
    for workflow_idx in range(start_workflow_index, len(workflows)):
        workflow = workflows[workflow_idx]
        workflow_name = workflow.get("name", f"workflow_{workflow_idx}")
        steps = workflow.get("steps", [])
        
        print(f"\n\n{'='*60}")
        print(f"WORKFLOW {workflow_idx + 1}/{len(workflows)}: {workflow_name}")
        print(f"{'='*60}")
        print(f"Steps: {len(steps)}")
        
        # Initialize or get existing workflow results
        if workflow_name not in state["workflow_results"]:
            state["workflow_results"][workflow_name] = {
                "status": "running",
                "steps_completed": 0,
                "steps_failed": 0,
                "step_results": {}
            }
        else:
            # Resuming - update status back to running
            state["workflow_results"][workflow_name]["status"] = "running"
        
        # Build step name -> index map for goto
        step_name_to_index = {
            step.get("name"): idx 
            for idx, step in enumerate(steps)
        }
        
        # Determine starting step index
        if workflow_idx == start_workflow_index:
            # This is the workflow we're resuming - use start_step_index
            current_step_index = start_step_index
            if is_resuming:
                print(f"▶️  Resuming from step {current_step_index + 1}/{len(steps)}")
        else:
            # Start from beginning for subsequent workflows
            current_step_index = 0
        
        # Execute steps
        while current_step_index < len(steps):
            step = steps[current_step_index]
            step_name = step.get("name", f"step_{current_step_index}")
            
            state["current_workflow_index"] = workflow_idx
            state["current_step_index"] = current_step_index
            
            # Execute step
            result = await execute_workflow_step_node(
                workflow=workflow,
                step=step,
                step_index=current_step_index,
                state=state
            )
            
            # Store result
            state["workflow_results"][workflow_name]["step_results"][step_name] = result
            
            # Update counters
            if result.get("success"):
                state["workflow_results"][workflow_name]["steps_completed"] += 1
            else:
                state["workflow_results"][workflow_name]["steps_failed"] += 1
            
            # Get next action
            next_action = result.get("next_action", {})
            action = next_action.get("action", "next")
            
            # Handle next action
            if action == "next":
                # Move to next step
                current_step_index += 1
            
            elif action == "goto":
                # Jump to target step
                target_step = next_action.get("target_step")
                if target_step in step_name_to_index:
                    new_index = step_name_to_index[target_step]
                    print(f"\n      ⏭️  Jumping to step {new_index + 1}: {target_step}")
                    current_step_index = new_index
                else:
                    print(f"\n      ⚠️  Unknown target step: {target_step}, stopping workflow")
                    state["workflow_results"][workflow_name]["status"] = "failed"
                    state["error_message"] = f"Unknown target step: {target_step}"
                    break
            
            elif action == "skip":
                # Skip remaining steps
                print(f"\n      ⏭️  Skipping remaining steps")
                state["workflow_results"][workflow_name]["status"] = "skipped"
                break
            
            elif action == "stop":
                # Stop workflow with error
                print(f"\n      🛑 Stopping workflow")
                state["workflow_results"][workflow_name]["status"] = "failed"
                break
            
            elif action == "pause":
                # Pause for human intervention
                reason = next_action.get("reason", "Workflow paused")
                print(f"\n      ⏸️  Paused: {reason}")
                
                state["execution_paused"] = True
                state["pause_reason"] = reason
                state["requires_human_intervention"] = True
                state["current_workflow_index"] = workflow_idx
                state["current_step_index"] = current_step_index
                state["intervention_data"] = {
                    "workflow_name": workflow_name,
                    "step_name": step_name,
                    "step_index": current_step_index,
                    "result": result,
                    "timestamp": asyncio.get_event_loop().time()
                }
                state["workflow_results"][workflow_name]["status"] = "paused"
                state["current_step"] = "workflow_paused"
                
                # Return early - don't continue to next workflow
                return state
        
        # Mark workflow as complete if we finished all steps
        if state["workflow_results"][workflow_name]["status"] == "running":
            state["workflow_results"][workflow_name]["status"] = "completed"
            print(f"\n✅ Workflow '{workflow_name}' completed successfully")
    
    # All workflows executed
    state["current_step"] = "all_workflows_complete"
    print(f"\n\n{'='*60}")
    print(f"ALL WORKFLOWS COMPLETE")
    print(f"{'='*60}")
    
    return state