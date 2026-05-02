"""
main.py — Mythic TUI Workstation Entry Point
MORBION SCADA v02 — REBOOT (VERIFIED PT API)
"""
import asyncio
import json
import os
from io import StringIO
from datetime import datetime

from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.widgets import Frame, TextArea
from prompt_toolkit.formatted_text import ANSI

from rich.console import Console
from rich.panel import Panel

# Internal Imports
from connection.rest_client import RestClient
from connection.ws_client import WSClient
from ui.styles import MYTHIC_THEME, ACCENT, SAFE, WARN, DANGER
from ui.components import UIComponents
from engine.msl_parser import MSLParser
from engine.msl_executor import MSLExecutor
from engine.completer import MSLCompleter

class MorbionTUI:
    def __init__(self):
        # 1. Load Config
        if not os.path.exists("config.json"):
            raise FileNotFoundError("Run installer.py first.")
            
        with open("config.json") as f:
            self.config = json.load(f)

        # 2. State & Mode Initialisation
        self.state = {}
        self.cmd_log = []
        self.current_view = "F1" 
        self.mode = "hybrid"     # Initialised to prevent AttributeError
        
        # 3. Connection & Engine
        self.rest = RestClient(self.config["server_host"], self.config["server_port"])
        self.executor = MSLExecutor(self.rest, lambda: self.state, self.add_log)

        # 4. Rich for Buffer Rendering
        self.render_buffer = StringIO()
        self.console = Console(file=self.render_buffer, force_terminal=True, theme=MYTHIC_THEME)
        
        # 5. UI Controls (Prompt Toolkit)
        self.top_control = FormattedTextControl()
        self.watch_control = FormattedTextControl()
        self.log_control = FormattedTextControl()
        
        self.input_field = TextArea(
            height=1, 
            prompt="morbion › ", 
            multiline=False, 
            wrap_lines=False,
            completer=MSLCompleter(), 
            accept_handler=self.on_input
        )

    def add_log(self, msg, style="white"):
        """Add entry to the Scripting Command Log with ANSI colors."""
        ts = datetime.now().strftime("%H:%M:%S")
        # ANSI color codes: 36=Cyan, 32=Green, 33=Amber, 31=Red
        color_code = {"accent": "36", "safe": "32", "warn": "33", "danger": "31"}.get(style, "37")
        self.cmd_log.append(f"\x1b[90m{ts}\x1b[0m \x1b[{color_code}m{msg}\x1b[0m")
        if len(self.cmd_log) > 50: self.cmd_log.pop(0)
        self.refresh_ui()

    def on_input(self, buffer):
        """Handle Enter key in terminal input."""
        cmd = buffer.text.strip()
        if not cmd: return
        buffer.text = "" # Clear buffer
        
        try:
            tokens = MSLParser.parse(cmd)
            if tokens:
                asyncio.create_task(self.executor.run(tokens))
            else:
                self.add_log(f"SYNTAX ERROR: {cmd}", "danger")
        except Exception as e:
            self.add_log(f"PARSER ERROR: {e}", "danger")

    def refresh_ui(self):
        """Standardised Render Loop: Rich -> ANSI -> PromptToolkit."""
        # --- 1. Top Pane ---
        self.render_buffer.truncate(0)
        self.render_buffer.seek(0)
        
        header = UIComponents.create_status_header(self.state)
        self.console.print(header)

        if self.current_view == "F1":
            from rich.columns import Columns
            quads = []
            for p in ["pumping_station", "heat_exchanger", "boiler", "pipeline"]:
                p_data = self.state.get(p, {"online": False})
                quads.append(UIComponents.create_register_table(p, p_data))
            self.console.print(Columns(quads, expand=True))
        else:
            proc_map = {"F2": "pumping_station", "F3": "heat_exchanger", "F4": "boiler", "F5": "pipeline"}
            p_key = proc_map.get(self.current_view, "pumping_station")
            p_data = self.state.get(p_key, {"online": False})
            self.console.print(UIComponents.create_register_table(p_key, p_data))

        self.top_control.text = ANSI(self.render_buffer.getvalue())

        # --- 2. Watchlist ---
        self.render_buffer.truncate(0)
        self.render_buffer.seek(0)
        wl_data = self.state.get("alarms", [])
        wl_text = "\n".join([f"![{a['sev']}] {a['id']}" for a in wl_data[:10]])
        self.console.print(Panel(wl_text or "SYSTEM NOMINAL", title="WATCHLIST", border_style="cyan"))
        self.watch_control.text = ANSI(self.render_buffer.getvalue())

        # --- 3. Log ---
        self.log_control.text = ANSI("\n".join(self.cmd_log))

    async def run(self):
        # Keybindings
        kb = KeyBindings()
        @kb.add("c-c")
        def _(event): event.app.exit()

        @kb.add("tab")
        def _(event):
            self.mode = "scripting" if self.mode == "hybrid" else "hybrid"
            self.add_log(f"MODE: {self.mode.upper()}", "accent")

        @kb.add("f1")
        @kb.add("f2")
        @kb.add("f3")
        @kb.add("f4")
        @kb.add("f5")
        def _(event):
            self.current_view = event.key_sequence[0].key.name
            self.add_log(f"VIEW: {self.current_view}", "accent")

        # Layout Logic (Surgically Fixed: Removed HALLUCINATED padding argument)
        root = HSplit([
            Window(content=self.top_control, height=lambda: 18 if self.mode == "hybrid" else 3),
            Frame(
                VSplit([
                    Window(content=self.watch_control, width=32),
                    Window(content=self.log_control), # Fixed: padding removed
                ]),
                title="[ MORBION COMMAND CENTER ]"
            ),
            self.input_field
        ])

        # WebSocket Task
        self.ws = WSClient(self.config["server_host"], self.config["server_port"], self.ws_callback)
        asyncio.create_task(self.ws.start())

        # App Launch
        app = Application(layout=Layout(root), key_bindings=kb, full_screen=True, mouse_support=True)
        await app.run_async()

    def ws_callback(self, data):
        self.state = data
        self.refresh_ui()

if __name__ == "__main__":
    tui = MorbionTUI()
    try:
        asyncio.run(tui.run())
    except KeyboardInterrupt:
        pass
