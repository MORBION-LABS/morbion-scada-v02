"""
valve_bar.py — Valve position indicator
MORBION SCADA v02
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QPainter, QColor
import theme


class ValveBar(QWidget):

    def __init__(self, label: str):
        super().__init__()
        self._position = 0.0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(8)

        self._lbl = QLabel(label.upper())
        self._lbl.setFixedWidth(140)
        self._lbl.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(self._lbl)

        self._bar = _ValveCanvas()
        layout.addWidget(self._bar)

        self._pct = QLabel("0.0 %")
        self._pct.setFixedWidth(52)
        self._pct.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._pct.setStyleSheet(theme.STYLE_TEXT)
        layout.addWidget(self._pct)

        self.setFixedHeight(28)

    def set_position(self, pct: float):
        self._position = pct
        self._bar.set_value(pct)
        self._pct.setText(f"{pct:.1f} %")


class _ValveCanvas(QWidget):

    def __init__(self):
        super().__init__()
        self._value = 0.0
        self.setFixedHeight(14)

    def set_value(self, v: float):
        self._value = max(0.0, min(100.0, v))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w = self.width()
        h = self.height()

        p.fillRect(0, 0, w, h, QColor(theme.BORDER))

        fill = int((self._value / 100.0) * w)
        if self._value > 80:
            color = QColor(theme.AMBER)
        elif self._value < 5:
            color = QColor(theme.TEXT_DIM)
        else:
            color = QColor(theme.ACCENT)
        color.setAlpha(200)
        p.fillRect(0, 0, fill, h, color)
        p.end()
