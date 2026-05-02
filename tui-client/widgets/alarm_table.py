"""
alarm_table.py — Industrial Alarm Data Grid
MORBION SCADA v02

DataTable subclass with severity-based row highlighting.
"""

from textual.widgets import DataTable
from textual.app import RenderResult

class AlarmTable(DataTable):
    """
    A specialized table for displaying active and historical alarms.
    """
    
    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("ID", "TIME", "PROC", "SEV", "DESCRIPTION", "ACK")
        self.fixed_columns = 1

    def update_alarms(self, alarms_list: list):
        """Refresh the table with new alarm data."""
        self.clear()
        
        for alarm in alarms_list:
            sev = alarm.get("sev", "LOW")
            acked = alarm.get("acked", False)
            
            # Determine Color based on severity
            if acked:
                color = "#4a7a8c" # TEXT_DIM
            elif sev == "CRIT":
                color = "#ff3333" # RED
            elif sev == "HIGH":
                color = "#ffaa00" # AMBER
            elif sev == "MED":
                color = "#00d4ff" # ACCENT
            else:
                color = "#d0e8f0" # TEXT

            ack_status = "✓" if acked else " "
            
            self.add_row(
                f"[{color}]{alarm.get('id')}[/]",
                f"[{color}]{alarm.get('ts')}[/]",
                f"[{color}]{alarm.get('process')}[/]",
                f"[{color}]{sev}[/]",
                f"[{color}]{alarm.get('desc')}[/]",
                f"[{color}]{ack_status}[/]"
            )
