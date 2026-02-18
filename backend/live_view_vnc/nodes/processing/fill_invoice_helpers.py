# nodes/processing/fill_invoice_helpers.py

from typing import Dict, Any, Optional
from utils.workflow_graph_state import WorkflowGraphState
from service.workflow_executor import WorkflowExecutor
from schemas.actions_schemas import WorkflowStep, WorkflowActionType
from browser_use.dom.service import DomService
import re
import asyncio


async def get_page_state(page, state: WorkflowGraphState) -> Dict[str, Any]:
    """Get current page DOM representation"""
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


def find_element_index(llm_representation: str, pattern: str) -> Optional[int]:
    """Find element index by pattern in DOM"""
    for line in llm_representation.split('\n'):
        if pattern in line:
            match = re.search(r'\[(\d+)\]', line)
            if match:
                return int(match.group(1))
    return None


def find_element_with_text(llm_representation: str, search_text: str, element_type: str = "role=option") -> Optional[int]:
    """Find element index that contains specific text"""
    search_text = search_text.lower()
    lines = llm_representation.split('\n')
    
    for i, line in enumerate(lines):
        if search_text in line.lower():
            # Look backwards for element with specified type
            for j in range(i, max(0, i - 5), -1):
                prev_line = lines[j]
                if element_type in prev_line:
                    match = re.search(r'\[(\d+)\]', prev_line)
                    if match:
                        return int(match.group(1))
    return None

async def fill_combobox_field(
    executor: WorkflowExecutor,
    page: Any,
    state: WorkflowGraphState,
    field_name: str,
    value: str,
    search_pattern: str,
    retry_count: int = 2,
    wait_after_type: int = 3
) -> Dict[str, Any]:
    """
    Fill a combobox field (click input → type → select from dropdown)
    
    If any step fails, retries from the beginning (Step 1)
    
    Args:
        executor: WorkflowExecutor instance
        page: Page instance
        state: Workflow state
        field_name: Name for logging (e.g., "Customer", "Payment Terms")
        value: Value to type and select
        search_pattern: Pattern to find input field in DOM
        retry_count: Number of full retries if process fails
        wait_after_type: Seconds to wait after typing for dropdown
    
    Returns:
        {"success": bool, "error": str or None, "message": str}
    """
    
    print(f"\n  🔄 Filling {field_name}: {value}")
    
    last_error = None
    
    # Retry entire process from Step 1 if any step fails
    for attempt in range(retry_count + 1):
        if attempt > 0:
            print(f"\n  🔁 Retry attempt {attempt}/{retry_count} for {field_name}...")
            await asyncio.sleep(2)
        
        try:
            # ============================================
            # Step 1: Find input field
            # ============================================
            
            page_state = await get_page_state(page, state)
            llm_representation = page_state.get('dom_representation', '')
            
            input_index = find_element_index(llm_representation, search_pattern)
            
            if not input_index:
                last_error = f"{field_name} input field not found"
                print(f"  ✗ {last_error}")
                continue  # Retry from Step 1
            
            print(f"  ✓ Found {field_name} input at index: {input_index}")
            
            # ============================================
            # Step 2: Click input field
            # ============================================
            
            click_step = WorkflowStep(
                name=f"click_{field_name.lower().replace(' ', '_')}",
                action_type=WorkflowActionType.CLICK,
                parameters={"index": input_index}
            )
            await executor.execute_step(click_step)
            await asyncio.sleep(1)
            
            # ============================================
            # Step 3: Type value
            # ============================================
            
            input_step = WorkflowStep(
                name=f"type_{field_name.lower().replace(' ', '_')}",
                action_type=WorkflowActionType.INPUT,
                parameters={
                    "index": input_index,
                    "text": value,
                    "clear": True
                }
            )
            await executor.execute_step(input_step)
            await asyncio.sleep(wait_after_type)
            
            print(f"  ✓ Typed {field_name}: {value}")
            
            # ============================================
            # Step 4: Find option in dropdown
            # ============================================
            
            page_state = await get_page_state(page, state)
            llm_representation = page_state.get('dom_representation', '')
            
            option_index = find_element_with_text(
                llm_representation=llm_representation,
                search_text=value,
                element_type="role=option"
            )
            
            if not option_index:
                last_error = f"{field_name} option not found in dropdown"
                print(f"  ✗ {last_error}")
                continue  # Retry from Step 1
            
            print(f"  ✓ Found {field_name} option at index: {option_index}")
            
            # ============================================
            # Step 5: Click option
            # ============================================
            
            option_click_step = WorkflowStep(
                name=f"select_{field_name.lower().replace(' ', '_')}",
                action_type=WorkflowActionType.CLICK,
                parameters={"index": option_index}
            )
            await executor.execute_step(option_click_step)
            await asyncio.sleep(2)
            
            print(f"  ✅ {field_name} filled successfully")
            
            # SUCCESS - return immediately
            return {
                "success": True,
                "error": None,
                "message": f"{field_name} filled: {value}"
            }
        
        except Exception as e:
            last_error = str(e)
            print(f"  ✗ Exception in attempt {attempt + 1}: {e}")
            continue  # Retry from Step 1
    
    # All retries exhausted
    return {
        "success": False,
        "error": last_error or "Unknown error",
        "message": f"Failed to fill {field_name} after {retry_count + 1} attempts"
    }


async def fill_text_field(
    executor: WorkflowExecutor,
    page: Any,
    state: WorkflowGraphState,
    field_name: str,
    value: str,
    search_pattern: str
) -> Dict[str, Any]:
    """
    Fill a simple text input field (no dropdown)
    
    Args:
        executor: WorkflowExecutor instance
        page: Page instance
        state: Workflow state
        field_name: Name for logging (e.g., "Invoice Date")
        value: Value to type
        search_pattern: Pattern to find input field in DOM
    
    Returns:
        {"success": bool, "error": str or None, "message": str}
    """
    
    print(f"\n  🔄 Filling {field_name}: {value}")
    
    try:
        # Find input field
        page_state = await get_page_state(page, state)
        llm_representation = page_state.get('dom_representation', '')
        
        input_index = find_element_index(llm_representation, search_pattern)
        
        if not input_index:
            return {
                "success": False,
                "error": f"{field_name} input field not found",
                "message": f"Could not find input with pattern: {search_pattern}"
            }
        
        print(f"  ✓ Found {field_name} input at index: {input_index}")
        
        # Click field
        click_step = WorkflowStep(
            name=f"click_{field_name.lower().replace(' ', '_')}",
            action_type=WorkflowActionType.CLICK,
            parameters={"index": input_index}
        )
        await executor.execute_step(click_step)
        await asyncio.sleep(2)
        
        # Type value
        input_step = WorkflowStep(
            name=f"type_{field_name.lower().replace(' ', '_')}",
            action_type=WorkflowActionType.INPUT,
            parameters={
                "index": input_index,
                "text": value,
                "clear": True
            }
        )
        await executor.execute_step(input_step)
        await asyncio.sleep(1)
        
        print(f"  ✅ {field_name} filled successfully")
        
        return {
            "success": True,
            "error": None,
            "message": f"{field_name} filled: {value}"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Exception while filling {field_name}: {str(e)}"
        }
        
        
        
# nodes/processing/fill_invoice_helpers.py (add this function)

async def configure_invoice_columns(
    executor: WorkflowExecutor,
    page: Any,
    state: WorkflowGraphState
) -> Dict[str, Any]:
    """
    Configure invoice line columns visibility
    
    Steps:
    1. Find and click the column settings button (expanded=false)
    2. Wait for dropdown to appear
    3. Find all checkboxes with checked=false
    4. Click each to set them to checked=true
    
    Returns:
        {"success": bool, "columns_checked": int, "error": str or None}
    """
    
    print(f"\n  🔄 Configuring invoice columns...")
    
    try:
        # ============================================
        # Step 1: Find column settings button
        # ============================================
        
        page_state = await get_page_state(page, state)
        llm_representation = page_state.get('dom_representation', '')
        
        # Find button with expanded=false near "Amount" text
        button_index = None
        lines = llm_representation.split('\n')
        
        for i, line in enumerate(lines):
            if 'Amount' in line:
                # Look ahead for button with expanded=false
                for j in range(i, min(i + 10, len(lines))):
                    if 'button' in lines[j] and 'expanded=false' in lines[j]:
                        match = re.search(r'\[(\d+)\]', lines[j])
                        if match:
                            button_index = int(match.group(1))
                            print(f"  ✓ Found column settings button at index: {button_index}")
                            break
                if button_index:
                    break
        
        if not button_index:
            return {
                "success": False,
                "columns_checked": 0,
                "error": "Column settings button not found"
            }
        
        # ============================================
        # Step 2: Click to expand dropdown
        # ============================================
        
        print(f"  🔽 Clicking to expand column options...")
        
        expand_step = WorkflowStep(
            name="expand_columns",
            action_type=WorkflowActionType.CLICK,
            parameters={"index": button_index}
        )
        await executor.execute_step(expand_step)
        await asyncio.sleep(2)
        
        # ============================================
        # Step 3: Get fresh DOM with expanded dropdown
        # ============================================
        
        page_state = await get_page_state(page, state)
        llm_representation = page_state.get('dom_representation', '')
        
        # ============================================
        # Step 4: Find all unchecked checkboxes
        # ============================================
        
        lines = llm_representation.split('\n')
        unchecked_checkboxes = []
        
        for i, line in enumerate(lines):
            if 'input type=checkbox' in line and 'checked=false' in line:
                match = re.search(r'\[(\d+)\]', line)
                if match:
                    checkbox_index = int(match.group(1))
                    
                    # Get checkbox name/label from nearby lines
                    checkbox_name = "Unknown"
                    for j in range(i, min(i + 10, len(lines))):
                        # Look for column names: Product, Quantity, Disc.%, Taxes, etc.
                        if any(col in lines[j] for col in ['Quantity', 'Disc.%', 'Taxes', 'Label']):
                            checkbox_name = lines[j].strip()
                            break
                    
                    unchecked_checkboxes.append({
                        "index": checkbox_index,
                        "name": checkbox_name
                    })
        
        if not unchecked_checkboxes:
            print(f"  ✓ All columns already checked")
            
            # Click the button again to close dropdown
            close_step = WorkflowStep(
                name="close_columns_dropdown",
                action_type=WorkflowActionType.CLICK,
                parameters={"index": button_index}
            )
            await executor.execute_step(close_step)
            await asyncio.sleep(1)
            return {
                "success": True,
                "columns_checked": 0,
                "error": None
            }
        
        print(f"  📋 Found {len(unchecked_checkboxes)} unchecked columns:")
        for cb in unchecked_checkboxes:
            print(f"    • {cb['name']}")
        
        # ============================================
        # Step 5: Click each unchecked checkbox
        # ============================================
        
        columns_checked = 0
        
        for cb in unchecked_checkboxes:
            print(f"  ☑️  Checking: {cb['name']}...")
            
            check_step = WorkflowStep(
                name=f"check_column_{cb['index']}",
                action_type=WorkflowActionType.CLICK,
                parameters={"index": cb['index']}
            )
            
            await executor.execute_step(check_step)
            await asyncio.sleep(0.5)
            columns_checked += 1
        
        print(f"  ✅ Configured {columns_checked} columns successfully")
        
        # ============================================
        # Step 6: Close dropdown (click button again or click away)
        # ============================================
        
        # Click the button again to close dropdown
        close_step = WorkflowStep(
            name="close_columns_dropdown",
            action_type=WorkflowActionType.CLICK,
            parameters={"index": button_index}
        )
        await executor.execute_step(close_step)
        await asyncio.sleep(1)
        
        return {
            "success": True,
            "columns_checked": columns_checked,
            "error": None
        }
    
    except Exception as e:
        print(f"  ✗ Error configuring columns: {e}")
        return {
            "success": False,
            "columns_checked": 0,
            "error": str(e)
        }
        
        
        
# nodes/processing/fill_invoice_helpers.py (add this function)

async def add_invoice_line(
    executor: WorkflowExecutor,
    page: Any,
    state: WorkflowGraphState
) -> Dict[str, Any]:
    """
    Click 'Add a line' button to add a new product line to invoice
    
    Returns:
        {"success": bool, "error": str or None}
    """
    
    print(f"\n  ➕ Adding invoice line...")
    print("started")
    
    try:
        # Get current DOM
        print("ok")
        page_state = await get_page_state(page, state)
        llm_representation = page_state.get('dom_representation', '')
        
        # Find "Add a line" button
        add_line_index = find_element_with_text(
            llm_representation=llm_representation,
            search_text="Add a line",
            element_type="role=button"
        )
        print(add_invoice_line)
        if not add_line_index:
            return {
                "success": False,
                "error": "'Add a line' button not found"
            }
        
        print(f"  ✓ Found 'Add a line' button at index: {add_line_index}")
        
        # Click the button
        click_step = WorkflowStep(
            name="add_invoice_line",
            action_type=WorkflowActionType.CLICK,
            parameters={"index": add_line_index}
        )
        
        await executor.execute_step(click_step)
        await asyncio.sleep(5)
        
        print(f"  ✅ Invoice line added successfully")
        
        return {
            "success": True,
            "error": None
        }
    
    except Exception as e:
        print(f"  ✗ Error adding line: {e}")
        return {
            "success": False,
            "error": str(e)
        }
        
        
        
        
        

# nodes/processing/fill_invoice_helpers.py (add this function)

async def fill_product_line(
    executor: WorkflowExecutor,
    page: Any,
    state: WorkflowGraphState,
    product: Dict[str, Any],
    line_number: int = 1
) -> Dict[str, Any]:
    """
    Fill a single product line in the invoice
    
    Fields filled:
    - Product name/description (textarea in td name=name)
    - Quantity (input in td name=quantity)
    - Price (input in td name=price_unit)
    - Discount % (input in td name=discount)
    - Taxes (combobox in td name=tax_ids) - optional
    
    Args:
        executor: WorkflowExecutor instance
        page: Page instance
        state: Workflow state
        product: Product dict with keys: product_code, description, quantity, unit_price, discount
        line_number: Line number for logging
    
    Returns:
        {"success": bool, "error": str or None}
    """
    
    product_code = product.get("product_code", "")
    description = product.get("description", "")
    quantity = product.get("quantity", 0)
    unit_price = product.get("unit_price", 0)
    discount = product.get("discount_percent", 0)  # From transformed data
    
    # Combine product code and description
    full_product_name = f"{product_code} - {description}" if product_code else description
    
    print(f"\n  📦 Filling product line {line_number}:")
    print(f"    Name: {full_product_name}")
    print(f"    Qty: {quantity}, Price: £{unit_price:.2f}, Discount: {discount}%")
    
    try:
        # Get current DOM
        page_state = await get_page_state(page, state)
        llm_representation = page_state.get('dom_representation', '')
        
        # ============================================
        # FILL PRODUCT NAME (textarea in td name=name)
        # ============================================
        
        name_index = None
        lines = llm_representation.split('\n')
        
        for i, line in enumerate(lines):
            if 'td name=name' in line:
                # Look ahead for textarea
                for j in range(i, min(i + 10, len(lines))):
                    if 'textarea' in lines[j]:
                        match = re.search(r'\[(\d+)\]', lines[j])
                        if match:
                            name_index = int(match.group(1))
                            break
                if name_index:
                    break
        
        if not name_index:
            return {
                "success": False,
                "error": "Product name field (textarea) not found"
            }
        
        print(f"  ✓ Found product name field at index: {name_index}")
        
        # Fill product name
        name_step = WorkflowStep(
            name="fill_product_name",
            action_type=WorkflowActionType.INPUT,
            parameters={
                "index": name_index,
                "text": full_product_name,
                "clear": True
            }
        )
        await executor.execute_step(name_step)
        await asyncio.sleep(1)
        
        print(f"  ✅ Product name filled")
        
        # ============================================
        # FILL QUANTITY (input in td name=quantity)
        # ============================================
        
        # Get fresh DOM
        page_state = await get_page_state(page, state)
        llm_representation = page_state.get('dom_representation', '')
        lines = llm_representation.split('\n')
        
        quantity_index = None
        for i, line in enumerate(lines):
            if 'td name=quantity' in line:
                # Look ahead for input
                for j in range(i, min(i + 10, len(lines))):
                    if 'input' in lines[j] and 'type=text' in lines[j]:
                        match = re.search(r'\[(\d+)\]', lines[j])
                        if match:
                            quantity_index = int(match.group(1))
                            break
                if quantity_index:
                    break
        
        if not quantity_index:
            return {
                "success": False,
                "error": "Quantity field not found"
            }
        
        print(f"  ✓ Found quantity field at index: {quantity_index}")
        
        # Fill quantity
        quantity_step = WorkflowStep(
            name="fill_quantity",
            action_type=WorkflowActionType.INPUT,
            parameters={
                "index": quantity_index,
                "text": str(quantity),
                "clear": True
            }
        )
        await executor.execute_step(quantity_step)
        await asyncio.sleep(1)
        
        print(f"  ✅ Quantity filled: {quantity}")
        
        # ============================================
        # FILL UNIT PRICE (input in td name=price_unit)
        # ============================================
        
        # Get fresh DOM
        page_state = await get_page_state(page, state)
        llm_representation = page_state.get('dom_representation', '')
        lines = llm_representation.split('\n')
        
        price_index = None
        for i, line in enumerate(lines):
            if 'td name=price_unit' in line:
                # Look ahead for input
                for j in range(i, min(i + 10, len(lines))):
                    if 'input' in lines[j] and 'type=text' in lines[j]:
                        match = re.search(r'\[(\d+)\]', lines[j])
                        if match:
                            price_index = int(match.group(1))
                            break
                if price_index:
                    break
        
        if not price_index:
            return {
                "success": False,
                "error": "Price field not found"
            }
        
        print(f"  ✓ Found price field at index: {price_index}")
        
        # Fill price
        price_step = WorkflowStep(
            name="fill_price",
            action_type=WorkflowActionType.INPUT,
            parameters={
                "index": price_index,
                "text": str(unit_price),
                "clear": True
            }
        )
        await executor.execute_step(price_step)
        await asyncio.sleep(1)
        
        print(f"  ✅ Price filled: £{unit_price:.2f}")
        
        # ============================================
        # FILL DISCOUNT (input in td name=discount)
        # ============================================
        
        if discount > 0:
            # Get fresh DOM
            page_state = await get_page_state(page, state)
            llm_representation = page_state.get('dom_representation', '')
            lines = llm_representation.split('\n')
            
            discount_index = None
            for i, line in enumerate(lines):
                if 'td name=discount' in line:
                    # Look ahead for input
                    for j in range(i, min(i + 10, len(lines))):
                        if 'input' in lines[j] and 'type=text' in lines[j]:
                            match = re.search(r'\[(\d+)\]', lines[j])
                            if match:
                                discount_index = int(match.group(1))
                                break
                    if discount_index:
                        break
            
            if discount_index:
                print(f"  ✓ Found discount field at index: {discount_index}")
                
                # Fill discount
                discount_step = WorkflowStep(
                    name="fill_discount",
                    action_type=WorkflowActionType.INPUT,
                    parameters={
                        "index": discount_index,
                        "text": str(discount),
                        "clear": True
                    }
                )
                await executor.execute_step(discount_step)
                await asyncio.sleep(1)
                
                print(f"  ✅ Discount filled: {discount}%")
            else:
                print(f"  ⚠️  Discount field not found, skipping...")
        else:
            print(f"  ⏭️  No discount to apply")
        
        # ============================================
        # TAXES - SKIP FOR NOW (can be added later)
        # ============================================
        
        print(f"  ✅ Product line {line_number} filled successfully")
        
        return {
            "success": True,
            "error": None
        }
    
    except Exception as e:
        print(f"  ✗ Error filling product line: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }