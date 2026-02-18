import argparse
import asyncio
import json
from typing import Any

from browser_use import Browser, Tools

URL = (
    "https://pivotaluksolutionsltd-my.sharepoint.com/"
    "personal/martin_clickbuy_ai/Lists/Sales%20Pipeline%20CRM/AllItems.aspx"
)
DEBUG_ENDPOINT = "http://localhost:9223"
WAIT_SECONDS = 8


def _safe_parse_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {"raw": raw}
    return {"raw": str(raw)}


async def _do_action(tools: Tools, browser: Browser, action_name: str, params: dict[str, Any]) -> Any:
    result = await tools.registry.execute_action(
        action_name=action_name,
        params=params,
        browser_session=browser,
    )
    extracted = getattr(result, "extracted_content", None)
    if extracted is not None:
        return extracted
    return getattr(result, "long_term_memory", "")


def _click_row_script(sales_request_ref: str) -> str:
    return f"""
    (function(){{
      const target = {json.dumps(sales_request_ref, ensure_ascii=False)}.toLowerCase();
      const clean = (v) => (v || '').replace(/\\s+/g, ' ').trim();
      const isVisible = (el) => {{
        if (!el) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== 'none' &&
               style.visibility !== 'hidden' &&
               style.opacity !== '0' &&
               rect.width > 0 &&
               rect.height > 0;
      }};

      const cells = Array.from(
        document.querySelectorAll('[role="gridcell"], td, a, span, div')
      ).filter((el) => isVisible(el));

      const match = cells.find((el) => clean(el.textContent || '').toLowerCase() === target);
      if (!match) {{
        return JSON.stringify({{ clicked: false, reason: 'sales-ref-not-found' }});
      }}

      const row = match.closest('[role="row"], tr, [data-selection-index], [class*="row"], [class*="Row"]') || match;
      row.scrollIntoView({{ block: 'center', inline: 'nearest' }});
      row.click();

      return JSON.stringify({{
        clicked: true,
        matched_text: clean(match.textContent || ''),
        row_tag: (row.tagName || '').toLowerCase(),
      }});
    }})();
    """


PANEL_CHECK_SCRIPT = """
(function(){
  const isVisible = (el) => {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' &&
           style.visibility !== 'hidden' &&
           style.opacity !== '0' &&
           rect.width > 0 &&
           rect.height > 0;
  };

  const selectors = [
    '[data-automation-id="DetailsPane"]',
    '[data-automationid="DetailsPane"]',
    '[class*="DetailsPane"]',
    '[class*="rightPane"]',
    '[class*="ItemDetail"]',
    '[class*="od-ItemContent"]',
    '[role="complementary"]',
    '[role="dialog"]',
    '[class*="panel"][class*="open"]',
  ];

  const panels = selectors.flatMap((s) => Array.from(document.querySelectorAll(s))).filter(isVisible);
  const panel = panels[0] || null;
  const panelText = panel ? (panel.innerText || '') : '';

  return JSON.stringify({
    panel_visible: !!panel,
    panel_loading: panelText.trim().toLowerCase().startsWith('loading'),
    panel_text_start: panelText.slice(0, 120)
  });
})();
"""


def _field_visible_script(field_name: str) -> str:
    return f"""
    (function(){{
      const field = {json.dumps(field_name, ensure_ascii=False)}.toLowerCase();
      const clean = (v) => (v || '').replace(/\\s+/g, ' ').trim().toLowerCase();
      const isVisible = (el) => {{
        if (!el) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== 'none' &&
               style.visibility !== 'hidden' &&
               style.opacity !== '0' &&
               rect.width > 0 &&
               rect.height > 0;
      }};

      const root = document.querySelector('[data-automation-id="DetailsPane"], [data-automationid="DetailsPane"], [class*="DetailsPane"], [role="complementary"], [role="dialog"]') || document;
      const found = Array.from(root.querySelectorAll('span, label, div'))
        .some((el) => isVisible(el) && clean(el.textContent || '').includes(field));

      return JSON.stringify({{ field_visible: found }});
    }})();
    """


CLICK_DETAILS_BUTTON_SCRIPT = """
(function(){
  const clean = (v) => (v || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  const isVisible = (el) => {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' &&
           style.visibility !== 'hidden' &&
           style.opacity !== '0' &&
           rect.width > 0 &&
           rect.height > 0;
  };

  const buttons = Array.from(document.querySelectorAll('button, [role="button"], a, [role="menuitem"]'))
    .filter((el) => isVisible(el) && clean(el.textContent || '') === 'details');

  if (!buttons.length) {
    return JSON.stringify({ clicked: false, reason: 'details-button-not-found' });
  }

  buttons[0].click();
  return JSON.stringify({ clicked: true, tag: (buttons[0].tagName || '').toLowerCase() });
})();
"""


CLICK_EDIT_ALL_BUTTON_SCRIPT = """
(function(){
  const clean = (v) => (v || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  const isVisible = (el) => {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' &&
           style.visibility !== 'hidden' &&
           style.opacity !== '0' &&
           rect.width > 0 &&
           rect.height > 0;
  };

  const panelSelectors = [
    '[data-automation-id="DetailsPane"]',
    '[data-automationid="DetailsPane"]',
    '[class*="DetailsPane"]',
    '[class*="rightPane"]',
    '[class*="ItemDetail"]',
    '[class*="od-ItemContent"]',
    '[role="complementary"]',
    '[role="dialog"]',
    '[class*="panel"][class*="open"]',
  ];
  const panels = panelSelectors
    .flatMap((s) => Array.from(document.querySelectorAll(s)))
    .filter((el) => isVisible(el));

  // First try inside right-side pane.
  let candidates = [];
  for (const panel of panels) {
    candidates = candidates.concat(
      Array.from(panel.querySelectorAll('button, a, [role="button"], [role="menuitem"], span, div'))
        .filter((el) => isVisible(el))
        .filter((el) => {
          const text = clean(el.textContent || '');
          const aria = clean(el.getAttribute('aria-label') || '');
          const title = clean(el.getAttribute('title') || '');
          return text === 'edit all' || aria === 'edit all' || title === 'edit all';
        })
    );
  }

  // Fallback: search globally for right-side visible "Edit all" labels.
  if (!candidates.length) {
    candidates = Array.from(document.querySelectorAll('button, a, [role="button"], [role="menuitem"], span, div'))
      .filter((el) => isVisible(el))
      .filter((el) => {
        const rect = el.getBoundingClientRect();
        if (rect.left < window.innerWidth * 0.55) return false;
        const text = clean(el.textContent || '');
        const aria = clean(el.getAttribute('aria-label') || '');
        const title = clean(el.getAttribute('title') || '');
        return text === 'edit all' || aria === 'edit all' || title === 'edit all';
      });
  }

  if (!candidates.length) {
    return JSON.stringify({ clicked: false, reason: 'edit-all-button-not-found' });
  }

  candidates[0].click();
  return JSON.stringify({
    clicked: true,
    tag: (candidates[0].tagName || '').toLowerCase(),
    text: (candidates[0].textContent || '').trim(),
  });
})();
"""


async def main() -> int:
    parser = argparse.ArgumentParser(description="Navigate SharePoint list and click a sales ref")
    parser.add_argument("--debug-endpoint", default=DEBUG_ENDPOINT, help="Chrome DevTools endpoint")
    parser.add_argument("--wait-seconds", type=int, default=WAIT_SECONDS, help="Seconds to wait after navigation")
    parser.add_argument("--sales-request-ref", default="", help="Sales ref to click, e.g. SO10016")
    parser.add_argument("--panel-timeout", type=int, default=30, help="Seconds to wait for details panel")
    parser.add_argument("--field-name", default="Agent_state", help="Field label used to confirm details pane")
    parser.add_argument("--find-retries", type=int, default=8, help="How many find/scroll attempts to perform")
    parser.add_argument(
        "--click-edit-all-only",
        action="store_true",
        help="Skip navigation/selection and only click visible 'Edit all' on the current page",
    )
    args = parser.parse_args()

    browser = Browser()
    tools = Tools()

    try:
        await browser.connect(args.debug_endpoint)

        if args.click_edit_all_only:
            diagnostics: dict[str, Any] = {"mode": "click-edit-all-only", "attempts": []}
            for attempt in range(1, max(1, args.panel_timeout) + 1):
                edit_all_result = _safe_parse_json(
                    await _do_action(
                        tools,
                        browser,
                        "evaluate",
                        {"code": CLICK_EDIT_ALL_BUTTON_SCRIPT},
                    )
                )
                diagnostics["attempts"].append({"attempt": attempt, "edit_all_click": edit_all_result})
                if edit_all_result.get("clicked"):
                    print(json.dumps({"ok": True, **diagnostics}, indent=2, ensure_ascii=False))
                    return 0
                await _do_action(tools, browser, "wait", {"seconds": 1})

            print(json.dumps({"ok": False, "error": "Edit all button not found", **diagnostics}, indent=2, ensure_ascii=False))
            return 1

        await _do_action(tools, browser, "navigate", {"url": URL, "new_tab": False})
        await _do_action(tools, browser, "wait", {"seconds": args.wait_seconds})
        print(f"Navigated to: {URL}")

        if not args.sales_request_ref:
            print(json.dumps({"ok": True, "message": "Navigation only mode."}, indent=2))
            return 0

        diagnostics: dict[str, Any] = {
            "sales_request_ref": args.sales_request_ref,
            "field_name": args.field_name,
            "attempts": [],
        }

        for attempt in range(1, args.find_retries + 1):
            row_result = _safe_parse_json(
                await _do_action(
                    tools,
                    browser,
                    "evaluate",
                    {"code": _click_row_script(args.sales_request_ref)},
                )
            )
            attempt_info: dict[str, Any] = {"attempt": attempt, "row_click": row_result}

            if row_result.get("clicked"):
                await _do_action(tools, browser, "wait", {"seconds": 1})
                details_result = _safe_parse_json(
                    await _do_action(tools, browser, "evaluate", {"code": CLICK_DETAILS_BUTTON_SCRIPT})
                )
                attempt_info["details_click"] = details_result

                for _ in range(max(1, args.panel_timeout)):
                    panel_result = _safe_parse_json(
                        await _do_action(tools, browser, "evaluate", {"code": PANEL_CHECK_SCRIPT})
                    )
                    attempt_info["panel_check"] = panel_result
                    if panel_result.get("panel_visible"):
                        edit_all_result = _safe_parse_json(
                            await _do_action(
                                tools,
                                browser,
                                "evaluate",
                                {"code": CLICK_EDIT_ALL_BUTTON_SCRIPT},
                            )
                        )
                        attempt_info["edit_all_click"] = edit_all_result
                        if not edit_all_result.get("clicked"):
                            await _do_action(tools, browser, "wait", {"seconds": 1})
                            continue

                        field_result = _safe_parse_json(
                            await _do_action(
                                tools,
                                browser,
                                "evaluate",
                                {"code": _field_visible_script(args.field_name)},
                            )
                        )
                        attempt_info["field_check"] = field_result
                        diagnostics["attempts"].append(attempt_info)
                        print(json.dumps({"ok": True, **diagnostics}, indent=2, ensure_ascii=False))
                        return 0
                    await _do_action(tools, browser, "wait", {"seconds": 1})

            diagnostics["attempts"].append(attempt_info)
            if attempt < args.find_retries:
                await _do_action(tools, browser, "scroll", {"down": True, "pages": 1.0})
                await _do_action(tools, browser, "wait", {"seconds": 1})

        print(json.dumps({"ok": False, "error": "Could not confirm details panel", **diagnostics}, indent=2, ensure_ascii=False))
        return 1
    finally:
        await browser.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
