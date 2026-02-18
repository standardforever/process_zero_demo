# nodes/processing/fill_invoice_node.py

from typing import Dict, Any
from utils.workflow_graph_state import WorkflowGraphState
from service.workflow_executor import WorkflowExecutor
from schemas.actions_schemas import WorkflowStep, WorkflowActionType

import re
import asyncio
from browser_use.dom.service import DomService

async def get_page_state(page,  state: WorkflowGraphState) -> Dict[str, Any]:
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



async def update_status_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Fill Odoo invoice form - Part 1: Customer Name
    
    Uses WorkflowExecutor for all interactions
    """
    
    print("\n" + "="*60)
    print("FILL INVOICE - CUSTOMER NAME")
    print("="*60)
    return "ok"
    