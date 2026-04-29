"""
MORBION — ValueLabel
A label that shows a live process value with unit.
Color changes based on value range thresholds.
"""

"""
value_label.py — Numeric value display with unit and label
MORBION SCADA v02
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore    import Qt
import theme


class ValueLabel(QWidget):
    """
    Displays:
        LABEL
        VALUE  unit
    Colour changes on threshold breach.
    """

    def __init__(self, label: str, unit: str = "",
                 hi_alarm: float = None, lo_alarm: float = None,
                 decimals: int = 1):
        super().__init__()
        self._unit     = unit
        self._hi       = hi_alarm
        self._lo       = lo_alarm
        self._decimals = decimals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(theme.STYLE_DIM)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._lbl)

        row = QHBoxLayout()
        row.setSpacing(4)

        self._val = QLabel("—")
        self._val.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Courier New', monospace; "
            f"font-size: 18px; font-weight: bold; background: transparent;"
        )
        row.addWidget(self._val)

        self._unit_lbl = QLabel(unit)
        self._unit_lbl.setStyleSheet(theme.STYLE_DIM)
        self._unit_lbl.setAlignment(
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft
        )
        row.addWidget(self._unit_lbl)
        row.addStretch()
        layout.addLayout(row)

        self.setStyleSheet(
            f"background: {theme.SURFACE}; "
            f"border: 1px solid {theme.BORDER}; "
            f"border-radius: 2px;"
        )

    def set_value(self, value, override_color: str = None):
        if value is None:
            self._val.setText("—")
            self._val.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-family: 'Courier New', monospace; "
                f"font-size: 18px; font-weight: bold; background: transparent;"
            )
            return

        if isinstance(value, bool):
            text  = "ON" if value else "OFF"
            color = theme.GREEN if value else theme.TEXT_DIM
        elif isinstance(value, float):
            text  = f"{value:.{self._decimals}f}"
            color = self._color_for(value)
        elif isinstance(value, int):
            text  = str(value)
            color = self._color_for(float(value))
        else:
            text  = str(value)
            color = theme.TEXT

        if override_color:
            color = override_color

        self._val.setText(text)
        self._val.setStyleSheet(
            f"color: {color}; font-family: 'Courier New', monospace; "
            f"font-size: 18px; font-weight: bold; background: transparent;"
        )

    def _color_for(self, v: float) -> str:
        if self._hi is not None and v >= self._hi:
            return theme.RED
        if self._lo is not None and v <= self._lo:
            return theme.AMBER
        return theme.GREEN
