"""
main.py — Mythic TUI Workstation
MORBION SCADA v02 — REBOOT (FIXED CALLBACKS)
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
from rich.columns import Columns
from rich.panel import Panel

# Internal Imports
from connection.rest_client import RestClient
from connection.ws_client import WSClient
from ui.styles import MYTHIC_THEME, ACCENT, SAFE
from ui.components import UIComponents
from engine.msl_parser import MSLParser
from engine.msl_executor import MSLExecutor
from engine.completer import MSLCompleter

class MorbionTUI:
    def __init__(self):
        with open("config.json") as f: self.config = json.load(f)
        self.state = {}
        self.cmd_log = []
        self.current_view = "F1" 
        self.mode = "hybrid"
        
        self.rest = RestClient(self.config["server_host"], self.config["server_port"])
        # FIXED: Passing all 5 required arguments
        self.executor = MSLExecutor(self.rest, lambda: self.state, self.add_log, self.set_view, self.set_mode)

        self.render_buffer = StringIO()
        self.console = Console(file=self.render_buffer, force_terminal=True, theme=MYTHIC_THEME)
        
        self.top_control = FormattedTextControl()
        self.watch_control = FormattedTextControl()
        self.log_control = FormattedTextControl()
        self.input_field = TextArea(height=1, prompt="morbion › ", multiline=False, completer=MSLCompleter(), accept_handler=self.on_input)

    def add_log(self, msg, style="white"):
        ts = datetime.now().strftime("%H:%M:%S")
        color_code = {"accent": "36", "safe": "32", "warn": "33", "danger": "31"}.get(style, "37")
        self.cmd_log.append(f"\x1b[90m{ts}\x1b[0m \x1b[{color_code}m{msg}\x1b[0m")
        if len(self.cmd_log) > 100: self.cmd_log.pop(0)
        self.refresh_ui()

    def set_view(self, v): self.current_view = v; self.refresh_ui()
    def set_mode(self, m): self.mode = m; self.refresh_ui()

    def on_input(self, buffer):
        cmd = buffer.text.strip()
        if not cmd: return
        buffer.text = ""
        try:
            tokens = MSLParser.parse(cmd)
            if tokens: asyncio.create_task(self.executor.run(tokens))
        except Exception as e: self.add_log(f"PARSER ERR: {e}", "danger")

    def refresh_ui(self):
        self.render_buffer.truncate(0); self.render_buffer.seek(0)
        self.console.print(UIComponents.create_status_header(self.state))
        
        if self.current_view == "F1":
            cards = [UIComponents.create_process_card(p, self.state.get(p, {})) for p in ["pumping_station", "heat_exchanger", "boiler", "pipeline"]]
            self.console.print(Columns(cards, expand=True))
        else:
            proc_map = {"F2":"pumping_station", "F3":"heat_exchanger", "F4":"boiler", "F5":"pipeline"}
            p_key = proc_map.get(self.current_view, "pumping_station")
            self.console.print(UIComponents.create_process_card(p_key, self.state.get(p_key, {})))

        self.top_control.text = ANSI(self.render_buffer.getvalue())
        
        self.render_buffer.truncate(0); self.render_buffer.seek(0)
        alarms = self.state.get("alarms", [])
        wl_text = "\n".join([f"![{a['sev']}] {a['id']} {a['desc'][:20]}" for a in alarms[:8]])
        self.console.print(Panel(wl_text or "SYSTEM NOMINAL", title="WATCHLIST", border_style="cyan"))
        self.watch_control.text = ANSI(self.render_buffer.getvalue())
        self.log_control.text = ANSI("\n".join(self.cmd_log[-15:]))

    async def run(self):
        kb = KeyBindings()
        @kb.add("c-c")
        def _(e): e.app.exit()

        root = HSplit([
            Window(content=self.top_control, height=lambda: 18 if self.mode == "hybrid" else 3),
            Frame(VSplit([Window(content=self.watch_control, width=35), Window(content=self.log_control)]), title="[ MORBION COMMAND CENTER ]"),
            self.input_field
        ])

        self.ws = WSClient(self.config["server_host"], self.config["server_port"], self.ws_callback)
        asyncio.create_task(self.ws.start())
        await Application(layout=Layout(root), key_bindings=kb, full_screen=True).run_async()

    def ws_callback(self, data):
        self.state = data; self.refresh_ui()

if __name__ == "__main__":
    tui = MorbionTUI()
    try: asyncio.run(tui.run())
    except KeyboardInterrupt: pass
