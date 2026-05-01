"""
plc_view.py — PLC Programming Interface
Surgical Overhaul v06 — Full Word Titles
"""
# ... (imports and Highlighter/Worker same as v05)

class PLCView(QWidget):
    # PURGED ABBREVIATIONS
    PROCESSES = [
        ("pumping_station", "PUMPING STATION"), 
        ("heat_exchanger",  "HEAT EXCHANGER"), 
        ("boiler",          "INDUSTRIAL STEAM BOILER"), 
        ("pipeline",        "PETROLEUM PIPELINE")
    ]

    def __init__(self, rest):
        super().__init__()
        self._rest = rest; self._process = "pumping_station"; self._build_ui(); self._refresh()

    def _build_ui(self):
        lay = QHBoxLayout(self); splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget(); left.setMinimumWidth(300); l_lay = QVBoxLayout(left)
        l_lay.addWidget(QLabel("PLC SOURCE MANAGEMENT"))
        
        p_box = QGroupBox("SELECT INDUSTRIAL PROCESS"); p_lay = QVBoxLayout(p_box)
        for full_name, label in self.PROCESSES:
            # Full descriptive buttons
            b = QPushButton(label)
            b.setFixedHeight(35)
            b.clicked.connect(lambda checked, f=full_name: self._select(f))
            p_lay.addWidget(b)
        l_lay.addWidget(p_box)
        
        # ... (badge, variable map logic same as v05)
        # Splicing in the Splitter logic
        lay.addWidget(splitter)
        
    def _select(self, p):
        self._process = p
        self._title.setText(f"{p.upper().replace('_',' ')} — plc_program.st")
        self._refresh()
    
    # ... (worker and refresh logic same as v05)
