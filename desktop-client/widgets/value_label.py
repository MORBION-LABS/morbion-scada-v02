"""
MORBION — ValueLabel
A label that shows a live process value with unit.
Color changes based on value range thresholds.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore    import Qt
from theme import C_ACCENT, C_RED, C_YELLOW, C_TEXT2


class ValueLabel(QWidget):
    """
    Displays:  LABEL_TEXT    VALUE    UNIT
    Colors the value by threshold.
    """

    def __init__(self, label: str, unit: str = "",
                 warn_threshold=None, crit_threshold=None,
                 high_is_bad: bool = True, parent=None):
        super().__init__(parent)
        self._warn = warn_threshold
        self._crit = crit_threshold
        self._high_is_bad = high_is_bad

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        self._lbl_label = QLabel(label.upper())
        self._lbl_label.setStyleSheet(f"color: {C_TEXT2}; font-size:10px; letter-spacing:1px;")
        self._lbl_label.setMinimumWidth(140)

        self._lbl_value = QLabel("—")
        self._lbl_value.setStyleSheet(f"color: {C_ACCENT}; font-size:13px; font-weight:bold;")
        self._lbl_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._lbl_value.setMinimumWidth(80)

        self._lbl_unit = QLabel(unit)
        self._lbl_unit.setStyleSheet(f"color: {C_TEXT2}; font-size:9px;")
        self._lbl_unit.setMinimumWidth(40)

        layout.addWidget(self._lbl_label)
        layout.addStretch()
        layout.addWidget(self._lbl_value)
        layout.addWidget(self._lbl_unit)

    def set_value(self, value, decimals: int = 1):
        if value is None:
            self._lbl_value.setText("—")
            self._lbl_value.setStyleSheet(f"color: {C_TEXT2}; font-size:13px; font-weight:bold;")
            return

        if isinstance(value, bool):
            text = "YES" if value else "NO"
        elif isinstance(value, float):
            text = f"{value:.{decimals}f}"
        else:
            text = str(value)

        self._lbl_value.setText(text)

        # Color by threshold
        color = C_ACCENT
        if self._crit is not None and self._warn is not None:
            numeric = value if isinstance(value, (int, float)) else None
            if numeric is not None:
                if self._high_is_bad:
                    if numeric >= self._crit:
                        color = C_RED
                    elif numeric >= self._warn:
                        color = C_YELLOW
                else:
                    if numeric <= self._crit:
                        color = C_RED
                    elif numeric <= self._warn:
                        color = C_YELLOW

        self._lbl_value.setStyleSheet(
            f"color: {color}; font-size:13px; font-weight:bold;")