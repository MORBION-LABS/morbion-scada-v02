"""
MORBION — SparklineWidget
Mini real-time trend. Canvas painting. No pyqtgraph dependency.
"""

from collections import deque
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QPainter, QColor, QPen, QPainterPath


class SparklineWidget(QWidget):

    def __init__(self, max_points: int = 120, color: str = "#00d4ff",
                 fill: bool = True, parent=None):
        super().__init__(parent)
        self._data      = deque(maxlen=max_points)
        self._color     = QColor(color)
        self._fill      = fill
        self._min_v     = None
        self._max_v     = None
        self.setMinimumHeight(32)
        self.setMaximumHeight(48)

    def push(self, value: float):
        if value is None:
            return
        self._data.append(float(value))
        self.update()

    def paintEvent(self, event):
        if len(self._data) < 2:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h   = self.width(), self.height()
        data   = list(self._data)
        mn, mx = min(data), max(data)
        rng    = mx - mn or 1.0

        def px(i):
            return (i / (len(data) - 1)) * w

        def py(v):
            return h - 2 - ((v - mn) / rng) * (h - 4)

        path = QPainterPath()
        path.moveTo(px(0), py(data[0]))
        for i in range(1, len(data)):
            path.lineTo(px(i), py(data[i]))

        # Fill
        if self._fill:
            fill_path = QPainterPath(path)
            fill_path.lineTo(w, h)
            fill_path.lineTo(0, h)
            fill_path.closeSubpath()
            fill_color = QColor(self._color)
            fill_color.setAlpha(25)
            p.fillPath(fill_path, fill_color)

        # Line
        pen = QPen(self._color, 1.5, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPath(path)

        p.end()