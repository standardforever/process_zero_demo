from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Awaitable, Callable

from selenium import webdriver
from selenium.webdriver.common.by import By


class AgentStopped(Exception):
    """Raised when the agent is stopped externally."""


class AgentController:
    def __init__(
        self,
        driver: webdriver.Remote,
        pause_check: Callable[[], Awaitable[None]],
        log: Callable[[str], Awaitable[None]],
    ) -> None:
        self.driver = driver
        self.pause_check = pause_check
        self.log = log

    async def run_task(self, url: str | None = None) -> None:
        """Main automation entry point. Keeps browser alive until stopped."""
        target_url = url or "about:blank"
        await self.log(f"Navigating to {target_url}")
        await asyncio.to_thread(self.driver.get, target_url)

        await self.pause_check()
        await self.log("Browser session active. Starting app.py workflow...")
        try:
            import importlib
            import app as workflow_app
            from service.workflow_executor import set_pause_check_callback

            cdp_url = None
            try:
                capabilities = getattr(self.driver, "capabilities", None) or {}
                cdp_url = capabilities.get("se:cdp") or capabilities.get("se:cdpUrl")
            except Exception:
                cdp_url = None

            await self.log(f"app.py loaded from {workflow_app.__file__}")
            workflow_app = importlib.reload(workflow_app)
            await self.log(f"app.py reloaded from {workflow_app.__file__}")

            if cdp_url:
                await self.log(
                    f"Selenium CDP endpoint detected: {cdp_url}. "
                    "app.py uses browser connection settings from config.json."
                )
                try:
                    config_path = Path(__file__).resolve().parent / "config.json"
                    with config_path.open("r", encoding="utf-8") as file:
                        config = json.load(file)
                    previous_url = str(config.get("browser_connection_url") or "").strip()
                    if previous_url != cdp_url:
                        config["browser_connection_url"] = cdp_url
                        with config_path.open("w", encoding="utf-8") as file:
                            json.dump(config, file, indent=2)
                            file.write("\n")
                        await self.log(
                            f"Updated config.json browser_connection_url from '{previous_url or '-'}' to '{cdp_url}'"
                        )
                except Exception as exc:
                    await self.log(f"Warning: failed to update config.json with CDP URL: {exc}")
            else:
                await self.log("No Selenium CDP endpoint detected. app.py will use config.json settings.")

            # Let workflow actions respect live pause/stop control requests.
            set_pause_check_callback(self.pause_check)
            try:
                result = await workflow_app.run_workflow("config.json")
            finally:
                set_pause_check_callback(None)

            final_step = result.get("current_step") if isinstance(result, dict) else "unknown"
            await self.log(f"app.py workflow finished (final step: {final_step})")
        except Exception as exc:
            await self.log(f"app.py workflow failed: {exc}")

        await self.log("Browser session active. Waiting for tasks or intervention...")

        while True:
            await self.pause_check()
            await asyncio.sleep(0.5)

    async def execute_step(self, action: dict) -> None:
        """Execute a single automation step with pause checking."""
        await self.pause_check()

        action_type = action.get("type")

        if action_type == "click":
            selector = action["selector"]

            def _click() -> None:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                element.click()

            await asyncio.to_thread(_click)
            await self.log(f"Clicked: {selector}")

        elif action_type == "type":
            selector = action["selector"]
            text = action["text"]

            def _type() -> None:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                element.send_keys(text)

            await asyncio.to_thread(_type)
            await self.log(f"Typed in: {selector}")

        elif action_type == "navigate":
            url = action["url"]
            await asyncio.to_thread(self.driver.get, url)
            await self.log(f"Navigated to: {url}")

        await self.pause_check()
