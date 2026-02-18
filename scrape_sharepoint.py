import asyncio
import json

from browser_use import Browser, Tools

URL = (
    "https://pivotaluksolutionsltd-my.sharepoint.com/"
    "personal/martin_clickbuy_ai/Lists/Sales%20Pipeline%20CRM/AllItems.aspx"
)
OUTPUT_FILE = "visible_rows.json"

JS_EXTRACT = """
() => {
    const clean = (text) => (text || '').replace(/\\s+/g, ' ').trim();
    const getLabel = (el) => {
        const direct = clean(el.innerText || el.textContent || '');
        if (direct) return direct;
        const aria = clean(el.getAttribute('aria-label') || '');
        if (aria) return aria;
        const title = clean(el.getAttribute('title') || '');
        if (title) return title;
        const child = el.querySelector('[aria-label]');
        if (child) {
            const childLabel = clean(child.getAttribute('aria-label') || child.textContent || '');
            if (childLabel) return childLabel;
        }
        return '';
    };

    const headerByIndex = {};
    const headerByKey = {};
    const headerOrder = [];
    const uniqueHeaders = [];
    const seen = new Set();

    const headerEls = Array.from(document.querySelectorAll('[role="columnheader"]'));
    if (headerEls.length) {
        headerEls.forEach((el, i) => {
            const colIndex = el.getAttribute('aria-colindex') || el.getAttribute('data-colindex') || String(i + 1);
            const label = getLabel(el);
            const key = el.getAttribute('data-automation-key') || el.getAttribute('data-field') || el.getAttribute('data-automationid') || (el.dataset && el.dataset.automationKey) || '';
            if (label) {
                headerByIndex[colIndex] = label;
                if (key) headerByKey[key] = label;
                if (!seen.has(label)) {
                    seen.add(label);
                    uniqueHeaders.push(label);
                }
            }
            headerOrder.push(label || '');
        });
    } else {
        const ths = Array.from(document.querySelectorAll('table thead th'));
        ths.forEach((el, i) => {
            const label = getLabel(el);
            if (label && !seen.has(label)) {
                seen.add(label);
                uniqueHeaders.push(label);
            }
            headerOrder.push(label || '');
        });
    }

    const rows = [];
    const rowEls = Array.from(document.querySelectorAll('[role="row"]'))
        .filter(r => r.querySelector('[role="gridcell"], [role="rowheader"]'));

    for (const row of rowEls) {
        const rowData = {};
        const cells = Array.from(row.querySelectorAll('[role="gridcell"], [role="rowheader"]'));
        cells.forEach((cell, idx) => {
            const colIndex = cell.getAttribute('aria-colindex') || cell.getAttribute('data-colindex');
            const cellKey = cell.getAttribute('data-automation-key') || cell.getAttribute('data-field') || cell.getAttribute('data-automationid') || (cell.dataset && cell.dataset.automationKey) || '';
            let key = cellKey ? headerByKey[cellKey] : null;
            if (!key) key = colIndex ? headerByIndex[colIndex] : null;
            if (!key) key = headerOrder[idx] || null;
            if (!key) return;
            const val = clean(cell.innerText || cell.textContent || cell.getAttribute('aria-label') || '');
            if (val !== '') rowData[key] = val;
        });
        if (Object.keys(rowData).length) rows.push(rowData);
    }

    return { headers: uniqueHeaders, rows };
}
"""


async def main():
    browser = Browser()
    tools = Tools()

    try:
        await browser.connect("http://localhost:9222")
        await tools.registry.execute_action(
            action_name="navigate",
            params={"url": URL, "new_tab": False},
            browser_session=browser,
        )
        async def wait_seconds(seconds: int) -> None:
            await tools.registry.execute_action(
                action_name="wait",
                params={"seconds": seconds},
                browser_session=browser,
            )

        await wait_seconds(6)

        page = await browser.get_current_page()

        async def read_table():
            result = await page.evaluate(JS_EXTRACT)
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except Exception:
                    result = {"headers": [], "rows": []}
            if not isinstance(result, dict):
                result = {"headers": [], "rows": []}
            return result

        all_rows = {}
        headers = []
        no_new = 0

        while no_new < 3:
            result = await read_table()
            if result.get("headers") and not headers:
                headers = result["headers"]

            rows = result.get("rows", [])
            key_field = "Sales Request Ref" if "Sales Request Ref" in headers else (headers[0] if headers else None)

            added = 0
            for row in rows:
                key = row.get(key_field) if key_field else None
                if not key:
                    key = json.dumps(row, sort_keys=True)
                if key not in all_rows:
                    all_rows[key] = row
                    added += 1

            no_new = no_new + 1 if added == 0 else 0

            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {"headers": headers, "rows": list(all_rows.values())},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            if no_new >= 3:
                break

            await tools.registry.execute_action(
                action_name="scroll",
                params={"down": True, "pages": 1.3},
                browser_session=browser,
            )
            await wait_seconds(2)

        print("Detected column headers:")
        for i, header in enumerate(headers, start=1):
            print(f"{i}. {header}")

        print(f"\nTotal rows saved: {len(all_rows)}")
        for i, row in enumerate(list(all_rows.values())[:3], start=1):
            print(f"Row {i}: {row}")
        print(f"\nSaved all rows to {OUTPUT_FILE}")
    finally:
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())
