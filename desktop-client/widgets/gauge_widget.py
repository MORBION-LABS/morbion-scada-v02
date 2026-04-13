"""
MORBION — GaugeWidget
Arc gauge. Animates smoothly.
"""

import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore    import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF
from PyQt6.QtGui     import QPainter, QColor, QPen, QFont, QConicalGradient


class GaugeWidget(QWidget):

    START_ANGLE = 225
    SPAN_ANGLE  = 270

    def __init__(self, min_val=0.0, max_val=100.0, unit="",
                 warn=None, crit=None, parent=None):
        super().__init__(parent)
        self._min    = min_val
        self._max    = max_val
        self._unit   = unit
        self._warn   = warn
        self._crit   = crit
        self._value  = min_val
        self._filled = 0.0
        self._label  = "—"
        self.setMinimumSize(120, 120)

        self._anim = QPropertyAnimation(self, b"arc_fill", self)
        self._anim.setDuration(600)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(float)
    def arc_fill(self) -> float:
        return self._filled

    @arc_fill.setter
    def arc_fill(self, val: float):
        self._filled = max(0.0, min(1.0, val))
        self.update()

    def set_value(self, value: float):
        self._value  = value
        self._label  = f"{value:.1f}"
        frac = (value - self._min) / max(1e-9, self._max - self._min)
        self._anim.stop()
        self._anim.setStartValue(self._filled)
        self._anim.setEndValue(max(0.0, min(1.0, frac)))
        self._anim.start()

    def _arc_color(self) -> QColor:
        if self._crit is not None and self._value >= self._crit:
            return QColor("#ff3333")
        if self._warn is not None and self._value >= self._warn:
            return QColor("#ffcc00")
        return QColor("#00d4ff")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h   = self.width(), self.height()
        size   = min(w, h) - 16
        rect   = QRectF((w - size) / 2, (h - size) / 2, size, size)
        cx, cy = w / 2, h / 2

        pen = QPen(QColor("#0d2030"), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, int(self.START_ANGLE * 16), int(-self.SPAN_ANGLE * 16))

        if self._filled > 0:
            pen.setColor(self._arc_color())
            p.setPen(pen)
            p.drawArc(rect, int(self.START_ANGLE * 16), int(-self._filled * self.SPAN_ANGLE * 16))

        p.setPen(QColor("#00d4ff"))
        font = QFont("Courier New", 11, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(int(cx - 40), int(cy - 8), 80, 20, Qt.AlignmentFlag.AlignCenter, self._label)

        p.setPen(QColor("#2a5a6a"))
        font2 = QFont("Courier New", 8)
        p.setFont(font2)
        p.drawText(int(cx - 30), int(cy + 10), 60, 16, Qt.AlignmentFlag.AlignCenter, self._unit)

        p.end()