"""
alarms.py — Alarm Management Screen
MORBION SCADA v02

Provides a centralized interface for viewing and acknowledging process alarms.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Label, Button
from textual.binding import Binding

from widgets.alarm_table import AlarmTable

class AlarmsScreen(Screen):
    """
    Alarm monitoring and acknowledgement interface.
    """
    DEFAULT_CSS = """
    AlarmsScreen #main-container {
        padding: 1;
        background: #02080a;
    }

    .alarm-header {
        height: 3;
        border-bottom: double #ff3333;
        margin-bottom: 1;
    }

    .alarm-title {
        color: #ff3333;
        text-style: bold;
        width: 40;
    }

    .info-bar {
        height: 1;
        color: #4a7a8c;
        margin-bottom: 1;
    }

    #ack-panel {
        height: 3;
        padding: 0 1;
        background: #051014;
        border-top: solid #0a2229;
        dock: bottom;
        content-align: right middle;
    }

    #ack-panel Label {
        margin-right: 2;
    }
    """

    BINDINGS = [
        Binding("enter", "acknowledge_selected", "Ack Selected", show=True),
        Binding("a", "acknowledge_all", "Ack All", show=True),
        Binding("h", "load_history", "Refresh History", show=True),
    ]

    def __init__(self, rest_client, operator_name: str, **kwargs):
        super().__init__(**kwargs)
        self.rest = rest_client
        self.operator = operator_name
        self.active_alarms = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            with Horizontal(classes="alarm-header"):
                yield Label("SYSTEM ALARMS & EVENTS", classes="alarm-title")
            
            yield Label("Select an alarm and press ENTER to acknowledge.", classes="info-bar")
            
            yield AlarmTable(id="alarm-grid")

            with Horizontal(id="ack-panel"):
                yield Label("Operator: [cyan]" + self.operator + "[/]")
                yield Button("ACK ALL (A)", variant="warning", id="btn-ack-all")

        yield Footer()

    def update_data(self, data: dict):
        """
        Receives the full plant snapshot via WebSocket and extracts alarms.
        """
        self.active_alarms = data.get("alarms", [])
        table = self.query_one("#alarm-grid", AlarmTable)
        table.update_alarms(self.active_alarms)

    async def action_acknowledge_selected(self) -> None:
        """Acknowledge the currently highlighted alarm row."""
        table = self.query_one("#alarm-grid", AlarmTable)
        if table.cursor_row is None:
            return

        # Get ID from the first cell of the selected row
        # Textual DataTable row data is a list of segments/strings
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate)
        row_data = table.get_row(row_key.row_key)
        
        # Extract ID (removing rich text tags if present)
        raw_id = str(row_data[0])
        alarm_id = raw_id.split(']')[-1].split('[')[0] if ']' in raw_id else raw_id

        await self._do_ack(alarm_id)

    async def action_acknowledge_all(self) -> None:
        """Acknowledge all unacknowledged alarms."""
        await self._do_ack("all")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-ack-all":
            await self.action_acknowledge_all()

    async def _do_ack(self, alarm_id: str):
        """Execute the acknowledgement REST call."""
        result = await self.rest.ack_alarm(alarm_id, self.operator)
        if result.get("ok"):
            self.notify(f"Alarm {alarm_id} acknowledged", title="SUCCESS", severity="information")
        else:
            self.notify(f"Failed to ack {alarm_id}: {result.get('error')}", title="ERROR", severity="error")

    async def action_load_history(self) -> None:
        """Fetch historical alarms from the REST API."""
        history = await self.rest._request("GET", "/alarms/history")
        if isinstance(history, list):
            table = self.query_one("#alarm-grid", AlarmTable)
            table.update_alarms(history)
            self.notify("History loaded (Last 200 events)", title="REFRESH")
