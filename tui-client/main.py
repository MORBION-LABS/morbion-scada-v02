"""
tui/app.py — MORBION TUI Application
MORBION SCADA v02

Textual App. Wires everything together:
  - WebSocket live data feed
  - REST client for commands
  - Executor for all MSL commands
  - Screen management (dashboard, process, alarms, plc, trends)
  - Plant data routing to all active screens

Exit with Ctrl+Q — returns control to main.py menu.
Defensive: WS disconnect handled, screen errors caught,
           all async tasks cancelled cleanly on exit.
"""

import asyncio
from textual.app import App, ComposeResult
from textual.binding import Binding

from core.rest_client import RestClient
from core.ws_client import WSClient
from core.executor import Executor
from core.commands import PROCESS_NAMES

from tui.screens.dashboard import DashboardScreen
from tui.screens.process import ProcessScreen
from tui.screens.alarms import AlarmsScreen
from tui.screens.plc import PLCScreen
from tui.screens.trends import TrendsScreen


class MorbionTUI(App):
    """
    MORBION SCADA v02 — Full-screen TUI Dashboard.

    Lifecycle:
        app = MorbionTUI(config=config)
        app.run()   ← blocks until Ctrl+Q
    """

    TITLE   = "MORBION SCADA v02"
    CSS_PATH = None   # all CSS inline in widgets/screens

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
    ]

    # ── Theme ──────────────────────────────────────────────────────────────────

    DEFAULT_CSS = """
    App {
        background: #02080a;
        color: #d0e8f0;
    }
    Screen {
        background: #02080a;
    }
    """

    def __init__(self, config: dict, **kwargs):
        super().__init__(**kwargs)

        # Config
        self._host     = config.get("server_host", "")
        self._port     = int(config.get("server_port", 5000))
        self._operator = config.get("operator", "OPERATOR")
        self._verify   = int(config.get("verify_timeout_ms", 300))

        # State
        self._plant_cache: dict   = {}
        self._ws_connected: bool  = False
        self._heartbeat:    int   = 0

        # These are set during on_mount after event loop is running
        self._rest:     RestClient | None = None
        self._ws:       WSClient   | None = None
        self._executor: Executor   | None = None
        self._ws_task:  asyncio.Task | None = None
        self._rest_ctx  = None   # async context manager handle

    # ── Screens ───────────────────────────────────────────────────────────────

    SCREENS = {
        "dashboard": DashboardScreen,
        "process":   ProcessScreen,
        "alarms":    AlarmsScreen,
        "plc":       PLCScreen,
        "trends":    TrendsScreen,
    }

    def on_mount(self) -> None:
        """Start REST + WS, push dashboard, begin data feed."""
        # Install all screens
        for name, cls in self.SCREENS.items():
            self.install_screen(cls, name=name)

        # Push dashboard as base screen
        self.push_screen("dashboard")

        # Start async setup
        self.call_later(self._async_setup)

    async def _async_setup(self) -> None:
        """
        Open REST client, start WS feed, create executor.
        Defensive: if server unreachable, TUI still runs — shows OFFLINE.
        """
        if not self._host:
            return

        try:
            # Open REST client — keep it open for app lifetime
            rest = RestClient(self._host, self._port, timeout=10.0)
            await rest.__aenter__()
            self._rest     = rest
            self._rest_ctx = rest

            # Create executor
            self._executor = Executor(
                rest              = rest,
                get_plant         = lambda: self._plant_cache,
                operator          = self._operator,
                verify_timeout_ms = self._verify,
            )

            # Expose rest on app for screens that access it directly
            # (alarms screen loads history via app._rest)
        except Exception as e:
            # REST setup failed — TUI still loads, commands will fail gracefully
            pass

        # Start WebSocket feed as background task
        try:
            self._ws = WSClient(
                host          = self._host,
                port          = self._port,
                on_data       = self._on_ws_data,
                on_connect    = self._on_ws_connect,
                on_disconnect = self._on_ws_disconnect,
            )
            self._ws_task = asyncio.create_task(
                self._ws.run(),
                name="morbion-ws-feed",
            )
        except Exception:
            pass

    # ── WebSocket callbacks ───────────────────────────────────────────────────

    def _on_ws_data(self, data: dict) -> None:
        """
        Called on every WS push. Routes data to all screens.
        Defensive: invalid data silently ignored.
        """
        if not isinstance(data, dict):
            return

        self._plant_cache  = data
        self._ws_connected = True
        self._heartbeat    = (self._heartbeat + 1) % 10000

        # Route to screens — call_from_thread ensures thread safety
        self.call_from_thread(self._route_data, data, self._heartbeat)

    def _route_data(self, data: dict, heartbeat: int) -> None:
        """
        Route plant data to whichever screens are currently mounted.
        Catches all per-screen exceptions — one bad screen never kills feed.
        """
        # Dashboard (always mounted as base)
        try:
            screen = self.get_screen("dashboard")
            if hasattr(screen, "update_plant"):
                screen.update_plant(data, heartbeat)
        except Exception:
            pass

        # Trends (if active)
        try:
            screen = self.get_screen("trends")
            if hasattr(screen, "update_trends"):
                screen.update_trends(data)
        except Exception:
            pass

        # Alarms (if active)
        try:
            screen = self.get_screen("alarms")
            if hasattr(screen, "update_alarms"):
                screen.update_alarms(data.get("alarms", []))
        except Exception:
            pass

        # Process (if active) — cache is enough, it reads from _plant_cache
        try:
            screen = self.get_screen("process")
            if hasattr(screen, "update_process"):
                screen.update_process(data)
        except Exception:
            pass

    async def _on_ws_connect(self) -> None:
        self._ws_connected = True

    async def _on_ws_disconnect(self) -> None:
        self._ws_connected = False

    # ── Cleanup ───────────────────────────────────────────────────────────────

    async def action_quit(self) -> None:
        """Clean shutdown. Cancel WS task, close REST client."""
        await self._shutdown()
        self.exit()

    async def _shutdown(self) -> None:
        """Teardown all async resources."""
        # Stop WS
        if self._ws:
            try:
                self._ws.stop()
            except Exception:
                pass

        if self._ws_task and not self._ws_task.done():
            try:
                self._ws_task.cancel()
                await asyncio.wait_for(self._ws_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass

        # Close REST client
        if self._rest_ctx:
            try:
                await self._rest_ctx.__aexit__(None, None, None)
            except Exception:
                pass

        self._rest     = None
        self._executor = None
        self._ws       = None
