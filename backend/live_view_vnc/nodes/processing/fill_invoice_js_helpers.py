# nodes/processing/fill_invoice_js_helpers.py

from typing import Dict, Any
import json


# ============================================
# JAVASCRIPT HELPER SCRIPTS
# ============================================

# def get_fill_customer_script(customer_name: str) -> str:
#     """JavaScript to fill customer combobox field and pick the first result"""
#     import json
#     customer_name_json = json.dumps(customer_name)
    
#     return f"""
# () => {{
#     return (async () => {{
#         const CUSTOMER_NAME = {customer_name_json};
        
#         async function humanType(element, text) {{
#             element.focus();
#             element.click();
            
#             for (let i = 0; i < text.length; i++) {{
#                 const char = text[i];
#                 element.value = text.substring(0, i + 1);
#                 element.dispatchEvent(new KeyboardEvent('keydown', {{ key: char, bubbles: true }}));
#                 element.dispatchEvent(new KeyboardEvent('keypress', {{ key: char, bubbles: true }}));
#                 element.dispatchEvent(new Event('input', {{ bubbles: true }}));
#                 element.dispatchEvent(new KeyboardEvent('keyup', {{ key: char, bubbles: true }}));
#                 await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50));
#             }}
#             element.dispatchEvent(new Event('change', {{ bubbles: true }}));
#         }}
        
#         function wait(ms) {{
#             return new Promise(resolve => setTimeout(resolve, ms));
#         }}
        
#         try {{
#             const inputField = document.querySelector('input[placeholder*="Search a name"]') ||
#                               document.querySelector('input[placeholder*="Tax ID"]');
            
#             if (!inputField) {{
#                 return {{ success: false, error: "Customer input field not found" }};
#             }}
            
#             inputField.click();
#             inputField.focus();
#             await wait(1000);
            
#             inputField.value = '';
#             inputField.dispatchEvent(new Event('input', {{ bubbles: true }}));
#             await humanType(inputField, CUSTOMER_NAME);
#             await wait(3000);
            
#             const dropdownOptions = Array.from(document.querySelectorAll('[role="option"]'));
            
#             if (dropdownOptions.length === 0) {{
#                 return {{ success: false, error: "CUSTOMER_NOT_IN_DATABASE" }};
#             }}
            
#             const firstOption = dropdownOptions[0];
#             firstOption.click();
#             await wait(2000);
            
#             return {{ success: true, error: null }};
            
#         }} catch (e) {{
#             return {{ success: false, error: e.message }};
#         }}
#     }})();
# }}
# """.strip()



def get_fill_customer_script(customer_name: str) -> str:
    """JavaScript to fill customer combobox field"""
    # Use json.dumps for safe escaping
    customer_name_json = json.dumps(customer_name)
    
    return f"""
() => {{
    return (async () => {{
        const CUSTOMER_NAME = {customer_name_json};
        
        async function humanType(element, text) {{
            element.focus();
            element.click();
            
            for (let i = 0; i < text.length; i++) {{
                const char = text[i];
                element.value = text.substring(0, i + 1);
                element.dispatchEvent(new KeyboardEvent('keydown', {{ key: char, bubbles: true }}));
                element.dispatchEvent(new KeyboardEvent('keypress', {{ key: char, bubbles: true }}));
                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                element.dispatchEvent(new KeyboardEvent('keyup', {{ key: char, bubbles: true }}));
                await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50));
            }}
            element.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
        
        function wait(ms) {{
            return new Promise(resolve => setTimeout(resolve, ms));
        }}
        
        try {{
            const inputField = document.querySelector('input[placeholder*="Search a name"]') ||
                              document.querySelector('input[placeholder*="Tax ID"]');
            
            if (!inputField) {{
                return {{ success: false, error: "Customer input field not found" }};
            }}
            
            inputField.click();
            inputField.focus();
            await wait(1000);
            
            inputField.value = '';
            inputField.dispatchEvent(new Event('input', {{ bubbles: true }}));
            await humanType(inputField, CUSTOMER_NAME);
            await wait(3000);
            
            const dropdownOptions = Array.from(document.querySelectorAll('[role="option"]'));
            
            if (dropdownOptions.length === 0) {{
                return {{ success: false, error: "CUSTOMER_NOT_IN_DATABASE" }};
            }}
            
            const customerNameLower = CUSTOMER_NAME.toLowerCase().trim();
            const matchingOption = dropdownOptions.find(option => {{
                const optionTextLower = option.textContent.trim().toLowerCase();
                return optionTextLower === customerNameLower;
            }});
            
            if (!matchingOption) {{
                return {{ success: false, error: "CUSTOMER_NOT_IN_DATABASE" }};
            }}
            
            matchingOption.click();
            await wait(2000);
            
            return {{ success: true, error: null }};
            
        }} catch (e) {{
            return {{ success: false, error: e.message }};
        }}
    }})();
}}
""".strip()




def get_fill_invoice_date_script(invoice_date: str) -> str:
    """JavaScript to fill invoice date field"""
    invoice_date_json = json.dumps(invoice_date)
    
    return f"""
() => {{
    return (async () => {{
        const INVOICE_DATE = {invoice_date_json};
        
        async function humanType(element, text) {{
            element.focus();
            element.click();
            
            for (let i = 0; i < text.length; i++) {{
                const char = text[i];
                
                if (element.tagName === 'BUTTON') {{
                    element.setAttribute('value', text.substring(0, i + 1));
                    element.textContent = text.substring(0, i + 1);
                }} else {{
                    element.value = text.substring(0, i + 1);
                }}
                
                element.dispatchEvent(new KeyboardEvent('keydown', {{ key: char, bubbles: true }}));
                element.dispatchEvent(new KeyboardEvent('keypress', {{ key: char, bubbles: true }}));
                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                element.dispatchEvent(new KeyboardEvent('keyup', {{ key: char, bubbles: true }}));
                await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50));
            }}
            element.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
        
        function wait(ms) {{
            return new Promise(resolve => setTimeout(resolve, ms));
        }}
        
        try {{
            const inputField = document.getElementById('invoice_date_0');
            
            if (!inputField) {{
                return {{ success: false, error: "Invoice date input field not found" }};
            }}
            
            inputField.click();
            inputField.focus();
            await wait(500);
            
            // Clear existing value
            inputField.dispatchEvent(new KeyboardEvent('keydown', {{ 
                key: 'a', 
                code: 'KeyA',
                ctrlKey: true, 
                bubbles: true 
            }}));
            await wait(100);
            
            inputField.dispatchEvent(new KeyboardEvent('keydown', {{ 
                key: 'Backspace', 
                code: 'Backspace',
                bubbles: true 
            }}));
            await wait(100);
            
            if (inputField.tagName === 'BUTTON') {{
                inputField.setAttribute('value', '');
                inputField.textContent = '';
            }} else {{
                inputField.value = '';
            }}
            
            inputField.dispatchEvent(new Event('input', {{ bubbles: true }}));
            inputField.dispatchEvent(new Event('change', {{ bubbles: true }}));
            await wait(500);
            
            await humanType(inputField, INVOICE_DATE);
            inputField.blur();
            await wait(1000);
            
            return {{ success: true, error: null }};
            
        }} catch (e) {{
            return {{ success: false, error: e.message }};
        }}
    }})();
}}
""".strip()


def get_fill_payment_terms_script(payment_terms: str) -> str:
    """JavaScript to fill payment terms combobox with create option"""
    payment_terms_json = json.dumps(payment_terms)
    
    return f"""
() => {{
    return (async () => {{
        const PAYMENT_TERMS = {payment_terms_json};
        
        async function humanType(element, text) {{
            element.focus();
            element.click();
            
            for (let i = 0; i < text.length; i++) {{
                const char = text[i];
                element.value = text.substring(0, i + 1);
                element.dispatchEvent(new KeyboardEvent('keydown', {{ key: char, bubbles: true }}));
                element.dispatchEvent(new KeyboardEvent('keypress', {{ key: char, bubbles: true }}));
                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                element.dispatchEvent(new KeyboardEvent('keyup', {{ key: char, bubbles: true }}));
                await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50));
            }}
            element.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
        
        function wait(ms) {{
            return new Promise(resolve => setTimeout(resolve, ms));
        }}
        
        try {{
            const inputField = document.querySelector('input[placeholder*="Payment Terms"]') ||
                              document.querySelector('input[name*="payment"]') ||
                              document.querySelector('input[id*="payment"]') ||
                              Array.from(document.querySelectorAll('input')).find(input => {{
                                  const label = input.closest('div')?.querySelector('label');
                                  return label && label.textContent.toLowerCase().includes('payment terms');
                              }});
            
            if (!inputField) {{
                return {{ success: false, error: "Payment Terms input field not found" }};
            }}
            
            inputField.click();
            inputField.focus();
            await wait(1000);
            
            inputField.value = '';
            inputField.dispatchEvent(new Event('input', {{ bubbles: true }}));
            await humanType(inputField, PAYMENT_TERMS);
            await wait(3000);
            
            const dropdownOptions = Array.from(document.querySelectorAll('[role="option"]'));
            
            if (dropdownOptions.length === 0) {{
                return {{ success: false, error: "No dropdown appeared" }};
            }}
            
            const paymentTermsLower = PAYMENT_TERMS.toLowerCase().trim();
            const matchingOption = dropdownOptions.find(option => {{
                const optionTextLower = option.textContent.trim().toLowerCase();
                return optionTextLower === paymentTermsLower;
            }});
            
            if (matchingOption) {{
                matchingOption.click();
                await wait(2000);
                return {{ success: true, error: null, created: false }};
            }} else {{
                // Look for Create option
                const createOption = dropdownOptions.find(option => {{
                    const optionTextLower = option.textContent.trim().toLowerCase();
                    return optionTextLower.includes('create') || 
                           optionTextLower.includes('add') ||
                           optionTextLower.includes('new');
                }});
                
                if (!createOption) {{
                    return {{ success: false, error: "Payment Terms not found and no Create option" }};
                }}
                
                createOption.click();
                await wait(2000);
                
                const popup = document.querySelector('div[role="dialog"]');
                if (!popup) {{
                    return {{ success: false, error: "Create popup not found" }};
                }}
                
                const popupInput = document.getElementById('name_0');
                if (popupInput && (!popupInput.value || popupInput.value.trim() === '')) {{
                    await humanType(popupInput, PAYMENT_TERMS);
                }}
                await wait(1000);
                
                const saveButton = Array.from(popup.querySelectorAll('button')).find(btn => 
                    btn.textContent.trim().toLowerCase() === 'save'
                );
                
                if (!saveButton) {{
                    return {{ success: false, error: "Save button not found in popup" }};
                }}
                
                saveButton.click();
                await wait(2000);
                
                return {{ success: true, error: null, created: true }};
            }}
            
        }} catch (e) {{
            return {{ success: false, error: e.message }};
        }}
    }})();
}}
""".strip()


def get_add_products_script(products: list) -> str:
    """JavaScript to add and fill all product lines"""
    
    # Use json.dumps to convert the entire products list
    products_json = json.dumps(products)
    
    return f"""
() => {{
    return (async () => {{
        const DEMO_PRODUCTS = {products_json};
        
        async function humanType(element, text) {{
            element.focus();
            element.click();
            const textStr = String(text);
            
            for (let i = 0; i < textStr.length; i++) {{
                const char = textStr[i];
                element.value = textStr.substring(0, i + 1);
                
                // Only trigger input event, not keyboard events (to avoid Odoo conflicts)
                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                
                await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50));
            }}
            
            // Trigger final change event
            element.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
        
        // Simpler typing for textareas (to avoid Odoo resize errors)
        async function humanTypeTextarea(element, text) {{
            element.focus();
            element.click();
            await new Promise(resolve => setTimeout(resolve, 200));
            
            // Set value directly without character-by-character
            element.value = text;
            
            // Only trigger essential events
            element.dispatchEvent(new Event('input', {{ bubbles: true }}));
            await new Promise(resolve => setTimeout(resolve, 100));
            element.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
        
        function wait(ms) {{
            return new Promise(resolve => setTimeout(resolve, ms));
        }}
        
        function isRowEmpty(row) {{
            const nameCell = row.querySelector('td[name="name"]');
            if (!nameCell) return false;
            const nameTextarea = nameCell.querySelector('textarea');
            if (!nameTextarea) return false;
            return nameTextarea.value.trim() === '';
        }}
        
        function hasEmptyRow() {{
            const rows = Array.from(document.querySelectorAll('tbody tr, table tr')).filter(row => 
                row.querySelector('td[name="name"]')
            );
            return rows.some(row => isRowEmpty(row));
        }}
        
        async function fillProductLine(product, lineNumber) {{
            const productCode = product.product_code || "";
            const description = product.description || "";
            const quantity = product.quantity || 0;
            const unitPrice = product.unit_price || 0;
            const discount = product.discount_percent || 0;
            const tax = product.tax || "";
            
            const fullProductName = productCode ? `${{productCode}} - ${{description}}` : description;
            
            try {{
                // Retry logic to find the last row (it might take time to render)
                let currentRow = null;
                let retries = 0;
                const maxRetries = 5;
                
                while (!currentRow && retries < maxRetries) {{
                    const rows = Array.from(document.querySelectorAll('tbody tr, table tr')).filter(row => 
                        row.querySelector('td[name="name"]')
                    );
                    
                    if (rows.length > 0) {{
                        currentRow = rows[rows.length - 1];
                        
                        // Verify the row has all required cells
                        const nameCell = currentRow.querySelector('td[name="name"]');
                        const nameTextarea = nameCell?.querySelector('textarea');
                        
                        if (!nameTextarea) {{
                            currentRow = null;  // Row not fully rendered yet
                            await wait(500);
                            retries++;
                        }}
                    }} else {{
                        await wait(500);
                        retries++;
                    }}
                }}
                
                if (!currentRow) {{
                    throw new Error("No rows found in invoice table after " + maxRetries + " retries");
                }}
                
                // Fill Product Name (use textarea-specific function)
                const nameCell = currentRow.querySelector('td[name="name"]');
                if (!nameCell) throw new Error("Product name cell not found");
                const nameTextarea = nameCell.querySelector('textarea');
                if (!nameTextarea) throw new Error("Product name textarea not found");
                
                nameTextarea.click();
                await wait(500);
                nameTextarea.value = '';
                await humanTypeTextarea(nameTextarea, fullProductName);
                nameTextarea.blur();
                await wait(1500);  // Increased delay
                
                // Fill Quantity (use regular humanType for inputs)
                const quantityCell = currentRow.querySelector('td[name="quantity"]');
                if (!quantityCell) throw new Error("Quantity cell not found");
                const quantityInput = quantityCell.querySelector('input[type="text"]');
                if (!quantityInput) throw new Error("Quantity input not found");
                
                quantityInput.click();
                await wait(500);
                quantityInput.value = '';
                quantityInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                await humanType(quantityInput, quantity);
                quantityInput.blur();
                await wait(1500);  // Increased delay
                
                // Fill Unit Price
                const priceCell = currentRow.querySelector('td[name="price_unit"]');
                if (!priceCell) throw new Error("Price cell not found");
                const priceInput = priceCell.querySelector('input[type="text"]');
                if (!priceInput) throw new Error("Price input not found");
                
                priceInput.click();
                await wait(500);
                priceInput.value = '';
                priceInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                await humanType(priceInput, unitPrice);
                priceInput.blur();
                await wait(1500);  // Increased delay
                
                // Fill Discount
                if (discount > 0) {{
                    const discountCell = currentRow.querySelector('td[name="discount"]');
                    if (discountCell) {{
                        const discountInput = discountCell.querySelector('input[type="text"]');
                        if (discountInput) {{
                            discountInput.click();
                            await wait(500);
                            discountInput.value = '';
                            discountInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            await humanType(discountInput, discount);
                            discountInput.blur();
                            await wait(1500);  // Increased delay
                        }}
                    }}
                }}
                
                // Fill Tax
                if (tax) {{
                    const taxCell = currentRow.querySelector('td[name="tax_ids"]');
                    if (taxCell) {{
                        const taxInput = taxCell.querySelector('input[type="text"]');
                        if (taxInput) {{
                            taxInput.click();
                            await wait(500);
                            taxInput.value = '';
                            taxInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            await humanType(taxInput, tax);
                            await wait(2500);  // Increased delay for dropdown
                            
                            const taxOptions = Array.from(document.querySelectorAll('[role="option"]'));
                            if (taxOptions.length > 0) {{
                                const taxLower = tax.toLowerCase().trim();
                                const matchingTax = taxOptions.find(option => {{
                                    const optionText = option.textContent.trim().toLowerCase();
                                    return optionText === taxLower || optionText.includes(taxLower);
                                }});
                                
                                if (matchingTax) {{
                                    matchingTax.click();
                                    await wait(1500);  // Increased delay
                                }} else {{
                                    taxInput.blur();
                                    await wait(500);
                                }}
                            }} else {{
                                taxInput.blur();
                                await wait(500);
                            }}
                        }}
                    }}
                }}
                
                return {{ success: true, error: null }};
                
            }} catch (e) {{
                return {{ success: false, error: e.message || String(e) }};
            }}
        }}
        
        try {{
            // Validate products array
            if (!DEMO_PRODUCTS || DEMO_PRODUCTS.length === 0) {{
                return {{
                    success: false,
                    error: "No products provided",
                    productsAdded: 0,
                    totalProducts: 0,
                    details: []
                }};
            }}
            
            let successfullyAdded = 0;
            const results = [];
            
            for (let i = 0; i < DEMO_PRODUCTS.length; i++) {{
                const product = DEMO_PRODUCTS[i];
                const lineNumber = i + 1;
                
                try {{
                    const emptyRowExists = hasEmptyRow();
                    
                    if (!emptyRowExists) {{
                        const addLineButton = Array.from(document.querySelectorAll('a[role="button"]')).find(btn => 
                            btn.textContent.trim().toLowerCase() === 'add a line'
                        );
                        
                        if (!addLineButton) {{
                            const errorMsg = "Add a line button not found";
                            results.push({{ product: product.description || "Unknown", success: false, error: errorMsg }});
                            return {{
                                success: false,
                                error: errorMsg,
                                productsAdded: successfullyAdded,
                                totalProducts: DEMO_PRODUCTS.length,
                                details: results
                            }};
                        }}
                        
                        addLineButton.click();
                        await wait(3000);  // INCREASED: Wait longer for new row to render
                    }}
                    
                    const fillResult = await fillProductLine(product, lineNumber);
                    
                    if (!fillResult.success) {{
                        const errorMsg = fillResult.error || "Unknown error in fillProductLine";
                        results.push({{ product: product.description || "Unknown", success: false, error: errorMsg }});
                        return {{
                            success: false,
                            error: errorMsg,
                            productsAdded: successfullyAdded,
                            totalProducts: DEMO_PRODUCTS.length,
                            details: results
                        }};
                    }}
                    
                    successfullyAdded++;
                    results.push({{ product: product.description || "Unknown", success: true, error: null }});
                    
                    // ADDED: Wait between products to let Odoo process
                    if (i < DEMO_PRODUCTS.length - 1) {{
                        await wait(1000);
                    }}
                    
                }} catch (innerError) {{
                    const errorMsg = innerError.message || String(innerError) || "Unknown error in product loop";
                    results.push({{ product: product.description || "Unknown", success: false, error: errorMsg }});
                    return {{
                        success: false,
                        error: errorMsg,
                        productsAdded: successfullyAdded,
                        totalProducts: DEMO_PRODUCTS.length,
                        details: results
                    }};
                }}
            }}
            
            return {{
                success: successfullyAdded === DEMO_PRODUCTS.length,
                productsAdded: successfullyAdded,
                totalProducts: DEMO_PRODUCTS.length,
                details: results,
                error: null
            }};
            
        }} catch (e) {{
            return {{ 
                success: false, 
                error: e.message || String(e) || "Unknown error in main try block",
                productsAdded: 0,
                totalProducts: DEMO_PRODUCTS.length || 0,
                details: []
            }};
        }}
    }})();
}}
""".strip()



def get_log_note_script(message: str) -> str:
    """JavaScript to log internal note"""
    message_json = json.dumps(message)
    
    return f"""
() => {{
    return (async () => {{
        const LOG_MESSAGE = {message_json};
        
        async function humanType(element, text) {{
            element.focus();
            element.click();
            
            for (let i = 0; i < text.length; i++) {{
                const char = text[i];
                element.value = text.substring(0, i + 1);
                element.dispatchEvent(new KeyboardEvent('keydown', {{ key: char, bubbles: true }}));
                element.dispatchEvent(new KeyboardEvent('keypress', {{ key: char, bubbles: true }}));
                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                element.dispatchEvent(new KeyboardEvent('keyup', {{ key: char, bubbles: true }}));
                await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50));
            }}
            element.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
        
        function wait(ms) {{
            return new Promise(resolve => setTimeout(resolve, ms));
        }}
        
        // Helper function to find textarea in shadow DOM
        function findTextareaInShadowDOM() {{
            // Try regular DOM first
            let textarea = document.querySelector('textarea[placeholder*="Log an internal note"]');
            if (textarea) return textarea;
            
            // Search in shadow roots
            const allElements = document.querySelectorAll('*');
            for (const element of allElements) {{
                if (element.shadowRoot) {{
                    textarea = element.shadowRoot.querySelector('textarea[placeholder*="Log an internal note"]');
                    if (textarea) return textarea;
                }}
            }}
            
            return null;
        }}
        
        try {{
            const logNoteButton = Array.from(document.querySelectorAll('button')).find(btn => 
                btn.textContent.trim().toLowerCase() === 'log note'
            );
            
            if (!logNoteButton) {{
                return {{ success: false, error: "Log note button not found" }};
            }}
            
            logNoteButton.click();
            await wait(3000);  // Increased wait time for textarea to appear
            
            // Retry logic to find textarea
            let textarea = null;
            let retries = 0;
            const maxRetries = 5;
            
            while (!textarea && retries < maxRetries) {{
                textarea = findTextareaInShadowDOM();
                if (!textarea) {{
                    await wait(1000);
                    retries++;
                }}
            }}
            
            if (!textarea) {{
                return {{ success: false, error: "Log note textarea not found after " + maxRetries + " retries" }};
            }}
            
            textarea.click();
            await wait(500);
            textarea.value = '';
            textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
            await humanType(textarea, LOG_MESSAGE);
            await wait(1000);
            
            const logButton = Array.from(document.querySelectorAll('div, button')).find(el => 
                el.textContent.trim() === 'Log' && 
                (el.tagName === 'DIV' || el.tagName === 'BUTTON') &&
                el.offsetParent !== null
            );
            
            if (!logButton) {{
                return {{ success: false, error: "Log submit button not found" }};
            }}
            
            logButton.click();
            await wait(2000);
            
            return {{ success: true, error: null }};
            
        }} catch (e) {{
            return {{ success: false, error: e.message }};
        }}
    }})();
}}
""".strip()


def get_schedule_activity_script(summary: str) -> str:
    """JavaScript to schedule activity with retry logic"""
    summary_json = json.dumps(summary)
    
    return f"""
() => {{
    return (async () => {{
        const ACTIVITY_SUMMARY = {summary_json};
        
        async function humanType(element, text) {{
            element.focus();
            element.click();
            
            for (let i = 0; i < text.length; i++) {{
                const char = text[i];
                element.value = text.substring(0, i + 1);
                element.dispatchEvent(new KeyboardEvent('keydown', {{ key: char, bubbles: true }}));
                element.dispatchEvent(new KeyboardEvent('keypress', {{ key: char, bubbles: true }}));
                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                element.dispatchEvent(new KeyboardEvent('keyup', {{ key: char, bubbles: true }}));
                await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50));
            }}
            element.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
        
        function wait(ms) {{
            return new Promise(resolve => setTimeout(resolve, ms));
        }}
        
        try {{
            const activityButton = Array.from(document.querySelectorAll('button')).find(btn => 
                btn.textContent.trim().toLowerCase() === 'activity'
            );
            
            if (!activityButton) {{
                return {{ success: false, error: "Activity button not found" }};
            }}
            
            activityButton.click();
            await wait(2000);
            
            // ============================================
            // Retry logic to find popup
            // ============================================
            
            let popup = null;
            let retries = 0;
            const maxRetries = 5;
            
            while (!popup && retries < maxRetries) {{
                popup = document.querySelector('div[role="dialog"]');
                if (!popup) {{
                    await wait(1000);
                    retries++;
                }}
            }}
            
            if (!popup) {{
                return {{ success: false, error: "Activity popup not found after " + maxRetries + " retries" }};
            }}
            
            // ============================================
            // Retry logic to find summary input
            // ============================================
            
            let summaryInput = null;
            retries = 0;
            
            while (!summaryInput && retries < maxRetries) {{
                summaryInput = document.getElementById('summary_0');
                if (!summaryInput) {{
                    await wait(500);
                    retries++;
                }}
            }}
            
            if (!summaryInput) {{
                return {{ success: false, error: "Summary input not found after " + maxRetries + " retries" }};
            }}
            
            summaryInput.click();
            await wait(500);
            summaryInput.value = '';
            summaryInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
            await humanType(summaryInput, ACTIVITY_SUMMARY);
            await wait(1000);
            
            // ============================================
            // Find and click Save button
            // ============================================
            
            const saveButton = document.querySelector('button[name="action_schedule_activities"]');
            if (!saveButton) {{
                return {{ success: false, error: "Save button not found" }};
            }}
            
            saveButton.click();
            await wait(2000);
            
            return {{ success: true, error: null }};
            
        }} catch (e) {{
            return {{ success: false, error: e.message || String(e) }};
        }}
    }})();
}}
""".strip()

def get_configure_columns_script() -> str:
    """JavaScript to configure invoice columns visibility - only checks specific required columns"""
    
    return """
() => {
    return (async () => {
        
        // Only check these specific columns
        const REQUIRED_COLUMNS = ['Quantity', 'Disc.%', 'Taxes', 'Label'];
        
        function wait(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
        
        try {
            // ============================================
            // Step 1: Find column settings button
            // ============================================
            
            // Find button with expanded=false near "Amount" header
            const amountHeaders = Array.from(document.querySelectorAll('th')).filter(th => 
                th.textContent.trim() === 'Amount'
            );
            
            if (amountHeaders.length === 0) {
                return { success: false, columns_checked: 0, error: "Amount header not found" };
            }
            
            // Look for button near the Amount header
            const amountHeader = amountHeaders[0];
            const settingsButton = amountHeader.querySelector('button[aria-expanded="false"]') ||
                                  amountHeader.parentElement?.querySelector('button[aria-expanded="false"]') ||
                                  Array.from(document.querySelectorAll('button[aria-expanded="false"]')).find(btn => {
                                      const parent = btn.closest('th');
                                      return parent && parent.textContent.includes('Amount');
                                  });
            
            if (!settingsButton) {
                return { success: false, columns_checked: 0, error: "Column settings button not found" };
            }
            
            console.log("✓ Found column settings button");
            
            // ============================================
            // Step 2: Click to expand dropdown
            // ============================================
            
            settingsButton.click();
            await wait(2000);
            
            console.log("✓ Clicked to expand column options");
            
            // ============================================
            // Step 3: Find ONLY required unchecked checkboxes
            // ============================================
            
            // Find all checkboxes that are visible
            const allCheckboxes = Array.from(document.querySelectorAll('input[type="checkbox"]')).filter(cb => 
                cb.offsetParent !== null
            );
            
            const columnsToCheck = [];
            
            for (const checkbox of allCheckboxes) {
                // Skip if already checked
                if (checkbox.checked) continue;
                
                // Get label text
                const label = checkbox.closest('label') || 
                             document.querySelector(`label[for="${checkbox.id}"]`);
                
                if (!label) continue;
                
                const labelText = label.textContent.trim();
                
                // Check if this checkbox is for one of our required columns
                const isRequiredColumn = REQUIRED_COLUMNS.some(col => 
                    labelText === col || labelText.includes(col)
                );
                
                if (isRequiredColumn) {
                    columnsToCheck.push({
                        checkbox: checkbox,
                        name: labelText
                    });
                }
            }
            
            if (columnsToCheck.length === 0) {
                console.log("✓ All required columns already checked");
                
                // Close dropdown
                settingsButton.click();
                await wait(1000);
                
                return {
                    success: true,
                    columns_checked: 0,
                    error: null
                };
            }
            
            console.log(`Found ${columnsToCheck.length} required columns to check:`);
            columnsToCheck.forEach(col => console.log(`  • ${col.name}`));
            
            // ============================================
            // Step 4: Click each required unchecked checkbox
            // ============================================
            
            let columnsChecked = 0;
            
            for (const col of columnsToCheck) {
                console.log(`☑️  Checking: ${col.name}`);
                
                col.checkbox.click();
                await wait(500);
                columnsChecked++;
            }
            
            console.log(`✅ Configured ${columnsChecked} columns successfully`);
            
            // ============================================
            // Step 5: Close dropdown
            // ============================================
            
            // Click the button again to close
            settingsButton.click();
            await wait(1000);
            
            return {
                success: true,
                columns_checked: columnsChecked,
                error: null
            };
            
        } catch (e) {
            return {
                success: false,
                columns_checked: 0,
                error: e.message || String(e)
            };
        }
    })();
}
""".strip()


def get_click_other_info_tab_script() -> str:
    """JavaScript to click the 'Other Info' tab"""
    
    return """
() => {
    return (async () => {
        
        function wait(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
        
        try {
            // ============================================
            // Find and click "Other Info" tab
            // ============================================
            
            // Try multiple selectors
            let otherInfoTab = document.querySelector('a[role="tab"][name="other_info"]') ||
                              Array.from(document.querySelectorAll('a[role="tab"]')).find(tab => 
                                  tab.textContent.trim().toLowerCase() === 'other info'
                              );
            
            if (!otherInfoTab) {
                return { success: false, error: "Other Info tab not found" };
            }
            
            // Check if already selected
            if (otherInfoTab.getAttribute('selected') === 'true' || 
                otherInfoTab.getAttribute('aria-selected') === 'true') {
                return { success: true, error: null, already_selected: true };
            }
            
            otherInfoTab.click();
            await wait(2000);  // Wait for tab content to load
            
            return { success: true, error: null, already_selected: false };
            
        } catch (e) {
            return { success: false, error: e.message || String(e) };
        }
    })();
}
""".strip()


def get_fill_customer_reference_script(ref_id: str) -> str:
    """JavaScript to fill customer reference field"""
    ref_id_json = json.dumps(ref_id)
    
    return f"""
() => {{
    return (async () => {{
        const REF_ID = {ref_id_json};
        
        async function humanType(element, text) {{
            element.focus();
            element.click();
            const textStr = String(text);
            
            for (let i = 0; i < textStr.length; i++) {{
                const char = textStr[i];
                element.value = textStr.substring(0, i + 1);
                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50));
            }}
            
            element.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
        
        function wait(ms) {{
            return new Promise(resolve => setTimeout(resolve, ms));
        }}
        
        // Helper function to find input in shadow DOM
        function findInputInShadowDOM() {{
            // Try regular DOM first
            let input = document.getElementById('ref_2');
            if (input) return input;
            
            // Try by name attribute
            input = document.querySelector('input[id*="ref"]');
            if (input) return input;
            
            // Search in shadow roots
            const allElements = document.querySelectorAll('*');
            for (const element of allElements) {{
                if (element.shadowRoot) {{
                    input = element.shadowRoot.getElementById('ref_2');
                    if (input) return input;
                    
                    input = element.shadowRoot.querySelector('input[id*="ref"]');
                    if (input) return input;
                }}
            }}
            
            return null;
        }}
        
        try {{
            // ============================================
            // Retry logic to find customer reference input
            // ============================================
            
            let refInput = null;
            let retries = 0;
            const maxRetries = 5;
            
            while (!refInput && retries < maxRetries) {{
                refInput = findInputInShadowDOM();
                if (!refInput) {{
                    await wait(1000);
                    retries++;
                }}
            }}
            
            if (!refInput) {{
                return {{ success: false, error: "Customer reference input not found after " + maxRetries + " retries" }};
            }}
            
            // ============================================
            // Fill the customer reference field
            // ============================================
            
            refInput.click();
            await wait(500);
            refInput.value = '';
            refInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
            await humanType(refInput, REF_ID);
            refInput.blur();
            await wait(1000);
            
            return {{ success: true, error: null }};
            
        }} catch (e) {{
            return {{ success: false, error: e.message || String(e) }};
        }}
    }})();
}}
""".strip()


def get_click_confirm_button_script() -> str:
    """JavaScript to click the Confirm button"""
    
    return """
() => {
    return (async () => {
        
        function wait(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
        
        try {
            // ============================================
            // Find and click "Confirm" button
            // ============================================
            
            // Try multiple selectors for Confirm button
            let confirmButton = Array.from(document.querySelectorAll('button')).find(btn => 
                btn.textContent.trim().toLowerCase() === 'confirm'
            );
            
            if (!confirmButton) {
                // Try looking for button by name attribute
                confirmButton = document.querySelector('button[name="action_post"]') ||
                               document.querySelector('button[name*="confirm"]');
            }
            
            if (!confirmButton) {
                return { success: false, error: "Confirm button not found" };
            }
            
            // Check if button is disabled
            if (confirmButton.disabled || confirmButton.getAttribute('disabled') === 'true') {
                return { success: false, error: "Confirm button is disabled" };
            }
            
            confirmButton.click();
            await wait(4000);  // Wait for page to process confirmation
            
            return { success: true, error: null };
            
        } catch (e) {
            return { success: false, error: e.message || String(e) };
        }
    })();
}
""".strip()


def get_extract_invoice_id_script() -> str:
    """JavaScript to extract the invoice ID after confirmation"""
    
    return """
() => {
    return (async () => {
        
        function wait(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
        
        try {
            // ============================================
            // Retry logic to find invoice ID
            // ============================================
            
            let invoiceId = null;
            let retries = 0;
            const maxRetries = 5;
            
            while (!invoiceId && retries < maxRetries) {
                // Method 1: Look for text pattern like "INV/2026/00005"
                const invoicePattern = /INV\/\\d{4}\/\\d{5}/i;
                const bodyText = document.body.textContent;
                const match = bodyText.match(invoicePattern);
                
                if (match) {
                    invoiceId = match[0];
                    break;
                }
                
                // Method 2: Look in specific elements
                const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, .o_form_uri, .breadcrumb-item'));
                for (const heading of headings) {
                    const text = heading.textContent.trim();
                    const headingMatch = text.match(invoicePattern);
                    if (headingMatch) {
                        invoiceId = headingMatch[0];
                        break;
                    }
                }
                
                if (!invoiceId) {
                    await wait(1000);
                    retries++;
                }
            }
            
            if (!invoiceId) {
                return { 
                    success: false, 
                    error: "Invoice ID not found after " + maxRetries + " retries",
                    invoice_id: null 
                };
            }
            
            return { 
                success: true, 
                error: null,
                invoice_id: invoiceId
            };
            
        } catch (e) {
            return { 
                success: false, 
                error: e.message || String(e),
                invoice_id: null
            };
        }
    })();
}
""".strip()






def get_click_spreadsheet_row_script(sales_ref: str) -> str:
    """JavaScript to find and click a row in SharePoint spreadsheet by sales reference"""
    sales_ref_json = json.dumps(sales_ref)
    
    return f"""
() => {{
    return (async () => {{
        const SALES_REF = {sales_ref_json};
        
        function wait(ms) {{
            return new Promise(resolve => setTimeout(resolve, ms));
        }}
        
        try {{
            // ============================================
            // Find the spreadsheet/grid container
            // ============================================
            
            const listContainer = document.querySelector('#html-list_3, [role="grid"]');
            
            if (!listContainer) {{
                return {{ success: false, error: "Spreadsheet container not found" }};
            }}
            
            // ============================================
            // Find all rows in the spreadsheet
            // ============================================
            
            const allRows = Array.from(listContainer.querySelectorAll('[role="row"]')).filter(row => 
                !row.querySelector('[role="columnheader"]')  // Exclude header row
            );
            
            if (allRows.length === 0) {{
                return {{ success: false, error: "No data rows found in spreadsheet" }};
            }}
            
            // ============================================
            // Find the row containing the sales reference
            // ============================================
            
            let targetRow = null;
            let targetCell = null;
            
            for (const row of allRows) {{
                const cells = Array.from(row.querySelectorAll('[role="gridcell"]'));
                
                for (const cell of cells) {{
                    const cellText = cell.textContent.trim();
                    
                    // Check if this cell contains the sales ref
                    if (cellText === SALES_REF) {{
                        targetRow = row;
                        targetCell = cell;
                        break;
                    }}
                }}
                
                if (targetRow) break;
            }}
            
            if (!targetRow) {{
                return {{ 
                    success: false, 
                    error: "Row with sales reference '" + SALES_REF + "' not found in spreadsheet" 
                }};
            }}
            
            console.log("✓ Found row with sales reference:", SALES_REF);
            
            // ============================================
            // Click on the row/cell
            // ============================================
            
            // Try clicking the cell first
            targetCell.click();
            await wait(5000);
            
            // If that didn't open a form, try clicking the row
            const formOpened = document.querySelector('[role="dialog"]') || 
                              document.querySelector('.ms-Panel') ||
                              document.querySelector('[data-automationid*="panel"]');
            
            if (!formOpened) {{
                // Try double-click on cell
                const dblClickEvent = new MouseEvent('dblclick', {{
                    bubbles: true,
                    cancelable: true,
                    view: window
                }});
                targetCell.dispatchEvent(dblClickEvent);
                await wait(5000);
            }}
            
            return {{ 
                success: true, 
                error: null,
                sales_ref: SALES_REF,
                row_clicked: true
            }};
            
        }} catch (e) {{
            return {{ 
                success: false, 
                error: e.message || String(e) 
            }};
        }}
    }})();
}}
""".strip()






def get_click_edit_all_script() -> str:
    """JavaScript to click Edit all button in SharePoint form"""
    
    return """
() => {
    return (async () => {
        
        function wait(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
        
        try {
            // ============================================
            // Find and click "Edit all" button
            // ============================================
            
            const editAllButton = document.querySelector('button[aria-label="Edit all"]') ||
                                 document.querySelector('button[title="Edit all"]') ||
                                 Array.from(document.querySelectorAll('button[role="menuitem"]')).find(btn =>
                                     btn.textContent.trim() === 'Edit all'
                                 );
            
            if (!editAllButton) {
                return { success: false, error: "Edit all button not found" };
            }
            
            console.log("✓ Found Edit all button");
            
            editAllButton.click();
            await wait(3000);  // Wait for edit mode to activate
            
            console.log("✓ Clicked Edit all - form is now in edit mode");
            
            return { 
                success: true, 
                error: null 
            };
            
        } catch (e) {
            return { 
                success: false, 
                error: e.message || String(e) 
            };
        }
    })();
}
""".strip()





def get_fill_and_save_invoice_id_script(invoice_id: str) -> str:
    """JavaScript to fill Invoice ID and click Save button"""
    invoice_id_json = json.dumps(invoice_id)
    
    return f"""
() => {{
    return (async () => {{
        const INVOICE_ID = {invoice_id_json};
        
        function wait(ms) {{
            return new Promise(resolve => setTimeout(resolve, ms));
        }}
        
        try {{
            // ============================================
            // Step 1: Find Invoice ID input (NO shadow DOM!)
            // ============================================
            
            console.log("🔍 Looking for Invoice ID input...");
            
            let inputField = null;
            let retries = 0;
            const maxRetries = 10;
            
            while (!inputField && retries < maxRetries) {{
                // Find by aria-label
                inputField = document.querySelector('input[aria-label*="Invoice ID"]');
                
                if (!inputField) {{
                    await wait(500);
                    retries++;
                }}
            }}
            
            if (!inputField) {{
                return {{ success: false, error: "Invoice ID input not found after " + maxRetries + " retries" }};
            }}
            
            console.log("✓ Found Invoice ID input");
            console.log("  Input ID:", inputField.id);
            console.log("  Current value:", inputField.value);
            
            // ============================================
            // Step 2: Scroll Invoice ID into view
            // ============================================
            
            inputField.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            await wait(1000);
            
            // ============================================
            // Step 3: Fill the Invoice ID
            // ============================================
            
            inputField.focus();
            inputField.click();
            await wait(500);
            
            // Clear existing value
            inputField.value = '';
            
            // Set new value (React-safe)
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 
                'value'
            ).set;
            nativeInputValueSetter.call(inputField, INVOICE_ID);
            
            // Trigger change events
            inputField.dispatchEvent(new Event('input', {{ bubbles: true }}));
            inputField.dispatchEvent(new Event('change', {{ bubbles: true }}));
            
            console.log("✓ Filled Invoice ID:", INVOICE_ID);
            console.log("  Verified value:", inputField.value);
            
            await wait(1000);
            
            // ============================================
            // Step 4: Find and click Save button
            // ============================================
            
            console.log("💾 Looking for Save button...");
            
            let saveButton = null;
            retries = 0;
            
            while (!saveButton && retries < 5) {{
                // Find by data-automationid
                saveButton = document.querySelector('button[data-automationid="ReactClientFormSaveButton"]');
                
                if (!saveButton) {{
                    // Fallback: find by text
                    saveButton = Array.from(document.querySelectorAll('button')).find(btn =>
                        btn.textContent.trim() === 'Save' && 
                        btn.className.includes('ms-Button--primary')
                    );
                }}
                
                if (!saveButton) {{
                    await wait(500);
                    retries++;
                }}
            }}
            
            if (!saveButton) {{
                return {{ success: false, error: "Save button not found" }};
            }}
            
            console.log("✓ Found Save button");
            
            // Scroll Save button into view
            saveButton.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            await wait(500);
            
            saveButton.click();
            await wait(3000);  // Wait for save to complete
            
            console.log("✓ Clicked Save - waiting for form to close...");
            
            return {{ 
                success: true, 
                error: null,
                invoice_id: INVOICE_ID
            }};
            
        }} catch (e) {{
            console.error("❌ Error:", e);
            return {{ 
                success: false, 
                error: e.message || String(e) 
            }};
        }}
    }})();
}}
""".strip()






def get_close_sharepoint_form_script() -> str:
    """JavaScript to close the SharePoint form/panel"""
    
    return """
() => {
    return (async () => {
        
        function wait(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
        
        try {
            // ============================================
            // Find the Close button
            // ============================================
            
            // Try multiple selectors for the close button
            let closeButton = document.querySelector('button[aria-label="Close"]') ||
                             document.querySelector('button[title="Close"]') ||
                             Array.from(document.querySelectorAll('button[role="menuitem"]')).find(btn => 
                                 btn.textContent.trim().toLowerCase() === 'close'
                             );
            
            if (!closeButton) {
                // Try to find any close button by icon
                closeButton = Array.from(document.querySelectorAll('button')).find(btn => {
                    const icon = btn.querySelector('i');
                    return icon && (
                        icon.classList.contains('ms-Icon--Cancel') ||
                        icon.classList.contains('ms-Icon--ChromeClose')
                    );
                });
            }
            
            if (!closeButton) {
                return { success: false, error: "Close button not found" };
            }
            
            console.log("✓ Found Close button");
            
            // ============================================
            // Click the Close button
            // ============================================
            
            closeButton.click();
            await wait(2000);
            
            console.log("✓ Form closed");
            
            return { 
                success: true, 
                error: null 
            };
            
        } catch (e) {
            return { 
                success: false, 
                error: e.message || String(e) 
            };
        }
    })();
}
""".strip()