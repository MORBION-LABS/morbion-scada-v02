"""
tui/widgets/alarm_table.py — Alarm DataTable Widget
MORBION SCADA v02

Rich DataTable subclass showing active alarms.
Colour-coded by severity: CRIT=red, HIGH=amber, MED=dim amber, LOW=dim.
Acked alarms shown dim regardless of severity.
Defensive: handles empty alarm list, missing fields, None values.
"""

from textual.widgets import DataTable
from textual.reactive import reactive
from rich.text import Text

_RED   = "#ff3333"
_AMBER = "#ffaa00"
_DIM   = "#4a7a8c"
_TEXT  = "#d0e8f0"
_GREEN = "#00ff88"

SEV_COLOUR = {
    "CRIT": _RED,
    "HIGH": _AMBER,
    "MED":  _AMBER,
    "LOW":  _DIM,
}

COLUMNS = ["TIME", "ID", "SEV", "PROCESS", "TAG", "DESCRIPTION"]


class AlarmTable(DataTable):
    """
    Live alarm table. Call update_alarms(alarm_list) to refresh.
    alarm_list items follow the MORBION alarm structure:
      {id, process, tag, sev, desc, ts, acked, acked_at, acked_by}
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._alarms: list = []

    def on_mount(self) -> None:
        """Add columns on mount."""
        self.clear(columns=True)
        for col in COLUMNS:
            self.add_column(col, key=col)

    def update_alarms(self, alarms: list | None) -> None:
        """
        Refresh table from alarm list.
        Defensive: None → empty list, missing fields → default strings.
        """
        if alarms is None:
            alarms = []

        self._alarms = alarms
        self.clear()

        if not alarms:
            return

        for alarm in alarms:
            if not isinstance(alarm, dict):
                continue

            sev    = str(alarm.get("sev",     ""))
            acked  = bool(alarm.get("acked",  False))
            colour = _DIM if acked else SEV_COLOUR.get(sev, _TEXT)

            def cell(val: object, width: int = 0) -> Text:
                s = str(val) if val is not None else ""
                if width:
                    s = s[:width]
                t = Text(s)
                t.stylize(colour)
                return t

            ack_mark = "✓" if acked else " "

            self.add_row(
                cell(alarm.get("ts",      ""), 8),
                cell(alarm.get("id",      ""), 8),
                cell(sev,                      4),
                cell(alarm.get("process", ""), 20),
                cell(alarm.get("tag",     ""), 20),
                cell(f"{ack_mark} {alarm.get('desc', '')}", 60),
                key=str(alarm.get("id", id(alarm))),
            )
