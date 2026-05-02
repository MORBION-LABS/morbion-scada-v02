"""
tui/screens/dashboard.py — MORBION TUI Main Dashboard
MORBION SCADA v02

2×2 process grid + event log + command bar.
Updates on every WebSocket push.
Command bar activated with ':' key. Full MSL. Tab complete. Esc dismisses.
Defensive: all data access guarded, WS disconnect handled gracefully.
"""

import asyncio
import datetime
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Input, Label, RichLog
from textual.containers import Horizontal, Vertical, Container
from textual.binding import Binding
from textual.reactive import reactive
from rich.text import Text

from tui.widgets.process_panel import ProcessPanel
from core.commands import PROCESS_NAMES, get_completions

_CYAN  = "#00d4ff"
_GREEN = "#00ff88"
_RED   = "#ff3333"
_AMBER = "#ffaa00"
_DIM   = "#4a7a8c"
_TEXT  = "#d0e8f0"


class DashboardScreen(Screen):
    """
    Main dashboard. Launched by TUI app on startup.
    Receives plant data via app.plant_data reactive.
    """

    BINDINGS = [
        Binding("colon",   "show_command",  "Command",   show=True),
        Binding("f2",      "goto_process",  "Process",   show=True),
        Binding("f3",      "goto_alarms",   "Alarms",    show=True),
        Binding("f4",      "goto_plc",      "PLC",       show=True),
        Binding("f5",      "goto_trends",   "Trends",    show=True),
        Binding("ctrl+q",  "quit_app",      "Quit",      show=True),
        Binding("escape",  "hide_command",  "Close Cmd", show=False),
    ]

    DEFAULT_CSS = """
    DashboardScreen {
        background: #02080a;
    }

    #header-bar {
        height: 1;
        background: #051014;
        border-bottom: solid #0a2229;
        padding: 0 2;
    }

    #grid {
        height: 1fr;
        layout: grid;
        grid-size: 2 2;
        grid-gutter: 1;
        padding: 1;
    }

    #event-log {
        height: 6;
        border-top: solid #0a2229;
        background: #051014;
        padding: 0 1;
    }

    #alarm-banner {
        height: 1;
        background: #051014;
        padding: 0 2;
        display: none;
    }

    #alarm-banner.visible {
        display: block;
    }

    #cmd-bar {
        height: 3;
        border-top: solid #00d4ff;
        background: #051014;
        padding: 0 1;
        display: none;
    }

    #cmd-bar.visible {
        display: block;
    }

    #cmd-input {
        background: #02080a;
        border: none;
        color: #d0e8f0;
        padding: 0 1;
    }

    #cmd-label {
        color: #00d4ff;
        padding: 0 1;
        height: 1;
    }

    #cmd-result {
        color: #4a7a8c;
        height: 1;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._panels: dict[str, ProcessPanel] = {}
        self._cmd_history: list[str] = []
        self._cmd_pos: int = 0
        self._heartbeat: int = 0

    def compose(self) -> ComposeResult:
        # Header bar
        yield Label("", id="header-bar")

        # Alarm banner
        yield Label("", id="alarm-banner")

        # 2×2 process grid
        with Container(id="grid"):
            for proc in PROCESS_NAMES:
                panel = ProcessPanel(proc, id=f"panel-{proc}")
                self._panels[proc] = panel
                yield panel

        # Event log
        yield RichLog(id="event-log", markup=True, highlight=False,
                      max_lines=50, wrap=False)

        # Command bar
        with Container(id="cmd-bar"):
            yield Label("morbion ›", id="cmd-label")
            yield Input(placeholder="type command... Tab to complete  Esc to close",
                        id="cmd-input")
            yield Label("", id="cmd-result")

    def on_mount(self) -> None:
        self._update_header()

    # ── Data update ───────────────────────────────────────────────────────────

    def update_plant(self, data: dict, heartbeat: int) -> None:
        """
        Called by TUI app on every WS push.
        Routes data to each process panel and event log.
        Defensive: guards all dict access.
        """
        if not isinstance(data, dict):
            return

        self._heartbeat = heartbeat
        self._update_header(data, heartbeat)
        self._update_alarm_banner(data.get("alarms", []))

        prev_data = getattr(self, "_prev_data", {})

        for proc in PROCESS_NAMES:
            proc_data = data.get(proc, {})
            if not isinstance(proc_data, dict):
                continue
            panel = self._panels.get(proc)
            if panel:
                try:
                    panel.update_data(proc_data)
                except Exception:
                    pass

            # Event log — detect state changes
            self._log_changes(proc, prev_data.get(proc, {}), proc_data)

        self._prev_data = data

    def _update_header(self, data: dict | None = None,
                       heartbeat: int = 0) -> None:
        """Update the header bar label."""
        try:
            bar = self.query_one("#header-bar", Label)
        except Exception:
            return

        app = self.app
        host = getattr(app, "_host", "")
        port = getattr(app, "_port", 5000)

        connected = getattr(app, "_ws_connected", False)
        conn_str  = f"[{_GREEN}]●LIVE[/{_GREEN}]" if connected else f"[{_RED}]○DISCONNECTED[/{_RED}]"

        now = datetime.datetime.now().strftime("%H:%M:%S")
        hb  = f"♥{heartbeat % 100:02d}"

        n_online = 0
        if data:
            for p in PROCESS_NAMES:
                if data.get(p, {}).get("online"):
                    n_online += 1

        online_str = f"[{_GREEN}]{n_online}/4[/{_GREEN}]" if n_online == 4 else f"[{_AMBER}]{n_online}/4[/{_AMBER}]"

        bar.update(
            f"[{_CYAN}]◈ MORBION SCADA v02[/{_CYAN}]  "
            f"{conn_str}  "
            f"[{_DIM}]{host}:{port}[/{_DIM}]  "
            f"{online_str} online  "
            f"[{_DIM}]{now}[/{_DIM}]  "
            f"[{_DIM}]{hb}[/{_DIM}]"
        )

    def _update_alarm_banner(self, alarms: list) -> None:
        """Show/hide alarm banner based on active unacked alarms."""
        try:
            banner = self.query_one("#alarm-banner", Label)
        except Exception:
            return

        if not isinstance(alarms, list):
            alarms = []

        unacked = [a for a in alarms if isinstance(a, dict) and not a.get("acked")]

        if not unacked:
            banner.remove_class("visible")
            return

        crits = sum(1 for a in unacked if a.get("sev") == "CRIT")
        highs = sum(1 for a in unacked if a.get("sev") == "HIGH")

        colour = _RED if crits else _AMBER
        banner.update(
            f"[{colour}]⚠ {len(unacked)} ACTIVE ALARM(S)"
            f"{'  —  ' + str(crits) + ' CRITICAL' if crits else ''}"
            f"{'  —  ' + str(highs) + ' HIGH' if highs else ''}"
            f"    [F3] to view[/{colour}]"
        )
        banner.add_class("visible")

    def _log_changes(self, proc: str, prev: dict, curr: dict) -> None:
        """Log meaningful state changes to the event log."""
        if not curr.get("online"):
            return

        try:
            log = self.query_one("#event-log", RichLog)
        except Exception:
            return

        watch_fields = {
            "pumping_station": ["pump_running", "fault_code", "tank_level_pct"],
            "heat_exchanger":  ["fault_code", "efficiency_pct"],
            "boiler":          ["burner_state", "fault_code", "drum_pressure_bar"],
            "pipeline":        ["duty_pump_running", "fault_code", "leak_flag"],
        }

        fields = watch_fields.get(proc, ["fault_code"])
        now    = datetime.datetime.now().strftime("%H:%M:%S")

        for field in fields:
            old_val = prev.get(field)
            new_val = curr.get(field)
            if old_val is None or new_val is None:
                continue
            # Only log actual changes
            try:
                changed = old_val != new_val
            except Exception:
                changed = str(old_val) != str(new_val)

            if changed:
                colour = _RED if field == "fault_code" and new_val != 0 else _DIM
                try:
                    log.write(
                        f"[{_DIM}]{now}[/{_DIM}]  "
                        f"[{_CYAN}]{proc:<25}[/{_CYAN}]"
                        f"[{_TEXT}]{field:<30}[/{_TEXT}]"
                        f"[{colour}]{old_val} → {new_val}[/{colour}]"
                    )
                except Exception:
                    pass

    # ── Command bar ───────────────────────────────────────────────────────────

    def action_show_command(self) -> None:
        """Show command bar and focus input."""
        try:
            bar = self.query_one("#cmd-bar")
            bar.add_class("visible")
            inp = self.query_one("#cmd-input", Input)
            inp.focus()
            self.query_one("#cmd-result", Label).update("")
        except Exception:
            pass

    def action_hide_command(self) -> None:
        """Hide command bar."""
        try:
            self.query_one("#cmd-bar").remove_class("visible")
            self.query_one("#cmd-input", Input).value = ""
            self.query_one("#cmd-result", Label).update("")
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Execute command from command bar."""
        if event.input.id != "cmd-input":
            return

        line = event.value.strip()
        if not line:
            return

        event.input.value = ""
        self._cmd_history.append(line)
        self._cmd_pos = len(self._cmd_history)

        # Show "running..." feedback
        try:
            self.query_one("#cmd-result", Label).update(
                f"[{_DIM}]Running: {line[:60]}...[/{_DIM}]"
            )
        except Exception:
            pass

        # Execute via app executor
        try:
            executor = getattr(self.app, "_executor", None)
            if executor is None:
                self._cmd_feedback("No executor — is server connected?", _RED)
                return

            tokens = line.split()
            verb   = tokens[0].lower() if tokens else ""
            args   = tokens[1:]

            handler_map = {
                "read":   executor.cmd_read,
                "write":  lambda a: executor.cmd_write(a, "write"),
                "inject": executor.cmd_inject,
                "fault":  executor.cmd_fault,
                "alarms": executor.cmd_alarms,
                "plc":    executor.cmd_plc,
                "status": executor.cmd_status,
                "help":   executor.cmd_help,
            }

            handler = handler_map.get(verb)
            if not handler:
                self._cmd_feedback(f"Unknown: {verb!r} — type help", _AMBER)
                return

            result = await handler(args)

            if result and result.lines:
                # Show last meaningful line as feedback
                for text, style in reversed(result.lines):
                    if text and not text.startswith("__"):
                        colour_map = {
                            "green": _GREEN, "red": _RED,
                            "amber": _AMBER, "cyan": _CYAN,
                            "dim":   _DIM,   "white": _WHITE,
                        }
                        c = colour_map.get(style, _TEXT)
                        self._cmd_feedback(text.strip(), c)
                        break
                # Also log to event log
                try:
                    log = self.query_one("#event-log", RichLog)
                    log.write(f"[{_CYAN}]› {line}[/{_CYAN}]")
                    for text, style_key in result.lines[:3]:
                        if text and not text.startswith("__"):
                            log.write(f"  [{_DIM}]{text[:80]}[/{_DIM}]")
                except Exception:
                    pass

        except Exception as e:
            self._cmd_feedback(f"Error: {e}", _RED)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Tab completion on input change — triggered by Tab key."""
        pass  # Tab completion handled via key binding below

    async def on_key(self, event) -> None:
        """Handle Tab completion and history in command input."""
        inp = self.query_one("#cmd-input", Input)
        if not inp.has_focus:
            return

        if event.key == "tab":
            event.prevent_default()
            current = inp.value
            tokens  = current.split()
            if current.endswith(" "):
                tokens.append("")
            completions = get_completions(tokens)
            if len(completions) == 1:
                # Auto-complete
                tokens[-1] = completions[0]
                inp.value  = " ".join(tokens) + " "
                inp.cursor_position = len(inp.value)
            elif len(completions) > 1:
                self._cmd_feedback(
                    "  ".join(completions[:8]), _DIM
                )

        elif event.key == "up":
            event.prevent_default()
            if self._cmd_history and self._cmd_pos > 0:
                self._cmd_pos -= 1
                inp.value = self._cmd_history[self._cmd_pos]
                inp.cursor_position = len(inp.value)

        elif event.key == "down":
            event.prevent_default()
            if self._cmd_pos < len(self._cmd_history) - 1:
                self._cmd_pos += 1
                inp.value = self._cmd_history[self._cmd_pos]
                inp.cursor_position = len(inp.value)
            else:
                self._cmd_pos = len(self._cmd_history)
                inp.value = ""

    def _cmd_feedback(self, text: str, colour: str) -> None:
        """Update command result label."""
        try:
            label = self.query_one("#cmd-result", Label)
            label.update(f"[{colour}]{text[:120]}[/{colour}]")
        except Exception:
            pass

    # ── Navigation actions ────────────────────────────────────────────────────

    def action_goto_process(self) -> None:
        self.app.push_screen("process")

    def action_goto_alarms(self) -> None:
        self.app.push_screen("alarms")

    def action_goto_plc(self) -> None:
        self.app.push_screen("plc")

    def action_goto_trends(self) -> None:
        self.app.push_screen("trends")

    def action_quit_app(self) -> None:
        self.app.exit()
