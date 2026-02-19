from __future__ import annotations

import asyncio
import json
import signal
import uuid
from typing import Any

import websockets
from websockets.legacy.server import WebSocketServerProtocol, serve
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

from agent_controller import AgentController, AgentStopped


class LiveViewServer:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        selenium_url: str = "http://localhost:4444/wd/hub",
    ) -> None:
        self.host = host
        self.port = port
        self.selenium_url = selenium_url

        self.clients: set[WebSocketServerProtocol] = set()
        self.client_ids: dict[WebSocketServerProtocol, str] = {}

        self.agent_running = False
        self.intervention_active = False
        self.intervention_user: str | None = None
        self.driver: webdriver.Remote | None = None
        self.agent_task: asyncio.Task[None] | None = None

        self.state_lock = asyncio.Lock()

    async def run(self) -> None:
        async with serve(self.handle_client, self.host, self.port):
            print(f"LiveViewServer listening on ws://{self.host}:{self.port}")
            await asyncio.Future()

    async def handle_client(self, websocket: WebSocketServerProtocol) -> None:
        self.clients.add(websocket)
        await self.send_status(websocket)
        await self.broadcast_users()

        try:
            async for raw_message in websocket:
                await self.handle_message(websocket, raw_message)
        except websockets.ConnectionClosed:
            pass
        finally:
            await self.disconnect_client(websocket)

    async def handle_message(
        self,
        websocket: WebSocketServerProtocol,
        raw_message: str | bytes,
    ) -> None:
        if isinstance(raw_message, bytes):
            raw_message = raw_message.decode("utf-8", errors="replace")
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            await self.log("Received invalid JSON from client")
            return

        message_type = message.get("type")
        if message_type == "hello":
            user_id = self._ensure_user_id(websocket, message)
            await self.log(f"User connected: {user_id}")
            await self.broadcast_users()
            await self.send_status(websocket)
            return

        if message_type == "start":
            user_id = self._ensure_user_id(websocket, message)
            url = message.get("url")
            await self.log(f"Start requested by {user_id}")
            await self.start_agent(url)
            return

        if message_type == "stop":
            user_id = self._ensure_user_id(websocket, message)
            await self.log(f"Stop requested by {user_id}")
            await self.stop_agent()
            return

        if message_type == "request_intervention":
            user_id = self._ensure_user_id(websocket, message)
            await self.request_intervention(user_id)
            return

        if message_type == "release_intervention":
            user_id = self._ensure_user_id(websocket, message)
            await self.release_intervention(user_id)
            return

        await self.log(f"Unknown message type: {message_type}")

    async def send_status(self, websocket: WebSocketServerProtocol) -> None:
        async with self.state_lock:
            status = {
                "type": "status",
                "agent_running": self.agent_running,
                "intervention_active": self.intervention_active,
                "intervention_user": self.intervention_user,
            }
        await self._safe_send(websocket, status)

    async def broadcast_status(self) -> None:
        async with self.state_lock:
            status = {
                "type": "status",
                "agent_running": self.agent_running,
                "intervention_active": self.intervention_active,
                "intervention_user": self.intervention_user,
            }
        await self.broadcast(status)

    async def broadcast_users(self) -> None:
        users = list(self.client_ids.values())
        await self.broadcast({"type": "users", "users": users})

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self.clients:
            return

        payload = json.dumps(message)
        disconnected: list[WebSocketServerProtocol] = []

        for ws in self.clients:
            try:
                await ws.send(payload)
            except websockets.ConnectionClosed:
                disconnected.append(ws)

        for ws in disconnected:
            await self.disconnect_client(ws)

    async def _safe_send(self, websocket: WebSocketServerProtocol, message: dict[str, Any]) -> None:
        try:
            await websocket.send(json.dumps(message))
        except websockets.ConnectionClosed:
            await self.disconnect_client(websocket)

    async def log(self, message: str) -> None:
        print(message)
        await self.broadcast({"type": "log", "message": message})

    async def start_agent(self, url: str | None = None) -> None:
        already_running = False
        async with self.state_lock:
            if self.agent_running:
                already_running = True
            else:
                self.agent_running = True
                self.intervention_active = False
                self.intervention_user = None

        if already_running:
            await self.log("Agent already running")
            return

        await self.broadcast_status()

        try:
            self.driver = await self._create_driver()
        except Exception as exc:
            async with self.state_lock:
                self.agent_running = False
            await self.broadcast_status()
            await self.log(f"Failed to start Selenium driver: {exc}")
            return

        controller = AgentController(self.driver, self.pause_check, self.log)
        await self.log("Launching AgentController with app.py workflow")
        self.agent_task = asyncio.create_task(self._run_agent(controller, url))

    async def _run_agent(self, controller: AgentController, url: str | None) -> None:
        try:
            await controller.run_task(url)
        except AgentStopped:
            await self.log("Agent stopped by user")
        except Exception as exc:
            await self.log(f"Agent crashed: {exc}")
        else:
            await self.log("Agent session ended")
        finally:
            await self._cleanup_driver()
            async with self.state_lock:
                self.agent_running = False
                self.intervention_active = False
                self.intervention_user = None
                self.agent_task = None
            await self.broadcast_status()

    async def stop_agent(self) -> None:
        not_running = False
        task_to_stop: asyncio.Task[None] | None = None
        async with self.state_lock:
            if not self.agent_running:
                not_running = True
            else:
                self.agent_running = False
                self.intervention_active = False
                self.intervention_user = None
                task_to_stop = self.agent_task

        if not_running:
            await self.log("Agent not running")
            return

        await self.broadcast_status()

        if task_to_stop:
            task_to_stop.cancel()
            try:
                await asyncio.wait_for(task_to_stop, timeout=10)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                await self.log("Agent stop timeout; forcing browser cleanup")
            finally:
                async with self.state_lock:
                    if self.agent_task is task_to_stop:
                        self.agent_task = None

        await self._cleanup_driver()
        await self.log("Agent stopped")

    async def request_intervention(self, user_id: str) -> None:
        message = None
        async with self.state_lock:
            if not self.agent_running:
                message = "Agent is not running. Start the agent before requesting control."
            if self.intervention_active:
                if self.intervention_user == user_id:
                    message = "You already have control"
                else:
                    message = f"Control already held by {self.intervention_user}"
            elif message is None:
                self.intervention_active = True
                self.intervention_user = user_id

        if message:
            await self.log(message)
            return

        await self.broadcast_status()
        await self.log(f"{user_id} took control")

    async def release_intervention(self, user_id: str) -> None:
        message = None
        async with self.state_lock:
            if not self.intervention_active:
                message = "No active intervention to release"
            elif self.intervention_user != user_id:
                message = f"{user_id} cannot release control held by {self.intervention_user}"
            else:
                self.intervention_active = False
                self.intervention_user = None

        if message:
            await self.log(message)
            return

        await self.broadcast_status()
        await self.log(f"{user_id} released control")

    async def pause_check(self) -> None:
        while True:
            async with self.state_lock:
                if not self.agent_running:
                    raise AgentStopped()
                paused = self.intervention_active

            if not paused:
                return

            await asyncio.sleep(0.2)

    async def disconnect_client(self, websocket: WebSocketServerProtocol) -> None:
        if websocket in self.clients:
            self.clients.remove(websocket)

        user_id = self.client_ids.pop(websocket, None)
        if user_id and self.intervention_user == user_id:
            async with self.state_lock:
                self.intervention_active = False
                self.intervention_user = None
            await self.broadcast_status()
            await self.log(f"{user_id} disconnected; control released")

        await self.broadcast_users()

    def _ensure_user_id(self, websocket: WebSocketServerProtocol, message: dict[str, Any]) -> str:
        user_id = message.get("user_id") or self.client_ids.get(websocket)
        if not user_id:
            user_id = f"user-{uuid.uuid4().hex[:8]}"
        self.client_ids[websocket] = user_id
        return user_id

    async def _create_driver(self) -> webdriver.Remote:
        options = ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--remote-debugging-address=0.0.0.0")
        options.add_argument("--disable-features=PasswordManagerOnboarding,PasswordManagerEnabled")
        options.add_argument("--disable-save-password-bubble")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option(
            "prefs",
            {
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
            },
        )
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        return await asyncio.to_thread(
            webdriver.Remote,
            command_executor=self.selenium_url,
            options=options,
        )

    async def _cleanup_driver(self) -> None:
        if not self.driver:
            return

        driver = self.driver
        self.driver = None
        await asyncio.to_thread(driver.quit)


async def _main() -> None:
    server = LiveViewServer()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _stop() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _stop)

    server_task = asyncio.create_task(server.run())
    await stop_event.wait()
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(_main())
