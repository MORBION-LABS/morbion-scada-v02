"""
plc_view.py — PLC Monitor View
Surgical Rebuild v02 — Pro Threading
"""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import theme, re

class SyncWorker(QThread):
    """Dedicated background worker for PLC syncing."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, rest, process):
        super().__init__()
        self.rest = rest
        self.process = process

    def run(self):
        try:
            prog = self.rest.plc_get_program(self.process)
            vars = self.rest.plc_get_variables(self.process)
            if prog:
                self.finished.emit({"prog": prog, "vars": vars})
            else:
                self.error.emit("Connection Timeout")
        except Exception as e:
            self.error.emit(str(e))

class PLCView(QWidget):
    PROCESSES = [("ps", "Pumping Station"), ("hx", "Heat Exchanger"), ("bl", "Boiler"), ("pl", "Pipeline")]

    def __init__(self, rest):
        super().__init__()
        self._rest = rest
        self._process = "bl"
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        root = QHBoxLayout(self); splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget(); left.setMinimumWidth(280); l_lay = QVBoxLayout(left)
        l_lay.addWidget(QLabel("PLC PROGRAMS"))
        
        p_box = QGroupBox("PROCESS"); p_lay = QVBoxLayout(p_box)
        for alias, name in self.PROCESSES:
            b = QPushButton(f"[{alias.upper()}] {name}")
            b.clicked.connect(lambda checked, a=alias: self._select(a))
            p_lay.addWidget(b)
        l_lay.addWidget(p_box)
        
        self._status = QLabel("Ready"); l_lay.addWidget(self._status)
        self._in_list = QListWidget(); self._out_list = QListWidget()
        l_lay.addWidget(QLabel("IO MAP")); l_lay.addWidget(self._in_list); l_lay.addWidget(self._out_list)
        l_lay.addStretch(); splitter.addWidget(left)
        
        self._editor = QTextEdit(); self._editor.setFont(QFont("Courier New", 10))
        self._editor.setReadOnly(True) # Safe for now
        splitter.addWidget(self._editor)
        root.addWidget(splitter)

    def _select(self, p):
        self._process = p
        self._refresh()

    def _refresh(self):
        self._status.setText("Syncing...")
        self._status.setStyleSheet(f"color: {theme.ACCENT};")
        # Kill any existing worker
        if hasattr(self, "_worker") and self._worker.isRunning():
            self._worker.terminate()
            
        self._worker = SyncWorker(self._rest, self._process)
        self._worker.finished.connect(self._on_sync_done)
        self._worker.error.connect(self._on_sync_error)
        self._worker.start()

    def _on_sync_done(self, data):
        self._status.setText("ONLINE")
        self._status.setStyleSheet(f"color: {theme.GREEN};")
        self._editor.setPlainText(data['prog'].get("source", ""))
        
        self._in_list.clear(); self._out_list.clear()
        v = data['vars'].get("variables", {}) if data['vars'] else {}
        for k in v.get("inputs", {}): self._in_list.addItem(k)
        for k in v.get("outputs", {}): self._out_list.addItem(k)

    def _on_sync_error(self, err):
        self._status.setText(f"OFFLINE: {err[:20]}")
        self._status.setStyleSheet(f"color: {theme.RED};")
