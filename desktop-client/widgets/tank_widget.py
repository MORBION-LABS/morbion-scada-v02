"""
tank_widget.py — Vertical tank level display
MORBION SCADA v02
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QPainter, QColor, QPen, QFont
import theme


class TankWidget(QWidget):

    def __init__(self, label: str = "TANK",
                 hi_alarm: float = 90.0,
                 lo_alarm: float = 10.0):
        super().__init__()
        self._label    = label
        self._hi       = hi_alarm
        self._lo       = lo_alarm
        self._level    = 0.0
        self._volume   = 0.0

        self.setMinimumSize(80, 160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(lbl)

        self._canvas = _TankCanvas(hi_alarm, lo_alarm)
        layout.addWidget(self._canvas)

        self._pct_lbl = QLabel("0.0 %")
        self._pct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pct_lbl.setStyleSheet(theme.STYLE_TEXT)
        layout.addWidget(self._pct_lbl)

    def set_level(self, pct: float, volume_m3: float = 0.0):
        self._level  = pct
        self._volume = volume_m3
        self._canvas.set_level(pct)

        color = theme.TEXT
        if pct >= self._hi:
            color = theme.RED
        elif pct <= self._lo:
            color = theme.AMBER

        self._pct_lbl.setText(f"{pct:.1f} %")
        self._pct_lbl.setStyleSheet(
            f"color: {color}; font-family: 'Courier New', monospace; "
            f"font-size: 13px; font-weight: bold; background: transparent;"
        )


class _TankCanvas(QWidget):

    def __init__(self, hi_alarm: float, lo_alarm: float):
        super().__init__()
        self._hi    = hi_alarm
        self._lo    = lo_alarm
        self._level = 0.0
        self.setMinimumSize(60, 120)

    def set_level(self, pct: float):
        self._level = max(0.0, min(100.0, pct))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w  = self.width()
        h  = self.height()
        m  = 8   # margin
        tw = w - 2 * m
        th = h - 2 * m

        # Tank outline
        p.setPen(QPen(QColor(theme.BORDER), 2))
        p.drawRect(m, m, tw, th)

        # Fill
        fill_h = int((self._level / 100.0) * th)
        fill_y = m + th - fill_h

        if self._level >= self._hi:
            fill_color = QColor(theme.RED)
        elif self._level <= self._lo:
            fill_color = QColor(theme.AMBER)
        else:
            fill_color = QColor(theme.ACCENT)
        fill_color.setAlpha(180)

        p.fillRect(m + 1, fill_y, tw - 1, fill_h, fill_color)

        # Alarm lines
        p.setPen(QPen(QColor(theme.RED), 1, Qt.PenStyle.DashLine))
        y_hi = m + th - int((self._hi / 100.0) * th)
        p.drawLine(m, y_hi, m + tw, y_hi)

        p.setPen(QPen(QColor(theme.AMBER), 1, Qt.PenStyle.DashLine))
        y_lo = m + th - int((self._lo / 100.0) * th)
        p.drawLine(m, y_lo, m + tw, y_lo)

        # Level text inside tank
        p.setPen(QColor(theme.WHITE))
        f = QFont("Courier New", 9, QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(
            m, m, tw, th,
            Qt.AlignmentFlag.AlignCenter,
            f"{self._level:.0f}%"
        )

        p.end()
