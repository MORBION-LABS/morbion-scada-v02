"""
tui/screens/alarms.py — Alarm Management Screen
MORBION SCADA v02

Active alarm table + history table.
ACK ALL button. Individual row acknowledge.
Auto-refreshes on every WS push.
Defensive: None alarm lists, missing fields, ack failures.
"""

import asyncio
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Label, Button, RichLog
from textual.containers import Horizontal, Vertical, Container
from textual.binding import Binding

from tui.widgets.alarm_table import AlarmTable

_CYAN  = "#00d4ff"
_GREEN = "#00ff88"
_RED   = "#ff3333"
_AMBER = "#ffaa00"
_DIM   = "#4a7a8c"
_TEXT  = "#d0e8f0"


class AlarmsScreen(Screen):
    """Alarm management — active alarms + history."""

    BINDINGS = [
        Binding("escape", "go_back",     "Dashboard", show=True),
        Binding("f2",     "goto_process","Process",   show=True),
        Binding("a",      "ack_all",     "ACK ALL",   show=True),
    ]

    DEFAULT_CSS = """
    AlarmsScreen {
        background: #02080a;
    }
    #alarm-header {
        height: 1;
        background: #051014;
        padding: 0 2;
        border-bottom: solid #0a2229;
    }
    #alarm-toolbar {
        height: 3;
        background: #051014;
        padding: 0 2;
        border-bottom: solid #0a2229;
    }
    #active-label {
        height: 1;
        padding: 0 2;
        color: #00d4ff;
    }
    #active-table {
        height: 1fr;
        border: solid #0a2229;
    }
    #history-label {
        height: 1;
        padding: 0 2;
        color: #4a7a8c;
    }
    #history-log {
        height: 10;
        border-top: solid #0a2229;
        background: #051014;
        padding: 0 1;
    }
    #alarm-feedback {
        height: 1;
        padding: 0 2;
    }
    Button {
        background: #051014;
        border: solid #0a2229;
        color: #d0e8f0;
        margin: 0 1;
    }
    Button:hover {
        border: solid #00d4ff;
        color: #00d4ff;
    }
    Button.-ack {
        border: solid #ffaa00;
        color: #ffaa00;
    }
    Button.-ack:hover {
        background: #ffaa00;
        color: #02080a;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_alarms: list = []

    def compose(self) -> ComposeResult:
        yield Label(
            f"[{_CYAN}]◈ ALARM MANAGEMENT[/{_CYAN}]",
            id="alarm-header"
        )

        with Horizontal(id="alarm-toolbar"):
            yield Button("ACK ALL",      id="btn-ack-all",  classes="-ack")
            yield Button("LOAD HISTORY", id="btn-history")
            yield Label("", id="alarm-feedback")

        yield Label(
            f"[{_CYAN}]ACTIVE ALARMS[/{_CYAN}]",
            id="active-label"
        )
        yield AlarmTable(id="active-table")

        yield Label(
            f"[{_DIM}]ALARM HISTORY (last 20)[/{_DIM}]",
            id="history-label"
        )
        yield RichLog(
            id="history-log",
            markup=True, highlight=False,
            max_lines=20, wrap=False
        )

    def on_mount(self) -> None:
        # Load initial data
        plant = getattr(self.app, "_plant_cache", {})
        alarms = plant.get("alarms", [])
        self._refresh_alarms(alarms)

    def update_alarms(self, alarms: list) -> None:
        """Called by TUI app on every WS push."""
        self._active_alarms = alarms if isinstance(alarms, list) else []
        self._refresh_alarms(self._active_alarms)

    def _refresh_alarms(self, alarms: list) -> None:
        """Refresh the active alarm table."""
        try:
            table = self.query_one("#active-table", AlarmTable)
            table.update_alarms(alarms)
        except Exception:
            pass

        # Update header count
        try:
            n      = len(alarms) if alarms else 0
            unacked= sum(1 for a in (alarms or []) if not a.get("acked"))
            crits  = sum(1 for a in (alarms or []) if a.get("sev") == "CRIT")
            colour = _RED if crits else (_AMBER if n else _GREEN)
            self.query_one("#active-label", Label).update(
                f"[{_CYAN}]ACTIVE ALARMS[/{_CYAN}]  "
                f"[{colour}]{n} total  {unacked} unacked  {crits} CRIT[/{colour}]"
            )
        except Exception:
            pass

    # ── Buttons ───────────────────────────────────────────────────────────────

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        if btn_id == "btn-ack-all":
            await self._ack_all()

        elif btn_id == "btn-history":
            await self._load_history()

    async def _ack_all(self) -> None:
        """Acknowledge all active alarms."""
        executor = getattr(self.app, "_executor", None)
        if not executor:
            self._feedback("No executor", _RED)
            return
        try:
            op     = getattr(self.app, "_operator", "OPERATOR")
            result = await executor.cmd_alarms(["acknowledge", "all"])
            if result and result.ok:
                self._feedback("All alarms acknowledged", _GREEN)
            else:
                self._feedback("ACK failed", _RED)
        except Exception as e:
            self._feedback(f"Error: {e}", _RED)

    async def _load_history(self) -> None:
        """Load alarm history into the history log."""
        try:
            rest = getattr(self.app, "_rest", None)
            if not rest:
                self._feedback("No REST client", _RED)
                return

            history = await rest.get_alarm_history()
            log     = self.query_one("#history-log", RichLog)
            log.clear()

            if not history:
                log.write(f"[{_DIM}]No history[/{_DIM}]")
                return

            recent = history[-20:]
            for alarm in reversed(recent):
                if not isinstance(alarm, dict):
                    continue
                sev    = alarm.get("sev", "")
                colour = {
                    "CRIT": _RED, "HIGH": _AMBER
                }.get(sev, _DIM)
                log.write(
                    f"[{_DIM}]{alarm.get('ts',''):<10}[/{_DIM}]"
                    f"[{_CYAN}]{alarm.get('id',''):<10}[/{_CYAN}]"
                    f"[{colour}]{sev:<6}[/{colour}]"
                    f"[{_DIM}]{alarm.get('process',''):<22}[/{_DIM}]"
                    f"[{_TEXT}]{alarm.get('desc','')}[/{_TEXT}]"
                )
            self._feedback(f"Loaded {len(recent)} history entries", _DIM)
        except Exception as e:
            self._feedback(f"History error: {e}", _RED)

    def _feedback(self, text: str, colour: str) -> None:
        try:
            self.query_one("#alarm-feedback", Label).update(
                f"[{colour}]{text}[/{colour}]"
            )
        except Exception:
            pass

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_goto_process(self) -> None:
        self.app.push_screen("process")

    def action_ack_all(self) -> None:
        self.app.call_later(self._ack_all)
