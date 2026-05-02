"""
main.py — MORBION SCADA TUI Main Entry Point
MORBION SCADA v02

Integrates all subsystems: Connection, Engine, Widgets, and Screens.
"""

import json
import os
import asyncio
import logging
from typing import Dict, Any

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static
from textual.containers import Vertical
from textual.binding import Binding
from textual import work

# ── Connections ──
from connection.rest_client import RestClient
from connection.ws_client import WSClient

# ── Engine ──
from engine.parser import MSLParser, MSLParserError
from engine.executor import MSLExecutor
from engine.history import CommandHistory

# ── Screens ──
from screens.dashboard import DashboardScreen
from screens.process import ProcessScreen
from screens.alarms import AlarmsScreen
from screens.plc import PLCScreen
from screens.trends import TrendsScreen

logging.basicConfig(level=logging.INFO, filename="tui_client.log")
log = logging.getLogger("morbion_tui")

class MorbionApp(App):
    """
    The main TUI Application.
    """
    TITLE = "MORBION SCADA v02"
    SUB_TITLE = "Intelligence. Precision. Vigilance."
    
    CSS = """
    MorbionApp {
        background: #02080a;
        color: #d0e8f0;
        font-family: 'Courier New', 'Consolas', monospace;
    }

    #terminal-area {
        height: 4;
        dock: bottom;
        background: #051014;
        border-top: solid #00d4ff;
        padding: 0 1;
    }

    #cmd-input {
        background: #02080a;
        border: none;
        color: #00d4ff;
    }

    #status-line {
        height: 1;
        color: #4a7a8c;
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("f3", "switch_screen('alarms')", "Alarms", show=True),
        Binding("f4", "switch_screen('plc')", "PLC", show=True),
        Binding("f5", "switch_screen('trends')", "Trends", show=True),
        Binding("f6", "switch_screen('dashboard')", "Dashboard", show=True),
        Binding("f10", "quit", "Quit", show=True),
        Binding("escape", "switch_screen('dashboard')", "Home", show=False),
        Binding("up", "history_prev", "Prev Cmd", show=False),
        Binding("down", "history_next", "Next Cmd", show=False),
    ]

    SCREENS = {
        "dashboard": DashboardScreen(),
        "alarms": AlarmsScreen(None, ""), # Initialized in on_mount
        "plc": PLCScreen(None),           # Initialized in on_mount
        "trends": TrendsScreen(),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = self._load_config()
        self.rest = RestClient(self.config["server_host"], self.config["server_port"])
        self.history = CommandHistory()
        self.plant_state = {}
        
        # Executor needs a way to get the latest state for verification
        self.executor = MSLExecutor(self.rest, lambda: self.plant_state)

    def _load_config(self) -> Dict[str, Any]:
        path = os.path.join(os.path.dirname(__file__), "config.json")
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return {"server_host": "localhost", "server_port": 5000, "operator": "OPERATOR"}

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="terminal-area"):
            yield Static("morbion › ", id="status-line")
            yield Input(placeholder="Enter MSL command...", id="cmd-input")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize communication and default screens."""
        # Re-initialize screens that need connections
        self.SCREENS["alarms"] = AlarmsScreen(self.rest, self.config["operator"])
        self.SCREENS["plc"] = PLCScreen(self.rest)
        
        # Start WebSocket Telemetry
        self.ws = WSClient(self.config["server_host"], self.config["server_port"], self.on_telemetry)
        await self.ws.start()
        
        # Default to dashboard
        self.push_screen("dashboard")

    async def on_telemetry(self, data: Dict[str, Any]):
        """WebSocket Callback: Routes data to the active screen."""
        self.plant_state = data
        
        # Update current screen if it supports update_data
        if hasattr(self.screen, "update_data"):
            self.screen.update_data(data)

    async def action_switch_screen(self, screen_id: str) -> None:
        """Navigate between main views."""
        if self.screen.name != screen_id:
            self.push_screen(screen_id)

    def action_history_prev(self):
        """Navigate terminal history up."""
        cmd = self.history.get_prev()
        self.query_one("#cmd-input", Input).value = cmd

    def action_history_next(self):
        """Navigate terminal history down."""
        cmd = self.history.get_next()
        self.query_one("#cmd-input", Input).value = cmd

    @work(exclusive=True)
    async def handle_command(self, raw_input: str) -> None:
        """Process MSL terminal input."""
        input_widget = self.query_one("#cmd-input", Input)
        status_widget = self.query_one("#status-line", Static)
        
        if not raw_input.strip():
            return

        input_widget.value = ""
        self.history.append(raw_input)

        try:
            # 1. Parse
            parsed_cmd = MSLParser.parse(raw_input)
            
            # 2. Execute Internal TUI commands
            if parsed_cmd["verb"] == "cls":
                self.notify("Terminal Cleared")
                return
            
            if parsed_cmd["verb"] == "read" and len(parsed_cmd["args"]) == 1:
                target = parsed_cmd["args"][0]
                if target in ["pumping_station", "heat_exchanger", "boiler", "pipeline"]:
                    # Semantic: 'read process' switches to that process view
                    labels = {
                        "pumping_station": "Pumping Station",
                        "heat_exchanger": "Heat Exchanger",
                        "boiler": "Steam Boiler",
                        "pipeline": "Petroleum Pipeline"
                    }
                    self.install_screen(ProcessScreen(target, labels[target]), name=f"proc-{target}")
                    self.push_screen(f"proc-{target}")
                    return

            # 3. Execute MSL commands via Executor
            result = await self.executor.execute(parsed_cmd)
            
            # 4. Feedback
            status_widget.update(f"morbion › [dim]{raw_input}[/]")
            self.notify(result, title="MSL EXEC", timeout=4)

        except MSLParserError as e:
            self.notify(str(e), title="SYNTAX ERROR", severity="error")
        except Exception as e:
            self.notify(f"System Error: {e}", severity="error")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Event triggered when Enter is pressed in the cmd-input."""
        self.handle_command(event.value)

    async def on_unmount(self) -> None:
        """Graceful shutdown."""
        if hasattr(self, "ws"):
            self.ws.stop()

if __name__ == "__main__":
    app = MorbionApp()
    app.run()
