"""
MORBION — TankWidget
Animated vertical fill level indicator.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore    import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui     import QPainter, QColor, QLinearGradient, QPen, QFont


class TankWidget(QWidget):

    def __init__(self, min_val=0.0, max_val=100.0,
                 warn_pct=80.0, crit_pct=90.0, parent=None):
        super().__init__(parent)
        self._min      = min_val
        self._max      = max_val
        self._warn     = warn_pct
        self._crit     = crit_pct
        self._level    = 0.0
        self._display  = "—"
        self.setMinimumSize(60, 120)

        self._anim = QPropertyAnimation(self, b"fill_level", self)
        self._anim.setDuration(800)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    @pyqtProperty(float)
    def fill_level(self) -> float:
        return self._level

    @fill_level.setter
    def fill_level(self, val: float):
        self._level = max(0.0, min(100.0, val))
        self.update()

    def set_value(self, value: float, label: str = ""):
        pct = ((value - self._min) / (self._max - self._min)) * 100.0
        pct = max(0.0, min(100.0, pct))
        self._display = label or f"{value:.1f}"
        self._anim.stop()
        self._anim.setStartValue(self._level)
        self._anim.setEndValue(pct)
        self._anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        margin = 4
        inner_w = w - margin * 2
        inner_h = h - margin * 2

        p.setPen(QPen(QColor("#0d2030"), 1))
        p.setBrush(QColor("#020a12"))
        p.drawRect(margin, margin, inner_w, inner_h)

        fill_h  = int(inner_h * self._level / 100.0)
        fill_y  = margin + inner_h - fill_h

        if self._level >= self._crit:
            top_color = QColor("#ff3333")
            bot_color = QColor("#880000")
        elif self._level >= self._warn:
            top_color = QColor("#ffcc00")
            bot_color = QColor("#885500")
        else:
            top_color = QColor("#003a5a")
            bot_color = QColor("#00d4ff")

        if fill_h > 0:
            grad = QLinearGradient(0, fill_y, 0, fill_y + fill_h)
            grad.setColorAt(0, top_color)
            grad.setColorAt(1, bot_color)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(grad)
            p.drawRect(margin + 1, fill_y, inner_w - 1, fill_h)

        p.setPen(QPen(QColor("#071520"), 1))
        for i in range(1, 5):
            y = margin + int(inner_h * i / 5)
            p.drawLine(margin + 1, y, margin + inner_w - 1, y)

        p.setPen(QColor("#ffffff"))
        font = QFont("Courier New", 9, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(margin, margin, inner_w, inner_h, Qt.AlignmentFlag.AlignCenter, self._display)

        p.end()