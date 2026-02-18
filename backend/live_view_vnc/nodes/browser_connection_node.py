# nodes/check_browser_connection_node.py
import aiohttp
import asyncio
from utils.workflow_graph_state import WorkflowGraphState

async def check_browser_connection_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Node 2: Verify browser connection accessibility
    
    Steps:
    1. Get browser URL from state
    2. Check if URL exists
    3. Verify browser is accessible
    4. Update state with results
    """
    
    print("🌐 Node: Checking browser connection...")
    
    browser_url = state.get("browser_connection_url")
    
    # Step 1: Check if browser URL exists in state
    if not browser_url:
        error_msg = "Browser connection URL not found in configuration"
        print(f"  ✗ {error_msg}")
        return {
            **state,
            "browser_accessible": False,
            "error_message": error_msg,
            "current_step": "browser_url_missing"
        }
    
    print(f"  ℹ️  Browser URL: {browser_url}")

    # Selenium Grid exposes CDP as ws://.../se/cdp. That endpoint does not
    # support /json/version.
    if isinstance(browser_url, str) and browser_url.lower().startswith(("ws://", "wss://")):
        print("  ✓ WebSocket CDP endpoint detected; skipping HTTP /json/version probe")
        return {
            **state,
            "browser_accessible": True,
            "error_message": None,
            "current_step": "browser_connected",
        }
    
    # Step 2: Verify browser accessibility
    accessible = False
    error_msg = None
    
    try:
        async with aiohttp.ClientSession() as session:
            # Try to connect to the browser DevTools endpoint
            test_url = f"{browser_url.rstrip('/')}/json/version"
            
            timeout = state.get("global_settings", {}).get("timeout", 5)
            
            async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"  ✓ Browser is accessible")
                    print(f"    Browser: {data.get('Browser', 'Unknown')}")
                    print(f"    Protocol: {data.get('Protocol-Version', 'Unknown')}")
                    print(f"    User-Agent: {data.get('User-Agent', 'Unknown')[:50]}...")
                    accessible = True
                else:
                    error_msg = f"Browser returned status code: {response.status}"
                    print(f"  ✗ {error_msg}")
    
    except aiohttp.ClientConnectorError as e:
        error_msg = f"Cannot connect to browser at {browser_url}: Connection refused"
        print(f"  ✗ {error_msg}")
        print(f"    Make sure Chrome/Chromium is running with --remote-debugging-port=9222")
    
    except asyncio.TimeoutError:
        error_msg = "Connection to browser timed out"
        print(f"  ✗ {error_msg}")
    
    except Exception as e:
        error_msg = f"Error verifying browser connection: {str(e)}"
        print(f"  ✗ {error_msg}")
    
    # Step 3: Update state
    return {
        **state,
        "browser_accessible": accessible,
        "error_message": error_msg if not accessible else None,
        "current_step": "browser_connected" if accessible else "browser_connection_failed"
    }
