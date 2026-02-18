# workflow_graph_state.py
from typing import TypedDict, Optional, List, Dict, Any
from browser_use import Browser, Tools


class WorkflowGraphState(TypedDict):
    """State for the workflow LangGraph execution"""
    
    # ============================================
    # Configuration
    # ============================================
    odoo_retry_count: int
    spreadsheet_retry_count: int
    config_file_path: str
    """Path to the workflow configuration JSON file"""
    
    full_config: Optional[Dict[str, Any]]
    """Complete loaded configuration from JSON"""
    
    # ============================================
    # Browser Connection
    # ============================================
    browser_connection_url: Optional[str]
    """Browser CDP connection URL (e.g., http://localhost:9222/)"""
    
    browser_accessible: bool
    """Whether the browser connection is accessible"""
    
    browser_instance: Browser
    """Browser instance from browser_use.Browser"""
    
    # ============================================
    # Tools
    # ============================================
    tools: Tools
    """Tools instance from browser_use.agent.tools.Tools"""
    
    # ============================================
    # Workflows (enhanced with tab info and execution tracking)
    # ============================================
    workflows: Optional[List[Dict[str, Any]]]
    """
    List of workflows from config, enhanced with runtime data:
    - name: str
    - description: str
    - steps: List[Dict]
    - variables: Dict
    - tab_id: str (added at runtime)
    - tab_url: str (added at runtime)
    - tab_title: str (added at runtime)
    - browser_context_id: str (added at runtime)
    - page_instance: Any (added at runtime)
    """
    
    global_settings: Optional[Dict[str, Any]]
    """
    Global settings from config:
    - timeout: int
    - max_retries: int
    - screenshot_on_error: bool
    - headless: bool
    """
    
    # ============================================
    # Execution Tracking
    # ============================================
    current_workflow_index: int
    """Index of the currently executing workflow"""
    
    current_step_index: int
    """Index of the currently executing step within current workflow"""
    
    workflow_results: Dict[str, Any]
    """
    Results for each workflow:
    {
        "workflow_name": {
            "status": "running" | "completed" | "failed",
            "steps_completed": int,
            "steps_failed": int,
            "step_results": {
                "step_name": {
                    "success": bool,
                    "validation_passed": bool,
                    "error": Optional[str],
                    "execution_result": Any,
                    "populated_parameters": Dict
                }
            }
        }
    }
    """
    
    # ============================================
    # Pause/Resume Control
    # ============================================
    execution_paused: bool
    """Whether workflow execution is currently paused"""
    
    pause_reason: Optional[str]
    """Reason for pausing execution"""
    
    resume_from_step: Optional[int]
    """Step index to resume from (None = resume from current)"""
    
    # ============================================
    # Human Intervention
    # ============================================
    requires_human_intervention: bool
    """Whether human intervention is required to continue"""
    
    intervention_data: Optional[Dict[str, Any]]
    """
    Data about the intervention requirement:
    {
        "workflow_name": str,
        "step_name": str,
        "step_index": int,
        "validation_result": Dict,
        "dom_state": Dict,
        "timestamp": str
    }
    """
    
    # ============================================
    # Status Tracking
    # ============================================
    error_message: Optional[str]
    """Current error message if any"""
    
    current_step: str
    """
    Current execution step/state:
    - "start"
    - "config_loaded"
    - "config_load_failed"
    - "browser_connected"
    - "browser_connection_failed"
    - "tabs_created"
    - "workflow_running"
    - "workflow_paused"
    - "workflow_complete"
    - "workflow_failed"
    - "all_workflows_complete"
    - "awaiting_human_action"
    - "error"
    """