import json
import re
import asyncio
from typing import Dict, Any
from utils.workflow_graph_state import WorkflowGraphState
from browser_use.browser.events import SwitchTabEvent


# ============================================================
# SHARED JS PRIMITIVES
# Identical to setup_odoo_node — self-contained in every script.
# ============================================================

_JS_PRIMITIVES = """
    // ── Bounding-box highlight ───────────────────────────────
    function highlight(el, label = '', color = '#0078D4') {
        const rect = el.getBoundingClientRect();

        const box = document.createElement('div');
        box.setAttribute('data-sp-bot', '1');
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
        document.querySelectorAll('[data-sp-bot]').forEach(el => el.remove());
    }

    // ── Human-paced typing ───────────────────────────────────
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
            await wait(Math.random() * 60 + 70);   // 70-130 ms per char
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


def get_wait_for_url_script(fragment: str, timeout_ms: int = 15000) -> str:
    frag = json.dumps(fragment)
    return f"""
() => new Promise(resolve => {{
    const frag = {frag};
    const end  = Date.now() + {timeout_ms};
    const tick = () => {{
        if (window.location.href.includes(frag))
            resolve({{ success: true, url: window.location.href }});
        else if (Date.now() > end)
            resolve({{ success: false, error: `Timeout waiting for: ${{frag}} | got: ${{window.location.href}}` }});
        else setTimeout(tick, 300);
    }};
    tick();
}})""".strip()


def get_wait_for_element_script(selector: str, timeout_ms: int = 10000) -> str:
    sel = json.dumps(selector)
    return f"""
() => new Promise(resolve => {{
    const sel = {sel};
    const end = Date.now() + {timeout_ms};
    const tick = () => {{
        if (document.querySelector(sel)) resolve({{ success: true }});
        else if (Date.now() > end)       resolve({{ success: false, error: `Not found: ${{sel}}` }});
        else setTimeout(tick, 300);
    }};
    tick();
}})""".strip()


def get_wait_for_text_script(text: str, timeout_ms: int = 10000) -> str:
    """Poll until the given text appears anywhere in the page body."""
    t = json.dumps(text)
    return f"""
() => new Promise(resolve => {{
    const text = {t};
    const end  = Date.now() + {timeout_ms};
    const tick = () => {{
        if (document.body && document.body.innerText.includes(text))
            resolve({{ success: true }});
        else if (Date.now() > end)
            resolve({{ success: false, error: `Text not found: "${{text}}"` }});
        else setTimeout(tick, 300);
    }};
    tick();
}})""".strip()


def get_page_state_script() -> str:
    """Return current URL + visible text snippet to decide which login step we're on."""
    return """
() => {
    const url  = window.location.href;
    const body = (document.body && document.body.innerText) || '';
    return {
        success: true,
        url,
        has_email_field:       !!document.querySelector('input[name="loginfmt"], input[type="email"]'),
        has_password_field:    !!document.querySelector('input[name="passwd"], input[type="password"]'),
        has_stay_signed_in:    body.includes('Stay signed in'),
        has_mfa:               body.includes('Verify your identity') || body.includes('Approve sign in') || body.includes('two-step'),
        has_crm:               url.includes('Sales%20Pipeline%20CRM') || url.includes('AllItems'),
        has_access_denied:     body.includes('Access Denied') || body.includes("don't have access"),
        on_ms_login:           url.includes('login.microsoftonline.com'),
        on_sharepoint:         url.includes('sharepoint.com'),
    };
}
""".strip()


# ============================================================
# ACTION SCRIPTS  (highlight → pause → interact)
# Microsoft brand colour: #0078D4 (blue)
# Confirm/success actions: #059669 (green)
# ============================================================

def get_enter_email_script(email: str) -> str:
    e = json.dumps(email)
    body = f"""
        const EMAIL = {e};
        try {{
            const emailInput = (
                document.querySelector('input[name="loginfmt"]') ||
                document.querySelector('input[type="email"]')    ||
                document.querySelector('input[id="i0116"]')
            );
            let nextBtn = null;
            for (const btn of document.querySelectorAll('button, input[type="submit"]')) {{
                const txt = (btn.textContent || btn.value || '').trim().toLowerCase();
                if (txt === 'next' || btn.id === 'idSIButton9') {{ nextBtn = btn; break; }}
            }}

            const diag = {{
                emailFound: !!emailInput,
                emailName:  emailInput?.name,
                btnFound:   !!nextBtn,
                btnText:    nextBtn?.textContent?.trim(),
            }};

            if (!emailInput) return {{ success: false, error: 'Email input not found', diag }};
            if (!nextBtn)    return {{ success: false, error: 'Next button not found',  diag }};

            // ── Email field ──────────────────────────────────────
            emailInput.scrollIntoView({{ block: 'center' }});
            const rmEmail = highlight(emailInput, '📧  Email / Username', '#0078D4');
            await wait(800);
            await humanType(emailInput, EMAIL);
            await wait(500);
            rmEmail();

            // ── Next button ──────────────────────────────────────
            nextBtn.scrollIntoView({{ block: 'center' }});
            const rmBtn = highlight(nextBtn, '▶  Next', '#0078D4');
            await wait(900);
            rmBtn();
            await wait(150);
            nextBtn.click();

            return {{ success: true, diag }};
        }} catch (e) {{
            removeAllHighlights();
            return {{ success: false, error: e.message }};
        }}
    """
    return _script(body)


def get_enter_password_script(password: str) -> str:
    p = json.dumps(password)
    body = f"""
        const PASSWORD = {p};
        try {{
            const passInput = (
                document.querySelector('input[name="passwd"]')   ||
                document.querySelector('input[type="password"]') ||
                document.querySelector('input[id="i0118"]')
            );
            let signInBtn = null;
            for (const btn of document.querySelectorAll('button, input[type="submit"]')) {{
                const txt = (btn.textContent || btn.value || '').trim().toLowerCase();
                if (txt === 'sign in' || btn.id === 'idSIButton9') {{ signInBtn = btn; break; }}
            }}

            const diag = {{
                passFound:  !!passInput,
                passName:   passInput?.name,
                btnFound:   !!signInBtn,
                btnText:    signInBtn?.textContent?.trim(),
            }};

            if (!passInput)  return {{ success: false, error: 'Password input not found', diag }};
            if (!signInBtn)  return {{ success: false, error: 'Sign in button not found', diag }};

            // ── Password field ───────────────────────────────────
            passInput.scrollIntoView({{ block: 'center' }});
            const rmPass = highlight(passInput, '🔒  Password', '#0078D4');
            await wait(800);
            await humanType(passInput, PASSWORD);
            await wait(500);
            rmPass();

            // ── Sign in button ───────────────────────────────────
            signInBtn.scrollIntoView({{ block: 'center' }});
            const rmBtn = highlight(signInBtn, '🚀  Sign in', '#059669');
            await wait(900);
            rmBtn();
            await wait(150);
            signInBtn.click();

            return {{ success: true, diag }};
        }} catch (e) {{
            removeAllHighlights();
            return {{ success: false, error: e.message }};
        }}
    """
    return _script(body)


def get_click_stay_signed_in_script() -> str:
    body = """
        try {
            // "Yes" button on "Stay signed in?" prompt
            let yesBtn = null;
            for (const btn of document.querySelectorAll('button, input[type="submit"]')) {
                const txt = (btn.textContent || btn.value || '').trim().toLowerCase();
                if (txt === 'yes' || btn.id === 'idSIButton9') { yesBtn = btn; break; }
            }

            if (!yesBtn) return { success: false, error: '"Yes" button not found on Stay signed in prompt' };

            yesBtn.scrollIntoView({ block: 'center' });
            const rm = highlight(yesBtn, '✅  Stay signed in — Yes', '#059669');
            await wait(900);
            rm();
            await wait(150);
            yesBtn.click();

            return { success: true };
        } catch (e) {
            removeAllHighlights();
            return { success: false, error: e.message };
        }
    """
    return _script(body)


def get_verify_crm_script() -> str:
    """Highlight key CRM elements to confirm the page loaded correctly."""
    body = """
        try {
            const url     = window.location.href;
            const body    = document.body?.innerText || '';
            const hasCRM  = url.includes('Sales%20Pipeline%20CRM') || url.includes('AllItems');
            const hasRef  = body.includes('Sales Request Ref');

            if (hasCRM) {
                // Highlight the page title / header area
                const header = (
                    document.querySelector('.ms-List-headerWrapper') ||
                    document.querySelector('[data-automation-id="FieldRenderer-title"]') ||
                    document.querySelector('h1, h2, .ms-CommandBar')
                );
                if (header) {
                    header.scrollIntoView({ block: 'center' });
                    const rm = highlight(header, '✅  Sales Pipeline CRM Loaded', '#059669');
                    await wait(1000);
                    rm();
                }
            }

            return {
                success:  hasCRM,
                has_ref:  hasRef,
                url,
                error:    hasCRM ? null : 'CRM page not detected in URL',
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

async def setup_spreadsheet_node(state: WorkflowGraphState) -> WorkflowGraphState:
    """
    Navigate to SharePoint Sales Pipeline CRM using JS evaluate() calls.

    Visual feedback:
    - Every element gets a blue/green bounding box + label before interaction
    - ~800-900 ms pause while box is visible so the user can follow along
    - Human-paced typing (70-130 ms per character)

    Login flow handled:
    - Microsoft email → Next → password → Sign in
    - "Stay signed in?" → Yes
    - MFA detected → pause and wait for user to complete

    Smart recovery:
    - Reads page state at startup and jumps to correct step
    - Every click step has a direct-navigation fallback

    Target: URL contains 'Sales%20Pipeline%20CRM'
    """

    print("\n" + "=" * 60)
    print("SHAREPOINT SETUP NODE  [JS + BOUNDING BOX MODE]")
    print("=" * 60)

    # ----------------------------------------------------------
    # 1. Locate spreadsheet workflow in state
    # ----------------------------------------------------------
    workflows  = state.get("workflows", [])
    browser    = state.get("browser_instance")
    sp_workflow = None
    sp_index    = -1

    for idx, wf in enumerate(workflows):
        tab_ref = wf.get("tab_config", {}).get("tab_reference")
        if tab_ref == "spreadsheet_tab" or wf.get("name") == "sharepoint_crm_navigation":
            sp_workflow = wf
            sp_index    = idx
            break

    if not sp_workflow:
        print("  ✗ Spreadsheet workflow not found in state")
        return {**state, "error_message": "Spreadsheet workflow not found", "current_step": "spreadsheet_setup_failed"}

    page      = sp_workflow.get("page_instance")
    tab_id    = sp_workflow.get("tab_id")
    variables = sp_workflow.get("variables", {})
    email     = variables.get("email",    "yusuf@clickbuy.ai")
    password  = variables.get("password", "Engr@Bash#123m")

    SP_URL    = "https://pivotaluksolutionsltd-my.sharepoint.com/personal/martin_clickbuy_ai/Lists/Sales%20Pipeline%20CRM/AllItems.aspx"
    TARGET    = "Sales%20Pipeline%20CRM"

    if not page:
        print("  ✗ Page instance not found")
        return {**state, "error_message": "Spreadsheet page instance not found", "current_step": "spreadsheet_setup_failed"}

    def _fail(error: str) -> WorkflowGraphState:
        print(f"  ✗ {error}")
        updated = workflows.copy()
        updated[sp_index] = {**sp_workflow, "page_valid": False, "setup_complete": False, "error": error}
        return {**state, "workflows": updated, "error_message": error, "current_step": "spreadsheet_setup_failed"}

    def _pause(reason: str) -> WorkflowGraphState:
        print(f"  ⏸️  PAUSED: {reason}")
        updated = workflows.copy()
        updated[sp_index] = {**sp_workflow, "page_valid": False, "paused": True, "pause_reason": reason}
        return {**state, "workflows": updated, "execution_paused": True, "pause_reason": reason, "current_step": "spreadsheet_setup_paused"}

    def _success() -> WorkflowGraphState:
        print("  ✅ Successfully reached Sales Pipeline CRM!")
        updated = workflows.copy()
        updated[sp_index] = {**sp_workflow, "page_valid": True, "setup_complete": True, "error": None}
        return {**state, "workflows": updated, "current_step": "spreadsheet_setup_complete"}

    # Switch to the spreadsheet tab
    await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))

    try:
        # ----------------------------------------------------------
        # 2. Smart recovery — read page state, pick starting step
        # ----------------------------------------------------------
        ps = await evaluate(page, get_page_state_script())
        current_url = ps.get("url", "")
        print(f"\n  📍 Current URL: {current_url[:90]}...")
        print(f"  🔍 Page state: {ps}")

        # Already at target
        if ps.get("has_crm"):
            print("  ✅ Already at Sales Pipeline CRM!")
            return _success()

        # Decide starting step from page state
        if   ps.get("has_mfa"):            start = "mfa"
        elif ps.get("has_stay_signed_in"): start = "stay_signed_in"
        elif ps.get("has_password_field"): start = "password"
        elif ps.get("has_email_field"):    start = "email"
        elif ps.get("on_sharepoint"):      start = "wait_sp"
        else:                              start = "navigate"

        print(f"  🎯 Starting from: [{start}]")

        # ----------------------------------------------------------
        # [1/6] navigate_to_sharepoint
        # ----------------------------------------------------------
        if start == "navigate":
            print("\n  [1/6] Navigating to SharePoint...")
            await evaluate(page, get_navigate_script(SP_URL))

            # Wait for Microsoft login OR SharePoint to appear
            r = await evaluate(page, get_wait_for_url_script("microsoftonline.com", timeout_ms=50000))
            if not r.get("success"):
                # Maybe already authenticated → check for SharePoint directly
                r2 = await evaluate(page, get_wait_for_url_script("sharepoint.com", timeout_ms=50000))
                if not r2.get("success"):
                    return _fail("Neither Microsoft login nor SharePoint loaded after navigation")

            await asyncio.sleep(5)
            ps = await evaluate(page, get_page_state_script())
            current_url = ps.get("url", "")
            print(f"  📍 Loaded: {current_url[:90]}...")

            if   ps.get("has_crm"):            return _success()
            elif ps.get("has_stay_signed_in"): start = "stay_signed_in"
            elif ps.get("has_password_field"): start = "password"
            elif ps.get("has_email_field"):    start = "email"
            elif ps.get("on_sharepoint"):      start = "wait_sp"
            else:                              start = "email"

        # ----------------------------------------------------------
        # [2/6] enter_email
        # ----------------------------------------------------------
        if start == "email":
            await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
            print("\n  [2/6] Entering email...")

            r = await evaluate(page, get_wait_for_element_script(
                'input[name="loginfmt"], input[type="email"], input[id="i0116"]',
                timeout_ms=12000
            ))
            if not r.get("success"):
                return _fail(f"Email input never appeared: {r.get('error')}")

            await asyncio.sleep(2)
            r = await evaluate(page, get_enter_email_script(email))
            if r.get("diag"):
                print(f"  🔍 Diag: {r['diag']}")
            if not r.get("success"):
                return _fail(f"Email entry failed: {r.get('error')}")

            print("  ✅ Email submitted — waiting for password page...")
            r = await evaluate(page, get_wait_for_element_script(
                'input[name="passwd"], input[type="password"], input[id="i0118"]',
                timeout_ms=15000
            ))
            if not r.get("success"):
                # Check if we skipped straight to SharePoint (already authed)
                ps = await evaluate(page, get_page_state_script())
                if ps.get("has_crm"):
                    return _success()
                if ps.get("has_stay_signed_in"):
                    start = "stay_signed_in"
                else:
                    return _fail(f"Password page never appeared: {r.get('error')}")
            else:
                start = "password"

        # ----------------------------------------------------------
        # [3/6] enter_password
        # ----------------------------------------------------------
        if start == "password":
            await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
            print("\n  [3/6] Entering password...")

            await asyncio.sleep(2)
            r = await evaluate(page, get_enter_password_script(password))
            if r.get("diag"):
                print(f"  🔍 Diag: {r['diag']}")
            if not r.get("success"):
                return _fail(f"Password entry failed: {r.get('error')}")

            print("  ✅ Password submitted — waiting for next page...")

            # Wait up to 20 s for any of: Stay signed in / MFA / SharePoint
            await asyncio.sleep(3)
            ps = await evaluate(page, get_page_state_script())

            if   ps.get("has_crm"):            return _success()
            elif ps.get("has_access_denied"):  return _fail("Access denied to SharePoint CRM")
            elif ps.get("has_mfa"):            start = "mfa"
            elif ps.get("has_stay_signed_in"): start = "stay_signed_in"
            elif ps.get("on_sharepoint"):      start = "wait_sp"
            else:
                # Poll a bit longer
                r = await evaluate(page, get_wait_for_url_script("sharepoint.com", timeout_ms=20000))
                if r.get("success"):
                    start = "wait_sp"
                else:
                    ps2 = await evaluate(page, get_page_state_script())
                    if ps2.get("has_mfa"):            start = "mfa"
                    elif ps2.get("has_stay_signed_in"): start = "stay_signed_in"
                    else: return _fail(f"Post-login page unknown: {ps2.get('url')}")

        # ----------------------------------------------------------
        # [4/6] handle_mfa  (pause — user must complete manually)
        # ----------------------------------------------------------
        if start == "mfa":
            await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
            print("\n  [4/6] MFA detected — pausing for user...")
            return _pause("MFA required — please complete verification in the browser then resume")

        # ----------------------------------------------------------
        # [5/6] stay_signed_in
        # ----------------------------------------------------------
        if start == "stay_signed_in":
            await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
            print("\n  [5/6] Handling 'Stay signed in?' prompt...")

            await asyncio.sleep(2)
            r = await evaluate(page, get_click_stay_signed_in_script())
            if not r.get("success"):
                # Not a hard failure — may have already moved on
                print(f"  ⚠️  Stay signed in click failed ({r.get('error')}) — continuing...")

            print("  ✅ 'Stay signed in' handled — waiting for SharePoint...")
            start = "wait_sp"

        # ----------------------------------------------------------
        # [6/6] wait_for_sharepoint / verify
        # ----------------------------------------------------------
        if start == "wait_sp":
            await browser.on_SwitchTabEvent(event=SwitchTabEvent(target_id=tab_id))
            print("\n  [6/6] Waiting for SharePoint CRM to load...")

            r = await evaluate(page, get_wait_for_url_script(TARGET, timeout_ms=25000))
            if not r.get("success"):
                # Could be on generic SharePoint root — check page state
                ps = await evaluate(page, get_page_state_script())
                if ps.get("has_access_denied"):
                    return _fail("Access denied to Sales Pipeline CRM — verify permissions")
                if ps.get("has_mfa"):
                    return _pause("MFA required — please complete verification in the browser then resume")
                if not ps.get("has_crm"):
                    return _fail(f"CRM did not load. URL: {ps.get('url', '')[:90]}")

            await asyncio.sleep(2)
            r = await evaluate(page, get_verify_crm_script())
            if not r.get("success"):
                print(f"  ⚠️  CRM verify warning: {r.get('error')} — URL check is final arbiter")

            final_url = await get_url(page)
            if TARGET not in final_url:
                return _fail(f"Final URL check failed. Expected '{TARGET}' in: {final_url[:90]}")

        # ----------------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------------
        print(f"\n  📍 Final URL: {(await get_url(page))[:90]}...")
        return _success()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return _fail(str(e))