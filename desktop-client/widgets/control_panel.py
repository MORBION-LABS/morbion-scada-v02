"""
MORBION — ControlPanel
Per-process control widget.
Named fault injection buttons + direct register write.
Calls rest_client.write_register() — non-blocking.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt
from theme import C_ACCENT, C_TEXT2, C_RED, C_GREEN


class ControlPanel(QWidget):
    """
    Builds a control panel from a process spec dict:
    {
        "process":  "boiler",
        "label":    "BOILER — EABL/Bidco",
        "faults": [
            {"name": "Inject LOW_WATER",  "register": 2,  "value": 150, "danger": True},
            {"name": "Clear Fault Code",  "register": 14, "value": 0,   "danger": False},
        ],
        "writes": [
            {"label": "Drum Level (raw×10)", "register": 2,  "min": 0, "max": 1000, "default": 500},
            {"label": "Burner State (0/1/2)","register": 6,  "min": 0, "max": 2,    "default": 1},
        ]
    }
    """

    def __init__(self, spec: dict, rest_client, parent=None):
        super().__init__(parent)
        self._rest    = rest_client
        self._process = spec["process"]
        self._fb_label = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── Feedback bar ──────────────────────────────────────────────────────
        self._fb = QLabel("")
        self._fb.setStyleSheet(
            f"color:{C_ACCENT};font-size:10px;padding:3px 8px;"
            f"background:#020a12;border:1px solid #0d2030;"
        )
        self._fb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fb.hide()
        layout.addWidget(self._fb)

        # ── Fault injection ───────────────────────────────────────────────────
        if spec.get("faults"):
            fg = QGroupBox("FAULT INJECTION")
            fg_layout = QVBoxLayout(fg)
            fg_layout.setSpacing(4)
            for f in spec["faults"]:
                btn = QPushButton(f["name"])
                if f.get("danger", False):
                    btn.setProperty("danger", "true")
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                else:
                    btn.setProperty("action", "clear")
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                reg = f["register"]
                val = f["value"]
                btn.clicked.connect(
                    lambda checked, r=reg, v=val: self._send(r, v))
                fg_layout.addWidget(btn)
            layout.addWidget(fg)

        # ── Direct register write ─────────────────────────────────────────────
        if spec.get("writes"):
            wg = QGroupBox("DIRECT REGISTER WRITE")
            wg_layout = QGridLayout(wg)
            wg_layout.setSpacing(4)
            for i, w in enumerate(spec["writes"]):
                lbl = QLabel(w["label"])
                lbl.setStyleSheet(f"color:{C_TEXT2};font-size:9px;")
                spin = QSpinBox()
                spin.setRange(w.get("min", 0), w.get("max", 65535))
                spin.setValue(w.get("default", 0))
                spin.setMinimumWidth(80)
                btn = QPushButton("WRITE")
                btn.setFixedWidth(60)
                reg = w["register"]
                btn.clicked.connect(
                    lambda checked, s=spin, r=reg: self._send(r, s.value()))
                wg_layout.addWidget(lbl,  i, 0)
                wg_layout.addWidget(spin, i, 1)
                wg_layout.addWidget(btn,  i, 2)
            layout.addWidget(wg)

        layout.addStretch()

    def _send(self, register: int, value: int):
        self._show_fb(f"Sending reg={register} val={value}...", C_TEXT2)
        self._rest.write_register(
            self._process, register, value, self._on_result)

    def _on_result(self, result: dict):
        if result.get("ok") and result.get("confirmed"):
            self._show_fb(f"✓ reg={result.get('register')} val={result.get('value')} — confirmed", C_GREEN)
        elif result.get("ok"):
            self._show_fb(f"⚠ Written but not confirmed", "#ffcc00")
        else:
            self._show_fb(f"✗ {result.get('error', 'Failed')}", C_RED)

    def _show_fb(self, msg: str, color: str):
        self._fb.setText(msg)
        self._fb.setStyleSheet(
            f"color:{color};font-size:10px;padding:3px 8px;"
            f"background:#020a12;border:1px solid #0d2030;"
        )
        self._fb.show()