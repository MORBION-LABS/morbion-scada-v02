"""
MORBION SCADA Desktop — Theme
All colors, fonts, dimensions in one place.
Change here — changes everywhere.
"""

STYLESHEET = """
/* ── Base ── */
QWidget {
    background-color: #020c16;
    color: #8ab8c8;
    font-family: 'Courier New', 'Consolas', monospace;
    font-size: 11px;
}

QMainWindow {
    background-color: #020c16;
}

/* ── Tab Bar ── */
QTabWidget::pane {
    border: 1px solid #0d2030;
    background-color: #020c16;
}

QTabBar::tab {
    background-color: #030f1a;
    color: #2a5a6a;
    border: 1px solid #0a1e2a;
    border-bottom: none;
    padding: 8px 20px;
    font-size: 10px;
    letter-spacing: 2px;
    font-weight: bold;
    min-width: 100px;
}

QTabBar::tab:selected {
    background-color: #051525;
    color: #00d4ff;
    border-color: #00d4ff;
    border-bottom: 2px solid #00d4ff;
}

QTabBar::tab:hover:!selected {
    background-color: #040e18;
    color: #5aaacc;
}

/* ── Cards / GroupBox ── */
QGroupBox {
    background-color: #040e18;
    border: 1px solid #0d2030;
    border-radius: 2px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-size: 9px;
    letter-spacing: 2px;
    color: #2a5a6a;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #2a5a6a;
    letter-spacing: 2px;
    font-size: 9px;
}

/* ── Labels ── */
QLabel {
    background: transparent;
    color: #8ab8c8;
}

/* ── Buttons ── */
QPushButton {
    background-color: #030f1a;
    border: 1px solid #0d2030;
    color: #5aaacc;
    padding: 5px 14px;
    font-family: 'Courier New', monospace;
    font-size: 10px;
    letter-spacing: 1px;
    border-radius: 1px;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #051e30;
    border-color: #00d4ff;
    color: #00d4ff;
}

QPushButton:pressed {
    background-color: #002030;
    border-color: #00aacc;
}

QPushButton:disabled {
    color: #1a3a4a;
    border-color: #071520;
}

/* Danger buttons */
QPushButton[danger="true"] {
    border-color: #3a1010;
    color: #cc4433;
}
QPushButton[danger="true"]:hover {
    border-color: #ff3333;
    color: #ff3333;
    background-color: #1a0000;
}

/* OK/clear buttons */
QPushButton[action="clear"] {
    border-color: #103a10;
    color: #33cc44;
}
QPushButton[action="clear"]:hover {
    border-color: #00ff44;
    color: #00ff44;
    background-color: #001a00;
}

/* ── Inputs ── */
QLineEdit, QSpinBox {
    background-color: #020a12;
    border: 1px solid #0d2030;
    color: #00d4ff;
    padding: 3px 6px;
    font-family: 'Courier New', monospace;
    font-size: 11px;
    border-radius: 1px;
}

QLineEdit:focus, QSpinBox:focus {
    border-color: #00d4ff;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #030f1a;
    border: 1px solid #0d2030;
    width: 14px;
}

/* ── ComboBox ── */
QComboBox {
    background-color: #020a12;
    border: 1px solid #0d2030;
    color: #00d4ff;
    padding: 3px 6px;
    font-family: 'Courier New', monospace;
    font-size: 10px;
    min-height: 22px;
}

QComboBox QAbstractItemView {
    background-color: #030f1a;
    border: 1px solid #0d2030;
    color: #00d4ff;
    selection-background-color: #051e30;
}

/* ── ScrollBar ── */
QScrollBar:vertical {
    background: #020a12;
    width: 6px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #0d2030;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #00d4ff;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background: #020a12;
    height: 6px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #0d2030;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover { background: #00d4ff; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Table ── */
QTableWidget {
    background-color: #020a12;
    border: 1px solid #0d2030;
    gridline-color: #071520;
    color: #8ab8c8;
    selection-background-color: #051e30;
    selection-color: #00d4ff;
}

QTableWidget::item { padding: 4px 8px; border: none; }
QTableWidget::item:selected { background-color: #051e30; color: #00d4ff; }

QHeaderView::section {
    background-color: #030f1a;
    border: none;
    border-right: 1px solid #0d2030;
    border-bottom: 1px solid #0d2030;
    padding: 5px 8px;
    color: #2a5a6a;
    font-size: 9px;
    letter-spacing: 2px;
    font-weight: bold;
}

/* ── Splitter ── */
QSplitter::handle { background: #0d2030; }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical { height: 1px; }

/* ── Status bar ── */
QStatusBar {
    background-color: #030f1a;
    border-top: 1px solid #0d2030;
    color: #2a5a6a;
    font-size: 10px;
    letter-spacing: 1px;
}
"""

# ── Color tokens for use in  code ──────────────────────────────────────

C_BG       = "#020c16"
C_SURFACE  = "#040e18"
C_BORDER   = "#0d2030"
C_ACCENT   = "#00d4ff"
C_GREEN    = "#00ff88"
C_YELLOW   = "#ffcc00"
C_RED      = "#ff3333"
C_ORANGE   = "#ff8800"
C_MUTED    = "#2a5a6a"
C_TEXT     = "#8ab8c8"
C_TEXT2    = "#4a7a8a"

SEV_COLORS = {
    "CRIT": C_RED,
    "HIGH": C_ORANGE,
    "MED":  C_YELLOW,
    "LOW":  C_TEXT2,
}

def status_color(fault_code: int, online: bool) -> str:
    if not online:
        return C_MUTED
    if fault_code != 0:
        return C_RED
    return C_GREEN