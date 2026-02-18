# nodes/spreadsheet/extract_spreadsheet_data_node.py

from typing import Dict, Any, List
from utils.workflow_graph_state import WorkflowGraphState
from browser_use.browser.events import SwitchTabEvent
import asyncio



# nodes/spreadsheet/extract_spreadsheet_data_node.py - UPDATE

async def extract_spreadsheet_data_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Extract data from SharePoint Sales Pipeline CRM
    
    Uses JavaScript to extract all active rows from Microsoft Lists
    Stores extracted data in workflow for processing
    
    NOTE: If data already extracted, skips re-extraction
    """
    
    print("\n" + "="*60)
    print("SPREADSHEET DATA EXTRACTION")
    print("="*60)
    
    # ============================================
    # FIND SPREADSHEET WORKFLOW
    # ============================================
    
    workflows = state.get("workflows", [])
    spreadsheet_workflow = None
    spreadsheet_index = -1
    
    for idx, wf in enumerate(workflows):
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "spreadsheet_tab" or wf.get("name") == "sharepoint_crm_navigation":
            spreadsheet_workflow = wf
            spreadsheet_index = idx
            tab_id = wf.get("tab_id")
            break
    
    if not spreadsheet_workflow:
        print("  ✗ Spreadsheet workflow not found in state")
        return {
            **state,
            "error_message": "Spreadsheet workflow not found",
            "current_step": "extraction_failed"
        }
    
    # ============================================
    # CHECK IF ALREADY EXTRACTED
    # ============================================
    
    extraction_complete = spreadsheet_workflow.get("extraction_complete", False)
    extracted_rows = spreadsheet_workflow.get("extracted_rows", None)
    
    if extraction_complete and extracted_rows:
        total_rows = spreadsheet_workflow.get("total_rows", len(extracted_rows) if extracted_rows else 0)
        print(f"\n  ✅ Data already extracted!")
        print(f"  📊 Total Rows: {total_rows}")
        print(f"  ⏭️  Skipping re-extraction")
        
        return {
            **state,
            "current_step": "extraction_complete"
        }
    
    # ============================================
    # GET RETRY COUNT
    # ============================================
    
    retry_count = spreadsheet_workflow.get("extraction_retry_count", 0)
    
    if retry_count > 0:
        print(f"\n  🔄 Extraction retry attempt {retry_count}")
    
    # ============================================
    # GET PAGE FROM WORKFLOW
    # ============================================
    
    page = spreadsheet_workflow.get("page_instance")
    
    if not page:
        print("  ✗ Spreadsheet page instance not found in workflow")
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "extraction_complete": False,
            "extracted_rows": None,
            "total_rows": 0,
            "extraction_retry_count": retry_count + 1,  # ✅ Increment retry
            "error": "Page instance not found"
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": "Spreadsheet page instance not found",
            "current_step": "extraction_failed"
        }
        
    # --- Switch to correct tab ---
    browser = state.get("browser_instance")
    await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
    await asyncio.sleep(2)
    
    # ============================================
    # JAVASCRIPT EXTRACTION SCRIPT
    # ============================================
    
    EXTRACTION_SCRIPT = """
() => {
    return (async () => {
        const rows = [];
        
        function wait(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
        
        // ============================================
        // Retry logic to find list container
        // ============================================
        
        let listContainer = null;
        let retries = 0;
        const maxRetries = 5;
        
        while (!listContainer && retries < maxRetries) {
            listContainer = document.querySelector('#html-list_3, [role=grid]');
            if (!listContainer) {
                await wait(1000);
                retries++;
            }
        }
        
        if (!listContainer) {
            return { success: false, error: 'List container not found after ' + maxRetries + ' retries' };
        }
        
        // Wait a bit for content to fully load
        await wait(1500);
        
        // Get headers
        const headers = Array.from(listContainer.querySelectorAll('[role=columnheader]'))
            .map(header => {
                const button = header.querySelector('[role=button]');
                return button ? button.textContent.trim().split('\\n')[0].trim() : '';
            })
            .filter(h => h && h !== 'Add column');
        
        // ============================================
        // Retry logic to find data rows
        // ============================================
        
        let dataRows = [];
        retries = 0;
        
        while (dataRows.length === 0 && retries < maxRetries) {
            dataRows = Array.from(listContainer.querySelectorAll('[role=row]'))
                .filter(row => !row.querySelector('[role=columnheader]'));
            
            if (dataRows.length === 0) {
                await wait(1000);
                retries++;
            }
        }
        
        if (dataRows.length === 0) {
            return { 
                success: false, 
                error: 'No data rows found after ' + maxRetries + ' retries',
                total_rows: 0,
                total_columns: headers.length,
                headers: headers,
                rows: []
            };
        }
        
        let skipped_already_processed = 0;
        let skipped_inactive = 0;
        
        // Extract data from each row
        dataRows.forEach((row, index) => {
            const allCells = Array.from(row.querySelectorAll('[role=gridcell]'));
            
            // Skip first cell (checkbox/selection)
            const dataCells = allCells.slice(1);
            
            // Build row object dynamically
            const rowData = { row_index: index };
            
            headers.forEach((header, colIndex) => {
                const key = header
                    .toLowerCase()
                    .replace(/\\s+/g, '_')
                    .replace(/%/g, 'percent')
                    .replace(/[^a-z0-9_]/g, '');
                
                rowData[key] = dataCells[colIndex]?.textContent.trim() || '';
            });
            
            // Skip if status is not Active
            if (rowData.status !== 'Active') {
                skipped_inactive++;
                return;
            }
            
            // Skip if Invoice ID is already filled
            const invoiceIdFields = ['invoice_id', 'invoiceid', 'invoice_number', 'invoicenumber'];
            let hasInvoiceId = false;
            
            for (const field of invoiceIdFields) {
                if (rowData[field] && rowData[field].trim() !== '' && rowData[field].trim() !== '-') {
                    hasInvoiceId = true;
                    break;
                }
            }
            
            if (hasInvoiceId) {
                skipped_already_processed++;
                return;
            }
            
            rows.push(rowData);
        });
        
        return {
            success: true,
            total_rows: rows.length,
            total_columns: headers.length,
            headers: headers,
            rows: rows,
            skipped_already_processed: skipped_already_processed,
            skipped_inactive: skipped_inactive
        };
    })();
}
""".strip()
            
    try:
        # ============================================
        # EXECUTE JAVASCRIPT EXTRACTION
        # ============================================
        
        print(f"\n  🔄 Executing JavaScript extraction...")
        
        # Execute the script directly on the page
        extraction_result = await page.evaluate(EXTRACTION_SCRIPT)
        
        # Parse JSON if result is a string
        if isinstance(extraction_result, str):
            import json
            extraction_result = json.loads(extraction_result)

        # ============================================
        # VALIDATE EXTRACTION RESULT
        # ============================================
        
        if isinstance(extraction_result, dict) and extraction_result.get("error"):
            error_msg = extraction_result.get("error")
            print(f"  ✗ Extraction error: {error_msg}")
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "extraction_complete": False,
                "extracted_rows": None,
                "total_rows": 0,
                "extraction_retry_count": retry_count + 1,  # ✅ Increment retry
                "error": f"Extraction error: {error_msg}"
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": f"Extraction error: {error_msg}",
                "current_step": "extraction_failed"
            }
        
        if not isinstance(extraction_result, dict):
            print(f"  ✗ Unexpected result type: {type(extraction_result)}")
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "extraction_complete": False,
                "extracted_rows": None,
                "total_rows": 0,
                "extraction_retry_count": retry_count + 1,  # ✅ Increment retry
                "error": "Extraction returned unexpected data type"
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": "Extraction returned unexpected data type",
                "current_step": "extraction_failed"
            }
        
        # ============================================
        # EXTRACT DATA
        # ============================================
        
        success = extraction_result.get("success", False)
        total_rows = extraction_result.get("total_rows", 0)
        headers = extraction_result.get("headers", [])
        rows = extraction_result.get("rows", [])
        skipped_already_processed = extraction_result.get("skipped_already_processed", 0)
        skipped_inactive = extraction_result.get("skipped_inactive", 0)
        
        if not success:
            print(f"  ✗ Extraction unsuccessful")
            
            updated_workflows = workflows.copy()
            updated_workflows[spreadsheet_index] = {
                **spreadsheet_workflow,
                "extraction_complete": False,
                "extracted_rows": None,
                "total_rows": 0,
                "extraction_retry_count": retry_count + 1,  # ✅ Increment retry
                "error": "Extraction returned success=false"
            }
            
            return {
                **state,
                "workflows": updated_workflows,
                "error_message": "Extraction returned success=false",
                "current_step": "extraction_failed"
            }
        
        # ============================================
        # PRINT EXTRACTION SUMMARY
        # ============================================
        
        print(f"\n  ✅ Extraction successful!")
        print(f"  📊 Rows to Process: {total_rows}")
        print(f"  ⏭️  Skipped (Already Processed): {skipped_already_processed}")
        print(f"  ⏭️  Skipped (Inactive): {skipped_inactive}")
        print(f"  📋 Total Columns: {len(headers)}")
        
        if total_rows > 0:
            print(f"\n  🔍 Sample Data (First Row):")
            first_row = rows[0]
            
            # Print key fields
            key_fields = [
                'sales_request_ref',
                'customer_company', 
                'customer_contact',
                'trading_address'
            ]
            
            for field in key_fields:
                if field in first_row:
                    value = first_row[field]
                    display_value = value[:50] + "..." if len(value) > 50 else value
                    print(f"    • {field}: {display_value}")
            
            # Show all extracted rows summary
            print(f"\n  📝 Extracted Rows:")
            for idx, row in enumerate(rows):
                sales_ref = row.get('sales_request_ref', 'N/A')
                customer = row.get('customer_company', 'N/A')
                print(f"    [{idx + 1}] {sales_ref} - {customer}")
        else:
            print(f"\n  ⚠️  No rows to process")
            print(f"  ℹ️  All rows either inactive or already processed")
        
        # ============================================
        # UPDATE WORKFLOW WITH EXTRACTED DATA
        # ============================================
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "extraction_complete": True,
            "extracted_rows": rows,
            "total_rows": total_rows,
            "extracted_headers": headers,
            "current_row_index": 0,
            "rows_processed": 0,
            "rows_failed": 0,
            "failed_transformations": [],
            "failed_spreadsheet_updates": [],
            "extraction_retry_count": 0,  # ✅ Reset on success
            "error": None
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": None,
            "current_step": "extraction_complete"
        }
    
    except Exception as e:
        print(f"\n  ✗ Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        
        updated_workflows = workflows.copy()
        updated_workflows[spreadsheet_index] = {
            **spreadsheet_workflow,
            "extraction_complete": False,
            "extracted_rows": None,
            "total_rows": 0,
            "extraction_retry_count": retry_count + 1,  # ✅ Increment retry
            "error": f"Extraction exception: {str(e)}"
        }
        
        return {
            **state,
            "workflows": updated_workflows,
            "error_message": f"Extraction exception: {str(e)}",
            "current_step": "extraction_failed"
        }