"""
status_badge.py — Online/Offline/Fault status badge
MORBION SCADA v02
"""

from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore    import Qt
import theme


class StatusBadge(QLabel):

    def __init__(self, text: str = "UNKNOWN"):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set("UNKNOWN", theme.TEXT_DIM)

    def set_online(self):
        self._set("● ONLINE", theme.GREEN)

    def set_offline(self):
        self._set("○ OFFLINE", theme.RED)

    def set_fault(self, code: int = 0, text: str = ""):
        label = f"⚠ FAULT {text or code}"
        self._set(label, theme.RED)

    def set_warning(self, text: str):
        self._set(f"▲ {text}", theme.AMBER)

    def set_custom(self, text: str, color: str):
        self._set(text, color)

    def _set(self, text: str, color: str):
        self.setText(text)
        self.setStyleSheet(
            f"color: {color}; font-family: 'Courier New', monospace; "
            f"font-size: 11px; letter-spacing: 1px; background: transparent; "
            f"padding: 2px 8px; border: 1px solid {color}; border-radius: 2px;"
        )
