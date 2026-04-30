"""
MORBION SCADA Desktop — Theme
All colors, fonts, dimensions in one place.
Change here — changes everywhere.
"""

"""
theme.py — MORBION SCADA Desktop Client Theme
MORBION SCADA v02
"""

# ── Colours ───────────────────────────────────────────────────────────────────
BG          = "#02080a"
SURFACE     = "#051014"
BORDER      = "#0a2229"
ACCENT      = "#00d4ff"
TEXT        = "#d0e8f0"
TEXT_DIM    = "#4a7a8c"
GREEN       = "#00ff88"
RED         = "#ff3333"
AMBER       = "#ffaa00"
WHITE       = "#ffffff"

# ── QSS colour strings (for stylesheet use) ───────────────────────────────────
QSS = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Courier New", "Consolas", monospace;
    font-size: 12px;
}}

QMainWindow {{
    background-color: {BG};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {SURFACE};
}}

QTabBar::tab {{
    background-color: {SURFACE};
    color: {TEXT_DIM};
    padding: 8px 18px;
    border: 1px solid {BORDER};
    border-bottom: none;
    font-family: "Courier New", monospace;
    font-size: 11px;
    letter-spacing: 1px;
}}

QTabBar::tab:selected {{
    background-color: {BG};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}

QTabBar::tab:hover {{
    color: {TEXT};
}}

QScrollBar:vertical {{
    background: {SURFACE};
    width: 8px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {SURFACE};
    height: 8px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
}}

QSplitter::handle {{
    background: {BORDER};
    height: 3px;
}}

QSplitter::handle:hover {{
    background: {ACCENT};
}}

QLineEdit {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
    font-family: "Courier New", monospace;
}}

QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}

QPushButton {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 5px 14px;
    font-family: "Courier New", monospace;
    font-size: 11px;
    letter-spacing: 1px;
}}

QPushButton:hover {{
    border: 1px solid {ACCENT};
    color: {ACCENT};
}}

QPushButton:pressed {{
    background-color: {BORDER};
}}

QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
}}

QLabel {{
    background: transparent;
}}

QGroupBox {{
    border: 1px solid {BORDER};
    margin-top: 8px;
    padding-top: 8px;
    font-family: "Courier New", monospace;
    font-size: 11px;
    color: {TEXT_DIM};
    letter-spacing: 1px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: {ACCENT};
}}

QTextEdit {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    font-family: "Courier New", monospace;
    font-size: 12px;
}}

QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}

QTableWidget {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    font-family: "Courier New", monospace;
    font-size: 11px;
    selection-background-color: {BORDER};
}}

QTableWidget::item {{
    padding: 4px 8px;
    border: none;
}}

QHeaderView::section {{
    background-color: {BG};
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
    padding: 4px 8px;
    font-family: "Courier New", monospace;
    font-size: 10px;
    letter-spacing: 1px;
}}

QComboBox {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
    font-family: "Courier New", monospace;
}}

QComboBox:focus {{
    border: 1px solid {ACCENT};
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {BORDER};
}}
"""

# ── Label styles (inline stylesheet strings) ──────────────────────────────────
def label_style(color: str, size: int = 12, bold: bool = False) -> str:
    weight = "bold" if bold else "normal"
    return (f"color: {color}; font-family: 'Courier New', monospace; "
            f"font-size: {size}px; font-weight: {weight}; background: transparent;")

STYLE_ACCENT  = label_style(ACCENT,   12)
STYLE_DIM     = label_style(TEXT_DIM, 11)
STYLE_GREEN   = label_style(GREEN,    12)
STYLE_RED     = label_style(RED,      12)
STYLE_AMBER   = label_style(AMBER,    12)
STYLE_TEXT    = label_style(TEXT,     12)
STYLE_HEADER  = label_style(ACCENT,   14, bold=True)

# ── Logo SVG fallback — used only if PNG not found ────────────────────────────
# The real logo is MORBION__.png — loaded at runtime by load_logo_pixmap()
LOGO_SVG = """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <polygon points="50,5 93,27.5 93,72.5 50,95 7,72.5 7,27.5"
           fill="none" stroke="#00d4ff" stroke-width="3"/>
  <text x="50" y="62" text-anchor="middle"
        font-family="Courier New, monospace" font-size="36"
        font-weight="bold" fill="#00d4ff">M</text>
</svg>"""

WATERMARK_SVG = """<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <polygon points="100,10 186,55 186,145 100,190 14,145 14,55"
           fill="none" stroke="#00d4ff" stroke-width="2" opacity="0.08"/>
  <text x="100" y="118" text-anchor="middle"
        font-family="Courier New, monospace" font-size="72"
        font-weight="bold" fill="#00d4ff" opacity="0.05">M</text>
</svg>"""


def load_logo_pixmap(config: dict, size: int = 120):
    """
    Load the MORBION PNG logo as a QPixmap.
    Falls back to SVG rendering if PNG not found.
    config["logo_path"] is relative to the directory containing main.py.
    """
    import os
    from PyQt6.QtGui     import QPixmap
    from PyQt6.QtCore    import Qt

    base_dir   = os.path.dirname(os.path.abspath(__file__))
    logo_file  = config.get("logo_path", "MORBION__.png")
    logo_path  = os.path.join(base_dir, logo_file)

    if os.path.exists(logo_path):
        px = QPixmap(logo_path)
        if not px.isNull():
            return px.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    # Fallback — render SVG to pixmap
    from PyQt6.QtSvg     import QSvgRenderer
    from PyQt6.QtGui     import QPainter
    from PyQt6.QtCore    import QByteArray, QSize

    renderer = QSvgRenderer(QByteArray(LOGO_SVG.encode()))
    px       = QPixmap(QSize(size, size))
    px.fill(Qt.GlobalColor.transparent)
    painter  = QPainter(px)
    renderer.render(painter)
    painter.end()
    return px
