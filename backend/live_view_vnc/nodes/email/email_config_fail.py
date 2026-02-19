# nodes/load_config_node.py
import json
import os
from typing import Dict, Any
from utils.workflow_graph_state import WorkflowGraphState



async def email_failure_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Send failure email and gracefully stop workflow
    """
    print("📧 Node: Sending failure notification email...")
    browser_instance = state.get('browser_instance')
    await browser_instance.stop()

    error = state.get("error_message", "Unknown error")
    step = state.get("current_step", "unknown_step")

    print(f"  ⚠️ Failure at step: {step}")
    print(f"  ⚠️ Error: {error}")

    # TODO: plug in real email service
    # send_email(to=..., subject=..., body=...)

    return {
        **state,
        "current_step": "email_sent"
    }
