import json
import re
from typing import Dict, Any
from utils.workflow_graph_state import WorkflowGraphState
import asyncio
from browser_use.browser.events import SwitchTabEvent

# ============================================================
# SHARED JS PRIMITIVES
# Injected into every interaction script so each one is
# fully self-contained — no page.addScriptTag needed.
#
# Provides:
#   highlight(el, label, color) → draws labelled bounding box,
#                                 returns a removeHighlight fn
#   removeAllHighlights()       → cleans up all boxes at once
#   humanType(el, text)         → realistic keystroke typing
#   wait(ms)                    → simple sleep
# ============================================================

_JS_PRIMITIVES = """
    // ── Bounding-box highlight ───────────────────────────────
    function highlight(el, label = '', color = '#7C3AED') {
        const rect = el.getBoundingClientRect();

        const box = document.createElement('div');
        box.setAttribute('data-odoo-bot', '1');
        Object.assign(box.style, {
            position:      'fixed',
            left:          (rect.left   - 4) + 'px',
            top:           (rect.top    - 4) + 'px',
            width:         (rect.width  + 8) + 'px',
            height:        (rect.height + 8) + 'px',
            border:        `2.5px solid ${color}`,
            borderRadius:  '5px',
            background:    hexToRgba(color, 0.10),
            zIndex:        '2147483647',
            pointerEvents: 'none',
            boxSizing:     'border-box',
            boxShadow:     `0 0 8px 1px ${hexToRgba(color, 0.35)}`,
        });

        if (label) {
            const tag = document.createElement('div');
            Object.assign(tag.style, {
                position:     'absolute',
                top:          '-24px',
                left:         '0',
                background:   color,
                color:        '#fff',
                fontSize:     '11px',
                fontFamily:   'monospace',
                padding:      '2px 8px',
                borderRadius: '3px',
                whiteSpace:   'nowrap',
                letterSpacing:'0.03em',
            });
            tag.textContent = label;
            box.appendChild(tag);
        }

        document.body.appendChild(box);
        return () => { if (box.parentNode) box.remove(); };
    }

    function hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1,3), 16);
        const g = parseInt(hex.slice(3,5), 16);
        const b = parseInt(hex.slice(5,7), 16);
        return `rgba(${r},${g},${b},${alpha})`;
    }

    function removeAllHighlights() {
        document.querySelectorAll('[data-odoo-bot]').forEach(el => el.remove());
    }

    // ── Human-paced typing ───────────────────────────────────
    // ~70-130 ms per character — clearly visible but not slow
    async function humanType(element, text) {
        element.focus();
        element.click();
        element.value = '';
        element.dispatchEvent(new Event('input',  { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        await wait(300);

        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            element.value = text.substring(0, i + 1);
            element.dispatchEvent(new KeyboardEvent('keydown',  { key: char, bubbles: true }));
            element.dispatchEvent(new KeyboardEvent('keypress', { key: char, bubbles: true }));
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new KeyboardEvent('keyup',    { key: char, bubbles: true }));
            await wait(Math.random() * 60 + 70);   // 70-130 ms
        }
        element.dispatchEvent(new Event('change', { bubbles: true }));
        element.blur();
    }

    // ── Sleep ────────────────────────────────────────────────
    function wait(ms) { return new Promise(r => setTimeout(r, ms)); }
"""


def _script(body: str) -> str:
    """Wrap shared primitives + action body into a self-invoking async fn."""
    return f"""
() => {{
    return (async () => {{
{_JS_PRIMITIVES}
{body}
    }})();
}}
""".strip()


# ============================================================
# UTILITY SCRIPTS  (navigation / polling — no highlight)
# ============================================================

def get_current_url_script() -> str:
    return "() => ({ success: true, url: window.location.href })"


def get_navigate_script(url: str) -> str:
    url_json = json.dumps(url)
    return f"""
() => {{
    try {{
        window.location.href = {url_json};
        return {{ success: true }};
    }} catch (e) {{
        return {{ success: false, error: e.message }};
    }}
}}""".strip()


def get_wait_for_url_script(fragment: str, timeout_ms: int = 12000) -> str:
    frag = json.dumps(fragment)
    return f"""
() => new Promise(resolve => {{
    const frag = {frag};
    const end  = Date.now() + {timeout_ms};
    const tick = () => {{
        if (window.location.href.includes(frag))
            resolve({{ success: true, url: window.location.href }});
        else if (Date.now() > end)
            resolve({{ success: false, error: `Timeout waiting for URL fragment: ${{frag}} | current: ${{window.location.href}}` }});
        else setTimeout(tick, 250);
    }};
    tick();
}})""".strip()


def get_wait_for_element_script(selector: str, timeout_ms: int = 8000) -> str:
    sel = json.dumps(selector)
    return f"""
() => new Promise(resolve => {{
    const sel = {sel};
    const end = Date.now() + {timeout_ms};
    const tick = () => {{
        if (document.querySelector(sel)) resolve({{ success: true }});
        else if (Date.now() > end)       resolve({{ success: false, error: `Not found: ${{sel}}` }});
        else setTimeout(tick, 250);
    }};
    tick();
}})""".strip()


def get_wait_for_login_page_script(timeout_ms: int = 12000) -> str:
    return f"""
() => new Promise(resolve => {{
    const end = Date.now() + {timeout_ms};
    const tick = () => {{
        const email = document.querySelector('input[name="login"], input[type="email"], input[placeholder*="email" i]');
        const pass  = document.querySelector('input[name="password"], input[type="password"]');
        if (email && pass)   resolve({{ success: true }});
        else if (Date.now() > end)
            resolve({{ success: false, error: `Login form not ready — email=${{!!email}} pass=${{!!pass}}` }});
        else setTimeout(tick, 250);
    }};
    tick();
}})""".strip()


# ============================================================
# ACTION SCRIPTS  (highlight → pause → interact)
#
# Pacing per element:
#   scroll into view → highlight appears
#   700-900 ms pause  ← user can clearly see what's targeted
#   highlight removed → action fires
#   400-600 ms gap    ← before moving to next element
# ============================================================

def get_login_script(username: str, password: str) -> str:
    u = json.dumps(username)
    p = json.dumps(password)
    body = f"""
        const USERNAME = {u};
        const PASSWORD = {p};

        try {{
            // ── Locate elements ──────────────────────────────────
            const emailInput = (
                document.querySelector('input[name="login"]')          ||
                document.querySelector('input[id="login"]')            ||
                document.querySelector('input[type="email"]')          ||
                document.querySelector('input[placeholder*="email" i]')
            );
            const passwordInput = (
                document.querySelector('input[name="password"]') ||
                document.querySelector('input[id="password"]')   ||
                document.querySelector('input[type="password"]')
            );
            let loginBtn = null;
            for (const btn of document.querySelectorAll('button, input[type="submit"]')) {{
                const txt = (btn.textContent || btn.value || '').trim().toLowerCase();
                if (txt === 'log in' || txt === 'login' || btn.type === 'submit') {{
                    loginBtn = btn; break;
                }}
            }}

            const diag = {{
                emailFound:    !!emailInput,
                emailName:     emailInput?.name,
                passwordFound: !!passwordInput,
                buttonFound:   !!loginBtn,
                buttonText:    loginBtn?.textContent?.trim(),
            }};

            if (!emailInput)    return {{ success: false, error: 'Email input not found',    diag }};
            if (!passwordInput) return {{ success: false, error: 'Password input not found', diag }};
            if (!loginBtn)      return {{ success: false, error: 'Log in button not found',  diag }};

            // ── Email field ──────────────────────────────────────
            emailInput.scrollIntoView({{ block: 'center' }});
            const rmEmail = highlight(emailInput, '📧  Email', '#7C3AED');
            await wait(800);                   // user sees the highlight
            await humanType(emailInput, USERNAME);
            await wait(500);
            rmEmail();

            // ── Password field ───────────────────────────────────
            passwordInput.scrollIntoView({{ block: 'center' }});
            const rmPass = highlight(passwordInput, '🔒  Password', '#7C3AED');
            await wait(800);
            await humanType(passwordInput, PASSWORD);
            await wait(500);
            rmPass();

            // ── Log in button ────────────────────────────────────
            loginBtn.scrollIntoView({{ block: 'center' }});
            const rmBtn = highlight(loginBtn, '🚀  Log in', '#059669');
            await wait(900);                   // clear pause before clicking
            rmBtn();
            await wait(150);
            loginBtn.click();

            return {{ success: true, diag }};

        }} catch (e) {{
            removeAllHighlights();
            return {{ success: false, error: e.message }};
        }}
    """
    return _script(body)


def get_click_invoicing_app_script() -> str:
    body = """
        try {
            let link = null;
            const candidates = ['a[href*="accounting"]', '.o_app', 'a', 'button', 'span'];
            for (const sel of candidates) {
                for (const el of document.querySelectorAll(sel)) {
                    const text = (el.textContent || '').trim();
                    if (text === 'Invoicing' || text === 'Accounting') { link = el; break; }
                }
                if (link) break;
            }
            if (!link) return { success: false, error: 'Invoicing app link not found' };

            link.scrollIntoView({ block: 'center' });
            const rm = highlight(link, '🧾  Invoicing App', '#7C3AED');
            await wait(850);
            rm();
            await wait(150);
            link.click();

            return { success: true };
        } catch (e) {
            removeAllHighlights();
            return { success: false, error: e.message };
        }
    """
    return _script(body)


def get_click_customers_dropdown_script() -> str:
    body = """
        try {
            let btn = null;
            const selectors = [
                '.o_menu_sections .o_nav_entry',
                '.o_menu_sections .dropdown-toggle',
                '.o_main_navbar a',
                '.o_main_navbar button',
                'a', 'button', 'span', 'li',
            ];
            for (const sel of selectors) {
                for (const el of document.querySelectorAll(sel)) {
                    if ((el.textContent || '').trim() === 'Customers') { btn = el; break; }
                }
                if (btn) break;
            }
            if (!btn) return { success: false, error: 'Customers dropdown not found' };

            btn.scrollIntoView({ block: 'center' });
            const rm = highlight(btn, '👥  Customers', '#7C3AED');
            await wait(850);
            rm();
            await wait(150);
            btn.click();
            await wait(500);   // let dropdown animate open

            return { success: true };
        } catch (e) {
            removeAllHighlights();
            return { success: false, error: e.message };
        }
    """
    return _script(body)


def get_click_invoices_menu_script() -> str:
    body = """
        try {
            let link = null;

            // Prefer items inside an open dropdown
            for (const menu of document.querySelectorAll('.dropdown-menu, .o_dropdown_menu, [role="menu"]')) {
                for (const el of menu.querySelectorAll('a, li')) {
                    if ((el.textContent || '').trim() === 'Invoices') { link = el; break; }
                }
                if (link) break;
            }
            // Fallback: any visible <a> with exactly "Invoices"
            if (!link) {
                for (const el of document.querySelectorAll('a')) {
                    if ((el.textContent || '').trim() === 'Invoices' && el.offsetParent !== null) {
                        link = el; break;
                    }
                }
            }
            if (!link) return { success: false, error: 'Invoices menu item not found' };

            link.scrollIntoView({ block: 'center' });
            const rm = highlight(link, '📄  Invoices', '#7C3AED');
            await wait(850);
            rm();
            await wait(150);
            link.click();

            return { success: true };
        } catch (e) {
            removeAllHighlights();
            return { success: false, error: e.message };
        }
    """
    return _script(body)


def get_click_new_invoice_script() -> str:
    body = """
        try {
            let btn = null;
            const selectors = ['.o_list_button_add', '.o_control_panel .btn-primary', '.btn-primary', 'button'];
            for (const sel of selectors) {
                for (const el of document.querySelectorAll(sel)) {
                    if ((el.textContent || '').trim() === 'New' && el.offsetParent !== null) {
                        btn = el; break;
                    }
                }
                if (btn) break;
            }
            if (!btn) return { success: false, error: 'New invoice button not found' };

            btn.scrollIntoView({ block: 'center' });
            const rm = highlight(btn, '➕  New Invoice', '#059669');
            await wait(900);
            rm();
            await wait(150);
            btn.click();

            return { success: true };
        } catch (e) {
            removeAllHighlights();
            return { success: false, error: e.message };
        }
    """
    return _script(body)


def get_verify_invoice_form_script() -> str:
    body = """
        try {
            const customerField = document.querySelector(
                'input[id*="partner"], .o_field_widget[name="partner_id"] input, input[placeholder*="Customer"]'
            );
            const dateField = document.querySelector(
                'input[id*="invoice_date"], .o_field_widget[name="invoice_date"] input'
            );
            const isNewUrl  = window.location.href.includes('/new');
            const formReady = isNewUrl && (!!customerField || !!dateField);

            // Briefly highlight confirmed fields — green = all good
            if (customerField) {
                customerField.scrollIntoView({ block: 'center' });
                const rm = highlight(customerField, '✅  Customer', '#059669');
                await wait(700);
                rm();
            }
            if (dateField) {
                dateField.scrollIntoView({ block: 'center' });
                const rm = highlight(dateField, '✅  Invoice Date', '#059669');
                await wait(700);
                rm();
            }

            return {
                success:          formReady,
                url:              window.location.href,
                has_customer_field: !!customerField,
                has_date_field:   !!dateField,
                error:            formReady ? null : 'Invoice form fields not detected',
            };
        } catch (e) {
            return { success: false, error: e.message };
        }
    """
    return _script(body)


# ============================================================
# HELPERS
# ============================================================

async def evaluate(page, script: str) -> Dict[str, Any]:
    result = await page.evaluate(script)
    if isinstance(result, str):
        result = json.loads(result)
    return result or {}


async def get_url(page) -> str:
    r = await evaluate(page, get_current_url_script())
    return r.get("url", "")


# ============================================================
# MAIN NODE
# ============================================================

async def setup_odoo_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Navigate to the Odoo new invoice page using JS evaluate() calls.

    Visual feedback:
    - Every element gets a purple/green bounding box + label before interaction
    - ~800-900 ms pause while box is visible so the user can follow along
    - Human-paced typing (70-130 ms per character)

    Smart recovery:
    - Reads current URL at startup and jumps to the correct step
    - Every click step has a direct-navigation fallback

    Target: https://process-zero.odoo.com/odoo/customer-invoices/new
    """

    print("\n" + "=" * 60)
    print("ODOO SETUP NODE  [JS + BOUNDING BOX MODE]")
    print("=" * 60)
    

    # ----------------------------------------------------------
    # 1. Locate Odoo workflow in state
    # ----------------------------------------------------------
    workflows = state.get("workflows", [])
    browser = state.get("browser_instance")
    odoo_workflow = None
    odoo_index = -1

    for idx, wf in enumerate(workflows):
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "odoo_tab" or wf.get("name") == "odoo_invoice_creation":
            odoo_workflow = wf
            odoo_index = idx
            break

    if not odoo_workflow:
        print("  ✗ Odoo workflow not found in state")
        return {**state, "error_message": "Odoo workflow not found", "current_step": "odoo_setup_failed"}

    page = odoo_workflow.get("page_instance")
    variables = odoo_workflow.get("variables", {})
    username = variables.get("username", "standard.forever123@gmail.com")
    password = variables.get("password", "8sf$rt*Fu3f#+.u")
    

    if not page:
        print("  ✗ Page instance not found")
        return {**state, "error_message": "Odoo page instance not found", "current_step": "odoo_setup_failed"}

    TARGET_URL = "customer-invoices/new"

    def _fail(error: str) -> WorkflowGraphState:
        print(f"  ✗ {error}")
        updated = workflows.copy()
        updated[odoo_index] = {**odoo_workflow, "page_valid": False, "setup_complete": False, "error": error}
        return {**state, "workflows": updated, "error_message": error, "current_step": "odoo_setup_failed"}

    def _success() -> WorkflowGraphState:
        print("  ✅ Successfully reached new invoice form!")
        updated = workflows.copy()
        updated[odoo_index] = {**odoo_workflow, "page_valid": True, "setup_complete": True, "error": None}
        return {**state, "workflows": updated, "current_step": "odoo_setup_complete"}
    
    tab_id = odoo_workflow.get("tab_id")
    await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))

    try:
        # ----------------------------------------------------------
        # 2. Smart recovery — skip already-completed steps
        # ----------------------------------------------------------
        current_url = await get_url(page)
        print(f"\n  📍 Current URL: {current_url}")

        if re.search(r'customer-invoices/new$', current_url):
            print("  ✅ Already at target!")
            return _success()

        if   re.search(r'customer-invoices/new$', current_url):               start = "verify"
        elif "customer-invoices"     in current_url:                        start = "click_new"
        elif "/odoo/accounting" in current_url or "/odoo/account" in current_url: start = "open_customers"
        elif "/odoo" in current_url and "/web/login" not in current_url:    start = "click_invoicing"
        elif "/web/login" in current_url:                                   start = "login"
        else:                                                               start = "navigate"

        print(f"  🎯 Starting from: [{start}]")

        # ----------------------------------------------------------
        # [1/7] navigate_to_odoo
        # ----------------------------------------------------------
        if start == "navigate":
            await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
            print("\n  [1/7] Navigating to Odoo...")
            await evaluate(page, get_navigate_script("https://standeva.odoo.com/"))
            r = await evaluate(page, get_wait_for_url_script("standeva.odoo.com", timeout_ms=15000))
            if not r.get("success"):
                return _fail(f"Odoo did not load: {r.get('error')}")
            current_url = r.get("url", "")
            print(f"  📍 Loaded: {current_url}")
            start = "login" if "/web/login" in current_url else "click_invoicing"
            await asyncio.sleep(3)
            

        # ----------------------------------------------------------
        # [2/7] perform_login
        # ----------------------------------------------------------
        if start == "login":
            await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
            print("\n  [2/7] Waiting for login form...")
            r = await evaluate(page, get_wait_for_login_page_script(timeout_ms=12000))
            await asyncio.sleep(3)
            if not r.get("success"):
                return _fail(f"Login form never appeared: {r.get('error')}")

            print("  ✅ Login form ready — filling credentials...")
            r = await evaluate(page, get_login_script(username, password))
            if r.get("diag"):
                print(f"  🔍 Diag: {r['diag']}")
            if not r.get("success"):
                return _fail(f"Login failed: {r.get('error')}")

            print("  ✅ Submitted — waiting for /odoo redirect...")
            r = await evaluate(page, get_wait_for_url_script("/odoo", timeout_ms=20000))
            if not r.get("success"):
                if "/web/login" in (await get_url(page)):
                    return _fail("Still on login page after submit — check credentials")
                return _fail(f"Login redirect timed out: {r.get('error')}")

            print(f"  ✅ Logged in — URL: {r.get('url')}")
            start = "click_invoicing"

        # ----------------------------------------------------------
        # [3/7] click_invoicing_app
        # ----------------------------------------------------------
        if start == "click_invoicing":
            await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
            print("\n  [3/7] Clicking Invoicing app...")
            await evaluate(page, get_wait_for_element_script(
                ".o_app, .o_home_menu, a[href*='accounting']", timeout_ms=12000
            ))
            await asyncio.sleep(3)
            r = await evaluate(page, get_click_invoicing_app_script())
            if not r.get("success"):
                print(f"  ⚠️  Click failed ({r.get('error')}) — direct nav fallback...")
                await evaluate(page, get_navigate_script("https://standeva.odoo.com/odoo/accounting"))

            r = await evaluate(page, get_wait_for_url_script("/accounting", timeout_ms=15000))
            if not r.get("success"):
                return _fail(f"Invoicing page did not load: {r.get('error')}")
            print(f"  ✅ Invoicing — URL: {r.get('url')}")
            start = "open_customers"

        # ----------------------------------------------------------
        # [4/7] open_customers_dropdown
        # ----------------------------------------------------------
        if start == "open_customers":
            await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
            print("\n  [4/7] Opening Customers dropdown...")
            await evaluate(page, get_wait_for_element_script(
                ".o_menu_sections, .o_main_navbar", timeout_ms=10000
            ))
            await asyncio.sleep(3)
            r = await evaluate(page, get_click_customers_dropdown_script())
            if not r.get("success"):
                return _fail(f"Customers dropdown failed: {r.get('error')}")
            print("  ✅ Customers dropdown opened")
            start = "click_invoices"

        # ----------------------------------------------------------
        # [5/7] select_invoices_from_menu
        # ----------------------------------------------------------
        if start == "click_invoices":
            await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
            print("\n  [5/7] Selecting Invoices from menu...")
            await evaluate(page, get_wait_for_element_script(
                ".dropdown-menu a, .o_dropdown_menu a", timeout_ms=6000
            ))
            await asyncio.sleep(3)
            r = await evaluate(page, get_click_invoices_menu_script())
            if not r.get("success"):
                print(f"  ⚠️  Menu click failed ({r.get('error')}) — direct nav fallback...")
                await evaluate(page, get_navigate_script(
                    "https://standeva.odoo.com/odoo/accounting/customer-invoices"
                ))
            r = await evaluate(page, get_wait_for_url_script("customer-invoices", timeout_ms=12000))
            if not r.get("success"):
                return _fail(f"Invoice list did not load: {r.get('error')}")
            print(f"  ✅ Invoice list — URL: {r.get('url')}")
            start = "click_new"

        # ----------------------------------------------------------
        # [6/7] click_new_invoice
        # ----------------------------------------------------------
        if start == "click_new":
            await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
            print("\n  [6/7] Clicking New invoice button...")
            await evaluate(page, get_wait_for_element_script(
                ".o_list_button_add, .o_control_panel button", timeout_ms=10000
            ))
            await asyncio.sleep(3)
            r = await evaluate(page, get_click_new_invoice_script())
            if not r.get("success"):
                print(f"  ⚠️  New button failed ({r.get('error')}) — direct nav fallback...")
                await evaluate(page, get_navigate_script(
                    "https://standeva.odoo.com/odoo/customer-invoices/new"
                ))
            r = await evaluate(page, get_wait_for_url_script("customer-invoices/new", timeout_ms=12000))
            if not r.get("success"):
                return _fail(f"New invoice form did not load: {r.get('error')}")
            print(f"  ✅ New invoice form — URL: {r.get('url')}")
            start = "verify"

        # ----------------------------------------------------------
        # [7/7] verify_invoice_form_loaded
        # ----------------------------------------------------------
        if start == "verify":
            await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
            print("\n  [7/7] Verifying invoice form...")
            await evaluate(page, get_wait_for_element_script(
                'input[id*="partner"], .o_field_widget[name="partner_id"] input, input[id*="invoice_date"]',
                timeout_ms=10000
            ))
            await asyncio.sleep(3)
            r = await evaluate(page, get_verify_invoice_form_script())
            if not r.get("success"):
                print(f"  ⚠️  Form verify: {r.get('error')} — URL check is final arbiter")

            if TARGET_URL not in (await get_url(page)):
                return _fail(f"Final URL check failed. Expected '{TARGET_URL}' in: {await get_url(page)}")

        # ----------------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------------
        print(f"\n  📍 Final URL: {await get_url(page)}")
        return _success()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return _fail(str(e))