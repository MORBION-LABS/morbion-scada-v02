"""
sparkline_widget.py — Mini trend sparkline
MORBION SCADA v02
"""

from collections import deque
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QPainter, QColor, QPen, QPainterPath
import theme


class SparklineWidget(QWidget):

    def __init__(self, label: str, unit: str = "",
                 max_points: int = 120,
                 hi_alarm: float = None,
                 lo_alarm: float = None):
        super().__init__()
        self._label     = label
        self._unit      = unit
        self._max       = max_points
        self._hi        = hi_alarm
        self._lo        = lo_alarm
        self._data      = deque(maxlen=max_points)
        self._last_val  = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(theme.STYLE_DIM)
        top_layout.addWidget(self._lbl)
        top_layout.addStretch()

        self._val_lbl = QLabel("—")
        self._val_lbl.setStyleSheet(theme.STYLE_TEXT)
        top_layout.addWidget(self._val_lbl)

        u = QLabel(unit)
        u.setStyleSheet(theme.STYLE_DIM)
        top_layout.addWidget(u)

        layout.addWidget(top)

        self._canvas = _SparkCanvas(hi_alarm, lo_alarm)
        layout.addWidget(self._canvas)

        self.setMinimumHeight(70)

    def push(self, value: float):
        self._last_val = value
        self._data.append(value)
        self._canvas.set_data(list(self._data), self._hi, self._lo)

        color = theme.TEXT
        if self._hi is not None and value >= self._hi:
            color = theme.RED
        elif self._lo is not None and value <= self._lo:
            color = theme.AMBER

        self._val_lbl.setText(f"{value:.1f}")
        self._val_lbl.setStyleSheet(
            f"color: {color}; font-family: 'Courier New', monospace; "
            f"font-size: 12px; background: transparent;"
        )


class _SparkCanvas(QWidget):

    def __init__(self, hi_alarm, lo_alarm):
        super().__init__()
        self._data = []
        self._hi   = hi_alarm
        self._lo   = lo_alarm
        self.setMinimumHeight(40)

    def set_data(self, data: list, hi, lo):
        self._data = data
        self._hi   = hi
        self._lo   = lo
        self.update()

    def paintEvent(self, event):
        if len(self._data) < 2:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w   = self.width()
        h   = self.height()
        pad = 4

        mn  = min(self._data)
        mx  = max(self._data)
        rng = mx - mn or 1.0

        def px(i):
            return pad + int(i / (len(self._data) - 1) * (w - 2 * pad))

        def py(v):
            return h - pad - int(((v - mn) / rng) * (h - 2 * pad))

        # Alarm lines
        if self._hi is not None and mn <= self._hi <= mx:
            p.setPen(QPen(QColor(theme.RED), 1, Qt.PenStyle.DashLine))
            y = py(self._hi)
            p.drawLine(pad, y, w - pad, y)

        if self._lo is not None and mn <= self._lo <= mx:
            p.setPen(QPen(QColor(theme.AMBER), 1, Qt.PenStyle.DashLine))
            y = py(self._lo)
            p.drawLine(pad, y, w - pad, y)

        # Line
        path = QPainterPath()
        path.moveTo(px(0), py(self._data[0]))
        for i, v in enumerate(self._data[1:], 1):
            path.lineTo(px(i), py(v))

        last = self._data[-1]
        if self._hi is not None and last >= self._hi:
            line_color = QColor(theme.RED)
        elif self._lo is not None and last <= self._lo:
            line_color = QColor(theme.AMBER)
        else:
            line_color = QColor(theme.ACCENT)

        p.setPen(QPen(line_color, 1.5))
        p.drawPath(path)
        p.end()
