from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSplitter
from PyQt6.QtCore    import Qt
import theme


class BaseProcessView(QWidget):

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

        left = self._build_data_panel()
        left.setStyleSheet(f"background: {theme.BG};")

        right = self._build_control_panel()
        right.setStyleSheet(
            f"background: {theme.SURFACE}; "
            f"border-left: 1px solid {theme.BORDER};"
        )

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([700, 300])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        root.addWidget(splitter)

    def _build_data_panel(self) -> QWidget:
        return QWidget()

    def _build_control_panel(self) -> QWidget:
        return QWidget()

    def update_data(self, data: dict):
        pass
