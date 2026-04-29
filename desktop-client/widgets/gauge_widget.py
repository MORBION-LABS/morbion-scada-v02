"""
gauge_widget.py — Horizontal bar gauge
MORBION SCADA v02
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore    import Qt, QRect
from PyQt6.QtGui     import QPainter, QColor, QPen
import theme


class GaugeWidget(QWidget):

    def __init__(self, label: str, unit: str = "",
                 min_val: float = 0.0, max_val: float = 100.0,
                 hi_alarm: float = None, lo_alarm: float = None,
                 decimals: int = 1):
        super().__init__()
        self._label    = label
        self._unit     = unit
        self._min      = min_val
        self._max      = max_val
        self._hi       = hi_alarm
        self._lo       = lo_alarm
        self._decimals = decimals
        self._value    = 0.0

        self.setMinimumHeight(52)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # Top row — label + value
        top = QHBoxLayout()
        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(theme.STYLE_DIM)
        top.addWidget(self._lbl)
        top.addStretch()
        self._val_lbl = QLabel("—")
        self._val_lbl.setStyleSheet(theme.STYLE_TEXT)
        top.addWidget(self._val_lbl)
        self._unit_lbl = QLabel(unit)
        self._unit_lbl.setStyleSheet(theme.STYLE_DIM)
        top.addWidget(self._unit_lbl)
        layout.addLayout(top)

        # Bar canvas
        self._bar = _GaugeBar(min_val, max_val, hi_alarm, lo_alarm)
        self._bar.setFixedHeight(16)
        layout.addWidget(self._bar)

    def set_value(self, value: float):
        self._value = value
        self._bar.set_value(value)

        text = f"{value:.{self._decimals}f}"
        color = theme.TEXT

        if self._hi is not None and value >= self._hi:
            color = theme.RED
        elif self._lo is not None and value <= self._lo:
            color = theme.AMBER

        self._val_lbl.setText(text)
        self._val_lbl.setStyleSheet(
            f"color: {color}; font-family: 'Courier New', monospace; "
            f"font-size: 12px; background: transparent;"
        )


class _GaugeBar(QWidget):

    def __init__(self, min_val, max_val, hi_alarm, lo_alarm):
        super().__init__()
        self._min   = min_val
        self._max   = max_val
        self._hi    = hi_alarm
        self._lo    = lo_alarm
        self._value = 0.0

    def set_value(self, v: float):
        self._value = v
        self.update()

    def paintEvent(self, event):
        p   = QPainter(self)
        w   = self.width()
        h   = self.height()
        rng = self._max - self._min or 1.0

        # Background
        p.fillRect(0, 0, w, h, QColor(theme.BORDER))

        # Fill ratio
        ratio = max(0.0, min(1.0, (self._value - self._min) / rng))
        fill  = int(ratio * w)

        # Colour
        if self._hi is not None and self._value >= self._hi:
            color = QColor(theme.RED)
        elif self._lo is not None and self._value <= self._lo:
            color = QColor(theme.AMBER)
        else:
            color = QColor(theme.ACCENT)

        p.fillRect(0, 0, fill, h, color)

        # Alarm markers
        p.setPen(QPen(QColor(theme.RED), 1))
        if self._hi is not None:
            x = int(((self._hi - self._min) / rng) * w)
            p.drawLine(x, 0, x, h)

        p.setPen(QPen(QColor(theme.AMBER), 1))
        if self._lo is not None:
            x = int(((self._lo - self._min) / rng) * w)
            p.drawLine(x, 0, x, h)

        p.end()
