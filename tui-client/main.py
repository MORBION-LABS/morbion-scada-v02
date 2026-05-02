"""
main.py — Mythic TUI Workstation Entry Point
MORBION SCADA v02 — REBOOT
"""
import asyncio
import json
import os
from datetime import datetime

from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, WindowAlign, ConditionalContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.widgets import Frame, TextArea
from prompt_toolkit.filters import Condition

from rich.console import Console
from rich.io import StringIO

# Internal Imports
from connection.rest_client import RestClient
from connection.ws_client import WSClient
from ui.styles import MYTHIC_THEME, ACCENT, DIM, SAFE, WARN, DANGER
from ui.components import UIComponents
from engine.msl_parser import MSLParser
from engine.msl_executor import MSLExecutor
from engine.completer import MSLCompleter

class MorbionTUI:
    def __init__(self):
        # 1. Load Config
        with open("config.json") as f:
            self.config = json.load(f)

        # 2. Connection & Engine
        self.rest = RestClient(self.config["server_host"], self.config["server_port"])
        self.state = {}
        self.cmd_log = []
        self.current_view = "F1" # Overview
        self.mode = "hybrid"     # hybrid | scripting
        
        # 3. Rich for Buffer Rendering
        self.console = Console(file=StringIO(), force_terminal=True, theme=MYTHIC_THEME)
        
        # 4. MSL Executor
        self.executor = MSLExecutor(self.rest, lambda: self.state, self.add_log)

        # 5. UI Elements (Prompt Toolkit)
        self.top_buffer = FormattedTextControl()
        self.watch_buffer = FormattedTextControl()
        self.log_buffer = FormattedTextControl()
        self.input_field = TextArea(
            height=1, prompt="morbion › ", multiline=False, 
            completer=MSLCompleter(), accept_handler=self.on_input
        )

    def add_log(self, msg, style="white"):
        """Add entry to the Scripting Command Log."""
        ts = datetime.now().strftime("%H:%M:%S")
        color = {"accent": ACCENT, "safe": SAFE, "warn": WARN, "danger": DANGER}.get(style, "white")
        self.cmd_log.append(f"[dim]{ts}[/] [{color}]{msg}[/]")
        if len(self.cmd_log) > 50: self.cmd_log.pop(0)
        self.refresh_ui()

    def on_input(self, buffer):
        """Handle Enter key in terminal."""
        cmd = buffer.text.strip()
        if not cmd: return
        
        # Parse and execute
        tokens = MSLParser.parse(cmd)
        if tokens:
            asyncio.create_task(self.executor.run(tokens))
        else:
            self.add_log(f"SYNTAX ERROR: {cmd}", "danger")

    def refresh_ui(self):
        """The Master Render Loop. Converts Rich -> ANSI -> PromptToolkit."""
        # --- 1. Render Top Pane (The Monitor) ---
        self.console.file = StringIO() # Reset buffer
        
        header = UIComponents.create_status_header(self.state)
        self.console.print(header)

        if self.current_view == "F1":
            # 4-Quadrant Overview
            from rich.columns import Columns
            quads = []
            for p in ["pumping_station", "heat_exchanger", "boiler", "pipeline"]:
                p_data = self.state.get(p, {"online": False})
                quads.append(UIComponents.create_register_table(p, p_data))
            self.console.print(Columns(quads, expand=True))
        else:
            # Single Process Deep-Dive
            proc_map = {"F2": "pumping_station", "F3": "heat_exchanger", "F4": "boiler", "F5": "pipeline"}
            p_key = proc_map.get(self.current_view, "pumping_station")
            p_data = self.state.get(p_key, {"online": False})
            self.console.print(UIComponents.create_register_table(p_key, p_data))

        self.top_buffer.text = self.console.file.getvalue()

        # --- 2. Render Watchlist ---
        self.console.file = StringIO()
        wl = self.state.get("alarms", [])
        wl_text = "\n".join([f"[bold red]![/] {a['id']}: {a['sev']}" for a in wl[:10]])
        self.console.print(Panel(wl_text or "[dim]NO ACTIVE ALARMS[/]", title="WATCHLIST", border_style=ACCENT))
        self.watch_buffer.text = self.console.file.getvalue()

        # --- 3. Render Command Log ---
        self.log_buffer.text = "\n".join(self.cmd_log)

    async def run(self):
        # Keybindings
        kb = KeyBindings()
        @kb.add("c-c")
        def _(event): event.app.exit()

        @kb.add("tab")
        def _(event):
            self.mode = "scripting" if self.mode == "hybrid" else "hybrid"
            self.add_log(f"MODE SWAP: {self.mode.upper()}", "accent")

        @kb.add("f1")
        @kb.add("f2")
        @kb.add("f3")
        @kb.add("f4")
        @kb.add("f5")
        def _(event):
            self.current_view = event.key_sequence[0].key.name
            self.add_log(f"VIEW SWAP: {self.current_view}", "accent")

        # Define Layout
        root = HSplit([
            # Top Monitor (70% in Hybrid, 10% in Scripting)
            Window(content=self.top_buffer, height=lambda: 18 if self.mode == "hybrid" else 3),
            # Bottom Scripting Engine (Fixed Frame)
            Frame(
                VSplit([
                    Window(content=self.watch_buffer, width=30), # Left Watchlist
                    Window(content=self.log_buffer, padding=1),  # Right Log
                ]),
                title="[ COMMAND CENTER ]"
            ),
            # Command Line Input
            self.input_field
        ])

        # Start WebSocket Background Task
        self.ws = WSClient(self.config["server_host"], self.config["server_port"], self.ws_callback)
        asyncio.create_task(self.ws.start())

        # Build App
        app = Application(layout=Layout(root), key_bindings=kb, full_screen=True, mouse_support=True)
        await app.run_async()

    def ws_callback(self, data):
        """Called every 1.0s by WSClient."""
        self.state = data
        self.refresh_ui()

if __name__ == "__main__":
    tui = MorbionTUI()
    asyncio.run(tui.run())
