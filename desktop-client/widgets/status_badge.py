"""
MORBION — StatusBadge + AlarmBadge
Small colored indicator labels.
"""

from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore    import Qt
from theme import C_GREEN, C_RED, C_ORANGE, C_YELLOW, C_MUTED, SEV_COLORS


class StatusBadge(QLabel):
    """Online / Offline / Fault badge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(90)
        self._set("UNKNOWN", C_MUTED)

    def _set(self, text: str, color: str):
        self.setText(text)
        self.setStyleSheet(
            f"color: {color};"
            f"border: 1px solid {color};"
            f"background: transparent;"
            f"padding: 2px 8px;"
            f"font-size: 9px;"
            f"letter-spacing: 2px;"
            f"font-weight: bold;"
        )

    def set_online(self):      self._set("● ONLINE",  C_GREEN)
    def set_offline(self):     self._set("● OFFLINE", C_MUTED)
    def set_fault(self, text="FAULT"): self._set(f"⚠ {text}", C_RED)
    def set_running(self):     self._set("● RUNNING", C_GREEN)
    def set_stopped(self):     self._set("● STOPPED", C_MUTED)
    def set_standby(self):     self._set("◌ STANDBY", C_YELLOW)

    def update_process(self, data: dict):
        if not data.get("online"):
            self.set_offline()
        elif data.get("fault_code", 0) != 0:
            self.set_fault(data.get("fault_text", "FAULT"))
        else:
            self.set_online()


class SeverityBadge(QLabel):
    """CRIT / HIGH / MED / LOW alarm severity badge."""

    def __init__(self, severity: str = "LOW", parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(46)
        self.set_severity(severity)

    def set_severity(self, sev: str):
        color = SEV_COLORS.get(sev, C_MUTED)
        self.setText(sev)
        self.setStyleSheet(
            f"color: {color};"
            f"border: 1px solid {color};"
            f"background: transparent;"
            f"padding: 2px 6px;"
            f"font-size: 9px;"
            f"letter-spacing: 1px;"
            f"font-weight: bold;"
        )