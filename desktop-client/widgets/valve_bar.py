"""
MORBION — ValveBar
Horizontal position bar for valve position display.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QPainter, QColor
from theme import C_TEXT2, C_ACCENT, C_BORDER


class ValveBar(QWidget):

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._pct = 0.0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(f"color:{C_TEXT2};font-size:9px;letter-spacing:1px;")
        self._lbl.setFixedWidth(110)

        self._bar = _BarCanvas(self)
        self._bar.setFixedHeight(8)

        self._pct_lbl = QLabel("—")
        self._pct_lbl.setStyleSheet(f"color:{C_ACCENT};font-size:10px;")
        self._pct_lbl.setFixedWidth(38)
        self._pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self._lbl)
        layout.addWidget(self._bar, 1)
        layout.addWidget(self._pct_lbl)

    def set_value(self, pct: float):
        self._pct = max(0.0, min(100.0, pct))
        self._bar.set_pct(self._pct)
        self._pct_lbl.setText(f"{self._pct:.1f}%")


class _BarCanvas(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct = 0.0

    def set_pct(self, pct: float):
        self._pct = pct
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(C_BORDER))
        fill_w = int(w * self._pct / 100.0)
        if fill_w > 0:
            p.fillRect(0, 0, fill_w, h, QColor("#0099bb"))
        p.end()