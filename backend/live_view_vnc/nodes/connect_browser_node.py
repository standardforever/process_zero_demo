# nodes/connect_browser_node.py
from browser_use import Browser
from utils.workflow_graph_state import WorkflowGraphState


async def connect_browser_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Node 3: Connect to browser using browser_use
    
    Steps:
    1. Get browser URL from state
    2. Create Browser instance
    3. Connect to browser
    4. Update state with browser instance
    """
    
    print("🔌 Node: Connecting to browser...")
    
    browser_url = state.get("browser_connection_url")
    
    # Step 1: Validate browser URL exists
    if not browser_url:
        error_msg = "Browser connection URL not found in state"
        print(f"  ✗ {error_msg}")
        return {
            **state,
            "browser_instance": None,
            "error_message": error_msg,
            "current_step": "browser_connect_failed"
        }
    
    # Step 2: Check if browser is accessible
    if not state.get("browser_accessible", False):
        error_msg = "Browser is not accessible. Cannot connect."
        print(f"  ✗ {error_msg}")
        print(f"    Hint: Run the check_browser_connection_node first")
        return {
            **state,
            "browser_instance": None,
            "error_message": error_msg,
            "current_step": "browser_connect_failed"
        }
    
    # Step 3: Create and connect to browser
    try:
        print(f"  ℹ️  Creating Browser instance...")
        browser = Browser()
        
        print(f"  ℹ️  Connecting to: {browser_url}")
        await browser.connect(browser_url)
        await browser.start()
        
        print(f"  ✓ Successfully connected to browser")
        
        # Optional: Get browser info
        try:
            # If Browser has methods to get context info
            print(f"  ✓ Browser session established")
        except:
            pass
        
        # Step 4: Update state
        return {
            **state,
            "browser_instance": browser,
            "error_message": None,
            "current_step": "browser_connected"
        }
        
    except ConnectionError as e:
        error_msg = f"Failed to connect to browser: {str(e)}"
        print(f"  ✗ {error_msg}")
        return {
            **state,
            "browser_instance": None,
            "error_message": error_msg,
            "current_step": "browser_connect_failed"
        }
    
    except Exception as e:
        error_msg = f"Error connecting to browser: {str(e)}"
        print(f"  ✗ {error_msg}")
        return {
            **state,
            "browser_instance": None,
            "error_message": error_msg,
            "current_step": "browser_connect_failed"
        }