import asyncio
import argparse
import json
from pathlib import Path
from typing import Dict, Any, Optional, Literal, List
from dataclasses import dataclass, field
from datetime import datetime
from browser_use import Browser, Tools
from browser_use.dom.service import DomService
from browser_use.dom.serializer.serializer import DOMTreeSerializer

_UNSET = object()


@dataclass
class InvoiceFillingResult:
    status: Literal["success", "partial", "failed", "awaiting_human"]
    fields_attempted: List[str]
    fields_filled: Dict[str, Any]
    fields_failed: Dict[str, str]
    awaiting_human_decision: Optional[Dict[str, Any]] = None
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None
    debug_screenshots: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    execution_time: float = 0.0
    steps_taken: List[str] = field(default_factory=list)

    def to_email_summary(self) -> str:
        return f"""
Invoice Creation: {self.status.upper()}

Filled {len(self.fields_filled)}/{len(self.fields_attempted)} fields

Success:
{self.fields_filled}

Failed:
{self.fields_failed}

Time taken: {self.execution_time:.2f}s
        """


class GenericFormFiller:
    def __init__(
        self,
        browser: Browser,
        force_search_more_taxes: bool = False,
        force_search_more_products: bool = False,
        human_handoff: bool = True,
        handoff_state_path: str = "handoff_state.json",
        resume_state: Optional[Dict[str, Any]] = None,
        handoff_wait: bool = True,
        handoff_retries: int = 1
    ):
        self.browser = browser
        self.tools = Tools()
        self.force_search_more_taxes = force_search_more_taxes
        self.force_search_more_products = force_search_more_products
        self.catalog_used = False
        self.human_handoff = human_handoff
        self.handoff_wait = handoff_wait
        self.handoff_retries = max(0, int(handoff_retries))
        self.handoff_state_path = Path(handoff_state_path)
        self.resume_state = resume_state or {}
        self.resume_checkpoint = self.resume_state.get("checkpoint") if self.resume_state else None
        self.current_checkpoint = {"stage": "init"}
        self.invoice_data: Optional[Dict[str, Any]] = None
        self.batch_invoices: Optional[List[Dict[str, Any]]] = None
        self._handoff_active = False
        self.result = InvoiceFillingResult(
            status="success",
            fields_attempted=[],
            fields_filled={},
            fields_failed={}
        )
        if self.resume_state:
            self.apply_resume_state(self.resume_state)

    def apply_resume_state(self, state: Dict[str, Any]):
        """Apply saved run state for resuming."""
        result_state = state.get("result") or {}
        if result_state:
            self.result.status = result_state.get("status", self.result.status)
            self.result.fields_attempted = result_state.get("fields_attempted", self.result.fields_attempted)
            self.result.fields_filled = result_state.get("fields_filled", self.result.fields_filled)
            self.result.fields_failed = result_state.get("fields_failed", self.result.fields_failed)
            self.result.awaiting_human_decision = result_state.get("awaiting_human_decision")
            self.result.screenshot_before = result_state.get("screenshot_before")
            self.result.screenshot_after = result_state.get("screenshot_after")
            self.result.debug_screenshots = result_state.get("debug_screenshots", self.result.debug_screenshots)
            self.result.steps_taken = result_state.get("steps_taken", self.result.steps_taken)
            ts = result_state.get("timestamp")
            if ts:
                try:
                    self.result.timestamp = datetime.fromisoformat(ts)
                except Exception:
                    pass

        self.catalog_used = state.get("catalog_used", self.catalog_used)
        self.force_search_more_taxes = state.get("force_search_more_taxes", self.force_search_more_taxes)
        self.force_search_more_products = state.get("force_search_more_products", self.force_search_more_products)
        self.current_checkpoint = state.get("checkpoint", self.current_checkpoint) or self.current_checkpoint
        self.resume_checkpoint = state.get("checkpoint") if state.get("checkpoint") else self.resume_checkpoint
        if isinstance(state.get("invoice_data"), list):
            self.batch_invoices = state.get("invoice_data")

    def _set_checkpoint(
        self,
        stage: Optional[str] = _UNSET,
        step: Optional[str] = _UNSET,
        field: Optional[str] = _UNSET,
        batch_index: Optional[int] = _UNSET,
        line_index: Optional[int] = _UNSET,
        substep: Optional[str] = _UNSET,
        last_completed_substep: Optional[str] = _UNSET
    ):
        if stage is not _UNSET:
            self.current_checkpoint["stage"] = stage
        if step is not _UNSET:
            self.current_checkpoint["step"] = step
        if field is not _UNSET:
            self.current_checkpoint["field"] = field
        if batch_index is not _UNSET:
            self.current_checkpoint["batch_index"] = batch_index
        if line_index is not _UNSET:
            self.current_checkpoint["line_index"] = line_index
        if substep is not _UNSET:
            self.current_checkpoint["substep"] = substep
        if last_completed_substep is not _UNSET:
            self.current_checkpoint["last_completed_substep"] = last_completed_substep
        self.current_checkpoint["timestamp"] = datetime.now().isoformat()

    def _serialize_result(self) -> Dict[str, Any]:
        return {
            "status": self.result.status,
            "fields_attempted": self.result.fields_attempted,
            "fields_filled": self.result.fields_filled,
            "fields_failed": self.result.fields_failed,
            "awaiting_human_decision": self.result.awaiting_human_decision,
            "screenshot_before": self.result.screenshot_before,
            "screenshot_after": self.result.screenshot_after,
            "debug_screenshots": self.result.debug_screenshots,
            "timestamp": self.result.timestamp.isoformat() if self.result.timestamp else None,
            "execution_time": self.result.execution_time,
            "steps_taken": self.result.steps_taken
        }

    def clear_handoff_state(self):
        try:
            if self.handoff_state_path.exists():
                self.handoff_state_path.unlink()
        except Exception:
            pass

    def reset_for_new_invoice(self, preserve_resume: bool = False):
        if not preserve_resume:
            self.resume_checkpoint = None
            self.current_checkpoint = {"stage": "init"}
        self.catalog_used = False
        if not preserve_resume:
            self.result = InvoiceFillingResult(
                status="success",
                fields_attempted=[],
                fields_filled={},
                fields_failed={}
            )

    async def detect_blockers(self) -> Optional[Dict[str, Any]]:
        """Detect common blockers like captchas or verification dialogs."""
        page = await self.browser.get_current_page()
        result = await page.evaluate("""
            () => {
                const blockers = [];
                const isVisible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    if (!style) return false;
                    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                    if (el.offsetParent === null && style.position !== 'fixed') return false;
                    return true;
                };

                const hasRecaptcha = !!document.querySelector('iframe[src*="recaptcha"], .g-recaptcha, [data-sitekey][class*="recaptcha"]');
                const hasHcaptcha = !!document.querySelector('iframe[src*="hcaptcha"], .h-captcha, [data-sitekey][class*="hcaptcha"]');
                if (hasRecaptcha) blockers.push({ type: 'captcha', detail: 'recaptcha' });
                if (hasHcaptcha) blockers.push({ type: 'captcha', detail: 'hcaptcha' });

                const dialogSelectors = ['[role="dialog"]', '.modal', '.o_dialog', '.o_notification', '.alert', '.o_dialog_container'];
                const dialogs = dialogSelectors.flatMap(sel => Array.from(document.querySelectorAll(sel)));
                const keywordList = [
                    'are you human', 'verify', 'robot', 'captcha', 'access denied',
                    'unusual traffic', 'security check', 'verification', 'please verify'
                ];
                for (const dialog of dialogs) {
                    if (!isVisible(dialog)) continue;
                    const text = (dialog.textContent || '').toLowerCase().replace(/\\s+/g, ' ').trim();
                    if (!text) continue;
                    if (keywordList.some(k => text.includes(k))) {
                        blockers.push({ type: 'dialog', detail: text.slice(0, 200) });
                        break;
                    }
                }

                return blockers;
            }
        """)

        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                result = []

        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return None

    async def save_handoff_state(
        self,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
        blocker: Optional[Dict[str, Any]] = None,
        screenshot_path: Optional[str] = None
    ):
        current_url = None
        try:
            current_url = await self.browser.get_url()
        except Exception:
            current_url = None

        state = {
            "version": 1,
            "reason": reason,
            "context": context or {},
            "blocker": blocker,
            "checkpoint": self.current_checkpoint,
            "invoice_data": self.batch_invoices if self.batch_invoices is not None else self.invoice_data,
            "catalog_used": self.catalog_used,
            "force_search_more_taxes": self.force_search_more_taxes,
            "force_search_more_products": self.force_search_more_products,
            "result": self._serialize_result(),
            "current_url": current_url,
            "screenshot_path": screenshot_path,
            "timestamp": datetime.now().isoformat()
        }

        try:
            self.handoff_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    async def pause_for_human(
        self,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
        blocker: Optional[Dict[str, Any]] = None
    ) -> bool:
        if not self.human_handoff or self._handoff_active:
            return False

        self._handoff_active = True
        screenshot_path = None
        try:
            page = await self.browser.get_current_page()
            screenshot = await page.screenshot()
            screenshot_path = f"handoff_{int(datetime.now().timestamp())}.png"
            with open(screenshot_path, "wb") as f:
                f.write(screenshot)
        except Exception:
            screenshot_path = None

        self.result.steps_taken.append(f"⏸️ Human intervention required: {reason}")
        await self.save_handoff_state(reason, context=context, blocker=blocker, screenshot_path=screenshot_path)

        print("\n" + "=" * 60)
        print("HUMAN INTERVENTION REQUIRED")
        print("=" * 60)
        print(f"Reason: {reason}")
        if blocker:
            print(f"Detected blocker: {blocker}")
        if screenshot_path:
            print(f"Screenshot: {screenshot_path}")
        print(f"State saved to: {self.handoff_state_path}")
        print("Resolve the issue in the browser, then press Enter to continue.")

        if self.handoff_wait:
            await asyncio.to_thread(input)
        self._handoff_active = False
        return True

    async def handoff_if_blocked(
        self,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> bool:
        if not self.human_handoff:
            return False

        blocker = await self.detect_blockers()
        if blocker or force:
            return await self.pause_for_human(reason, context=context, blocker=blocker)
        return False

    async def wait_for_page_ready(self, timeout: int = 10):
        """
        Wait for page to finish loading/saving.
        Mimics human waiting for page to be ready.
        """
        page = await self.browser.get_current_page()

        for attempt in range(timeout * 2):
            is_loading = await page.evaluate("""
                () => {
                    const loadingSelectors = [
                        '.o_loading', '.o_blockUI', '[class*="loading"]',
                        '[class*="spinner"]', '.fa-spinner'
                    ];

                    for (const selector of loadingSelectors) {
                        const el = document.querySelector(selector);
                        if (el && el.offsetParent !== null) return true;
                    }
                    return false;
                }
            """)

            if not is_loading:
                break

            await asyncio.sleep(0.5)

        # Random human-like pause after loading
        import random
        await asyncio.sleep(random.uniform(0.2, 0.6))

        # Pause if a blocker is detected after load
        await self.handoff_if_blocked("Blocker detected after page load")

    async def wait_for_element(
        self,
        selector: str,
        timeout: int = 30,
        poll_interval: float = 0.5,
        visible: bool = True,
        description: str = None
    ) -> bool:
        """
        Wait for an element to exist (and optionally be visible) in the DOM.

        Args:
            selector: CSS selector or JS expression returning element
            timeout: Maximum seconds to wait
            poll_interval: Seconds between checks
            visible: If True, also check element is visible
            description: Human-readable description for logging

        Returns:
            True if element found within timeout, False otherwise
        """
        page = await self.browser.get_current_page()
        desc = description or selector

        for attempt in range(int(timeout / poll_interval)):
            try:
                if visible:
                    found = await page.evaluate(f"""
                        () => {{
                            const el = document.querySelector('{selector}');
                            if (!el) return false;
                            const style = window.getComputedStyle(el);
                            if (!style) return false;
                            if (style.display === 'none' || style.visibility === 'hidden') return false;
                            if (el.offsetParent === null && style.position !== 'fixed') return false;
                            return true;
                        }}
                    """)
                else:
                    found = await page.evaluate(f"""
                        () => {{
                            return !!document.querySelector('{selector}');
                        }}
                    """)

                if isinstance(found, str):
                    found = found.strip().lower() == 'true'

                if found:
                    return True

            except Exception:
                pass

            await asyncio.sleep(poll_interval)

        self.result.steps_taken.append(f"⚠ Timeout waiting for: {desc}")
        return False

    async def wait_for_any_element(
        self,
        selectors: List[str],
        timeout: int = 30,
        poll_interval: float = 0.5,
        description: str = None
    ) -> Optional[str]:
        """
        Wait for any of multiple elements to appear.

        Returns:
            The selector that matched, or None if timeout
        """
        page = await self.browser.get_current_page()
        selectors_json = json.dumps(selectors)

        for attempt in range(int(timeout / poll_interval)):
            try:
                result = await page.evaluate(f"""
                    () => {{
                        const selectors = {selectors_json};
                        for (const sel of selectors) {{
                            const el = document.querySelector(sel);
                            if (el) {{
                                const style = window.getComputedStyle(el);
                                if (style && style.display !== 'none' && style.visibility !== 'hidden') {{
                                    return sel;
                                }}
                            }}
                        }}
                        return null;
                    }}
                """)

                if result and result != 'null':
                    return result

            except Exception:
                pass

            await asyncio.sleep(poll_interval)

        return None

    async def wait_for_network_idle(self, timeout: int = 10, idle_time: float = 0.5):
        """
        Wait for network to be idle (no pending requests).
        Useful after navigation or AJAX-heavy operations.
        """
        page = await self.browser.get_current_page()

        last_activity = asyncio.get_event_loop().time()
        start_time = last_activity

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                is_busy = await page.evaluate("""
                    () => {
                        // Check for Odoo-specific loading indicators
                        const loadingIndicators = [
                            '.o_loading',
                            '.o_blockUI',
                            '.o_loading_indicator',
                            '[class*="loading"]',
                            '[class*="spinner"]',
                            '.fa-spinner.fa-spin'
                        ];

                        for (const sel of loadingIndicators) {
                            const el = document.querySelector(sel);
                            if (el && el.offsetParent !== null) return true;
                        }

                        // Check document ready state
                        if (document.readyState !== 'complete') return true;

                        return false;
                    }
                """)

                if isinstance(is_busy, str):
                    is_busy = is_busy.strip().lower() == 'true'

                if is_busy:
                    last_activity = asyncio.get_event_loop().time()
                elif (asyncio.get_event_loop().time() - last_activity) >= idle_time:
                    return True

            except Exception:
                pass

            await asyncio.sleep(0.2)

        return False

    async def navigate_to_form(self, url: str):
        """Navigate to the invoice form URL."""
        self.result.steps_taken.append(f"Navigating to {url}")

        await self.tools.registry.execute_action(
            action_name='navigate',
            params={'url': url, 'new_tab': False},
            browser_session=self.browser
        )

        await self.tools.registry.execute_action(
            action_name='wait',
            params={'seconds': 5},
            browser_session=self.browser
        )

        self.result.steps_taken.append("Form loaded")

    async def login_and_navigate_to_new_invoice(self, login_url: str, email: str, password: str) -> bool:
        """
        Login to Odoo and navigate to: Invoicing -> Customers -> Invoices -> New
        With proper waits for each element to ensure stability on slow networks.
        """
        page = await self.browser.get_current_page()
        self.result.steps_taken.append("Starting login flow")
        self._set_checkpoint(stage="login", step="navigate_login")

        # Navigate to login page
        await self.tools.registry.execute_action(
            action_name='navigate',
            params={'url': login_url, 'new_tab': False},
            browser_session=self.browser
        )

        # Wait for either login form OR dashboard (already logged in)
        self.result.steps_taken.append("Waiting for page to load...")
        login_or_dashboard = await self.wait_for_any_element(
            selectors=[
                'input[name="login"]',
                'input[type="email"]',
                '.o_home_menu',
                '.o_app',
                '.o_main_navbar'
            ],
            timeout=30,
            description="login form or dashboard"
        )

        if not login_or_dashboard:
            self.result.steps_taken.append("✗ Page did not load (no login form or dashboard)")
            await self.pause_for_human("Page failed to load - check network connection", context={"step": "navigate_login"})
            return False

        # Check if already logged in
        already_logged_in = login_or_dashboard in ['.o_home_menu', '.o_app', '.o_main_navbar']
        self.result.steps_taken.append(f"Already logged in: {already_logged_in}")

        if not already_logged_in:
            # Wait for email input to be ready
            self._set_checkpoint(stage="login", step="email")
            email_ready = await self.wait_for_element(
                'input[name="login"], input[type="email"]',
                timeout=15,
                description="email input"
            )
            if not email_ready:
                self.result.steps_taken.append("✗ Login email input not found")
                await self.pause_for_human("Email input not found", context={"step": "login_email"})
                return False

            # Fill email with human-like typing
            email_filled = await page.evaluate("""
                () => {
                    const input = document.querySelector('input[name="login"], input[type="email"]');
                    if (!input) return false;
                    input.focus();
                    input.value = '';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    return true;
                }
            """)

            import random
            chars_per_second = random.uniform(10, 12)
            delay_per_char = 1.0 / chars_per_second
            for char in email:
                await page.evaluate(
                    """
                    (ch) => {
                        const input = document.querySelector('input[name="login"], input[type="email"]');
                        if (!input) return false;
                        input.value += ch;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        return true;
                    }
                    """,
                    char,
                )
                await asyncio.sleep(delay_per_char)

            # Wait for and fill password
            self._set_checkpoint(stage="login", step="password")
            pass_ready = await self.wait_for_element(
                'input[name="password"], input[type="password"]',
                timeout=10,
                description="password input"
            )
            if not pass_ready:
                self.result.steps_taken.append("✗ Login password input not found")
                await self.pause_for_human("Password input not found", context={"step": "login_password"})
                return False

            await page.evaluate("""
                () => {
                    const input = document.querySelector('input[name="password"], input[type="password"]');
                    if (!input) return false;
                    input.focus();
                    input.value = '';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    return true;
                }
            """)

            for char in password:
                await page.evaluate(
                    """
                    (ch) => {
                        const input = document.querySelector('input[name="password"], input[type="password"]');
                        if (!input) return false;
                        input.value += ch;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        return true;
                    }
                    """,
                    char,
                )
                await asyncio.sleep(delay_per_char)

            # Click Log in button
            self._set_checkpoint(stage="login", step="submit_login")
            await asyncio.sleep(0.3)
            login_clicked = await page.evaluate("""
                () => {
                    const btn = Array.from(document.querySelectorAll('button, a[role="button"], input[type="submit"]'))
                        .find(el => (el.textContent || '').trim().toLowerCase() === 'log in' || (el.value || '').trim().toLowerCase() === 'log in');
                    if (btn) {
                        btn.click();
                        return true;
                    }
                    return false;
                }
            """)

            if not login_clicked:
                self.result.steps_taken.append("✗ Login button not found")
                await self.pause_for_human("Login button not found", context={"step": "login_button"})
                return False

            # CRITICAL: Wait for dashboard to fully load after login
            self.result.steps_taken.append("Waiting for dashboard after login...")
            dashboard_ready = await self.wait_for_any_element(
                selectors=['.o_home_menu', '.o_app', '.o_apps'],
                timeout=45,  # Longer timeout for login
                description="dashboard/home menu"
            )
            if not dashboard_ready:
                self.result.steps_taken.append("✗ Dashboard did not load after login")
                await self.pause_for_human("Dashboard failed to load after login", context={"step": "wait_dashboard"})
                return False

            # Additional wait for network to settle
            await self.wait_for_network_idle(timeout=10)
            self.result.steps_taken.append("Dashboard loaded")

        # STEP: Click Invoicing app
        self._set_checkpoint(stage="login", step="open_invoicing")
        self.result.steps_taken.append("Looking for Invoicing app...")

        # Wait for app tiles to be visible
        apps_ready = await self.wait_for_element(
            '.o_app, .o_home_menu',
            timeout=20,
            description="app tiles"
        )
        if not apps_ready:
            self.result.steps_taken.append("✗ App tiles not found")
            await self.pause_for_human("App tiles not visible", context={"step": "open_invoicing"})
            return False

        # Small delay to ensure apps are interactive
        await asyncio.sleep(0.5)

        invoicing_clicked = False
        for attempt in range(5):  # Retry up to 5 times
            invoicing_clicked = await page.evaluate("""
                () => {
                    const tiles = Array.from(document.querySelectorAll('a.o_app, .o_app, .o_menuitem'));
                    const match = tiles.find(el => (el.textContent || '').trim().toLowerCase().includes('invoicing'));
                    if (match) {
                        match.click();
                        return true;
                    }
                    return false;
                }
            """)
            if isinstance(invoicing_clicked, str):
                invoicing_clicked = invoicing_clicked.strip().lower() == 'true'
            if invoicing_clicked:
                break
            await asyncio.sleep(1)  # Wait before retry

        if not invoicing_clicked:
            self.result.steps_taken.append("✗ Invoicing app not found")
            await self.pause_for_human("Invoicing app not found", context={"step": "open_invoicing"})
            return False

        self.result.steps_taken.append("Clicked Invoicing, waiting for navbar...")

        # CRITICAL: Wait for Invoicing app to load (navbar with Customers menu)
        navbar_ready = await self.wait_for_element(
            '.o_main_navbar',
            timeout=30,
            description="main navbar"
        )
        if not navbar_ready:
            self.result.steps_taken.append("✗ Navbar did not load")
            await self.pause_for_human("Invoicing app navbar did not load", context={"step": "wait_navbar"})
            return False

        await self.wait_for_network_idle(timeout=10)

        # STEP: Open Customers dropdown
        self._set_checkpoint(stage="login", step="open_customers")
        self.result.steps_taken.append("Looking for Customers menu...")

        # Wait for Customers menu to appear
        customers_ready = await self.wait_for_element(
            '.o_main_navbar',
            timeout=15,
            description="navbar with Customers"
        )

        customers_clicked = False
        for attempt in range(5):
            customers_clicked = await page.evaluate("""
                () => {
                    const items = Array.from(document.querySelectorAll('.o_main_navbar a, .o_main_navbar button, .o_menu_sections button, .o_menu_sections a'));
                    const match = items.find(el => (el.textContent || '').trim().toLowerCase() === 'customers');
                    if (match) {
                        match.click();
                        return true;
                    }
                    return false;
                }
            """)
            if isinstance(customers_clicked, str):
                customers_clicked = customers_clicked.strip().lower() == 'true'
            if customers_clicked:
                break
            await asyncio.sleep(0.8)

        if not customers_clicked:
            self.result.steps_taken.append("✗ Customers menu not found")
            await self.pause_for_human("Customers menu not found", context={"step": "open_customers"})
            return False

        self.result.steps_taken.append("Clicked Customers, waiting for dropdown...")

        # Wait for dropdown to appear
        dropdown_ready = await self.wait_for_element(
            '.dropdown-menu, .o-dropdown--menu',
            timeout=10,
            description="customers dropdown"
        )
        await asyncio.sleep(0.3)  # Small extra delay for dropdown animation

        # STEP: Click Invoices in dropdown
        self._set_checkpoint(stage="login", step="open_invoices")
        invoices_clicked = False
        for attempt in range(5):
            invoices_clicked = await page.evaluate("""
                () => {
                    const items = Array.from(document.querySelectorAll('.dropdown-menu a, .o-dropdown--menu a, .o_menu_sections a'));
                    const match = items.find(el => (el.textContent || '').trim().toLowerCase() === 'invoices');
                    if (match) {
                        match.click();
                        return true;
                    }
                    return false;
                }
            """)
            if isinstance(invoices_clicked, str):
                invoices_clicked = invoices_clicked.strip().lower() == 'true'
            if invoices_clicked:
                break
            await asyncio.sleep(0.5)

        if not invoices_clicked:
            self.result.steps_taken.append("✗ Invoices menu item not found")
            await self.pause_for_human("Invoices menu item not found", context={"step": "open_invoices"})
            return False

        self.result.steps_taken.append("Clicked Invoices, waiting for list view...")

        # CRITICAL: Wait for invoice list view to load
        list_ready = await self.wait_for_any_element(
            selectors=['.o_list_view', '.o_kanban_view', '.o_view_controller', 'button:has-text("New")'],
            timeout=30,
            description="invoice list view"
        )
        await self.wait_for_network_idle(timeout=10)

        # STEP: Click New button
        self._set_checkpoint(stage="login", step="open_new_invoice")
        self.result.steps_taken.append("Looking for New button...")

        # Wait for New button to be visible
        new_button_ready = await self.wait_for_element(
            'button.o_list_button_add, button.o-kanban-button-new, .o_cp_buttons button',
            timeout=20,
            description="New button"
        )

        new_clicked = False
        for attempt in range(5):
            new_clicked = await page.evaluate("""
                () => {
                    const btns = Array.from(document.querySelectorAll('button, a[role="button"]'));
                    const newBtn = btns.find(el => (el.textContent || '').trim().toLowerCase() === 'new');
                    if (newBtn) {
                        newBtn.click();
                        return true;
                    }
                    return false;
                }
            """)
            if isinstance(new_clicked, str):
                new_clicked = new_clicked.strip().lower() == 'true'
            if new_clicked:
                break
            await asyncio.sleep(0.8)

        if not new_clicked:
            self.result.steps_taken.append("✗ New button not found")
            await self.pause_for_human("New button not found", context={"step": "open_new_invoice"})
            return False

        self.result.steps_taken.append("Clicked New, waiting for invoice form...")

        # CRITICAL: Wait for new invoice form to fully load
        form_ready = await self.wait_for_any_element(
            selectors=[
                '.o_form_view',
                '[name="partner_id"]',
                '[name="invoice_line_ids"]',
                'input[name="partner_id"]'
            ],
            timeout=30,
            description="invoice form"
        )
        if not form_ready:
            self.result.steps_taken.append("✗ Invoice form did not load")
            await self.pause_for_human("Invoice form failed to load", context={"step": "wait_form"})
            return False

        # Final network idle wait
        await self.wait_for_network_idle(timeout=10)
        await asyncio.sleep(0.5)  # Extra stability pause

        self.result.steps_taken.append("✓ Reached new invoice form")
        self._set_checkpoint(stage="fill_form", step="start")
        return True

    async def get_dom_representation(self) -> str:
        """Extract DOM structure for analysis."""
        tabs = await self.browser.get_tabs()
        current_tab = tabs[0]

        dom_service = DomService(self.browser)
        dom_tree, _ = await dom_service.get_dom_tree(target_id=current_tab.target_id)
        serialized, _ = DOMTreeSerializer(
            dom_tree, None, paint_order_filtering=True
        ).serialize_accessible_elements()

        return serialized.llm_representation()

    async def find_field_by_id(self, field_name: str, dom: str) -> Optional[str]:
        """Fast: Find field by exact ID match."""
        if f'id={field_name}' in dom or f'id="{field_name}"' in dom:
            return f'#{field_name}'
        return None

    async def find_field_by_label(self, field_name: str, dom: str) -> Optional[str]:
        """Medium: Find field by searching for label text."""
        search_terms = [
            field_name.lower(),
            field_name.replace('_', ' ').lower(),
            field_name.replace('-', ' ').lower()
        ]

        lines = dom.split('\n')
        for i, line in enumerate(lines):
            for term in search_terms:
                if term in line.lower() and 'id=' in line:
                    import re
                    match = re.search(r'id=([^\s>]+)', line)
                    if match:
                        field_id = match.group(1).strip('"\'')
                        return f'#{field_id}'
        return None

    async def find_field_semantic(self, field_name: str, dom: str) -> Optional[str]:
        """Slow but accurate: Use LLM to find field semantically."""
        self.result.steps_taken.append(f"Using LLM to find field: {field_name}")
        return None

    async def find_field(self, field_name: str) -> Optional[Dict[str, Any]]:
        """
        Find field using priority order:
        1. Exact ID match
        2. Label text match
        3. LLM semantic match
        """
        dom = await self.get_dom_representation()

        exact_match = await self.find_field_by_id(field_name, dom)
        if exact_match:
            self.result.steps_taken.append(f"Found {field_name} by exact ID")
            return {'selector': exact_match, 'method': 'exact'}

        label_match = await self.find_field_by_label(field_name, dom)
        if label_match:
            self.result.steps_taken.append(f"Found {field_name} by label")
            return {'selector': label_match, 'method': 'label'}

        semantic_match = await self.find_field_semantic(field_name, dom)
        if semantic_match:
            self.result.steps_taken.append(f"Found {field_name} by LLM")
            return {'selector': semantic_match, 'method': 'llm'}

        return None

    async def fill_text_field(self, selector: str, value: str) -> Dict[str, Any]:
        """Fill a text input field."""
        page = await self.browser.get_current_page()
        value_literal = json.dumps(value if value is not None else "")

        filled = await page.evaluate(f"""
            () => {{
                const input = document.querySelector('{selector}');
                if (!input) return {{ success: false, error: 'Input not found' }};
                if (input.disabled || input.readOnly) return {{ success: false, error: 'Input is readonly' }};
                input.focus();
                if (input.isContentEditable) {{
                    input.textContent = {value_literal};
                }} else {{
                    input.value = {value_literal};
                }}
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                return {{ success: true, value: input.value || input.textContent || '' }};
            }}
        """)

        if isinstance(filled, str):
            try:
                filled = json.loads(filled)
            except Exception:
                filled = {"success": False, "error": "Parse error"}

        return filled

    async def fill_customer_invoice_field(self, value: str) -> Dict[str, Any]:
        """
        Fill the Customer Invoice number field (title) with human-like typing.
        """
        page = await self.browser.get_current_page()
        value_str = "" if value is None else str(value)
        key = f"cust_inv_{int(datetime.now().timestamp())}"
        key_literal = json.dumps(key)

        setup = await page.evaluate(f"""
            () => {{
                const isVisible = (el) => {{
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    if (!style) return false;
                    if (style.display === 'none' || style.visibility === 'hidden') return false;
                    if (el.offsetParent === null && style.position !== 'fixed') return false;
                    return true;
                }};

                const selectors = [
                    '.o_form_title input[name="name"]',
                    '.o_form_title [name="name"] input',
                    '.o_form_title .o_field_widget[name="name"] input',
                    'input[name="name"]',
                    '[name="name"] input',
                    '.o_form_title [data-name="name"] input',
                    '[data-name="name"] input',
                    'input[name="move_name"]',
                    '[name="move_name"] input',
                ];

                let input = null;
                for (const sel of selectors) {{
                    const candidate = document.querySelector(sel);
                    if (candidate && isVisible(candidate)) {{
                        input = candidate;
                        break;
                    }}
                }}

                if (!input) {{
                    const titleWidget = document.querySelector(
                        '.o_form_title [name="name"], .o_form_title [data-name="name"], .o_form_title .o_field_widget[name="name"]'
                    );
                    if (titleWidget) {{
                        titleWidget.click();
                        input = titleWidget.querySelector('input, textarea, [contenteditable="true"]') ||
                            document.querySelector('.o_form_title input[name="name"]');
                    }}
                }}

                if (!input) {{
                    return {{ error: 'Customer Invoice number field not found' }};
                }}

                if (input.disabled || input.readOnly) {{
                    return {{ error: 'Customer Invoice field is readonly' }};
                }}

                input.setAttribute('data-codex-ci', {key_literal});
                input.focus();
                if (input.isContentEditable) {{
                    input.textContent = '';
                }} else {{
                    input.value = '';
                }}
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return {{ success: true, key: {key_literal}, isContentEditable: !!input.isContentEditable }};
            }}
        """)

        if isinstance(setup, str):
            try:
                setup = json.loads(setup)
            except Exception:
                setup = {"error": "Parse error"}

        if setup.get("error"):
            return {"success": False, "error": setup.get("error")}

        # Human-like typing: 125–150 WPM (~80–100ms per char)
        import random
        delay_per_char = random.uniform(0.08, 0.10)

        for char in value_str:
            char_literal = json.dumps(char)
            await page.evaluate(f"""
                () => {{
                    const input = document.querySelector('[data-codex-ci="{key}"]');
                    if (!input) return false;
                    if (input.isContentEditable) {{
                        input.textContent += {char_literal};
                    }} else {{
                        input.value += {char_literal};
                    }}
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    return true;
                }}
            """)
            await asyncio.sleep(delay_per_char)

        await page.evaluate(f"""
            () => {{
                const input = document.querySelector('[data-codex-ci="{key}"]');
                if (!input) return false;
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                return true;
            }}
        """)

        return {"success": True, "value": value_str}

    async def fill_payment_terms_field(self, value: str) -> Dict[str, Any]:
        """
        Fallback: locate Payment Terms by label and select the matching option.
        """
        page = await self.browser.get_current_page()
        value_str = "" if value is None else str(value)
        value_literal = json.dumps(value_str)
        key = f"pt_{int(datetime.now().timestamp())}"
        key_literal = json.dumps(key)

        setup = await page.evaluate(f"""
            () => {{
                const labelText = 'payment terms';
                const labels = Array.from(document.querySelectorAll('label, .o_form_label, .o_td_label'));
                const match = labels.find(el => (el.textContent || '').trim().toLowerCase().includes(labelText));
                if (!match) return {{ error: 'Payment Terms label not found' }};

                const labelCell = match.closest('.o_cell') || match.parentElement;
                let fieldCell = null;
                if (labelCell && labelCell.nextElementSibling) {{
                    fieldCell = labelCell.nextElementSibling;
                }} else if (labelCell) {{
                    const group = labelCell.closest('.o_inner_group');
                    if (group) {{
                        const cells = Array.from(group.querySelectorAll('.o_cell'));
                        const idx = cells.indexOf(labelCell);
                        if (idx > -1 && idx + 1 < cells.length) fieldCell = cells[idx + 1];
                    }}
                }}

                const fieldWidget = (fieldCell || labelCell || match.parentElement)?.querySelector('.o_field_widget');
                let input = null;
                if (fieldWidget) {{
                    input = fieldWidget.querySelector('input, select, textarea, [contenteditable=\"true\"]');
                }}
                if (!input) {{
                    input = (fieldCell || labelCell || match.parentElement)?.querySelector('input, select, textarea, [contenteditable=\"true\"]');
                }}
                if (!input) return {{ error: 'Payment Terms input not found' }};
                if (input.disabled || input.readOnly) return {{ error: 'Payment Terms input readonly' }};

                input.setAttribute('data-codex-pt', {key_literal});
                input.focus();
                if (input.tagName && input.tagName.toLowerCase() === 'select') {{
                    return {{ success: true, key: {key_literal}, isSelect: true }};
                }}
                if (input.isContentEditable) {{
                    input.textContent = '';
                }} else {{
                    input.value = '';
                }}
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return {{ success: true, key: {key_literal}, isSelect: false }};
            }}
        """)

        if isinstance(setup, str):
            try:
                setup = json.loads(setup)
            except Exception:
                setup = {"error": "Parse error"}

        if setup.get("error"):
            return {"success": False, "error": setup.get("error")}

        if setup.get("isSelect"):
            selected = await page.evaluate(f"""
                () => {{
                    const input = document.querySelector('[data-codex-pt="{key}"]');
                    if (!input || input.tagName.toLowerCase() !== 'select') return {{ error: 'Select not found' }};
                    const opt = Array.from(input.options).find(o =>
                        (o.textContent || '').trim().toLowerCase() === {value_literal}.toLowerCase() ||
                        (o.textContent || '').trim().toLowerCase().includes({value_literal}.toLowerCase())
                    );
                    if (!opt) return {{ error: 'Payment Terms option not found' }};
                    input.value = opt.value;
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return {{ success: true, selected: opt.textContent.trim() }};
                }}
            """)
            if isinstance(selected, str):
                selected = json.loads(selected)
            return selected if selected.get("success") else {"success": False, "error": selected.get("error")}

        # Human-like typing
        import random
        delay = random.uniform(0.08, 0.10)
        for char in value_str:
            char_literal = json.dumps(char)
            await page.evaluate(f"""
                () => {{
                    const input = document.querySelector('[data-codex-pt="{key}"]');
                    if (!input) return false;
                    if (input.isContentEditable) {{
                        input.textContent += {char_literal};
                    }} else {{
                        input.value += {char_literal};
                    }}
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    return true;
                }}
            """)
            await asyncio.sleep(delay)

        await asyncio.sleep(0.4)

        selected = await page.evaluate(f"""
            () => {{
                const dropdown = document.querySelector('.o-autocomplete--dropdown-menu, [role="listbox"]');
                if (!dropdown) return {{ error: 'Dropdown not found' }};
                const items = Array.from(dropdown.querySelectorAll('a[role="option"], .dropdown-item, li')).filter(el => {{
                    const text = (el.textContent || '').trim();
                    if (!text) return false;
                    const lower = text.toLowerCase();
                    if (lower.includes('create') || lower.includes('search more') || lower.includes('search worldwide')) return false;
                    return true;
                }});
                if (items.length === 0) return {{ error: 'No options found' }};
                const target = {value_literal}.toLowerCase().trim();
                let match = items.find(el => (el.textContent || '').trim().toLowerCase() === target);
                if (!match) {{
                    match = items.find(el => (el.textContent || '').trim().toLowerCase().includes(target));
                }}
                if (!match) return {{ error: 'Payment Terms option not found' }};
                match.click();
                return {{ success: true, selected: match.textContent.trim() }};
            }}
        """)
        if isinstance(selected, str):
            selected = json.loads(selected)

        return selected if selected.get("success") else {"success": False, "error": selected.get("error")}

    async def fill_dropdown_field(self, selector: str, value: str) -> Dict[str, Any]:
        """
        Fill a dropdown/autocomplete field.
        Returns options if multiple matches found (for human decision).
        """
        page = await self.browser.get_current_page()

        filled = await page.evaluate(f"""
            () => {{
                const input = document.querySelector('{selector}');
                if (input) {{
                    input.focus();
                    input.value = '{value}';
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    input.click();
                    return true;
                }}
                return false;
            }}
        """)

        if not filled:
            return {'success': False, 'error': f'Field {selector} not found'}

        await asyncio.sleep(3)

        options_result = await page.evaluate("""
            () => {
                // Odoo uses .o-autocomplete--dropdown-item
                const dropdownItems = document.querySelectorAll('.o-autocomplete--dropdown-item a[role="option"]');

                // Filter out "Create and edit...", "Search more...", "Search Worldwide"
                const realOptions = Array.from(dropdownItems).filter(item => {
                    const text = item.textContent.trim();
                    return !text.includes('Create and edit') &&
                           !text.includes('Search more') &&
                           !text.includes('Search Worldwide');
                });

                const options = realOptions.map((item, idx) => ({
                    index: idx,
                    text: item.textContent.trim()
                }));

                return JSON.stringify({
                    count: realOptions.length,
                    options: options,
                    debug: {
                        totalDropdownItems: dropdownItems.length,
                        afterFilter: realOptions.length
                    }
                });
            }
        """)

        import json
        try:
            result_data = json.loads(options_result) if isinstance(options_result, str) else options_result
            options = result_data.get('options', [])
            debug_info = result_data.get('debug', {})

            print(f"Debug - Found {result_data.get('count', 0)} customer options")
            print(f"Debug - Total dropdown items: {debug_info.get('totalDropdownItems', 0)}")
            print(f"Debug - After filtering: {debug_info.get('afterFilter', 0)}")

        except Exception as e:
            print(f"Debug - Parse error: {e}")
            options = []

        if not options or len(options) == 0:
            return {'success': False, 'error': 'No dropdown options found'}

        if len(options) == 1:
            clicked = await page.evaluate("""
                () => {
                    const dropdownItems = document.querySelectorAll('.o-autocomplete--dropdown-item a[role="option"]');
                    const realOptions = Array.from(dropdownItems).filter(item => {
                        const text = item.textContent.trim();
                        return !text.includes('Create and edit') &&
                               !text.includes('Search more') &&
                               !text.includes('Search Worldwide');
                    });
                    if (realOptions[0]) {
                        realOptions[0].click();
                        return true;
                    }
                    return false;
                }
            """)
            await asyncio.sleep(1)
            return {'success': True, 'selected': options[0]['text']}

        if len(options) > 1:
            # For now, just pick the first option automatically
            clicked = await page.evaluate("""
                () => {
                    const dropdownItems = document.querySelectorAll('.o-autocomplete--dropdown-item a[role="option"]');
                    const realOptions = Array.from(dropdownItems).filter(item => {
                        const text = item.textContent.trim();
                        return !text.includes('Create and edit') &&
                               !text.includes('Search more') &&
                               !text.includes('Search Worldwide');
                    });
                    if (realOptions[0]) {
                        realOptions[0].click();
                        return true;
                    }
                    return false;
                }
            """)
            await asyncio.sleep(1)
            return {'success': True, 'selected': options[0]['text'], 'note': f'Auto-selected from {len(options)} options'}

    async def select_first_dropdown_option(self, selector: str) -> Dict[str, Any]:
        """
        Open a dropdown and select the first real option (excluding create/search).
        """
        page = await self.browser.get_current_page()

        opened = await page.evaluate(f"""
            () => {{
                const input = document.querySelector('{selector}');
                if (!input) return false;
                input.focus();
                input.click();
                const dropdownBtn = input.closest('.o_field_widget')?.querySelector('.o_dropdown_button');
                if (dropdownBtn) dropdownBtn.click();
                return true;
            }}
        """)
        if not opened:
            return {'success': False, 'error': f'Field {selector} not found'}

        await asyncio.sleep(0.4)

        selected = await page.evaluate("""
            () => {
                const dropdown = document.querySelector('.o-autocomplete--dropdown-menu, [role="listbox"]');
                if (!dropdown) return {error: 'Dropdown not found'};

                const options = Array.from(dropdown.querySelectorAll('a[role="option"], .dropdown-item, li')).filter(el => {
                    const text = (el.textContent || '').trim();
                    if (!text) return false;
                    const lower = text.toLowerCase();
                    if (lower.includes('create and edit') || lower.includes('create')) return false;
                    if (lower.includes('search more') || lower.includes('search worldwide')) return false;
                    return true;
                });

                if (!options.length) return {error: 'No dropdown options found'};
                options[0].click();
                return {success: true, selected: options[0].textContent.trim()};
            }
        """)

        if isinstance(selected, str):
            try:
                selected = json.loads(selected)
            except Exception:
                selected = {'success': False, 'error': 'Parse error'}

        return selected

    async def select_existing_customer(self, value: str) -> Dict[str, Any]:
        """
        Select an existing customer from dropdown or Search more... without creating duplicates.
        With proper waits for slow networks.
        """
        page = await self.browser.get_current_page()
        value_str = "" if value is None else str(value)
        value_literal = json.dumps(value_str)

        # Wait for customer input to be ready
        input_ready = await self.wait_for_element(
            '[name="partner_id"] input, #partner_id_0, .o_field_widget[name="partner_id"] input',
            timeout=15,
            description="customer input"
        )
        if not input_ready:
            return {"success": False, "error": "Customer input not found (timeout)"}

        # Focus and clear customer input
        setup = await page.evaluate("""
            () => {
                const selectors = [
                    '#partner_id_0',
                    'input[name="partner_id"]',
                    '[name="partner_id"] input',
                    '.o_field_widget[name="partner_id"] input',
                    'input[placeholder*="Search a name" i]',
                    'input[placeholder*="Tax ID" i]'
                ];
                let input = null;
                for (const sel of selectors) {
                    const candidate = document.querySelector(sel);
                    if (candidate) { input = candidate; break; }
                }
                if (!input) return { error: 'Customer input not found' };
                if (input.disabled || input.readOnly) return { error: 'Customer input readonly' };
                input.focus();
                input.value = '';
                input.dispatchEvent(new Event('input', { bubbles: true }));
                return { success: true };
            }
        """)
        if isinstance(setup, str):
            try:
                setup = json.loads(setup)
            except Exception:
                setup = {"error": "Parse error"}
        if setup.get("error"):
            return {"success": False, "error": setup.get("error")}

        # Human-like typing (80-100ms per char)
        import random
        delay = random.uniform(0.08, 0.10)
        for ch in value_str:
            await page.evaluate(
                """
                (c) => {
                    const input = document.querySelector('#partner_id_0, input[name="partner_id"], [name="partner_id"] input, .o_field_widget[name="partner_id"] input, input[placeholder*="Search a name" i], input[placeholder*="Tax ID" i]');
                    if (!input) return false;
                    input.value += c;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    return true;
                }
                """,
                ch,
            )
            await asyncio.sleep(delay)

        # CRITICAL: Wait for dropdown to appear (may take time on slow networks)
        dropdown_ready = await self.wait_for_element(
            '.o-autocomplete--dropdown-menu, [role="listbox"], .dropdown-menu.show',
            timeout=10,
            description="customer dropdown"
        )
        if not dropdown_ready:
            # Dropdown didn't appear, might need to trigger it again
            await page.evaluate("""
                () => {
                    const input = document.querySelector('#partner_id_0, input[name="partner_id"], [name="partner_id"] input');
                    if (input) {
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('focus', { bubbles: true }));
                    }
                }
            """)
            await asyncio.sleep(1)

        # Additional small delay for dropdown to fully populate
        await asyncio.sleep(0.5)

        # Try select from dropdown - prefer existing customers over creating new
        dropdown_selected = await page.evaluate(f"""
            () => {{
                const dropdown = document.querySelector('.o-autocomplete--dropdown-menu, [role="listbox"]');
                if (!dropdown) return {{ error: 'Dropdown not found' }};

                const allItems = Array.from(dropdown.querySelectorAll('a[role="option"], .dropdown-item, li'));

                // Filter to get only real customer options (not create/search actions)
                const options = allItems.filter(el => {{
                    const text = (el.textContent || '').trim();
                    if (!text) return false;
                    const lower = text.toLowerCase();
                    if (lower.includes('create and edit') || lower === 'create' || lower.startsWith('create "')) return false;
                    if (lower.includes('search more') || lower.includes('search worldwide')) return false;
                    return true;
                }});

                const target = {value_literal}.toLowerCase().trim();
                const targetWords = target.split(/\\s+/).filter(w => w.length > 2);

                // Priority 1: Exact match
                let match = options.find(el => (el.textContent || '').trim().toLowerCase() === target);

                // Priority 2: Option contains the full search term
                if (!match) {{
                    match = options.find(el => (el.textContent || '').trim().toLowerCase().includes(target));
                }}

                // Priority 3: Search term contains the option (partial input)
                if (!match) {{
                    match = options.find(el => {{
                        const optText = (el.textContent || '').trim().toLowerCase();
                        return target.includes(optText);
                    }});
                }}

                // Priority 4: First significant word matches (e.g., "Acme" matches "ACME TRADING...")
                if (!match && targetWords.length > 0) {{
                    match = options.find(el => {{
                        const optText = (el.textContent || '').trim().toLowerCase();
                        // Check if first word of search matches start of option
                        return optText.startsWith(targetWords[0]) ||
                               optText.includes(targetWords[0] + ' ');
                    }});
                }}

                // Priority 5: Any option available (better than creating duplicate)
                if (!match && options.length > 0) {{
                    // If we have existing options that might be related, select the first one
                    // This prevents creating duplicates when similar customers exist
                    match = options[0];
                }}

                if (match) {{
                    match.click();
                    return {{ success: true, selected: match.textContent.trim(), matchType: 'existing' }};
                }}

                return {{ not_found: true, availableOptions: options.length }};
            }}
        """)
        if isinstance(dropdown_selected, str):
            dropdown_selected = json.loads(dropdown_selected)

        if dropdown_selected.get("success"):
            return {"success": True, "selected": dropdown_selected.get("selected", value_str)}

        # Use Search more... to find existing customer
        search_more_clicked = await page.evaluate("""
            () => {
                const dropdown = document.querySelector('.o-autocomplete--dropdown-menu, [role="listbox"]');
                if (!dropdown) return false;
                const items = Array.from(dropdown.querySelectorAll('a[role="option"], .dropdown-item, li'));
                const searchMore = items.find(el => (el.textContent || '').trim().toLowerCase().includes('search more'));
                if (searchMore) {
                    searchMore.click();
                    return true;
                }
                return false;
            }
        """)
        if isinstance(search_more_clicked, str):
            search_more_clicked = search_more_clicked.strip().lower() == 'true'

        if not search_more_clicked:
            return {"success": False, "error": "Customer not found in dropdown"}

        # Wait for modal
        modal_ready = False
        for _ in range(10):
            modal_ready = await page.evaluate("""
                () => {
                    const dialog = document.querySelector('.o_dialog');
                    if (!dialog) return false;
                    return true;
                }
            """)
            if isinstance(modal_ready, str):
                modal_ready = modal_ready.strip().lower() == 'true'
            if modal_ready:
                break
            await asyncio.sleep(0.4)

        if not modal_ready:
            return {"success": False, "error": "Customer search modal not found"}

        # Filter in modal search box
        await page.evaluate(f"""
            () => {{
                const modal = document.querySelector('.o_dialog');
                if (!modal) return false;
                const input = modal.querySelector('input.o_searchview_input, input[placeholder*="Search"]');
                if (input) {{
                    input.focus();
                    input.value = {value_literal};
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', bubbles: true }}));
                    const searchBtn = modal.querySelector('button.o_searchview_button, button[aria-label*="Search"]');
                    if (searchBtn) searchBtn.click();
                    return true;
                }}
                return false;
            }}
        """)
        await asyncio.sleep(0.6)

        modal_selected = await page.evaluate(f"""
            () => {{
                const modal = document.querySelector('.o_dialog');
                if (!modal) return {{ error: 'Modal not found' }};
                const rows = modal.querySelectorAll('tr.o_data_row, tbody tr');
                const match = Array.from(rows).find(row => {{
                    const text = (row.textContent || '').toLowerCase();
                    return text.includes({value_literal}.toLowerCase());
                }});
                if (!match) return {{ error: 'Customer not found in modal' }};

                const checkbox = match.querySelector('input[type="checkbox"]');
                if (checkbox && !checkbox.checked) {{
                    checkbox.click();
                }} else {{
                    match.click();
                }}
                return {{ success: true }};
            }}
        """)
        if isinstance(modal_selected, str):
            modal_selected = json.loads(modal_selected)

        if modal_selected.get("error"):
            return {"success": False, "error": modal_selected.get("error")}

        select_clicked = await page.evaluate("""
            () => {
                const modal = document.querySelector('.o_dialog');
                if (!modal) return false;
                const buttons = modal.querySelectorAll('button');
                const selectBtn = Array.from(buttons).find(btn =>
                    (btn.textContent || '').trim().toLowerCase() === 'select'
                );
                if (selectBtn) {
                    selectBtn.click();
                    return true;
                }
                return false;
            }
        """)
        if isinstance(select_clicked, str):
            select_clicked = select_clicked.strip().lower() == 'true'

        if not select_clicked:
            return {"success": False, "error": "Select button not found in modal"}

        return {"success": True, "selected": value_str}

    async def ensure_partner_modal_saved(self) -> Dict[str, Any]:
        """
        If Create Partner modal is open, click Save and wait for it to close.
        Returns dict with success status and any errors.
        """
        page = await self.browser.get_current_page()
        result = {'success': True, 'modal_found': False, 'saved': False, 'error': None}

        # Check if Create Partner modal is visible
        modal_info = await page.evaluate("""
            () => {
                const dialog = document.querySelector('.o_dialog');
                if (!dialog) return {visible: false};

                const style = window.getComputedStyle(dialog);
                if (style.display === 'none' || style.visibility === 'hidden') {
                    return {visible: false};
                }

                const title = dialog.querySelector('.modal-title')?.textContent?.trim() || '';
                const titleLower = title.toLowerCase();

                // Check if this is a Create Partner modal
                const isCreatePartner = titleLower.includes('create partner') ||
                                       titleLower.includes('create contact') ||
                                       titleLower.includes('new partner') ||
                                       (titleLower.includes('partner') && dialog.querySelector('input[placeholder*="Name"]'));

                // Check for Save button
                const buttons = Array.from(dialog.querySelectorAll('button, .btn'));
                const saveBtn = buttons.find(btn => {
                    const text = (btn.textContent || '').trim().toLowerCase();
                    return text === 'save' || text === 'save & close';
                });

                return {
                    visible: true,
                    title: title,
                    isCreatePartner: isCreatePartner,
                    hasSaveButton: !!saveBtn
                };
            }
        """)

        if isinstance(modal_info, str):
            try:
                modal_info = json.loads(modal_info)
            except:
                modal_info = {'visible': False}

        if not modal_info.get('visible'):
            return result

        result['modal_found'] = True
        self.result.steps_taken.append(f"  └─ Detected modal: {modal_info.get('title', 'Unknown')}")

        if not modal_info.get('isCreatePartner'):
            # Not a Create Partner modal, might be something else
            return result

        if not modal_info.get('hasSaveButton'):
            result['success'] = False
            result['error'] = 'Create Partner modal has no Save button'
            return result

        # Human-like pause before clicking Save
        import random
        await asyncio.sleep(random.uniform(0.3, 0.6))

        # Click Save button
        save_clicked = await page.evaluate("""
            () => {
                const dialog = document.querySelector('.o_dialog');
                if (!dialog) return {error: 'Dialog disappeared'};

                const buttons = Array.from(dialog.querySelectorAll('button, .btn'));
                const saveBtn = buttons.find(btn => {
                    const text = (btn.textContent || '').trim().toLowerCase();
                    return text === 'save' || text === 'save & close';
                });

                if (saveBtn) {
                    saveBtn.click();
                    return {success: true};
                }
                return {error: 'Save button not found'};
            }
        """)

        if isinstance(save_clicked, str):
            try:
                save_clicked = json.loads(save_clicked)
            except:
                save_clicked = {'error': 'Parse error'}

        if save_clicked.get('error'):
            result['success'] = False
            result['error'] = save_clicked.get('error')
            return result

        self.result.steps_taken.append("  └─ Clicked Save on Create Partner modal")

        # Wait for modal to close (max 10 seconds)
        modal_closed = False
        for attempt in range(25):
            still_open = await page.evaluate("""
                () => {
                    const dialog = document.querySelector('.o_dialog');
                    if (!dialog) return false;
                    const style = window.getComputedStyle(dialog);
                    if (!style) return false;
                    return style.display !== 'none' && style.visibility !== 'hidden';
                }
            """)
            if isinstance(still_open, str):
                still_open = still_open.strip().lower() == 'true'

            if not still_open:
                modal_closed = True
                break

            # Check for validation errors in the modal
            has_error = await page.evaluate("""
                () => {
                    const dialog = document.querySelector('.o_dialog');
                    if (!dialog) return false;
                    const errorMsg = dialog.querySelector('.o_notification_content, .alert-danger, .text-danger, .o_form_error');
                    return !!errorMsg;
                }
            """)
            if isinstance(has_error, str):
                has_error = has_error.strip().lower() == 'true'

            if has_error:
                result['success'] = False
                result['error'] = 'Validation error in Create Partner modal'
                return result

            await asyncio.sleep(0.4)

        if not modal_closed:
            result['success'] = False
            result['error'] = 'Create Partner modal did not close after Save'
            return result

        result['saved'] = True
        self.result.steps_taken.append("  └─ Partner saved successfully")
        await self.wait_for_page_ready()
        return result

    async def click_button_by_text(self, button_text: str):
        """Click a button by searching for its text."""
        page = await self.browser.get_current_page()

        clicked = await page.evaluate(f"""
            () => {{
                const buttons = Array.from(document.querySelectorAll('button, a[role="button"]'));
                const btn = buttons.find(b => b.textContent.trim() === '{button_text}');
                if (btn) {{
                    btn.click();
                    return true;
                }}
                return false;
            }}
        """)

        return clicked

    async def fill_date_field(self, field_id: str, date_value: str = None):
        """
        Fill date field using calendar with stability checks and full diagnostics.

        Args:
            field_id: CSS selector ID (e.g., 'invoice_date_0')
            date_value: Date in 'YYYY-MM-DD' format

        Returns:
            Dict with success status, selected value, and debug info
        """
        page = await self.browser.get_current_page()
        debug_info = {
            'steps': [],
            'errors': [],
            'dom_snapshots': {}
        }

        try:
            from datetime import datetime
            import re
            import json

            if not date_value:
                return {'success': False, 'error': 'No date value provided', 'debug': debug_info}

            if '-' in date_value:
                target_date = datetime.strptime(date_value, '%Y-%m-%d')
            else:
                target_date = datetime.strptime(date_value, '%d/%m/%Y')

            target_year = target_date.year
            target_month = target_date.month
            target_day = target_date.day

            debug_info['steps'].append(f"Target: {target_day}/{target_month}/{target_year}")

            # Step 1: Click date field to open calendar
            clicked = await page.evaluate(f"""
                () => {{
                    const field = document.querySelector('#{field_id}');
                    if (field) {{
                        field.click();
                        return true;
                    }}
                    return false;
                }}
            """)

            if not clicked:
                debug_info['errors'].append(f"Field #{field_id} not found")
                return {'success': False, 'error': 'Date field not found', 'debug': debug_info}

            debug_info['steps'].append("Clicked date field")

            # Step 2: Wait for calendar to appear and be stable
            calendar_visible = False
            for attempt in range(5):
                await asyncio.sleep(0.5)

                visible = await page.evaluate("""
                    () => {
                        const calendar = document.querySelector('.o_datetime_picker');
                        const cells = document.querySelectorAll('.o_date_item_cell');
                        return calendar && cells.length > 0;
                    }
                """)

                if visible:
                    calendar_visible = True
                    debug_info['steps'].append(f"Calendar visible (attempt {attempt + 1})")
                    break

                debug_info['steps'].append(f"Calendar not ready (attempt {attempt + 1})")

            if not calendar_visible:
                dom_state = await page.evaluate("""
                    () => {
                        const calendar = document.querySelector('.o_datetime_picker');
                        const cells = document.querySelectorAll('.o_date_item_cell');
                        return {
                            calendarExists: !!calendar,
                            cellCount: cells.length,
                            calendarHtml: calendar ? calendar.outerHTML.substring(0, 500) : null
                        };
                    }
                """)
                debug_info['dom_snapshots']['calendar_not_visible'] = dom_state
                debug_info['errors'].append("Calendar did not appear after 2.5s")

                try:
                    screenshot = await page.screenshot()
                    debug_info['screenshot_path'] = f'debug_calendar_failed_{field_id}.png'
                    with open(debug_info['screenshot_path'], 'wb') as f:
                        f.write(screenshot)
                except:
                    pass

                return {'success': False, 'error': 'Calendar did not open', 'debug': debug_info}

            # Step 3: Navigate to target month/year (Python loop with delays)
            max_navigation_attempts = 24

            for nav_attempt in range(max_navigation_attempts):
                month_year_info = await page.evaluate("""
                    () => {
                        const titleElem = document.querySelector('.o_datetime_picker_header .o_header_part');
                        if (!titleElem) return null;

                        const text = titleElem.textContent.trim();
                        return {
                            text: text,
                            html: titleElem.outerHTML
                        };
                    }
                """)

                # Handle case where browser_use returns JSON as string
                if isinstance(month_year_info, str):
                    try:
                        month_year_info = json.loads(month_year_info)
                    except:
                        debug_info['errors'].append(f"Could not parse month_year_info JSON: {month_year_info}")
                        await asyncio.sleep(0.3)
                        continue

                if not month_year_info or not isinstance(month_year_info, dict):
                    debug_info['steps'].append(f"Nav attempt {nav_attempt + 1}: Month title not found")
                    await asyncio.sleep(0.3)
                    continue

                month_year_text = month_year_info.get('text', '')
                debug_info['steps'].append(f"Nav attempt {nav_attempt + 1}: Reading '{month_year_text}'")

                year_match = re.search(r'\d{4}', month_year_text)
                if not year_match:
                    debug_info['errors'].append(f"Could not parse year from '{month_year_text}'")
                    await asyncio.sleep(0.3)
                    continue

                current_year = int(year_match.group())

                month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                              'July', 'August', 'September', 'October', 'November', 'December']
                current_month = None

                for i, month_name in enumerate(month_names, 1):
                    if month_name in month_year_text:
                        current_month = i
                        break

                if current_month is None:
                    debug_info['errors'].append(f"Could not parse month from '{month_year_text}'")
                    await asyncio.sleep(0.3)
                    continue

                debug_info['steps'].append(f"Current: {current_month}/{current_year}, Target: {target_month}/{target_year}")

                if current_year == target_year and current_month == target_month:
                    debug_info['steps'].append("✓ Reached target month")
                    break

                if current_year < target_year or (current_year == target_year and current_month < target_month):
                    clicked_nav = await page.evaluate("""
                        () => {
                            const btn = document.querySelector('.o_datetime_picker_header .o_next');
                            if (btn) {
                                btn.click();
                                return true;
                            }
                            return false;
                        }
                    """)

                    if clicked_nav:
                        debug_info['steps'].append("→ Clicked next month")
                    else:
                        debug_info['errors'].append("Next button not found")
                        break
                else:
                    clicked_nav = await page.evaluate("""
                        () => {
                            const btn = document.querySelector('.o_datetime_picker_header .o_previous');
                            if (btn) {
                                btn.click();
                                return true;
                            }
                            return false;
                        }
                    """)

                    if clicked_nav:
                        debug_info['steps'].append("← Clicked previous month")
                    else:
                        debug_info['errors'].append("Previous button not found")
                        break

                await asyncio.sleep(0.6)

            # Step 4: Select target day
            await asyncio.sleep(0.3)

            day_selection_result = await page.evaluate(f"""
                () => {{
                    const cells = document.querySelectorAll('.o_date_item_cell');
                    const cellsArray = Array.from(cells);

                    const allCells = cellsArray.map(cell => ({{
                        text: cell.textContent.trim(),
                        classes: cell.className,
                        disabled: cell.classList.contains('o_disabled'),
                        outOfRange: cell.classList.contains('o_out_of_range')
                    }}));

                    const targetCell = cellsArray.find(cell => {{
                        const text = cell.textContent.trim();
                        const dayNum = parseInt(text);

                        return dayNum === {target_day} &&
                               !cell.classList.contains('o_out_of_range') &&
                               !cell.classList.contains('o_disabled') &&
                               text.length <= 2;
                    }});

                    if (targetCell) {{
                        targetCell.click();
                        return {{
                            success: true,
                            clickedText: targetCell.textContent.trim()
                        }};
                    }}

                    return {{
                        success: false,
                        allCells: allCells,
                        targetDay: {target_day}
                    }};
                }}
            """)

            # Handle case where browser_use returns JSON as string
            if isinstance(day_selection_result, str):
                try:
                    day_selection_result = json.loads(day_selection_result)
                except:
                    debug_info['errors'].append(f"Could not parse day_selection_result JSON: {day_selection_result}")
                    return {'success': False, 'error': 'Failed to parse day selection result', 'debug': debug_info}

            if not day_selection_result.get('success'):
                debug_info['dom_snapshots']['day_cells'] = day_selection_result.get('allCells', [])
                debug_info['errors'].append(f"Day {target_day} not found in calendar cells")

                try:
                    screenshot = await page.screenshot()
                    debug_info['screenshot_path'] = f'debug_day_not_found_{field_id}.png'
                    with open(debug_info['screenshot_path'], 'wb') as f:
                        f.write(screenshot)
                except:
                    pass

                return {'success': False, 'error': f'Day {target_day} not clickable', 'debug': debug_info}

            debug_info['steps'].append(f"✓ Clicked day {day_selection_result['clickedText']}")

            # Step 5: Wait for calendar to close and field to update
            await asyncio.sleep(0.5)

            # Step 6: Verify the date was set
            final_value = await page.evaluate(f"""
                () => {{
                    const field = document.querySelector('#{field_id}');
                    return field ? field.value || field.textContent.trim() : null;
                }}
            """)

            debug_info['steps'].append(f"Final field value: '{final_value}'")

            if final_value:
                return {
                    'success': True,
                    'selected': final_value,
                    'debug': debug_info
                }
            else:
                debug_info['errors'].append("Field value empty after selection")
                return {
                    'success': False,
                    'error': 'Date not set in field',
                    'debug': debug_info
                }

        except Exception as e:
            debug_info['errors'].append(f"Exception: {str(e)}")

            try:
                screenshot = await page.screenshot()
                debug_info['screenshot_path'] = f'debug_exception_{field_id}.png'
                with open(debug_info['screenshot_path'], 'wb') as f:
                    f.write(screenshot)
            except:
                pass

            return {
                'success': False,
                'error': f'Exception: {str(e)}',
                'debug': debug_info
            }

    async def ensure_line_item_columns(self, column_specs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Ensure optional columns in invoice line items are enabled (e.g., Quantity, Disc.%).

        Args:
            column_specs: List of dicts with keys:
                - label: canonical column label
                - aliases: list of label variants to match in the dropdown
        """
        page = await self.browser.get_current_page()
        result = {
            'success': False,
            'enabled': [],
            'already_enabled': [],
            'missing': [],
            'errors': []
        }

        try:
            import json
            import re

            def normalize(text: str) -> str:
                return re.sub(r'\s+', ' ', text or '').strip().lower()

            def compact(text: str) -> str:
                return re.sub(r'[^a-z0-9%]', '', normalize(text))

            # Check which columns are already visible
            headers_result = await page.evaluate("""
                () => {
                    const section = document.querySelector('[name="invoice_line_ids"]');
                    if (!section) return JSON.stringify({error: 'invoice_line_ids not found'});

                    const headerCells = Array.from(section.querySelectorAll('thead th'))
                        .map(th => (th.textContent || '').replace(/\\s+/g, ' ').trim())
                        .filter(Boolean);

                    return JSON.stringify({headers: headerCells});
                }
            """)

            if isinstance(headers_result, str):
                headers_data = json.loads(headers_result)
            else:
                headers_data = headers_result or {}

            if headers_data.get('error'):
                result['errors'].append(headers_data['error'])
                return result

            headers = headers_data.get('headers', [])

            specs_to_enable = []
            for spec in column_specs:
                label = spec.get('label') or ''
                aliases = [label] + [a for a in (spec.get('aliases') or []) if a]
                present = False

                for header in headers:
                    header_norm = normalize(header)
                    header_comp = compact(header)
                    for alias in aliases:
                        alias_norm = normalize(alias)
                        alias_comp = compact(alias)
                        if alias_norm and (alias_norm == header_norm or alias_norm in header_norm or header_norm in alias_norm):
                            present = True
                            break
                        if alias_comp and (alias_comp == header_comp or alias_comp in header_comp or header_comp in alias_comp):
                            present = True
                            break
                    if present:
                        break

                if present:
                    result['already_enabled'].append(label or aliases[0])
                else:
                    specs_to_enable.append({'label': label or aliases[0], 'aliases': aliases})

            if not specs_to_enable:
                result['success'] = True
                return result

            for spec in specs_to_enable:
                toggled = False
                for _ in range(3):
                    # Open the optional columns dropdown
                    open_result = await page.evaluate("""
                        () => {
                            const section = document.querySelector('[name="invoice_line_ids"]');
                            if (!section) return JSON.stringify({error: 'invoice_line_ids not found'});

                            const header = section.querySelector('thead') || section.querySelector('.o_list_view thead') || section.querySelector('table thead');
                            if (!header) return JSON.stringify({error: 'Header not found'});

                            const buttons = Array.from(header.querySelectorAll('button'));
                            if (buttons.length === 0) return JSON.stringify({error: 'No header buttons found'});

                            const candidate = buttons.find(btn => {
                                const cls = (btn.className || '').toLowerCase();
                                const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
                                const title = (btn.getAttribute('title') || '').toLowerCase();
                                return cls.includes('optional') ||
                                       cls.includes('dropdown') ||
                                       aria.includes('column') ||
                                       title.includes('column') ||
                                       aria.includes('optional') ||
                                       title.includes('optional') ||
                                       aria.includes('field') ||
                                       title.includes('field');
                            }) || buttons[buttons.length - 1];

                            candidate.click();
                            return JSON.stringify({
                                success: true,
                                buttonClass: candidate.className || '',
                                aria: candidate.getAttribute('aria-label') || '',
                                title: candidate.getAttribute('title') || ''
                            });
                        }
                    """)

                    if isinstance(open_result, str):
                        open_result = json.loads(open_result)

                    if open_result.get('error'):
                        result['errors'].append(open_result['error'])
                        await asyncio.sleep(0.4)
                        continue

                    await asyncio.sleep(0.4)

                    aliases_json = json.dumps(spec['aliases'])
                    toggle_result = await page.evaluate(f"""
                        () => {{
                            const aliases = {aliases_json};
                            const normalize = (text) => (text || '').toLowerCase().replace(/\\s+/g, ' ').replace(/\\u00A0/g, ' ').trim();
                            const compact = (text) => normalize(text).replace(/[^a-z0-9%]/g, '');

                            const aliasNorm = aliases.map(a => normalize(a));
                            const aliasComp = aliases.map(a => compact(a));

                            const menus = Array.from(document.querySelectorAll('.dropdown-menu, .o-dropdown--menu, [role="menu"], .o_optional_columns_dropdown_menu'))
                                .filter(menu => {{
                                    if (!menu) return false;
                                    const style = window.getComputedStyle(menu);
                                    return style && style.display !== 'none' && style.visibility !== 'hidden';
                                }});

                            if (menus.length === 0) {{
                                return JSON.stringify({{error: 'Dropdown menu not found'}});
                            }}

                            const sampled = [];
                            for (const menu of menus) {{
                                const items = Array.from(menu.querySelectorAll('a, li, button, label, div, span'))
                                    .filter(el => {{
                                        const text = (el.textContent || '').trim();
                                        if (!text) return false;
                                        const role = (el.getAttribute('role') || '').toLowerCase();
                                        const cls = (el.className || '').toLowerCase();
                                        if (role.includes('menuitem')) return true;
                                        if (cls.includes('dropdown-item')) return true;
                                        if (el.tagName.toLowerCase() === 'label') return true;
                                        if (el.querySelector('input[type="checkbox"]')) return true;
                                        return false;
                                    }});

                                for (const item of items) {{
                                    const text = (item.textContent || '').trim();
                                    if (sampled.length < 12) sampled.push(text);
                                    const normText = normalize(text);
                                    const compText = compact(text);

                                    const matchNorm = aliasNorm.some(a => a && (normText === a || normText.includes(a) || a.includes(normText)));
                                    const matchComp = aliasComp.some(a => a && (compText === a || compText.includes(a) || a.includes(compText)));

                                    if (!matchNorm && !matchComp) continue;

                                    const checkbox = item.querySelector('input[type="checkbox"]');
                                    let already = false;
                                    if (checkbox) {{
                                        already = checkbox.checked;
                                        if (!checkbox.checked) {{
                                            checkbox.click();
                                        }}
                                    }} else {{
                                        const ariaChecked = (item.getAttribute('aria-checked') || '').toLowerCase();
                                        if (ariaChecked === 'true') already = true;
                                        if (!already) {{
                                            item.click();
                                        }}
                                    }}

                                    return JSON.stringify({{
                                        success: true,
                                        matchedText: text,
                                        alreadyEnabled: already
                                    }});
                                }}
                            }}

                            return JSON.stringify({{error: 'Column option not found', sample: sampled}});
                        }}
                    """)

                    if isinstance(toggle_result, str):
                        toggle_result = json.loads(toggle_result)

                    if toggle_result.get('success'):
                        if toggle_result.get('alreadyEnabled'):
                            result['already_enabled'].append(spec['label'])
                        else:
                            result['enabled'].append(spec['label'])
                        toggled = True
                        break

                    await asyncio.sleep(0.4)

                if not toggled:
                    result['missing'].append(spec['label'])

            if result['enabled']:
                await self.wait_for_page_ready()

            # Hide optional columns dropdown after toggling
            await page.evaluate("""
                () => {
                    const section = document.querySelector('[name="invoice_line_ids"]');
                    if (!section) return false;

                    const header = section.querySelector('thead') ||
                                   section.querySelector('.o_list_view thead') ||
                                   section.querySelector('table thead');
                    if (!header) return false;

                    const buttons = Array.from(header.querySelectorAll('button'));
                    const toggle = header.querySelector('button[aria-expanded="true"], button[expanded="true"], button.show') ||
                        buttons.find(btn => {
                            const cls = (btn.className || '').toLowerCase();
                            const aria = (btn.getAttribute('aria-expanded') || '').toLowerCase();
                            const expanded = (btn.getAttribute('expanded') || '').toLowerCase();
                            return (aria === 'true' || expanded === 'true') && (cls.includes('dropdown') || cls.includes('optional'));
                        });

                    if (toggle) {
                        toggle.click();
                        return true;
                    }

                    document.body.click();
                    return false;
                }
            """)
            await asyncio.sleep(0.2)

            result['success'] = len(result['errors']) == 0 and len(result['missing']) == 0
            return result

        except Exception as e:
            result['errors'].append(f"Exception: {str(e)}")
            return result

    async def select_product_for_line(self, line_number: int, product_name: str) -> Dict[str, Any]:
        """
        Select a product for a given invoice line using the product dropdown,
        with Search more... fallback.
        """
        page = await self.browser.get_current_page()
        result = {
            'success': False,
            'selected': None,
            'errors': []
        }

        try:
            import json

            if product_name is None:
                result['errors'].append("Product name missing")
                return result

            product_literal = json.dumps(str(product_name))

            # Click product cell to activate
            clicked = await page.evaluate(f"""
                () => {{
                    const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                        .filter(r => {{
                            const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                            const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                            return !isNote && !isSection;
                        }});
                    if (rows.length <= {line_number}) return JSON.stringify({{error: 'Row not found'}});

                    const targetRow = rows[{line_number}];
                    if (!targetRow) return JSON.stringify({{error: 'Row not found'}});

                    const productCell = targetRow.querySelector('td[name="name"]') ||
                                       targetRow.querySelector('[name="name"]') ||
                                       targetRow.querySelector('.o_section_and_note_text_cell') ||
                                       targetRow.querySelector('td[name="product_id"]') ||
                                       targetRow.querySelector('[name="product_id"]');
                    if (!productCell) return JSON.stringify({{error: 'Product cell not found'}});

                    productCell.click();
                    return JSON.stringify({{success: true}});
                }}
            """)

            if isinstance(clicked, str):
                clicked = json.loads(clicked)

            if clicked.get('error') or not clicked.get('success'):
                result['errors'].append(clicked.get('error', 'Product cell not clickable'))
                return result

            await asyncio.sleep(0.4)

            # Focus and type into the product input (retry a few times)
            input_ready = False
            for _ in range(5):
                focus_result = await page.evaluate(f"""
                    () => {{
                        const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                            .filter(r => {{
                                const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                return !isNote && !isSection;
                            }});
                        const targetRow = rows[{line_number}];
                        if (!targetRow) return JSON.stringify({{error: 'Row not found'}});

                        const productCell = targetRow.querySelector('td[name="name"]') ||
                                           targetRow.querySelector('[name="name"]') ||
                                           targetRow.querySelector('.o_section_and_note_text_cell') ||
                                           targetRow.querySelector('td[name="product_id"]') ||
                                           targetRow.querySelector('[name="product_id"]');
                        if (!productCell) return JSON.stringify({{error: 'Product cell not found'}});

                        const input = productCell.querySelector('input.o-autocomplete--input') ||
                                     productCell.querySelector('input[placeholder*=\"Search\"]') ||
                                     productCell.querySelector('input') ||
                                     productCell.querySelector('textarea') ||
                                     targetRow.querySelector('input[name*="name"]') ||
                                     targetRow.querySelector('.o_many2one input');
                        if (!input) {{
                            productCell.click();
                            return JSON.stringify({{retry: true}});
                        }}

                        input.focus();
                        input.value = '';
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        return JSON.stringify({{success: true}});
                    }}
                """)

                if isinstance(focus_result, str):
                    focus_result = json.loads(focus_result)

                if focus_result.get('success'):
                    input_ready = True
                    break
                if focus_result.get('error'):
                    result['errors'].append(focus_result.get('error'))
                    return result

                await asyncio.sleep(0.4)

            if not input_ready:
                result['errors'].append('Product input not found')
                return result

            import random
            chars_per_second = random.uniform(10, 12)
            delay_per_char = 1.0 / chars_per_second

            for char in str(product_name):
                await page.evaluate(f"""
                    () => {{
                        const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                            .filter(r => {{
                                const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                return !isNote && !isSection;
                            }});
                        const targetRow = rows[{line_number}];
                        if (!targetRow) return;

                        const productCell = targetRow.querySelector('td[name="name"]') ||
                                           targetRow.querySelector('[name="name"]') ||
                                           targetRow.querySelector('.o_section_and_note_text_cell') ||
                                           targetRow.querySelector('td[name="product_id"]') ||
                                           targetRow.querySelector('[name="product_id"]');
                        if (!productCell) return;

                        const input = productCell.querySelector('input') ||
                                     productCell.querySelector('textarea') ||
                                     targetRow.querySelector('input[name*="name"]') ||
                                     targetRow.querySelector('.o_many2one input');
                        if (input) {{
                            input.value += '{char}';
                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    }}
                """)
                await asyncio.sleep(delay_per_char)

            await asyncio.sleep(0.5)

            # Check if this is a simple text field (textarea) without dropdown
            # If so, just trigger blur/change and return success
            field_type_check = await page.evaluate(f"""
                () => {{
                    const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                        .filter(r => {{
                            const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                            const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                            return !isNote && !isSection;
                        }});
                    const targetRow = rows[{line_number}];
                    if (!targetRow) return {{error: 'Row not found'}};

                    const productCell = targetRow.querySelector('td[name="name"]') ||
                                       targetRow.querySelector('[name="name"]') ||
                                       targetRow.querySelector('.o_section_and_note_text_cell');
                    if (!productCell) return {{error: 'Cell not found'}};

                    const textarea = productCell.querySelector('textarea');
                    const autocompleteInput = productCell.querySelector('input.o-autocomplete--input');
                    const dropdown = document.querySelector('.o-autocomplete--dropdown-menu, [role="listbox"]');

                    // If it's a simple textarea without autocomplete/dropdown, complete directly
                    if (textarea && !autocompleteInput && !dropdown) {{
                        textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        textarea.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                        return {{simple_text_field: true, value: textarea.value}};
                    }}

                    return {{has_dropdown_logic: true}};
                }}
            """)

            if isinstance(field_type_check, str):
                field_type_check = json.loads(field_type_check)

            if field_type_check.get('simple_text_field'):
                result['success'] = True
                result['selected'] = field_type_check.get('value', product_name)
                return result

            selected = None
            if not self.force_search_more_products:
                # Try to select from dropdown (retry a few times)
                for _ in range(5):
                    selected = await page.evaluate(f"""
                        () => {{
                            const target = {product_literal}.toLowerCase().trim();
                            const dropdown = document.querySelector('.o-autocomplete--dropdown-menu, [role="listbox"]');
                            if (!dropdown) return {{error: 'Dropdown not found'}};

                            const options = Array.from(dropdown.querySelectorAll('a[role="option"], .dropdown-item, li')).filter(el => {{
                                const text = (el.textContent || '').trim();
                                if (!text) return false;
                                const lower = text.toLowerCase();
                                if (lower.includes('create and edit') || lower.includes('create')) return false;
                                if (lower.includes('search more') || lower.includes('search worldwide')) return false;
                                return true;
                            }});

                            if (options.length > 0 && options.every(el => (el.textContent || '').trim().toLowerCase().includes('loading'))) {{
                                return {{error: 'Dropdown loading'}};
                            }}

                            let match = options.find(el => (el.textContent || '').trim().toLowerCase() === target);
                            if (!match) {{
                                match = options.find(el => (el.textContent || '').trim().toLowerCase().includes(target));
                            }}

                            if (match) {{
                                match.click();
                                return {{success: true, selected: match.textContent.trim()}};
                            }}

                            const searchMore = Array.from(dropdown.querySelectorAll('a[role="option"], .dropdown-item, li'))
                                .find(el => (el.textContent || '').trim().toLowerCase().includes('search more'));
                            if (searchMore) {{
                                searchMore.click();
                                return {{search_more: true}};
                            }}

                            return {{error: 'Product not found in dropdown'}};
                        }}
                    """)

                    if isinstance(selected, str):
                        selected = json.loads(selected)

                    if selected.get('success'):
                        result['success'] = True
                        result['selected'] = selected.get('selected', product_name)
                        return result

                    if selected.get('search_more'):
                        break

                    if selected.get('error') in ('Dropdown not found', 'Dropdown loading'):
                        await asyncio.sleep(0.4)
                        continue

                    break
            else:
                # Force Search more... path
                # Try to open dropdown if not already visible
                await page.evaluate(f"""
                    () => {{
                        const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                            .filter(r => {{
                                const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                return !isNote && !isSection;
                            }});
                        const targetRow = rows[{line_number}];
                        if (!targetRow) return false;

                        const productCell = targetRow.querySelector('td[name="name"]') ||
                                           targetRow.querySelector('[name="name"]') ||
                                           targetRow.querySelector('.o_section_and_note_text_cell') ||
                                           targetRow.querySelector('td[name="product_id"]') ||
                                           targetRow.querySelector('[name="product_id"]');
                        if (!productCell) return false;

                        const dropdownBtn = productCell.querySelector('.o_dropdown_button');
                        if (dropdownBtn) {{
                            dropdownBtn.click();
                            return true;
                        }}
                        return false;
                    }}
                """)
                await asyncio.sleep(0.3)

                forced_search = await page.evaluate("""
                    () => {
                        const dropdown = document.querySelector('.o-autocomplete--dropdown-menu, [role="listbox"]');
                        if (!dropdown) return {error: 'Dropdown not found'};

                        const items = Array.from(dropdown.querySelectorAll('a[role="option"], .dropdown-item, li'));
                        if (items.length === 0) return {error: 'Dropdown empty'};

                        const searchMore = items.find(el => (el.textContent || '').trim().toLowerCase().includes('search more'));
                        if (searchMore) {
                            searchMore.click();
                            return {search_more: true};
                        }

                        return {error: 'Search more not found'};
                    }
                """)

                if isinstance(forced_search, str):
                    forced_search = json.loads(forced_search)

                if not forced_search.get('search_more'):
                    result['errors'].append(forced_search.get('error', 'Search more not found'))
                    return result

            # Search more... fallback
            await asyncio.sleep(0.6)
            modal_ready = False
            for _ in range(10):
                modal_ready = await page.evaluate("""
                    () => {
                        const dialog = document.querySelector('.o_dialog');
                        if (!dialog) return false;
                        const title = dialog.querySelector('.modal-title')?.textContent?.trim() || '';
                        return title.length > 0;
                    }
                """)
                if isinstance(modal_ready, str):
                    modal_ready = modal_ready.strip().lower() == 'true'
                if modal_ready:
                    break
                await asyncio.sleep(0.4)

            if not modal_ready:
                result['errors'].append("Product search modal did not appear")
                return result

            # Filter in modal search box if present
            await page.evaluate(f"""
                () => {{
                    const modal = document.querySelector('.o_dialog');
                    if (!modal) return false;
                    const input = modal.querySelector('input.o_searchview_input, input[placeholder*="Search"]');
                    if (input) {{
                        input.focus();
                        input.value = {product_literal};
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', bubbles: true }}));
                        const searchBtn = modal.querySelector('button.o_searchview_button, button[aria-label*="Search"]');
                        if (searchBtn) searchBtn.click();
                        return true;
                    }}
                    return false;
                }}
            """)

            await asyncio.sleep(0.6)

            modal_selected = await page.evaluate(f"""
                () => {{
                    const modal = document.querySelector('.o_dialog');
                    if (!modal) return {{error: 'Modal not found'}};

                    const rows = modal.querySelectorAll('tr.o_data_row, tbody tr');
                    const match = Array.from(rows).find(row => {{
                        const text = (row.textContent || '').toLowerCase();
                        return text.includes({product_literal}.toLowerCase());
                    }});

                    if (!match) return {{error: 'Product not found in modal'}};

                    const checkbox = match.querySelector('input[type="checkbox"]');
                    if (checkbox && !checkbox.checked) {{
                        checkbox.click();
                    }} else {{
                        match.click();
                    }}

                    return {{success: true}};
                }}
            """)

            if isinstance(modal_selected, str):
                modal_selected = json.loads(modal_selected)

            if modal_selected.get('error'):
                result['errors'].append(modal_selected.get('error'))
                return result

            select_clicked = await page.evaluate("""
                () => {
                    const modal = document.querySelector('.o_dialog');
                    if (!modal) return false;

                    const buttons = modal.querySelectorAll('button');
                    const selectBtn = Array.from(buttons).find(btn =>
                        btn.textContent.trim() === 'Select'
                    );
                    if (selectBtn) {
                        selectBtn.click();
                        return true;
                    }
                    return false;
                }
            """)

            if isinstance(select_clicked, str):
                select_clicked = select_clicked.strip().lower() == 'true'

            if not select_clicked:
                result['errors'].append("Select button not found in product modal")
                return result

            result['success'] = True
            result['selected'] = product_name
            return result

        except Exception as e:
            result['errors'].append(f"Exception: {str(e)}")
            return result

    async def add_products_from_catalog(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Add products via the Catalog flow using the search bar and Add button.
        """
        page = await self.browser.get_current_page()
        result = {
            'success': False,
            'added': [],
            'errors': []
        }

        try:
            if not items:
                result['errors'].append("No catalog items provided")
                return result

            # Open catalog
            catalog_clicked = await self.click_button_by_text("Catalog")
            if not catalog_clicked:
                # Try by name attribute as fallback
                catalog_clicked = await page.evaluate("""
                    () => {
                        const btn = document.querySelector('button[name="action_add_from_catalog"], a[name="action_add_from_catalog"]');
                        if (btn) {
                            btn.click();
                            return true;
                        }
                        return false;
                    }
                """)

            if not catalog_clicked:
                result['errors'].append("Catalog button not found")
                return result

            # Wait for catalog page (Back to Invoice button or Products heading)
            catalog_ready = False
            for _ in range(12):
                catalog_ready = await page.evaluate("""
                    () => {
                        const backBtn = Array.from(document.querySelectorAll('button, a')).find(el =>
                            (el.textContent || '').trim().toLowerCase() === 'back to invoice'
                        );
                        const title = document.querySelector('.o_control_panel .o_breadcrumb, .o_breadcrumb, h1, h2');
                        const text = (title && title.textContent) ? title.textContent.toLowerCase() : '';
                        return !!backBtn || text.includes('products');
                    }
                """)
                if isinstance(catalog_ready, str):
                    catalog_ready = catalog_ready.strip().lower() == 'true'
                if catalog_ready:
                    break
                await asyncio.sleep(0.5)

            if not catalog_ready:
                result['errors'].append("Catalog page not ready")
                return result

            for item in items:
                name = item.get('name') or item.get('label') or item.get('product')
                if not name:
                    result['errors'].append("Catalog item missing name/label/product")
                    continue
                quantity = item.get('quantity', 1)
                try:
                    quantity = int(quantity)
                except Exception:
                    quantity = 1

                # Search in catalog
                import json
                name_literal = json.dumps(str(name))
                await page.evaluate(f"""
                    () => {{
                        const input = document.querySelector('input.o_searchview_input, input[placeholder*="Search"]');
                        if (!input) return false;
                        input.focus();
                        input.value = '';
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.value = {name_literal};
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', bubbles: true }}));
                        return true;
                    }}
                """)
                await asyncio.sleep(0.7)

                # Click Add on matching card
                card_action = await page.evaluate(f"""
                    () => {{
                        const target = {name_literal}.toLowerCase().trim();
                        const cards = Array.from(document.querySelectorAll(
                            '.o_kanban_record, .o_product_kanban, .o_catalog_record, .o_product_catalog, .o_kanban_card, .o_card, .o_grid_item'
                        ));
                        let match = cards.find(card => (card.textContent || '').toLowerCase().includes(target));
                        if (!match && cards.length === 1) match = cards[0];
                        if (!match) return {{error: 'Product card not found'}};

                        const buttons = Array.from(match.querySelectorAll('button, a'));
                        const addBtn = buttons.find(b => (b.textContent || '').trim().toLowerCase() === 'add');
                        if (addBtn) {{
                            addBtn.click();
                            return {{success: true, action: 'add'}};
                        }}

                        const removeBtn = buttons.find(b => (b.textContent || '').trim().toLowerCase() === 'remove');
                        if (removeBtn) {{
                            return {{success: true, action: 'already_added'}};
                        }}

                        // Some UIs show plus/minus immediately
                        const plusBtn = buttons.find(b => (b.textContent || '').trim() === '+');
                        if (plusBtn) {{
                            return {{success: true, action: 'already_added'}};
                        }}

                        return {{error: 'Add button not found'}};
                    }}
                """)

                if isinstance(card_action, str):
                    card_action = json.loads(card_action)

                if card_action.get('error'):
                    result['errors'].append(f"{name}: {card_action.get('error')}")
                    continue

                # Increase quantity if needed
                if quantity > 1:
                    for _ in range(quantity - 1):
                        clicked_plus = await page.evaluate(f"""
                            () => {{
                                const target = {name_literal}.toLowerCase().trim();
                                const cards = Array.from(document.querySelectorAll(
                                    '.o_kanban_record, .o_product_kanban, .o_catalog_record, .o_product_catalog, .o_kanban_card, .o_card, .o_grid_item'
                                ));
                                let match = cards.find(card => (card.textContent || '').toLowerCase().includes(target));
                                if (!match && cards.length === 1) match = cards[0];
                                if (!match) return false;

                                const buttons = Array.from(match.querySelectorAll('button, a'));
                                const plusBtn = buttons.find(b => (b.textContent || '').trim() === '+');
                                if (plusBtn) {{
                                    plusBtn.click();
                                    return true;
                                }}
                                return false;
                            }}
                        """)
                        if not clicked_plus:
                            break
                        await asyncio.sleep(0.2)

                result['added'].append({'name': name, 'quantity': quantity})

                # Clear search for next item
                await page.evaluate("""
                    () => {
                        const input = document.querySelector('input.o_searchview_input, input[placeholder*="Search"]');
                        if (!input) return false;
                        input.focus();
                        input.value = '';
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        return true;
                    }
                """)
                await asyncio.sleep(0.3)

            # Back to invoice
            back_clicked = await page.evaluate("""
                () => {
                    const backBtn = Array.from(document.querySelectorAll('button, a')).find(el =>
                        (el.textContent || '').trim().toLowerCase() === 'back to invoice'
                    );
                    if (backBtn) {
                        backBtn.click();
                        return true;
                    }
                    return false;
                }
            """)

            if not back_clicked:
                result['errors'].append("Back to Invoice button not found")
                return result

            # Wait for invoice lines table to reappear
            for _ in range(12):
                table_ready = await page.evaluate("""
                    () => {
                        return !!document.querySelector('[name="invoice_line_ids"]');
                    }
                """)
                if isinstance(table_ready, str):
                    table_ready = table_ready.strip().lower() == 'true'
                if table_ready:
                    break
                await asyncio.sleep(0.5)

            result['success'] = len(result['errors']) == 0
            return result

        except Exception as e:
            result['errors'].append(f"Exception: {str(e)}")
            return result

    async def add_note_line(self, note_text: str) -> Dict[str, Any]:
        """
        Add a note line in invoice lines and fill with text.
        """
        page = await self.browser.get_current_page()
        result = {'success': False, 'error': None}

        try:
            clicked = await self.click_button_by_text("Add a note")
            if not clicked:
                # Try switching back to Invoice Lines tab and retry
                await self.click_tab_by_text("Invoice Lines")
                await asyncio.sleep(0.4)
                clicked = await self.click_button_by_text("Add a note")
            if not clicked:
                result['error'] = "Add a note button not found"
                return result

            # Wait for note row
            target_ready = False
            for _ in range(10):
                target_ready = await page.evaluate("""
                    () => {
                        const container = document.querySelector('[name="invoice_line_ids"]');
                        if (!container) return false;
                        const rows = Array.from(container.querySelectorAll('.o_data_row'));
                        const noteRows = rows.filter(r => r.className.includes('o_is_note') ||
                            r.dataset && String(r.dataset.displayType || '').includes('note'));
                        if (noteRows.length > 0) return true;
                        const textarea = container.querySelector('textarea, [contenteditable="true"]');
                        return !!textarea;
                    }
                """)
                if isinstance(target_ready, str):
                    target_ready = target_ready.strip().lower() == 'true'
                if target_ready:
                    break
                await asyncio.sleep(0.3)

            # Fill note text
            import json
            note_literal = json.dumps(note_text or "")
            filled = await page.evaluate(f"""
                () => {{
                    const container = document.querySelector('[name="invoice_line_ids"]');
                    if (!container) return JSON.stringify({{error: 'Invoice lines not found'}});

                    const rows = Array.from(container.querySelectorAll('.o_data_row'));
                    const noteRows = rows.filter(r => r.className.includes('o_is_note') ||
                        r.dataset && String(r.dataset.displayType || '').includes('note'));
                    let targetRow = noteRows[noteRows.length - 1];
                    if (!targetRow) {{
                        targetRow = rows[rows.length - 1];
                    }}
                    if (!targetRow) return JSON.stringify({{error: 'Note row not found'}});

                    const candidates = Array.from(targetRow.querySelectorAll('textarea, input, [contenteditable="true"], .o_input'));
                    let field = candidates.find(el => !el.disabled && !el.readOnly) || candidates[0];
                    if (!field) {{
                        // fallback to any textarea within invoice lines
                        const fallback = container.querySelector('textarea, [contenteditable="true"]');
                        field = fallback;
                    }}
                    if (!field) return JSON.stringify({{error: 'Note input not found'}});

                    field.focus();
                    if (field.isContentEditable) {{
                        field.textContent = {note_literal};
                    }} else {{
                        field.value = {note_literal};
                    }}
                    field.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    field.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    field.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                    return JSON.stringify({{success: true}});
                }}
            """)

            if isinstance(filled, str):
                filled = json.loads(filled)

            if filled.get('error'):
                result['error'] = filled.get('error')
                return result

            result['success'] = True
            return result

        except Exception as e:
            result['error'] = str(e)
            return result

    async def click_tab_by_text(self, tab_text: str) -> bool:
        """Click a notebook tab by its visible text."""
        page = await self.browser.get_current_page()
        clicked = await page.evaluate(f"""
            () => {{
                const text = '{tab_text}'.toLowerCase().trim();
                const tabs = Array.from(document.querySelectorAll('.o_notebook .nav-tabs a, .o_notebook .nav-tabs button, .o_notebook .nav-tabs .nav-link, a, button'));
                const tab = tabs.find(el => (el.textContent || '').trim().toLowerCase() === text);
                if (tab) {{
                    tab.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                    tab.click();
                    return true;
                }}
                return false;
            }}
        """)
        return clicked

    async def fill_other_info_fields(self, other_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fill fields under the "Other Info" tab using labels.
        """
        page = await self.browser.get_current_page()
        result = {'success': False, 'filled': [], 'errors': []}

        try:
            # Switch to Other Info tab (retry until labels appear)
            tab_ready = False
            for _ in range(5):
                clicked = await self.click_tab_by_text("Other Info")
                if clicked:
                    await asyncio.sleep(0.6)
                tab_ready = await page.evaluate("""
                    () => {
                        const label = Array.from(document.querySelectorAll('label, .o_form_label'))
                            .find(el => (el.textContent || '').trim().toLowerCase().includes('customer reference'));
                        return !!label;
                    }
                """)
                if isinstance(tab_ready, str):
                    tab_ready = tab_ready.strip().lower() == 'true'
                if tab_ready:
                    break
                await asyncio.sleep(0.4)

            if not tab_ready:
                result['errors'].append("Other Info tab not ready")
                return result

            def field_type(label: str) -> str:
                dropdown_fields = {
                    "Salesperson", "Recipient Bank", "Incoterm",
                    "Fiscal Position", "Payment Method", "Auto-post"
                }
                if label == "Reviewed":
                    return "checkbox"
                if label in dropdown_fields:
                    return "dropdown"
                if label == "Delivery Date":
                    return "date"
                return "text"

            for label, value in (other_info or {}).items():
                ftype = field_type(label)
                import json
                import re
                label_literal = json.dumps(label)
                value_literal = json.dumps(value if value is not None else "")
                value_str = "" if value is None else str(value)
                key = re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_') or "field"
                key_literal = json.dumps(key)

                if ftype == "checkbox":
                    toggled = await page.evaluate(f"""
                        () => {{
                            const labelText = {label_literal}.toLowerCase();
                            const labels = Array.from(document.querySelectorAll('label, .o_form_label, .o_form_label label, .o_form_label .o_label, .o_td_label'));
                            const match = labels.find(el => (el.textContent || '').trim().toLowerCase().includes(labelText));
                            if (!match) return {{error: 'Label not found'}};

                            const labelCell = match.closest('.o_cell') || match.parentElement;
                            let fieldCell = null;
                            if (labelCell && labelCell.nextElementSibling) {{
                                fieldCell = labelCell.nextElementSibling;
                            }} else if (labelCell) {{
                                const group = labelCell.closest('.o_inner_group');
                                if (group) {{
                                    const cells = Array.from(group.querySelectorAll('.o_cell'));
                                    const idx = cells.indexOf(labelCell);
                                    if (idx > -1 && idx + 1 < cells.length) fieldCell = cells[idx + 1];
                                }}
                            }}

                            const checkbox = (fieldCell || labelCell || match.parentElement)?.querySelector('input[type="checkbox"]');
                            if (!checkbox) return {{error: 'Checkbox not found'}};

                            const desired = {str(bool(value)).lower()};
                            if (checkbox.checked !== desired) {{
                                checkbox.click();
                            }}
                            return {{success: true}};
                        }}
                    """)
                    if isinstance(toggled, str):
                        toggled = json.loads(toggled)
                    if toggled.get('error'):
                        result['errors'].append(f"{label}: {toggled.get('error')}")
                    else:
                        result['filled'].append(label)
                    continue

                # text/date/dropdown: locate input and set value
                set_result = await page.evaluate(f"""
                    () => {{
                        const labelText = {label_literal}.toLowerCase();
                        const labels = Array.from(document.querySelectorAll('label, .o_form_label, .o_form_label label, .o_form_label .o_label, .o_td_label'));
                        const match = labels.find(el => (el.textContent || '').trim().toLowerCase().includes(labelText));
                        if (!match) return {{error: 'Label not found'}};

                        const labelCell = match.closest('.o_cell') || match.parentElement;
                        let fieldCell = null;
                        if (labelCell && labelCell.nextElementSibling) {{
                            fieldCell = labelCell.nextElementSibling;
                        }} else if (labelCell) {{
                            const group = labelCell.closest('.o_inner_group');
                            if (group) {{
                                const cells = Array.from(group.querySelectorAll('.o_cell'));
                                const idx = cells.indexOf(labelCell);
                                if (idx > -1 && idx + 1 < cells.length) fieldCell = cells[idx + 1];
                            }}
                        }}

                        const fieldWidget = (fieldCell || labelCell || match.parentElement)?.querySelector('.o_field_widget');
                        let input = null;
                        if (fieldWidget) {{
                            input = fieldWidget.querySelector('input, textarea, select, [contenteditable="true"]');
                        }}
                        if (!input) {{
                            input = (fieldCell || labelCell || match.parentElement)?.querySelector('input, textarea, select, [contenteditable="true"]');
                        }}
                        if (!input) return {{error: 'Input not found'}};
                        if (input.disabled || input.readOnly) return {{error: 'Input is readonly'}};

                        input.setAttribute('data-codex-oi', {key_literal});
                        input.focus();
                        if (input.isContentEditable) {{
                            input.textContent = '';
                        }} else {{
                            input.value = '';
                        }}
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        return {{
                            success: true,
                            inputTag: input.tagName,
                            isSelect: input.tagName.toLowerCase() === 'select',
                            isContentEditable: !!input.isContentEditable,
                            key: {key_literal}
                        }};
                    }}
                """)

                if isinstance(set_result, str):
                    set_result = json.loads(set_result)

                if set_result.get('error'):
                    result['errors'].append(f"{label}: {set_result.get('error')}")
                    continue

                # Human-like typing for text/date/dropdown inputs
                if not set_result.get('isSelect'):
                    import random
                    chars_per_second = random.uniform(10, 12)
                    delay_per_char = 1.0 / chars_per_second

                    for char in value_str:
                        char_literal = json.dumps(char)
                        await page.evaluate(f"""
                            () => {{
                                const input = document.querySelector('[data-codex-oi="{key}"]');
                                if (!input) return false;
                                if (input.isContentEditable) {{
                                    input.textContent += {char_literal};
                                }} else {{
                                    input.value += {char_literal};
                                }}
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                return true;
                            }}
                        """)
                        await asyncio.sleep(delay_per_char)

                    await page.evaluate(f"""
                        () => {{
                            const input = document.querySelector('[data-codex-oi="{key}"]');
                            if (!input) return false;
                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                            return true;
                        }}
                    """)

                if ftype == "dropdown":
                    # Special handling for Auto-post select dropdown
                    if label == "Auto-post":
                        auto_value = value_str
                        auto_literal = json.dumps(auto_value)
                        auto_selected = await page.evaluate(f"""
                            () => {{
                                const key = {key_literal};
                                const input = document.querySelector(`[data-codex-oi="${{key}}"]`);
                                const wrapper = input ? (input.closest('.o_field_widget') || input.parentElement) : null;
                                const select = (input && input.tagName && input.tagName.toLowerCase() === 'select')
                                    ? input
                                    : (wrapper ? wrapper.querySelector('select') : null);

                                if (select) {{
                                    const opt = Array.from(select.options).find(o =>
                                        (o.textContent || '').trim().toLowerCase() === {auto_literal}.toLowerCase()
                                        || (o.textContent || '').trim().toLowerCase().includes({auto_literal}.toLowerCase())
                                    );
                                    if (opt) {{
                                        select.value = opt.value;
                                        select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        return {{ success: true, selected: opt.textContent.trim() }};
                                    }}
                                }}

                                // Fallback: open dropdown menu and click option
                                if (input) {{
                                    input.click();
                                }}
                                const dropdown = document.querySelector('.dropdown-menu.show, .o-autocomplete--dropdown-menu, [role="listbox"]');
                                if (dropdown) {{
                                    const items = Array.from(dropdown.querySelectorAll('a, button, li, .dropdown-item'));
                                    const match = items.find(el =>
                                        (el.textContent || '').trim().toLowerCase() === {auto_literal}.toLowerCase()
                                        || (el.textContent || '').trim().toLowerCase().includes({auto_literal}.toLowerCase())
                                    );
                                    if (match) {{
                                        match.click();
                                        return {{ success: true, selected: match.textContent.trim() }};
                                    }}
                                }}

                                return {{ error: 'Auto-post option not found' }};
                            }}
                        """)
                        if isinstance(auto_selected, str):
                            auto_selected = json.loads(auto_selected)
                        if auto_selected.get('error'):
                            result['errors'].append(f"{label}: {auto_selected.get('error')}")
                        else:
                            result['filled'].append(label)
                        continue

                    # Special handling for Recipient Bank many2one dropdown
                    if label == "Recipient Bank":
                        bank_literal = json.dumps(value_str)
                        bank_selected = await page.evaluate(f"""
                            () => {{
                                const key = {key_literal};
                                const input = document.querySelector(`[data-codex-oi="${{key}}"]`);
                                if (!input) return {{ error: 'Recipient Bank input not found' }};

                                if (input.tagName && input.tagName.toLowerCase() === 'select') {{
                                    const opt = Array.from(input.options).find(o =>
                                        (o.textContent || '').trim().toLowerCase().includes({bank_literal}.toLowerCase())
                                    );
                                    if (opt) {{
                                        input.value = opt.value;
                                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        return {{ success: true, selected: opt.textContent.trim() }};
                                    }}
                                    return {{ error: 'Recipient Bank option not found' }};
                                }}

                                input.focus();
                                input.click();

                                const dropdown = document.querySelector('.o-autocomplete--dropdown-menu, [role="listbox"]');
                                if (!dropdown) return {{ error: 'Dropdown not found' }};

                                const options = Array.from(dropdown.querySelectorAll('a[role="option"], .dropdown-item, li')).filter(el => {{
                                    const text = (el.textContent || '').trim();
                                    if (!text) return false;
                                    const lower = text.toLowerCase();
                                    if (lower.includes('create and edit') || lower.includes('create')) return false;
                                    if (lower.includes('search more') || lower.includes('search worldwide')) return false;
                                    return true;
                                }});

                                const target = {bank_literal}.toLowerCase().trim();
                                const match = options.find(el => (el.textContent || '').trim().toLowerCase().includes(target));
                                if (match) {{
                                    match.click();
                                    return {{ success: true, selected: match.textContent.trim() }};
                                }}

                                const searchMore = Array.from(dropdown.querySelectorAll('a[role="option"], .dropdown-item, li'))
                                    .find(el => (el.textContent || '').trim().toLowerCase().includes('search more'));
                                if (searchMore) {{
                                    searchMore.click();
                                    return {{ search_more: true }};
                                }}

                                return {{ error: 'Recipient Bank option not found' }};
                            }}
                        """)
                        if isinstance(bank_selected, str):
                            bank_selected = json.loads(bank_selected)

                        if bank_selected.get('search_more'):
                            await asyncio.sleep(0.6)
                            modal_ready = False
                            for _ in range(8):
                                modal_ready = await page.evaluate("""
                                    () => {
                                        const dialog = document.querySelector('.o_dialog');
                                        if (!dialog) return false;
                                        return true;
                                    }
                                """)
                                if isinstance(modal_ready, str):
                                    modal_ready = modal_ready.strip().lower() == 'true'
                                if modal_ready:
                                    break
                                await asyncio.sleep(0.4)

                            if not modal_ready:
                                result['errors'].append(f"{label}: Search more modal not found")
                            else:
                                # Filter in modal search box if present
                                await page.evaluate(f"""
                                    () => {{
                                        const modal = document.querySelector('.o_dialog');
                                        if (!modal) return false;
                                        const input = modal.querySelector('input.o_searchview_input, input[placeholder*="Search"]');
                                        if (input) {{
                                            input.focus();
                                            input.value = {bank_literal};
                                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                            input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', bubbles: true }}));
                                            const searchBtn = modal.querySelector('button.o_searchview_button, button[aria-label*="Search"]');
                                            if (searchBtn) searchBtn.click();
                                            return true;
                                        }}
                                        return false;
                                    }}
                                """)
                                await asyncio.sleep(0.5)

                                modal_selected = await page.evaluate(f"""
                                    () => {{
                                        const modal = document.querySelector('.o_dialog');
                                        if (!modal) return {{error: 'Modal not found'}};
                                        const rows = modal.querySelectorAll('tr.o_data_row, tbody tr');
                                        const match = Array.from(rows).find(row => {{
                                            const text = (row.textContent || '').toLowerCase();
                                            return text.includes({bank_literal}.toLowerCase());
                                        }});
                                        if (!match) return {{error: 'Recipient Bank not found in modal'}};

                                        const checkbox = match.querySelector('input[type="checkbox"]');
                                        if (checkbox && !checkbox.checked) {{
                                            checkbox.click();
                                        }} else {{
                                            match.click();
                                        }}
                                        return {{success: true}};
                                    }}
                                """)
                                if isinstance(modal_selected, str):
                                    modal_selected = json.loads(modal_selected)

                                if modal_selected.get('error'):
                                    result['errors'].append(f"{label}: {modal_selected.get('error')}")
                                else:
                                    select_clicked = await page.evaluate("""
                                        () => {
                                            const modal = document.querySelector('.o_dialog');
                                            if (!modal) return false;
                                            const buttons = modal.querySelectorAll('button');
                                            const selectBtn = Array.from(buttons).find(btn =>
                                                (btn.textContent || '').trim().toLowerCase() === 'select'
                                            );
                                            if (selectBtn) {
                                                selectBtn.click();
                                                return true;
                                            }
                                            return false;
                                        }
                                    """)
                                    if not select_clicked:
                                        result['errors'].append(f"{label}: Select button not found in modal")
                                    else:
                                        result['filled'].append(label)
                            continue

                        if bank_selected.get('error'):
                            result['errors'].append(f"{label}: {bank_selected.get('error')}")
                        else:
                            result['filled'].append(label)
                        continue

                    # Special handling for Incoterm dropdown match like "[EXW]"
                    if label == "Incoterm":
                        search_term = value_str or ""
                        if search_term and not search_term.startswith("["):
                            search_term = f"[{search_term}]"
                        search_literal = json.dumps(search_term)
                        incoterm_selected = await page.evaluate(f"""
                            () => {{
                                const key = {key_literal};
                                const input = document.querySelector(`[data-codex-oi="${{key}}"]`);
                                if (input) {{
                                    input.focus();
                                    input.click();
                                }}
                                const dropdown = document.querySelector('.o-autocomplete--dropdown-menu, [role="listbox"]');
                                if (!dropdown) return {{error: 'Dropdown not found'}};
                                const options = Array.from(dropdown.querySelectorAll('a[role="option"], .dropdown-item, li'));
                                const match = options.find(opt => (opt.textContent || '').includes({search_literal}));
                                if (match) {{
                                    match.click();
                                    return {{success: true, selected: match.textContent.trim()}};
                                }}
                                return {{error: 'Incoterm option not found'}};
                            }}
                        """)
                        if isinstance(incoterm_selected, str):
                            incoterm_selected = json.loads(incoterm_selected)
                        if incoterm_selected.get('error'):
                            result['errors'].append(f"{label}: {incoterm_selected.get('error')}")
                        else:
                            result['filled'].append(label)
                        continue

                    if set_result.get('isSelect'):
                        result['filled'].append(label)
                    else:
                        # Ensure dropdown opens (more robust: try wrapper, then click input)
                        await page.evaluate(f"""
                            () => {{
                                const input = document.querySelector('[data-codex-oi="{key}"]');
                                if (!input) return false;
                                const wrapper = input.closest('.o_field_widget') || input.parentElement;
                                const dropdownBtn = wrapper ? wrapper.querySelector('.o_dropdown_button') : null;
                                if (dropdownBtn) {{
                                    dropdownBtn.click();
                                    return true;
                                }}
                                input.click();
                                return true;
                            }}
                        """)
                        await asyncio.sleep(0.5)
                        # select first matching option (prefer non-create)
                        selected = await page.evaluate("""
                            () => {
                                const dropdown = document.querySelector('.o-autocomplete--dropdown-menu, [role="listbox"]');
                                if (!dropdown) return {error: 'Dropdown not found'};
                                const items = Array.from(dropdown.querySelectorAll('a[role="option"], .dropdown-item, li'));
                                const optionItems = items.filter(el => {
                                    const text = (el.textContent || '').trim();
                                    if (!text) return false;
                                    const lower = text.toLowerCase();
                                    if (lower.includes('search worldwide')) return false;
                                    return true;
                                });
                                if (optionItems.length === 0) return {error: 'No dropdown options'};

                                const nonCreate = optionItems.filter(el => {
                                    const t = (el.textContent || '').trim().toLowerCase();
                                    return !t.includes('create') && !t.includes('search more');
                                });

                                const searchMore = optionItems.find(el => (el.textContent || '').trim().toLowerCase().includes('search more'));

                                if (nonCreate.length > 0) {
                                    nonCreate[0].click();
                                    return {success: true, selected: nonCreate[0].textContent.trim()};
                                }

                                if (searchMore) {
                                    searchMore.click();
                                    return {search_more: true};
                                }

                                // fallback: click first option (may be Create)
                                optionItems[0].click();
                                return {success: true, selected: optionItems[0].textContent.trim()};
                            }
                        """)
                        if isinstance(selected, str):
                            selected = json.loads(selected)

                        # Search more modal handling (Recipient Bank, etc.)
                        if selected and selected.get('search_more'):
                            await asyncio.sleep(0.6)
                            modal_ready = False
                            for _ in range(8):
                                modal_ready = await page.evaluate("""
                                    () => {
                                        const dialog = document.querySelector('.o_dialog');
                                        if (!dialog) return false;
                                        return true;
                                    }
                                """)
                                if isinstance(modal_ready, str):
                                    modal_ready = modal_ready.strip().lower() == 'true'
                                if modal_ready:
                                    break
                                await asyncio.sleep(0.4)

                            if not modal_ready:
                                result['errors'].append(f"{label}: Search more modal not found")
                            else:
                                # Select first row and click Select
                                await page.evaluate("""
                                    () => {
                                        const modal = document.querySelector('.o_dialog');
                                        if (!modal) return false;
                                        const rows = modal.querySelectorAll('tr.o_data_row, tbody tr');
                                        if (rows.length === 0) return false;
                                        const first = rows[0];
                                        const checkbox = first.querySelector('input[type="checkbox"]');
                                        if (checkbox && !checkbox.checked) {
                                            checkbox.click();
                                        } else {
                                            first.click();
                                        }
                                        return true;
                                    }
                                """)
                                await asyncio.sleep(0.3)
                                await page.evaluate("""
                                    () => {
                                        const modal = document.querySelector('.o_dialog');
                                        if (!modal) return false;
                                        const buttons = modal.querySelectorAll('button');
                                        const selectBtn = Array.from(buttons).find(btn =>
                                            (btn.textContent || '').trim().toLowerCase() === 'select'
                                        );
                                        if (selectBtn) {
                                            selectBtn.click();
                                            return true;
                                        }
                                        return false;
                                    }
                                """)
                                result['filled'].append(label)
                            continue

                        # Special handling for Incoterm create flow
                        if label == "Incoterm" and selected and selected.get('selected') and "create" in selected.get('selected', '').lower():
                            await asyncio.sleep(0.6)
                            # Fill Code field and Save
                            await page.evaluate("""
                                () => {
                                    const modal = document.querySelector('.o_dialog');
                                    if (!modal) return false;
                                    const codeInput = modal.querySelector('input[name="code"], input[placeholder*="Code"], input');
                                    if (!codeInput) return false;
                                    codeInput.focus();
                                    codeInput.value = 'EX';
                                    codeInput.dispatchEvent(new Event('input', { bubbles: true }));
                                    codeInput.dispatchEvent(new Event('change', { bubbles: true }));
                                    return true;
                                }
                            """)
                            await asyncio.sleep(0.3)
                            await page.evaluate("""
                                () => {
                                    const modal = document.querySelector('.o_dialog');
                                    if (!modal) return false;
                                    const saveBtn = Array.from(modal.querySelectorAll('button')).find(btn =>
                                        (btn.textContent || '').trim().toLowerCase() === 'save'
                                    );
                                    if (saveBtn) {
                                        saveBtn.click();
                                        return true;
                                    }
                                    return false;
                                }
                            """)
                            await asyncio.sleep(0.6)
                            result['filled'].append(label)
                        elif selected.get('error'):
                            if label == "Auto-post" and selected.get('error') == 'No dropdown options':
                                result['filled'].append(label)
                            else:
                                result['errors'].append(f"{label}: {selected.get('error')}")
                        else:
                            result['filled'].append(label)
                else:
                    result['filled'].append(label)

            # Switch back to Invoice Lines tab
            await self.click_tab_by_text("Invoice Lines")
            await asyncio.sleep(0.3)

            result['success'] = len(result['errors']) == 0
            return result

        except Exception as e:
            result['errors'].append(f"Exception: {str(e)}")
            return result

    async def fill_line_item(
        self,
        line_number: int,
        item_data: Dict[str, Any],
        skip_product: bool = False,
        resume_from: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fill a single invoice line item.

        Args:
            line_number: The row number (0-based index)
            item_data: Dictionary with keys: 'label', 'price', 'taxes'
                Example: {"label": "Product A", "price": 100, "taxes": "20%"}

        Returns:
            Dict with success status and filled fields
        """
        page = await self.browser.get_current_page()
        result = {
            'success': False,
            'fields_filled': {},
            'errors': []
        }
        substep_order = ["product", "price", "quantity", "discount", "taxes"]
        last_completed = (resume_from or {}).get("last_completed_substep")

        def should_skip(step: str) -> bool:
            if not last_completed:
                return False
            if last_completed not in substep_order:
                return False
            return substep_order.index(step) <= substep_order.index(last_completed)

        try:
            self._set_checkpoint(
                stage="fill_form",
                field="line_items",
                line_index=line_number,
                substep="row_check",
                last_completed_substep=last_completed
            )
            # Ensure the target row exists before interacting
            row_exists = False
            for _ in range(5):
                row_exists = await page.evaluate(f"""
                    () => {{
                        const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                            .filter(r => {{
                                const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                return !isNote && !isSection;
                            }});
                        return rows.length > {line_number};
                    }}
                """)
                if isinstance(row_exists, str):
                    row_exists = row_exists.strip().lower() == 'true'
                if row_exists:
                    break
                await asyncio.sleep(0.3)

            if not row_exists:
                # Try adding a line if the row isn't present yet
                add_clicked = await self.click_button_by_text("Add a line")
                if add_clicked:
                    await asyncio.sleep(0.8)
                    for _ in range(5):
                        row_exists = await page.evaluate(f"""
                            () => {{
                        const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                            .filter(r => {{
                                const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                return !isNote && !isSection;
                            }});
                        return rows.length > {line_number};
                    }}
                """)
                        if isinstance(row_exists, str):
                            row_exists = row_exists.strip().lower() == 'true'
                        if row_exists:
                            break
                        await asyncio.sleep(0.3)

                if not row_exists:
                    result['errors'].append(f"Row {line_number} not available")
                    return result

            # Step 1: Fill Product/Label via product dropdown
            if not skip_product and ('label' in item_data or 'product' in item_data):
                if should_skip("product"):
                    last_completed = "product"
                else:
                    self._set_checkpoint(
                        stage="fill_form",
                        field="line_items",
                        line_index=line_number,
                        substep="product",
                        last_completed_substep=last_completed
                    )
                    product_value = item_data.get('product')
                    if product_value is None:
                        product_value = item_data.get('label')

                    if product_value is None or product_value == "":
                        result['errors'].append(f"Row {line_number} product/label value missing")
                    else:
                        product_result = await self.select_product_for_line(line_number, product_value)
                        if product_result.get('success'):
                            result['fields_filled']['product'] = product_result.get('selected', product_value)
                            last_completed = "product"
                            self._set_checkpoint(
                                stage="fill_form",
                                field="line_items",
                                line_index=line_number,
                                substep="after_product",
                                last_completed_substep=last_completed
                            )
                            await self.wait_for_page_ready()
                        else:
                            errors = product_result.get('errors') or ['Failed to select product']
                            result['errors'].append(f"Row {line_number} product select failed: {', '.join(errors)}")

            # Step 2: Fill Price field
            if 'price' in item_data:
                if should_skip("price"):
                    last_completed = "price"
                else:
                    self._set_checkpoint(
                        stage="fill_form",
                        field="line_items",
                        line_index=line_number,
                        substep="price",
                        last_completed_substep=last_completed
                    )
                    price_value = str(item_data['price'])

                    # Click on the price cell to activate editing
                    clicked = await page.evaluate(f"""
                        () => {{
                            const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                .filter(r => {{
                                    const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                    const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                    return !isNote && !isSection;
                                }});
                            if (rows.length <= {line_number}) return false;

                            const targetRow = rows[{line_number}];
                            if (!targetRow) return false;
                            const priceCell = targetRow.querySelector('[name="price_unit"]');
                            if (!priceCell) return false;

                            priceCell.click();
                            return true;
                        }}
                    """)

                    if not clicked:
                        result['errors'].append(f"Row {line_number} price cell not found")
                    else:
                        # Wait for input to appear
                        await asyncio.sleep(0.5)

                        # Type into the input - HUMAN-LIKE TYPING
                        import random
                        chars_per_second = random.uniform(10, 12)
                        delay_per_char = 1.0 / chars_per_second

                        # Focus and clear the input
                        focus_result = await page.evaluate(f"""
                            () => {{
                            const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                .filter(r => {{
                                    const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                    const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                    return !isNote && !isSection;
                                }});
                            const targetRow = rows[{line_number}];
                                if (!targetRow) return JSON.stringify({{error: 'Row not found'}});
                                const priceCell = targetRow.querySelector('[name="price_unit"]');
                                if (!priceCell) return JSON.stringify({{error: 'Price cell not found'}});

                                const input = priceCell.querySelector('input');
                                if (!input) return JSON.stringify({{error: 'Input not found'}});

                                input.focus();
                                input.value = '';
                                return JSON.stringify({{success: true}});
                            }}
                        """)

                        if isinstance(focus_result, str):
                            import json
                            focus_result = json.loads(focus_result)

                        if focus_result.get('error'):
                            result['errors'].append(f"Failed to find price input: {focus_result.get('error')}")
                        else:
                            # Type character by character in Python
                            for char in price_value:
                                await page.evaluate(f"""
                                    () => {{
                                        const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                            .filter(r => {{
                                                const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                                const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                                return !isNote && !isSection;
                                            }});
                                const targetRow = rows[{line_number}];
                                if (!targetRow) return JSON.stringify({{error: 'Row not found'}});
                                const priceCell = targetRow.querySelector('[name="price_unit"]');
                                if (!priceCell) return JSON.stringify({{error: 'Price cell not found'}});
                                        const input = priceCell.querySelector('input');
                                        if (input) {{
                                            input.value += '{char}';
                                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                        }}
                                    }}
                                """)
                                # Human typing delay
                                await asyncio.sleep(delay_per_char)

                            # Trigger change event
                            typed = await page.evaluate(f"""
                                () => {{
                                    const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                        .filter(r => {{
                                            const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                            const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                            return !isNote && !isSection;
                                        }});
                                    const targetRow = rows[{line_number}];
                                    if (!targetRow) return;
                                    const priceCell = targetRow.querySelector('[name="price_unit"]');
                                    if (!priceCell) return JSON.stringify({{error: 'Price cell not found'}});
                                    const input = priceCell.querySelector('input');
                                    if (input) {{
                                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                                        return JSON.stringify({{success: true, value: input.value}});
                                    }}
                                    return JSON.stringify({{error: 'Input lost'}});
                                }}
                            """)

                            if isinstance(typed, str):
                                import json
                                typed = json.loads(typed)

                            if typed.get('success'):
                                result['fields_filled']['price'] = typed['value']
                                last_completed = "price"
                                self._set_checkpoint(
                                    stage="fill_form",
                                    field="line_items",
                                    line_index=line_number,
                                    substep="after_price",
                                    last_completed_substep=last_completed
                                )
                            else:
                                result['errors'].append(f"Failed to type price: {typed.get('error')}")

                        # Wait for page to process the price change
                        await self.wait_for_page_ready()

            # Step 2.5: Fill Quantity field (optional)
            if 'quantity' in item_data:
                if should_skip("quantity"):
                    last_completed = "quantity"
                else:
                    self._set_checkpoint(
                        stage="fill_form",
                        field="line_items",
                        line_index=line_number,
                        substep="quantity",
                        last_completed_substep=last_completed
                    )
                    quantity_value = str(item_data['quantity'])

                    clicked = await page.evaluate(f"""
                        () => {{
                            const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                .filter(r => {{
                                    const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                    const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                    return !isNote && !isSection;
                                }});
                            if (rows.length <= {line_number}) return false;

                            const targetRow = rows[{line_number}];
                            if (!targetRow) return false;

                            const qtyCell = targetRow.querySelector('[name="quantity"]') ||
                                            targetRow.querySelector('[name*="quantity"]');
                            if (!qtyCell) return false;

                            qtyCell.click();
                            return true;
                        }}
                    """)

                    if not clicked:
                        result['errors'].append(f"Row {line_number} quantity cell not found")
                    else:
                        await asyncio.sleep(0.4)

                        focus_result = await page.evaluate(f"""
                            () => {{
                                const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                    .filter(r => {{
                                        const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                        const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                        return !isNote && !isSection;
                                    }});
                                const targetRow = rows[{line_number}];
                                if (!targetRow) return JSON.stringify({{error: 'Row not found'}});

                                const qtyCell = targetRow.querySelector('[name="quantity"]') ||
                                                targetRow.querySelector('[name*="quantity"]');
                                if (!qtyCell) return JSON.stringify({{error: 'Quantity cell not found'}});

                                const input = qtyCell.querySelector('input');
                                if (!input) return JSON.stringify({{error: 'Quantity input not found'}});

                                input.focus();
                                input.value = '';
                                return JSON.stringify({{success: true}});
                            }}
                        """)

                        if isinstance(focus_result, str):
                            import json
                            focus_result = json.loads(focus_result)

                        if focus_result.get('error'):
                            result['errors'].append(f"Failed to find quantity input: {focus_result.get('error')}")
                        else:
                            import random
                            chars_per_second = random.uniform(10, 12)
                            delay_per_char = 1.0 / chars_per_second

                            for char in quantity_value:
                                await page.evaluate(f"""
                                    () => {{
                                        const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                            .filter(r => {{
                                                const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                                const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                                return !isNote && !isSection;
                                            }});
                                        const targetRow = rows[{line_number}];
                                        if (!targetRow) return JSON.stringify({{error: 'Row not found'}});
                                        const qtyCell = targetRow.querySelector('[name="quantity"]') ||
                                                        targetRow.querySelector('[name*="quantity"]');
                                        const input = qtyCell ? qtyCell.querySelector('input') : null;
                                        if (input) {{
                                            input.value += '{char}';
                                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                        }}
                                    }}
                                """)
                                await asyncio.sleep(delay_per_char)

                            typed = await page.evaluate(f"""
                                () => {{
                                    const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                        .filter(r => {{
                                            const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                            const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                            return !isNote && !isSection;
                                        }});
                                    const targetRow = rows[{line_number}];
                                    if (!targetRow) return;
                                    const qtyCell = targetRow.querySelector('[name="quantity"]') ||
                                                    targetRow.querySelector('[name*="quantity"]');
                                    const input = qtyCell ? qtyCell.querySelector('input') : null;
                                    if (input) {{
                                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                                        return JSON.stringify({{success: true, value: input.value}});
                                    }}
                                    return JSON.stringify({{error: 'Quantity input lost'}});
                                }}
                            """)

                            if isinstance(typed, str):
                                import json
                                typed = json.loads(typed)

                            if typed.get('success'):
                                result['fields_filled']['quantity'] = typed['value']
                                last_completed = "quantity"
                                self._set_checkpoint(
                                    stage="fill_form",
                                    field="line_items",
                                    line_index=line_number,
                                    substep="after_quantity",
                                    last_completed_substep=last_completed
                                )
                            else:
                                result['errors'].append(f"Failed to type quantity: {typed.get('error')}")

                        await self.wait_for_page_ready()

            # Step 2.6: Fill Discount field (optional)
            if 'discount' in item_data:
                if should_skip("discount"):
                    last_completed = "discount"
                else:
                    self._set_checkpoint(
                        stage="fill_form",
                        field="line_items",
                        line_index=line_number,
                        substep="discount",
                        last_completed_substep=last_completed
                    )
                    discount_value = str(item_data['discount'])

                    clicked = await page.evaluate(f"""
                        () => {{
                            const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                .filter(r => {{
                                    const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                    const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                    return !isNote && !isSection;
                                }});
                            if (rows.length <= {line_number}) return false;

                            const targetRow = rows[{line_number}];
                            if (!targetRow) return false;

                            const discCell = targetRow.querySelector('[name="discount"]') ||
                                             targetRow.querySelector('[name*="discount"]');
                            if (!discCell) return false;

                            discCell.click();
                            return true;
                        }}
                    """)

                    if not clicked:
                        result['errors'].append(f"Row {line_number} discount cell not found")
                    else:
                        await asyncio.sleep(0.4)

                        focus_result = await page.evaluate(f"""
                            () => {{
                                const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                    .filter(r => {{
                                        const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                        const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                        return !isNote && !isSection;
                                    }});
                                const targetRow = rows[{line_number}];
                                if (!targetRow) return JSON.stringify({{error: 'Row not found'}});

                                const discCell = targetRow.querySelector('[name="discount"]') ||
                                                 targetRow.querySelector('[name*="discount"]');
                                if (!discCell) return JSON.stringify({{error: 'Discount cell not found'}});

                                const input = discCell.querySelector('input');
                                if (!input) return JSON.stringify({{error: 'Discount input not found'}});

                                input.focus();
                                input.value = '';
                                return JSON.stringify({{success: true}});
                            }}
                        """)

                        if isinstance(focus_result, str):
                            import json
                            focus_result = json.loads(focus_result)

                        if focus_result.get('error'):
                            result['errors'].append(f"Failed to find discount input: {focus_result.get('error')}")
                        else:
                            import random
                            chars_per_second = random.uniform(10, 12)
                            delay_per_char = 1.0 / chars_per_second

                            for char in discount_value:
                                await page.evaluate(f"""
                                    () => {{
                                        const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                            .filter(r => {{
                                                const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                                const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                                return !isNote && !isSection;
                                            }});
                                        const targetRow = rows[{line_number}];
                                        if (!targetRow) return JSON.stringify({{error: 'Row not found'}});
                                        const discCell = targetRow.querySelector('[name="discount"]') ||
                                                         targetRow.querySelector('[name*="discount"]');
                                        const input = discCell ? discCell.querySelector('input') : null;
                                        if (input) {{
                                            input.value += '{char}';
                                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                        }}
                                    }}
                                """)
                                await asyncio.sleep(delay_per_char)

                            typed = await page.evaluate(f"""
                                () => {{
                                    const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                        .filter(r => {{
                                            const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                            const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                            return !isNote && !isSection;
                                        }});
                                    const targetRow = rows[{line_number}];
                                    if (!targetRow) return;
                                    const discCell = targetRow.querySelector('[name="discount"]') ||
                                                     targetRow.querySelector('[name*="discount"]');
                                    const input = discCell ? discCell.querySelector('input') : null;
                                    if (input) {{
                                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                                        return JSON.stringify({{success: true, value: input.value}});
                                    }}
                                    return JSON.stringify({{error: 'Discount input lost'}});
                                }}
                            """)

                            if isinstance(typed, str):
                                import json
                                typed = json.loads(typed)

                            if typed.get('success'):
                                result['fields_filled']['discount'] = typed['value']
                                last_completed = "discount"
                                self._set_checkpoint(
                                    stage="fill_form",
                                    field="line_items",
                                    line_index=line_number,
                                    substep="after_discount",
                                    last_completed_substep=last_completed
                                )
                            else:
                                result['errors'].append(f"Failed to type discount: {typed.get('error')}")

                        await self.wait_for_page_ready()

            # Step 3: Fill Taxes field
            if 'taxes' in item_data:
                if should_skip("taxes"):
                    last_completed = "taxes"
                else:
                    self._set_checkpoint(
                        stage="fill_form",
                        field="line_items",
                        line_index=line_number,
                        substep="taxes",
                        last_completed_substep=last_completed
                    )
                    taxes_list = item_data['taxes']
                    if not isinstance(taxes_list, list):
                        taxes_list = [taxes_list]

                    # Click on the taxes cell
                    clicked = await page.evaluate(f"""
                        () => {{
                            const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                .filter(r => {{
                                    const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                    const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                    return !isNote && !isSection;
                                }});
                            if (rows.length <= {line_number}) return false;

                            const targetRow = rows[{line_number}];
                            if (!targetRow) return false;
                            const taxesCell = targetRow.querySelector('[name="tax_ids"]');
                            if (!taxesCell) return false;

                            taxesCell.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                            taxesCell.click();
                            return true;
                        }}
                    """)

                    if not clicked:
                        result['errors'].append(f"Row {line_number} taxes cell not found")
                    else:
                        await asyncio.sleep(0.6)

                        # Select taxes from dropdown when available; fallback to Search more for missing ones
                        taxes_selected = []
                        taxes_missing = []

                        if not self.force_search_more_taxes:
                            for tax_name in taxes_list:
                                import json
                                tax_literal = json.dumps(tax_name)

                                selected = None
                                for _ in range(5):
                                    # Open dropdown and type to filter
                                    await page.evaluate(f"""
                                        () => {{
                                            const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                                .filter(r => {{
                                                    const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                                    const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                                    return !isNote && !isSection;
                                                }});
                                            if (rows.length <= {line_number}) return false;
                                            const targetRow = rows[{line_number}];
                                            if (!targetRow) return false;
                                            const taxesCell = targetRow.querySelector('[name="tax_ids"]');
                                            if (!taxesCell) return false;

                                            const input = taxesCell.querySelector('input.o-autocomplete--input');
                                            const dropdownBtn = taxesCell.querySelector('.o_dropdown_button');
                                            if (input) {{
                                                input.focus();
                                                input.value = '';
                                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                                input.value = {tax_literal};
                                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                            }}
                                            if (dropdownBtn) dropdownBtn.click();
                                            return true;
                                        }}
                                    """)

                                    await asyncio.sleep(0.5)

                                    selected = await page.evaluate(f"""
                                        () => {{
                                            const target = {tax_literal}.toLowerCase().trim();
                                            const dropdown = document.querySelector('.o-autocomplete--dropdown-menu, [role="listbox"]');
                                            if (!dropdown) return {{error: 'Dropdown not found'}};

                                            const options = Array.from(dropdown.querySelectorAll('a[role="option"], .dropdown-item, li')).filter(el => {{
                                                const text = (el.textContent || '').trim();
                                                if (!text) return false;
                                                const lower = text.toLowerCase();
                                                if (lower.includes('search more')) return false;
                                                return true;
                                            }});

                                            if (options.length > 0 && options.every(el => (el.textContent || '').trim().toLowerCase().includes('loading'))) {{
                                                return {{error: 'Dropdown loading'}};
                                            }}

                                            const match = options.find(el => (el.textContent || '').trim().toLowerCase().includes(target));
                                            if (!match) return {{error: 'Tax not found in dropdown'}};

                                            match.click();
                                            return {{success: true, tax: {tax_literal}}};
                                        }}
                                    """)

                                    if isinstance(selected, str):
                                        selected = json.loads(selected)

                                    if selected.get('success'):
                                        break

                                    # Retry if dropdown didn't render or is still loading
                                    if selected.get('error') in ('Dropdown not found', 'Dropdown loading'):
                                        await asyncio.sleep(0.4)
                                        continue

                                    break

                                if selected and selected.get('success'):
                                    taxes_selected.append(selected['tax'])
                                else:
                                    taxes_missing.append(tax_name)

                                await asyncio.sleep(0.3)
                        else:
                            taxes_missing = list(taxes_list)

                        if taxes_missing:
                            # Re-open dropdown (unfiltered) to access Search more...
                            await page.evaluate(f"""
                                () => {{
                                    const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                        .filter(r => {{
                                            const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                            const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                            return !isNote && !isSection;
                                        }});
                                    if (rows.length <= {line_number}) return false;
                                    const targetRow = rows[{line_number}];
                                    if (!targetRow) return false;
                                    const taxesCell = targetRow.querySelector('[name="tax_ids"]');
                                    if (!taxesCell) return false;
                                    const dropdownBtn = taxesCell.querySelector('.o_dropdown_button');
                                    const input = taxesCell.querySelector('input.o-autocomplete--input');
                                    if (input) {{
                                        input.focus();
                                        input.value = '';
                                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    }}
                                    if (dropdownBtn) dropdownBtn.click();
                                    return true;
                                }}
                            """)

                            await asyncio.sleep(0.5)

                            search_more_clicked = False
                            for _ in range(10):
                                search_more_state = await page.evaluate("""
                                    () => {
                                        const dropdown = document.querySelector('.o-autocomplete--dropdown-menu, [role="listbox"]');
                                        if (!dropdown) return 'no_dropdown';

                                        const items = Array.from(dropdown.querySelectorAll('a, li, .dropdown-item'));
                                        if (items.length === 0) return 'no_items';

                                        const searchMore = items.find(el => {
                                            const text = (el.textContent || '').trim().toLowerCase();
                                            return text.includes('search more');
                                        });

                                        if (searchMore) {
                                            searchMore.click();
                                            return 'clicked';
                                        }

                                        const texts = items.map(el => (el.textContent || '').trim().toLowerCase()).filter(Boolean);
                                        if (texts.length > 0 && texts.every(t => t.includes('loading'))) {
                                            return 'loading';
                                        }

                                        return 'not_found';
                                    }
                                """)

                                if isinstance(search_more_state, str):
                                    search_more_state = search_more_state.strip().lower()

                                if search_more_state == 'clicked':
                                    search_more_clicked = True
                                    break

                                # Retry if dropdown not ready or still loading
                                await asyncio.sleep(0.4)

                                # Re-open dropdown if needed
                                await page.evaluate(f"""
                                    () => {{
                                        const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                            .filter(r => {{
                                                const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                                const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                                return !isNote && !isSection;
                                            }});
                                        if (rows.length <= {line_number}) return false;
                                        const targetRow = rows[{line_number}];
                                        if (!targetRow) return false;
                                        const taxesCell = targetRow.querySelector('[name="tax_ids"]');
                                        if (!taxesCell) return false;
                                        const dropdownBtn = taxesCell.querySelector('.o_dropdown_button');
                                        if (dropdownBtn) dropdownBtn.click();
                                        return true;
                                    }}
                                """)

                            if not search_more_clicked:
                                result['errors'].append("'Search more...' button not found")
                            else:
                                # Wait for modal dialog to appear
                                modal_ready = False
                                for _ in range(8):
                                    modal_ready = await page.evaluate("""
                                        () => {
                                            const dialog = document.querySelector('.o_dialog');
                                            if (!dialog) return false;
                                            const title = dialog.querySelector('.modal-title')?.textContent?.trim() || '';
                                            return title.toLowerCase().includes('tax');
                                        }
                                    """)
                                    if isinstance(modal_ready, str):
                                        modal_ready = modal_ready.strip().lower() == 'true'
                                    if modal_ready:
                                        break
                                    await asyncio.sleep(0.5)

                                if not modal_ready:
                                    result['errors'].append("Tax selection modal did not appear")
                                else:
                                    await asyncio.sleep(0.5)

                                    # Select missing taxes from modal
                                    for tax_name in taxes_missing:
                                        selected = await page.evaluate(f"""
                                            () => {{
                                                const modal = document.querySelector('.o_dialog');
                                                if (!modal) return {{error: 'Modal not found'}};

                                                const rows = modal.querySelectorAll('tr.o_data_row, tbody tr');
                                                const matchingRow = Array.from(rows).find(row => {{
                                                    const text = row.textContent || '';
                                                    return text.includes('{tax_name}');
                                                }});

                                                if (!matchingRow) return {{error: 'Tax not found: {tax_name}'}};

                                                const checkbox = matchingRow.querySelector('input[type=\"checkbox\"]');
                                                if (!checkbox) return {{error: 'Checkbox not found'}};

                                                if (!checkbox.checked) {{
                                                    checkbox.click();
                                                }}

                                                return {{success: true, tax: '{tax_name}'}};
                                            }}
                                        """)

                                        if isinstance(selected, str):
                                            selected = json.loads(selected)

                                        if selected.get('success'):
                                            taxes_selected.append(selected['tax'])
                                        else:
                                            result['errors'].append(f"Failed to select tax '{tax_name}': {selected.get('error')}")

                                        await asyncio.sleep(0.3)

                                    # Click Select button
                                    select_clicked = await page.evaluate("""
                                        () => {
                                            const modal = document.querySelector('.o_dialog');
                                            if (!modal) return false;

                                            const buttons = modal.querySelectorAll('button');
                                            const selectBtn = Array.from(buttons).find(btn =>
                                                btn.textContent.trim() === 'Select'
                                            );

                                            if (selectBtn) {
                                                selectBtn.click();
                                                return true;
                                            }
                                            return false;
                                        }
                                    """)
                                    if isinstance(select_clicked, str):
                                        select_clicked = select_clicked.strip().lower() == 'true'

                                    if not select_clicked:
                                        result['errors'].append("'Select' button not found in modal")

                        if taxes_selected:
                            result['fields_filled']['taxes'] = ', '.join(taxes_selected)
                            last_completed = "taxes"
                            self._set_checkpoint(
                                stage="fill_form",
                                field="line_items",
                                line_index=line_number,
                                substep="after_taxes",
                                last_completed_substep=last_completed
                            )

            result['success'] = len(result['errors']) == 0
            return result

        except Exception as e:
            result['errors'].append(f"Exception: {str(e)}")
            return result

    async def click_new_button(self) -> bool:
        """
        Click the 'New' button in Odoo to save current invoice as draft and start a new one.
        """
        page = await self.browser.get_current_page()
        import random
        await asyncio.sleep(random.uniform(0.3, 0.6))

        clicked = await page.evaluate("""
            () => {
                const isVisible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    if (!style) return false;
                    if (style.display === 'none' || style.visibility === 'hidden') return false;
                    if (el.offsetParent === null && style.position !== 'fixed') return false;
                    return true;
                };

                const candidates = Array.from(document.querySelectorAll('button, a[role="button"], a.btn'));

                const byHotkey = candidates.find(btn =>
                    isVisible(btn) && (
                        (btn.getAttribute('data-hotkey') || '').toLowerCase() === 'c' ||
                        (btn.getAttribute('accesskey') || '').toLowerCase() === 'c'
                    )
                );
                if (byHotkey) {
                    byHotkey.click();
                    return true;
                }

                const byText = candidates.find(btn => {
                    if (!isVisible(btn)) return false;
                    const text = (btn.textContent || '').trim().toLowerCase();
                    return text === 'new';
                });
                if (byText) {
                    byText.click();
                    return true;
                }

                const byIcon = candidates.find(btn => {
                    if (!isVisible(btn)) return false;
                    const text = (btn.textContent || '').trim().toLowerCase();
                    if (text.includes('new')) return true;
                    return !!btn.querySelector('.fa-plus, .o_button_icon');
                });
                if (byIcon) {
                    byIcon.click();
                    return true;
                }

                return false;
            }
        """)

        if isinstance(clicked, str):
            clicked = clicked.strip().lower() == 'true'

        if not clicked:
            await self.handoff_if_blocked("New button not found", context={"step": "click_new"}, force=True)
        return bool(clicked)

    async def process_invoice_batch(self, invoices: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process multiple invoices in sequence.
        """
        batch_result = {
            'total': len(invoices),
            'successful': 0,
            'failed': 0,
            'invoices': []
        }

        self.batch_invoices = invoices
        resume_checkpoint = self.resume_checkpoint or {}
        resume_batch_index = resume_checkpoint.get("batch_index")

        for index, invoice_data in enumerate(invoices):
            if resume_batch_index is not None and index < resume_batch_index:
                continue

            preserve_resume = resume_batch_index is not None and index == resume_batch_index
            self.reset_for_new_invoice(preserve_resume=preserve_resume)
            self._set_checkpoint(stage="batch", batch_index=index)

            print(f"\n{'='*60}")
            print(f"Processing Invoice {index + 1}/{len(invoices)}")
            print(f"Customer: {invoice_data.get('customer')}")
            print(f"{'='*60}")

            try:
                import random
                await asyncio.sleep(random.uniform(0.2, 0.6))
                result = await self.fill_invoice_form(invoice_data)

                invoice_result = {
                    'index': index,
                    'customer': invoice_data.get('customer'),
                    'ref': invoice_data.get('invoice_ref', f'Invoice {index + 1}'),
                    'status': result.status,
                    'fields_filled': result.fields_filled,
                    'fields_failed': result.fields_failed,
                    'execution_time': result.execution_time
                }

                if result.status in ('success', 'partial'):
                    batch_result['successful'] += 1

                    new_clicked = await self.click_new_button()
                    if new_clicked:
                        invoice_result['saved_as_draft'] = True
                        print("✓ Invoice saved as draft, ready for next")
                    else:
                        invoice_result['saved_as_draft'] = False
                        print("⚠ Could not click New button")

                    await self.wait_for_page_ready()
                    await asyncio.sleep(1)
                else:
                    batch_result['failed'] += 1
                    invoice_result['error'] = str(result.fields_failed)

                    await self.click_new_button()
                    await self.wait_for_page_ready()
                    await asyncio.sleep(1)

                batch_result['invoices'].append(invoice_result)

            except Exception as e:
                batch_result['failed'] += 1
                batch_result['invoices'].append({
                    'index': index,
                    'customer': invoice_data.get('customer'),
                    'status': 'error',
                    'error': str(e)
                })

                await self.click_new_button()
                await asyncio.sleep(2)

            if preserve_resume:
                self.resume_checkpoint = None
                resume_batch_index = None

        return batch_result

    async def fill_invoice_form(self, invoice_data: Dict[str, Any]) -> InvoiceFillingResult:
        """
        Generic invoice form filler.

        Args:
            invoice_data: Dictionary with keys matching form field names
            Example:
            {
                "customer": "John Doe",
                "invoice_date": "2026-01-25",
                "due_date": "2026-02-25",  # OR use "payment_terms" instead
                "payment_terms": "30 Days",  # Mutually exclusive with due_date
                "line_items": [
                    {"description": "Service A", "price": 100}
                ]
            }

            Note: Use either "due_date" OR "payment_terms", not both.
        """
        start_time = datetime.now()
        self.invoice_data = invoice_data

        try:
            if not self.resume_checkpoint:
                self.result = InvoiceFillingResult(
                    status="success",
                    fields_attempted=[],
                    fields_filled={},
                    fields_failed={}
                )
            pending_other_info = None
            processed_other_info = False
            resume_checkpoint = self.resume_checkpoint or {}
            resume_field = resume_checkpoint.get("field")
            resume_line_index = resume_checkpoint.get("line_index")
            resume_last_completed = resume_checkpoint.get("last_completed_substep")
            if resume_field and resume_field not in invoice_data:
                resume_field = None
            resume_active = True if resume_field else False
            if self.result.status == "awaiting_human":
                self.result.status = "success"
                self.result.awaiting_human_decision = None

            # Ensure deterministic field order with invoice_ref first
            skip_fields = {"invoice_ref"}
            field_order = [
                "customer",
                "invoice_date",
                "due_date",
                "payment_terms",
                "other_info",
                "catalog_items",
                "line_items",
                "sections",
                "notes"
            ]
            ordered_fields = []
            for key in field_order:
                if key in invoice_data and key not in skip_fields:
                    ordered_fields.append((key, invoice_data[key]))
            for key, value in invoice_data.items():
                if key not in field_order and key not in skip_fields:
                    ordered_fields.append((key, value))

            for field_name, field_value in ordered_fields:
                if field_name in skip_fields:
                    continue
                if resume_active and field_name != resume_field:
                    continue
                if resume_active and field_name == resume_field:
                    resume_active = False

                self.result.fields_attempted.append(field_name)
                self._set_checkpoint(
                    stage="fill_form",
                    field=field_name,
                    line_index=None,
                    substep=None,
                    last_completed_substep=None
                )

                if field_name == "customer":
                    result = await self.select_existing_customer(field_value)

                    if result is None:
                        self.result.fields_failed[field_name] = 'Unknown error'
                        self.result.steps_taken.append(f"✗ Failed {field_name}: Unknown error")
                        continue
                    if result.get('success'):
                        self.result.fields_filled[field_name] = result['selected']
                        self.result.steps_taken.append(f"✓ Filled {field_name}: {result['selected']}")

                        # Check for Create Partner modal and save if present
                        partner_modal_result = await self.ensure_partner_modal_saved()
                        if partner_modal_result.get('modal_found'):
                            if not partner_modal_result.get('success'):
                                # Modal found but save failed - pause for human intervention
                                error_msg = partner_modal_result.get('error', 'Failed to save new partner')
                                self.result.steps_taken.append(f"  └─ ✗ {error_msg}")
                                self.result.status = "failed"

                                # Trigger human handoff
                                await self.handoff_if_blocked(
                                    f"Create Partner modal error: {error_msg}",
                                    context={"field": "customer", "modal_error": error_msg},
                                    force=True
                                )

                                # After human intervention, retry check
                                retry_result = await self.ensure_partner_modal_saved()
                                if retry_result.get('modal_found') and not retry_result.get('success'):
                                    self.result.fields_failed[field_name] = error_msg
                                    continue

                        await self.wait_for_page_ready()
                    else:
                        self.result.fields_failed[field_name] = result.get('error', 'Unknown error')
                        self.result.steps_taken.append(f"✗ Failed {field_name}: {result.get('error')}")
                        continue

                elif field_name == "invoice_date":
                    result = None
                    for handoff_attempt in range(self.handoff_retries + 1):
                        result = await self.fill_date_field('invoice_date_0', field_value)
                        if result.get('success'):
                            break
                        if handoff_attempt < self.handoff_retries:
                            await self.handoff_if_blocked(
                                "Invoice date selection blocked",
                                context={"field": "invoice_date"},
                                force=True
                            )

                    if result.get('success'):
                        self.result.fields_filled[field_name] = result['selected']
                        self.result.steps_taken.append(f"✓ Filled {field_name}: {result['selected']}")
                        await self.wait_for_page_ready()
                    else:
                        self.result.fields_failed[field_name] = result.get('error', 'Unknown error')
                        self.result.steps_taken.append(f"✗ Failed {field_name}: {result.get('error')}")

                        debug = result.get('debug', {})
                        if debug.get('steps'):
                            self.result.steps_taken.extend([f"  └─ {step}" for step in debug['steps']])
                        if debug.get('errors'):
                            self.result.steps_taken.extend([f"  └─ ERROR: {err}" for err in debug['errors']])
                        if debug.get('screenshot_path'):
                            self.result.steps_taken.append(f"  └─ Screenshot: {debug['screenshot_path']}")
                            self.result.debug_screenshots[field_name] = debug['screenshot_path']

                        continue

                elif field_name == "due_date":
                    result = None
                    for handoff_attempt in range(self.handoff_retries + 1):
                        result = await self.fill_date_field('invoice_date_due_0', field_value)
                        if result.get('success'):
                            break
                        if handoff_attempt < self.handoff_retries:
                            await self.handoff_if_blocked(
                                "Due date selection blocked",
                                context={"field": "due_date"},
                                force=True
                            )

                    if result.get('success'):
                        self.result.fields_filled[field_name] = result['selected']
                        self.result.steps_taken.append(f"✓ Filled {field_name}: {result['selected']}")
                        await self.wait_for_page_ready()
                    else:
                        self.result.fields_failed[field_name] = result.get('error', 'Unknown error')
                        self.result.steps_taken.append(f"✗ Failed {field_name}: {result.get('error')}")

                        debug = result.get('debug', {})
                        if debug.get('steps'):
                            self.result.steps_taken.extend([f"  └─ {step}" for step in debug['steps']])
                        if debug.get('errors'):
                            self.result.steps_taken.extend([f"  └─ ERROR: {err}" for err in debug['errors']])
                        if debug.get('screenshot_path'):
                            self.result.steps_taken.append(f"  └─ Screenshot: {debug['screenshot_path']}")
                            self.result.debug_screenshots[field_name] = debug['screenshot_path']

                        continue

                elif field_name == "payment_terms":
                    result = None
                    for handoff_attempt in range(self.handoff_retries + 1):
                        result = await self.fill_dropdown_field('#invoice_payment_term_id_0', field_value)

                        if result.get('awaiting_human'):
                            self.result.status = "awaiting_human"
                            self.result.awaiting_human_decision = result
                            self.result.steps_taken.append(f"Need human decision for {field_name}")
                            break

                        if result.get('success'):
                            break

                        if handoff_attempt < self.handoff_retries:
                            await self.handoff_if_blocked(
                                "Payment terms selection blocked",
                                context={"field": "payment_terms"},
                                force=True
                            )

                    if not result.get('success'):
                        fallback = await self.fill_payment_terms_field(field_value)
                        if fallback.get('success'):
                            result = fallback

                    if result.get('success'):
                        self.result.fields_filled[field_name] = result['selected']
                        self.result.steps_taken.append(f"✓ Filled {field_name}: {result['selected']}")
                        await self.wait_for_page_ready()
                    else:
                        self.result.fields_failed[field_name] = result.get('error', 'Unknown error')
                        self.result.steps_taken.append(f"✗ Failed {field_name}: {result.get('error')}")
                        self.result.status = "awaiting_human"
                        await self.pause_for_human(
                            "Payment terms not filled. Please set it, then press Enter to continue.",
                            context={"field": "payment_terms"}
                        )
                        return self.result

                elif field_name == "other_info":
                    # Defer Other Info until after line items for a natural flow
                    pending_other_info = field_value
                    continue

                elif field_name == "catalog_items":
                    catalog_result = await self.add_products_from_catalog(field_value)
                    if catalog_result.get('success'):
                        self.catalog_used = True
                        added_items = ", ".join([f"{item['name']} (x{item['quantity']})" for item in catalog_result.get('added', [])])
                        self.result.steps_taken.append(f"✓ Added catalog items: {added_items}")
                        await self.wait_for_page_ready()
                    else:
                        self.result.steps_taken.append("✗ Failed to add catalog items")
                        for err in catalog_result.get('errors', []):
                            self.result.steps_taken.append(f"  └─ ERROR: {err}")

                elif field_name == "line_items":
                    # If catalog items exist and haven't been processed yet, do it first
                    if not self.catalog_used and isinstance(invoice_data, dict) and invoice_data.get("catalog_items"):
                        catalog_result = await self.add_products_from_catalog(invoice_data.get("catalog_items", []))
                        if catalog_result.get('success'):
                            self.catalog_used = True
                            added_items = ", ".join([f"{item['name']} (x{item['quantity']})" for item in catalog_result.get('added', [])])
                            self.result.steps_taken.append(f"✓ Added catalog items: {added_items}")
                            await self.wait_for_page_ready()
                        else:
                            self.result.steps_taken.append("✗ Failed to add catalog items")
                            for err in catalog_result.get('errors', []):
                                self.result.steps_taken.append(f"  └─ ERROR: {err}")

                    # Enable optional columns only when required by input data
                    needs_label = any(isinstance(item, dict) and ('label' in item or 'product' in item) for item in field_value)
                    needs_taxes = any(isinstance(item, dict) and 'taxes' in item for item in field_value)
                    needs_quantity = any(isinstance(item, dict) and 'quantity' in item for item in field_value)
                    needs_discount = any(isinstance(item, dict) and 'discount' in item for item in field_value)

                    column_specs = []
                    if needs_label:
                        column_specs.append({
                            "label": "Label",
                            "aliases": ["Label", "Product", "Product/Label", "Product / Label", "Description"]
                        })
                    if needs_taxes:
                        column_specs.append({
                            "label": "Taxes",
                            "aliases": ["Taxes", "Tax", "VAT"]
                        })
                    if needs_quantity:
                        column_specs.append({
                            "label": "Quantity",
                            "aliases": ["Quantity", "Qty", "Qty."]
                        })
                    if needs_discount:
                        column_specs.append({
                            "label": "Disc.%",
                            "aliases": ["Disc.%", "Disc. %", "Disc %", "Discount", "Discount %", "Discount (%)"]
                        })

                    if column_specs:
                        columns_result = await self.ensure_line_item_columns(column_specs)
                        if columns_result.get('enabled'):
                            enabled_str = ", ".join(columns_result['enabled'])
                            self.result.steps_taken.append(f"✓ Enabled line item columns: {enabled_str}")
                        if columns_result.get('already_enabled'):
                            already_str = ", ".join(columns_result['already_enabled'])
                            self.result.steps_taken.append(f"✓ Line item columns already visible: {already_str}")
                        if columns_result.get('missing'):
                            missing_str = ", ".join(columns_result['missing'])
                            self.result.steps_taken.append(f"✗ Line item columns missing: {missing_str}")
                        if columns_result.get('errors'):
                            for err in columns_result['errors']:
                                self.result.steps_taken.append(f"  └─ ERROR: {err}")

                    line_resume_index = resume_line_index if resume_field == "line_items" else None
                    line_resume_last_completed = resume_last_completed if line_resume_index is not None else None

                    for idx, item in enumerate(field_value):
                        if line_resume_index is not None and idx < line_resume_index:
                            continue

                        resume_for_line = None
                        if line_resume_index is not None and idx == line_resume_index:
                            resume_for_line = {"last_completed_substep": line_resume_last_completed}

                        self._set_checkpoint(
                            stage="fill_form",
                            field="line_items",
                            line_index=idx,
                            substep="start",
                            last_completed_substep=(resume_for_line or {}).get("last_completed_substep")
                        )
                        page = await self.browser.get_current_page()
                        # Check if row already exists (e.g., created via catalog)
                        row_exists = await page.evaluate(f"""
                            () => {{
                                const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                    .filter(r => {{
                                        const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                        const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                        return !isNote && !isSection;
                                    }});
                                return rows.length > {idx};
                            }}
                        """)
                        if isinstance(row_exists, str):
                            row_exists = row_exists.strip().lower() == 'true'

                        if not row_exists:
                            # Click "Add a line" button
                            clicked = await self.click_button_by_text("Add a line")
                            if not clicked:
                                self.result.steps_taken.append(f"✗ Failed to add line item {idx + 1}")
                                await self.handoff_if_blocked(
                                    "Add line button not clickable",
                                    context={"field": "line_items", "line_index": idx},
                                    force=True
                                )
                                continue

                            # Wait for the new row to appear (check up to 5 times)
                            row_exists = False
                            for attempt in range(5):
                                await asyncio.sleep(0.5)
                                exists = await page.evaluate(f"""
                                    () => {{
                                        const rows = Array.from(document.querySelectorAll('[name="invoice_line_ids"] .o_data_row'))
                                            .filter(r => {{
                                                const isNote = r.classList.contains('o_is_note') || String(r.dataset?.displayType || '').includes('note');
                                                const isSection = r.classList.contains('o_is_section') || String(r.dataset?.displayType || '').includes('section');
                                                return !isNote && !isSection;
                                            }});
                                        return rows.length > {idx};
                                    }}
                                """)
                                if exists:
                                    row_exists = True
                                    break

                            if not row_exists:
                                self.result.steps_taken.append(f"✗ Row {idx + 1} did not appear after adding line")
                                await self.handoff_if_blocked(
                                    "Line row did not appear after adding",
                                    context={"field": "line_items", "line_index": idx},
                                    force=True
                                )
                                continue

                        # Fill the line item fields
                        line_result = await self.fill_line_item(
                            idx,
                            item,
                            skip_product=self.catalog_used,
                            resume_from=resume_for_line
                        )

                        if line_result['success']:
                            fields_str = ", ".join([f"{k}={v}" for k, v in line_result['fields_filled'].items()])
                            self.result.steps_taken.append(f"✓ Filled line {idx + 1}: {fields_str}")
                            await self.wait_for_page_ready()
                        else:
                            errors_str = ", ".join(line_result['errors'])
                            self.result.steps_taken.append(f"✗ Failed line {idx + 1}: {errors_str}")
                            if self.handoff_retries > 0:
                                await self.handoff_if_blocked(
                                    "Line item fill blocked",
                                    context={"field": "line_items", "line_index": idx},
                                    force=True
                                )
                                line_retry = await self.fill_line_item(
                                    idx,
                                    item,
                                    skip_product=self.catalog_used,
                                    resume_from=resume_for_line
                                )
                                if line_retry.get('success'):
                                    fields_str = ", ".join([f"{k}={v}" for k, v in line_retry['fields_filled'].items()])
                                    self.result.steps_taken.append(f"✓ Filled line {idx + 1} after handoff: {fields_str}")
                                    await self.wait_for_page_ready()

                        if line_resume_index is not None and idx >= line_resume_index:
                            line_resume_index = None
                            line_resume_last_completed = None
                    # Now fill Other Info if it was provided earlier
                    if pending_other_info and not processed_other_info:
                        other_result = await self.fill_other_info_fields(pending_other_info)
                        if other_result.get('success'):
                            filled_list = ", ".join(other_result.get('filled', []))
                            if filled_list:
                                self.result.steps_taken.append(f"✓ Filled other info: {filled_list}")
                            await self.wait_for_page_ready()
                        else:
                            self.result.steps_taken.append("✗ Failed to fill other info")
                            for err in other_result.get('errors', []):
                                self.result.steps_taken.append(f"  └─ ERROR: {err}")
                        processed_other_info = True

                elif field_name == "sections":
                    for section in field_value:
                        clicked = await self.click_button_by_text("Add a section")
                        if clicked:
                            self.result.steps_taken.append("Added section")
                            await asyncio.sleep(2)

                elif field_name == "notes":
                    for note in field_value:
                        note_result = await self.add_note_line(note)
                        if note_result.get('success'):
                            self.result.steps_taken.append("✓ Added note")
                            await self.wait_for_page_ready()
                        else:
                            self.result.steps_taken.append(f"✗ Failed to add note: {note_result.get('error')}")

            # If other_info wasn't filled yet, do it last
            if pending_other_info and not processed_other_info:
                other_result = await self.fill_other_info_fields(pending_other_info)
                if other_result.get('success'):
                    filled_list = ", ".join(other_result.get('filled', []))
                    if filled_list:
                        self.result.steps_taken.append(f"✓ Filled other info: {filled_list}")
                    await self.wait_for_page_ready()
                else:
                    self.result.steps_taken.append("✗ Failed to fill other info")
                    for err in other_result.get('errors', []):
                        self.result.steps_taken.append(f"  └─ ERROR: {err}")

        except Exception as e:
            self.result.status = "failed"
            self.result.steps_taken.append(f"Error: {str(e)}")

        end_time = datetime.now()
        self.result.execution_time = (end_time - start_time).total_seconds()

        if self.result.status != "awaiting_human" and self.result.status != "failed":
            if len(self.result.fields_filled) == len(self.result.fields_attempted):
                self.result.status = "success"
            elif len(self.result.fields_filled) > 0:
                self.result.status = "partial"
            else:
                self.result.status = "failed"

        return self.result


def load_handoff_state(path: str) -> Optional[Dict[str, Any]]:
    try:
        state_path = Path(path)
        if not state_path.exists():
            return None
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_invoices_from_json(json_path: str = "visible_rows.json", count: int = None) -> List[Dict[str, Any]]:
    """
    Load invoice data from visible_rows.json and convert to invoice format.

    Maps fields from sales order format to invoice format:
    - Customer Company → customer
    - Date Raised → invoice_date
    - Sales Request Ref → invoice_ref
    - Sales Person → salesperson
    - Sales Discount % → discount on all line items
    - Product 1/2/3 → line_items
    """
    from pathlib import Path
    from datetime import datetime

    # Try to find the JSON file in common locations
    possible_paths = [
        Path(json_path),
        Path(__file__).parent / json_path,
        Path(__file__).parent.parent / json_path,
        Path.cwd() / json_path,
    ]

    json_file = None
    for p in possible_paths:
        if p.exists():
            json_file = p
            break

    if not json_file:
        print(f"Warning: {json_path} not found, using fallback sample data")
        return generate_sample_invoices(count or 3)

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load {json_path}: {e}, using fallback sample data")
        return generate_sample_invoices(count or 3)

    rows = data.get('rows', [])
    if not rows:
        print(f"Warning: No rows in {json_path}, using fallback sample data")
        return generate_sample_invoices(count or 3)

    # Limit to count if specified
    if count:
        rows = rows[:count]

    invoices = []

    for idx, row in enumerate(rows):
        # Parse date (format: "1/1/2026" -> "2026-01-01")
        date_str = row.get('Date Raised', '')
        try:
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
                    invoice_date = f"{year}-{month:02d}-{day:02d}"
                else:
                    invoice_date = datetime.now().strftime("%Y-%m-%d")
            else:
                invoice_date = datetime.now().strftime("%Y-%m-%d")
        except Exception:
            invoice_date = datetime.now().strftime("%Y-%m-%d")

        # Get customer (use Customer Company)
        customer = row.get('Customer Company', '').strip()
        if not customer:
            continue  # Skip rows without customer

        # Get discount (applies to all line items)
        try:
            discount = float(row.get('Sales Discount %', 0) or 0)
        except (ValueError, TypeError):
            discount = 0

        # Build line items from Product 1, 2, 3
        line_items = []
        for prod_num in [1, 2, 3]:
            product_label = row.get(f'Product {prod_num}', '').strip()
            if not product_label:
                continue

            # Parse quantity (handle comma separators like "10,000")
            qty_str = row.get(f'Product {prod_num} Quantity', '1') or '1'
            try:
                quantity = int(qty_str.replace(',', ''))
            except (ValueError, TypeError):
                quantity = 1

            # Parse price
            price_str = row.get(f'Product {prod_num} Price Per Unit', '0') or '0'
            try:
                price = float(price_str.replace(',', ''))
            except (ValueError, TypeError):
                price = 0

            line_items.append({
                "label": product_label,
                "price": price,
                "quantity": quantity,
                "discount": discount,
                "taxes": ["20%"]  # Default UK VAT
            })

        if not line_items:
            continue  # Skip rows without products

        # Build invoice object
        invoice = {
            "customer": customer,
            "invoice_date": invoice_date,
            "invoice_ref": row.get('Sales Request Ref', f'INV/{idx + 1:05d}'),
            "payment_terms": "30 Days",  # Default
            "other_info": {
                "Customer Reference": row.get('Sales Request Ref', ''),
                "Salesperson": row.get('Sales Person', ''),
                "Customer Contact": row.get('Customer Contact', ''),
                "Trading Address": row.get('Trading Address', ''),
                "Delivery Address": row.get('Delivery Address', ''),
                "Recipient Bank": "Bank",
                "Payment Method": "Manual",
            },
            "line_items": line_items,
            "notes": [
                f"Sales Order: {row.get('Sales Request Ref', '')}",
                f"Contact: {row.get('Customer Contact', '')}",
            ]
        }

        invoices.append(invoice)

    print(f"Loaded {len(invoices)} invoices from {json_file}")
    return invoices


def generate_sample_invoices(count: int = 10) -> List[Dict[str, Any]]:
    """Generate fallback sample invoices if JSON file not found."""
    from datetime import timedelta
    import random

    # Use real customer names from Odoo
    customers = [
        "Ekho IT services",
        "Red Internet Limited",
        "ABC Trading",
        "Trade Direct",
        "Universal Supplies",
    ]

    products = [
        {"label": "CHR100 - Black Office Chairs", "price": 89.99},
        {"label": "DSK100 - Oak Desk", "price": 145.00},
        {"label": "PAP200 - A4 Paper", "price": 1.45},
    ]

    invoices = []
    base_date = datetime(2026, 1, 1)

    for i in range(count):
        invoice_date = base_date + timedelta(days=i)
        customer = customers[i % len(customers)]

        # Random 1-3 products
        num_items = random.randint(1, 3)
        line_items = []
        for j in range(num_items):
            prod = products[j % len(products)]
            line_items.append({
                "label": prod["label"],
                "price": prod["price"],
                "quantity": random.randint(5, 50),
                "discount": random.choice([0, 5, 10]),
                "taxes": ["20%"]
            })

        invoice = {
            "customer": customer,
            "invoice_date": invoice_date.strftime("%Y-%m-%d"),
            "invoice_ref": f"SO{10001 + i}",
            "payment_terms": "30 Days",
            "other_info": {
                "Salesperson": random.choice(["Martin McDonagh", "Joan Gold", "Alan Smith"]),
            },
            "line_items": line_items,
            "notes": []
        }
        invoices.append(invoice)

    return invoices


async def run_invoice_filler(
    cdp_url: str = "http://localhost:9222",
    resume: bool = False,
    state_file: str = "handoff_state.json",
    no_handoff_wait: bool = False,
    human_handoff: bool = True,
    invoice_count: int = 3,
) -> None:
    """
    Main entry point for the invoice filler, callable from agent_controller.py.

    Args:
        cdp_url: Chrome DevTools Protocol URL (from Selenium's se:cdp capability)
        resume: Whether to resume from saved handoff state
        state_file: Path to handoff state file
        no_handoff_wait: If True, don't wait for human input on handoff
        human_handoff: If True, enable human intervention features
        invoice_count: Number of sample invoices to generate
    """
    browser = Browser()

    try:
        print(f"Connecting to browser at {cdp_url}...")
        await browser.connect(cdp_url)
        print(f"Connected to browser at {cdp_url}")

        force_search_more_taxes = False
        force_search_more_products = False
        resume_state = load_handoff_state(state_file) if resume else None
        if resume and not resume_state:
            print(f"No handoff state found at {state_file}. Aborting resume.")
            await browser.stop()
            return

        filler = GenericFormFiller(
            browser,
            force_search_more_taxes=force_search_more_taxes,
            force_search_more_products=force_search_more_products,
            human_handoff=human_handoff,
            handoff_state_path=state_file,
            resume_state=resume_state,
            handoff_wait=not no_handoff_wait
        )

        # Login and navigate to New Invoice
        login_url = "https://process-zero.odoo.com/web/login?redirect=%2Fodoo%3F"
        email = "martinm@processzero.co.uk"
        password = "0p9o8i7u^Y"
        nav_ok = await filler.login_and_navigate_to_new_invoice(login_url, email, password)
        if not nav_ok:
            print("Failed to navigate to new invoice. Aborting.")
            await browser.stop()
            return

        invoice_data = resume_state.get("invoice_data") if resume_state and resume_state.get("invoice_data") else None
        if isinstance(invoice_data, list):
            invoices_data = invoice_data
        elif isinstance(invoice_data, dict):
            invoices_data = [invoice_data]
        else:
            # Load from visible_rows.json (real sales order data)
            invoices_data = load_invoices_from_json(count=invoice_count)

        batch_result = await filler.process_invoice_batch(invoices_data)

        print("\n" + "="*60)
        print("BATCH PROCESSING COMPLETE")
        print("="*60)
        print(f"Total invoices: {batch_result['total']}")
        print(f"Successful: {batch_result['successful']}")
        print(f"Failed: {batch_result['failed']}")
        print("\nDetails:")
        for inv in batch_result['invoices']:
            status_icon = "✓" if inv['status'] == 'success' else "✗" if inv['status'] == 'failed' else "⚠"
            print(f"  {status_icon} {inv.get('ref')}: {inv.get('customer')} - {inv.get('status')}")

        if batch_result['failed'] == 0:
            filler.clear_handoff_state()

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
    finally:
        await browser.stop()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="Resume from saved handoff state")
    parser.add_argument("--state-file", default="handoff_state.json", help="Path to handoff state file")
    parser.add_argument("--no-handoff-wait", action="store_true", help="Do not wait for human input on handoff")
    parser.add_argument("--cdp-url", default="http://localhost:9222", help="Chrome DevTools Protocol URL")
    parser.add_argument("--invoice-count", type=int, default=3, help="Number of sample invoices to generate")
    args = parser.parse_args()

    await run_invoice_filler(
        cdp_url=args.cdp_url,
        resume=args.resume,
        state_file=args.state_file,
        no_handoff_wait=args.no_handoff_wait,
        invoice_count=args.invoice_count,
    )


if __name__ == "__main__":
    asyncio.run(main())
