# nodes/create_workflow_tabs_node.py

import json
from utils.workflow_graph_state import WorkflowGraphState


async def create_workflow_tabs_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Node 4: Create or assign tabs for workflows with intelligent tab management
    
    Features:
    1. Reuse existing tabs if they're still valid (survives restarts)
    2. Reconnect to tabs after script restart using saved tab_ids
    3. Create new tabs only when needed
    4. Allow workflows to share tabs via references
    5. Use initial browser tab when workflow doesn't need new tab
    6. Save tab assignments back to config file for persistence
    
    Tab config options per workflow:
    - requires_new_tab: true/false (default: true)
    - tab_reference: "name" (optional - give this tab a name for others to reference)
    - use_tab_reference: "name" (optional - use another workflow's tab)
    
    Saved to config per workflow:
    - tab_id: Browser tab ID
    - tab_url: Current URL
    - tab_title: Current title
    - browser_context_id: Browser context
    """
    
    print("📑 Node: Managing tabs for workflows...")
    
    browser = state.get("browser_instance")
    workflows = state.get("workflows", [])
    config_file_path = state.get("config_file_path")
    full_config = state.get("full_config", {})
    
    # ============================================
    # VALIDATION
    # ============================================
    if not browser:
        error_msg = "Browser instance not found in state"
        print(f"  ✗ {error_msg}")
        return {
            **state,
            "error_message": error_msg,
            "current_step": "tab_creation_failed"
        }
    
    if not workflows or len(workflows) == 0:
        error_msg = "No workflows found in configuration"
        print(f"  ✗ {error_msg}")
        return {
            **state,
            "error_message": error_msg,
            "current_step": "tab_creation_failed"
        }
    
    print(f"  ℹ️  Found {len(workflows)} workflow(s)")
    
    try:
        # ============================================
        # SETUP
        # ============================================
        
        # Get all existing browser tabs (returns list of TabInfo objects)
        existing_tabs = await browser.get_tabs()
        existing_tab_ids = {tab.target_id for tab in existing_tabs}  # Access attribute directly
        
        print(f"  ℹ️  Existing browser tabs: {len(existing_tabs)}")
        
        # Get all browser pages
        browser_pages = await browser.get_pages()
        
        # Build tab reference map for sharing tabs between workflows
        tab_reference_map = {}  # {reference_name: {tab_id, page_instance}}
        
        # ============================================
        # PROCESS EACH WORKFLOW
        # ============================================
        updated_workflows = []
        
        for idx, workflow in enumerate(workflows):
            workflow_name = workflow.get("name", f"workflow_{idx}")
            tab_config = workflow.get("tab_config", {})
            
            # Get tab configuration
            requires_new_tab = tab_config.get("requires_new_tab", True)
            tab_reference = tab_config.get("tab_reference")  # Name to give this tab
            use_tab_reference = tab_config.get("use_tab_reference")  # Reference to another tab
            
            print(f"\n  [{idx + 1}/{len(workflows)}] Processing: {workflow_name}")
            
            tab_id = None
            page = None
            tab_source = None
            
            # ============================================
            # CASE 1: Use another workflow's tab (shared tab)
            # ============================================
            if use_tab_reference:
                if use_tab_reference in tab_reference_map:
                    ref_info = tab_reference_map[use_tab_reference]
                    tab_id = ref_info["tab_id"]
                    page = ref_info["page_instance"]
                    tab_source = f"shared from '{use_tab_reference}'"
                    print(f"    ↪️  Using shared tab: {use_tab_reference}")
                else:
                    print(f"    ⚠️  Tab reference '{use_tab_reference}' not found yet, will create new tab")
            
            # ============================================
            # CASE 2: Reuse existing tab (from previous run or same session)
            # ============================================
            if not tab_id and workflow.get("tab_id"):
                existing_tab_id = workflow.get("tab_id")
                
                # Check if this tab still exists in browser
                if existing_tab_id in existing_tab_ids:
                    tab_id = existing_tab_id
                    page = workflow.get("page_instance")

                    # If page_instance is missing (e.g., after restart), reconstruct it
                    if not page:
                        print(f"    🔄 Reconstructing page instance for tab: {tab_id[:8]}...")
                        try:
                            # Find the page in browser's pages by matching tab_id
                            all_pages = await browser.get_pages()
                            for p in all_pages:
                                p_info = await p.get_target_info()
                                # Handle both dict and object responses
                                p_tab_id = p_info.get("targetId") if isinstance(p_info, dict) else getattr(p_info, "target_id", None)
                                if p_tab_id == tab_id:
                                    page = p
                                    break
                            
                            if page:
                                # Verify page is accessible
                                await page.get_target_info()
                                tab_source = "existing (reconnected)"
                                print(f"    ♻️  Reconnected to existing tab: {tab_id[:8]}...")
                            else:
                                print(f"    ⚠️  Could not find page for tab, will recreate")
                                tab_id = None
                                
                        except Exception as e:
                            print(f"    ⚠️  Could not reconnect to tab: {e}")
                            tab_id = None
                            page = None
                    else:
                        # Page instance exists, verify it's still valid
                        try:
                            await page.get_target_info()
                            tab_source = "existing (reused)"
                            print(f"    ♻️  Reusing existing tab: {tab_id[:8]}...")
                        except Exception as e:
                            # Page is stale or disconnected
                            print(f"    ⚠️  Existing page is stale ({e}), will recreate")
                            tab_id = None
                            page = None
                else:
                    print(f"    ⚠️  Previous tab {existing_tab_id[:8]}... is closed, will recreate")
        
            # ============================================
            # CASE 3: Use initial browser tab (don't create new)
            # ============================================
            if not tab_id and not requires_new_tab:
                if browser_pages and len(browser_pages) > 0:
                    page = browser_pages[0]
                    tab_info = await page.get_target_info()
                    # Handle both dict and object responses
                    tab_id = tab_info.get("targetId") if isinstance(tab_info, dict) else getattr(tab_info, "target_id", None)
                    tab_source = "initial browser tab"
                    print(f"    🔗 Using initial tab: {tab_id[:8]}...")
            
            # ============================================
            # CASE 4: Create new tab
            # ============================================
            if not tab_id:
                print(f"    ➕ Creating new tab...")
                page = await browser.new_page()
                tab_info = await page.get_target_info()
                # Handle both dict and object responses
                tab_id = tab_info.get("targetId") if isinstance(tab_info, dict) else getattr(tab_info, "target_id", None)
                tab_source = "newly created"
                print(f"    ✓ Tab created: {tab_id[:8]}...")
            
            # ============================================
            # GET TAB INFORMATION
            # ============================================
            tab_info = await page.get_target_info()
            
            # Handle both dict and object responses
            if isinstance(tab_info, dict):
                tab_url = tab_info.get("url", "about:blank")
                tab_title = tab_info.get("title", "")
                browser_context_id = tab_info.get("browserContextId")
            else:
                tab_url = getattr(tab_info, "url", "about:blank")
                tab_title = getattr(tab_info, "title", "")
                browser_context_id = getattr(tab_info, "browser_context_id", None)
            
            print(f"    ✓ Tab assigned ({tab_source})")
            print(f"      Tab ID: {tab_id[:12]}...")
            print(f"      URL: {tab_url[:50]}{'...' if len(tab_url) > 50 else ''}")
            
            # ============================================
            # BUILD UPDATED WORKFLOW
            # ============================================
            workflow_with_tab = {
                **workflow,
                "tab_id": tab_id,
                "tab_url": tab_url,
                "tab_title": tab_title,
                "browser_context_id": browser_context_id,
                "page_instance": page  # Runtime only, not saved to config
            }
            
            # Register tab reference if specified (for sharing)
            if tab_reference:
                tab_reference_map[tab_reference] = {
                    "tab_id": tab_id,
                    "page_instance": page
                }
                print(f"    📌 Tab registered as: '{tab_reference}'")
            
            updated_workflows.append(workflow_with_tab)
        
        # ============================================
        # SAVE TO CONFIG FILE
        # ============================================
        if config_file_path and full_config:
            try:
                # Prepare workflows for saving (remove page_instance - not JSON serializable)
                workflows_for_config = []
                for wf in updated_workflows:
                    wf_copy = {k: v for k, v in wf.items() if k != "page_instance"}
                    workflows_for_config.append(wf_copy)
                
                # Update config
                full_config["workflows"] = workflows_for_config
                
                # Write to file
                with open(config_file_path, 'w') as f:
                    json.dump(full_config, f, indent=2)
                
                print(f"\n  💾 Tab assignments saved to: {config_file_path}")
                
            except Exception as e:
                print(f"\n  ⚠️  Could not save to config file: {e}")
                # Don't fail the whole process if saving fails
        
        # ============================================
        # SUMMARY
        # ============================================
        all_tabs = await browser.get_tabs()
        print(f"\n  ✓ Tab management complete")
        print(f"  ℹ️  Total browser tabs: {len(all_tabs)}")
        
        # Display workflow-tab mapping
        print(f"\n  📋 Workflow Tab Assignment:")
        for wf in updated_workflows:
            ref_info = ""
            if wf.get("tab_config", {}).get("tab_reference"):
                ref_info = f" [ref: {wf['tab_config']['tab_reference']}]"
            elif wf.get("tab_config", {}).get("use_tab_reference"):
                ref_info = f" [uses: {wf['tab_config']['use_tab_reference']}]"
            print(f"    • {wf['name']}: {wf['tab_id'][:12]}...{ref_info}")
        
        return {
            **state,
            "workflows": updated_workflows,
            "full_config": full_config,  # Update full_config in state
            "error_message": None,
            "current_step": "tabs_created"
        }
        
    except Exception as e:
        error_msg = f"Error managing tabs: {str(e)}"
        print(f"\n  ✗ {error_msg}")
        import traceback
        traceback.print_exc()
        return {
            **state,
            "workflows": workflows,
            "error_message": error_msg,
            "current_step": "tab_creation_failed"
        }