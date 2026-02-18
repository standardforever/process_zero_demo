# nodes/load_config_node.py
import json
import os
from typing import Dict, Any
from utils.workflow_graph_state import WorkflowGraphState



def load_config_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Starting Node: Load configuration from JSON file into state
    
    Steps:
    1. Read JSON file from config_file_path
    2. Parse and validate JSON
    3. Load all configuration into state
    4. Extract key fields for easy access
    """
    
    print("📂 Node: Loading configuration...")
    
    config_file_path = state.get("config_file_path", "config.json")
    
    # Step 1: Check file exists
    try:
        if not os.path.exists(config_file_path):
            error_msg = f"Config file not found: {config_file_path}"
            print(f"  ✗ {error_msg}")
            return {
                **state,
                "full_config": None,
                "browser_connection_url": None,
                "workflows": None,
                "global_settings": None,
                "browser_accessible": False,
                "error_message": error_msg,
                "current_step": "config_load_failed"
            }
        
        # Step 2: Read and parse JSON
        with open(config_file_path, 'r') as f:
            config = json.load(f)
        
        print(f"  ✓ Config file loaded: {config_file_path}")
        
        # Step 3: Extract key fields
        browser_url = config.get("browser_connection_url")
        workflows = config.get("workflows", [])
        global_settings = config.get("global_settings", {})
        
        print(f"  ✓ Browser URL: {browser_url}")
        print(f"  ✓ Workflows found: {len(workflows)}")
        print(f"  ✓ Global settings loaded: {len(global_settings)} settings")
        
        # Display workflow names
        if workflows:
            print(f"  📋 Workflows:")
            for wf in workflows:
                print(f"    - {wf.get('name')}: {len(wf.get('steps', []))} steps")
        
        # Step 4: Update state with all config data
        return {
            **state,
            "full_config": config,
            "browser_connection_url": browser_url,
            "workflows": workflows,
            "global_settings": global_settings,
            "browser_accessible": False,  # Will be checked in next node
            "error_message": None,
            "current_step": "config_loaded"
        }
        
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in config file: {str(e)}"
        print(f"  ✗ {error_msg}")
        return {
            **state,
            "full_config": None,
            "browser_connection_url": None,
            "workflows": None,
            "global_settings": None,
            "browser_accessible": False,
            "error_message": error_msg,
            "current_step": "config_parse_failed"
        }
    
    except Exception as e:
        error_msg = f"Error reading config file: {str(e)}"
        print(f"  ✗ {error_msg}")
        return {
            **state,
            "full_config": None,
            "browser_connection_url": None,
            "workflows": None,
            "global_settings": None,
            "browser_accessible": False,
            "error_message": error_msg,
            "current_step": "config_load_failed"
        }