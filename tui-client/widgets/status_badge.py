"""
status_badge.py — Process Health Indicator
MORBION SCADA v02

Visual badge showing ONLINE, OFFLINE, or FAULT state.
"""

from textual.widgets import Static
from textual.app import RenderResult

class StatusBadge(Static):
    """
    A stylized badge for process status.
    """
    DEFAULT_CSS = """
    StatusBadge {
        width: 14;
        height: 1;
        content-align: center middle;
        text-style: bold;
        border: solid #0a2229;
        margin-right: 1;
    }
    """

    def update_status(self, online: bool, fault_code: int = 0):
        if not online:
            self.renderable = " OFFLINE "
            self.styles.color = "#ff3333" # RED
            self.styles.border = ("solid", "#ff3333")
        elif fault_code > 0:
            self.renderable = f" FAULT {fault_code} "
            self.styles.color = "#ffaa00" # AMBER
            self.styles.border = ("solid", "#ffaa00")
        else:
            self.renderable = " ONLINE "
            self.styles.color = "#00ff88" # GREEN
            self.styles.border = ("solid", "#00ff88")
