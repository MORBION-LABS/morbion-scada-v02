"""
base_view.py — Base class for all process views
MORBION SCADA v02
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSplitter
from PyQt6.QtCore    import Qt
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore    import QByteArray
import theme


class BaseProcessView(QWidget):
    """
    Two-column layout:
      Left  70% — process data, gauges, trends
      Right 30% — operator control panel

    Watermark hexagon drawn behind left panel.
    Subclasses implement _build_data_panel() and _build_control_panel().
    """

    def __init__(self):
        super().__init__()
        self._build_layout()

    def _build_layout(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {theme.BORDER}; }}"
        )

        # Left — data panel with watermark
        left_container = QWidget()
        left_container.setStyleSheet(f"background: {theme.BG};")
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Watermark
        wm = QSvgWidget()
        wm.load(QByteArray(theme.WATERMARK_SVG.encode()))
        wm.setStyleSheet("background: transparent;")

        # Stack watermark behind data panel using absolute positioning
        # We use a plain widget with the data panel on top
        data_panel = self._build_data_panel()
        left_layout.addWidget(data_panel)

        # Right — control panel
        right_panel = self._build_control_panel()
        right_panel.setStyleSheet(
            f"background: {theme.SURFACE}; "
            f"border-left: 1px solid {theme.BORDER};"
        )

        splitter.addWidget(left_container)
        splitter.addWidget(right_panel)
        splitter.setSizes([700, 300])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        root.addWidget(splitter)

    def _build_data_panel(self) -> QWidget:
        """Override in subclass."""
        return QWidget()

    def _build_control_panel(self) -> QWidget:
        """Override in subclass."""
        return QWidget()

    def update_data(self, data: dict):
        """Override in subclass."""
        pass
