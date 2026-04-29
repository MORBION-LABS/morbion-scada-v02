"""
control_panel.py — Operator control panel (right side of process views)
MORBION SCADA v02

Provides write controls for a single process.
Verify-after-write via rest_client.
"""

import time
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit,
    QGroupBox, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer
import theme


class ControlButton(QPushButton):

    def __init__(self, text: str, color: str = None):
        super().__init__(text)
        c = color or theme.ACCENT
        self.setStyleSheet(
            f"QPushButton {{ background: {theme.SURFACE}; color: {c}; "
            f"border: 1px solid {c}; padding: 6px 12px; "
            f"font-family: 'Courier New', monospace; letter-spacing: 1px; }}"
            f"QPushButton:hover {{ background: {c}; color: {theme.BG}; }}"
            f"QPushButton:pressed {{ background: {theme.BORDER}; }}"
            f"QPushButton:disabled {{ color: {theme.TEXT_DIM}; "
            f"border-color: {theme.BORDER}; }}"
        )


class RegisterWriteRow(QWidget):
    """Label + input + write button + feedback for a single register."""

    def __init__(self, label: str, rest, process: str,
                 register: int, scale: float = 1.0,
                 hint: str = ""):
        super().__init__()
        self._rest     = rest
        self._process  = process
        self._register = register
        self._scale    = scale

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        lbl = QLabel(label)
        lbl.setFixedWidth(150)
        lbl.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(lbl)

        self._input = QLineEdit()
        self._input.setPlaceholderText(hint)
        self._input.setFixedWidth(80)
        self._input.setStyleSheet(
            f"background: {theme.SURFACE}; color: {theme.TEXT}; "
            f"border: 1px solid {theme.BORDER}; padding: 3px 6px; "
            f"font-family: 'Courier New', monospace;"
        )
        layout.addWidget(self._input)

        btn = ControlButton("WRITE")
        btn.setFixedWidth(70)
        btn.clicked.connect(self._on_write)
        layout.addWidget(btn)

        self._fb = QLabel("")
        self._fb.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(self._fb)
        layout.addStretch()

    def _on_write(self):
        txt = self._input.text().strip()
        if not txt:
            return
        try:
            raw = int(round(float(txt) * self._scale))
            raw = max(0, min(65535, raw))
        except ValueError:
            self._feedback("INVALID", theme.RED)
            return

        threading.Thread(
            target=self._do_write,
            args=(raw,),
            daemon=True,
        ).start()

    def _do_write(self, raw: int):
        result = self._rest.write_register(self._process, self._register, raw)
        if not result.get("ok"):
            QTimer.singleShot(0, lambda: self._feedback(
                f"ERR: {result.get('error','')[:20]}", theme.RED))
            return

        time.sleep(0.35)
        readback = self._rest.read_register_value(self._process, self._register)

        if readback is None:
            QTimer.singleShot(0, lambda: self._feedback("UNVERIFIED", theme.AMBER))
        elif readback == raw:
            QTimer.singleShot(0, lambda: self._feedback("CONFIRMED", theme.GREEN))
        else:
            QTimer.singleShot(0, lambda: self._feedback("OVERRIDDEN", theme.AMBER))

    def _feedback(self, text: str, color: str):
        self._fb.setText(text)
        self._fb.setStyleSheet(
            f"color: {color}; font-family: 'Courier New', monospace; "
            f"font-size: 11px; background: transparent;"
        )
        QTimer.singleShot(4000, lambda: self._fb.setText(""))


class FaultClearButton(QWidget):
    """Operator reset — writes 0 to register 14."""

    def __init__(self, rest, process: str):
        super().__init__()
        self._rest    = rest
        self._process = process

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        btn = ControlButton("CLEAR FAULT / OPERATOR RESET", theme.AMBER)
        btn.clicked.connect(self._on_clear)
        layout.addWidget(btn)

        self._fb = QLabel("")
        self._fb.setStyleSheet(theme.STYLE_DIM)
        layout.addWidget(self._fb)
        layout.addStretch()

    def _on_clear(self):
        threading.Thread(target=self._do_clear, daemon=True).start()

    def _do_clear(self):
        result = self._rest.write_register(self._process, 14, 0)
        if result.get("ok"):
            QTimer.singleShot(0, lambda: self._show_fb("RESET SENT", theme.GREEN))
        else:
            QTimer.singleShot(0, lambda: self._show_fb("FAILED", theme.RED))

    def _show_fb(self, text: str, color: str):
        self._fb.setText(text)
        self._fb.setStyleSheet(
            f"color: {color}; font-family: 'Courier New', monospace; "
            f"font-size: 11px; background: transparent;"
        )
        QTimer.singleShot(3000, lambda: self._fb.setText(""))
