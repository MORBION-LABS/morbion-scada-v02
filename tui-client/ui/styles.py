"""
styles.py — Mythic Dark Industrial Theme
MORBION SCADA v02 — REBOOT
"""
from rich.theme import Theme
from rich.style import Style

# ── Colors ───────────────────────────────────────────────────────────────────
BG      = "#02080a"
ACCENT  = "#00d4ff"   # Cyan
SAFE    = "#00ff88"   # Green
DANGER  = "#ff3333"   # Red
WARN    = "#ffaa00"   # Amber
TEXT    = "#d0e8f0"
DIM     = "#4a7a8c"

MYTHIC_THEME = Theme({
    "status.online":  Style(color=SAFE, bold=True),
    "status.offline": Style(color=DANGER, bold=True),
    "status.fault":   Style(color=WARN, bold=True, reverse=True),
    "metric.label":   Style(color=ACCENT, bold=True),
    "metric.value":   Style(color=TEXT),
    "metric.unit":    Style(color=DIM),
    "border.mythic":  Style(color=ACCENT),
    "border.dim":     Style(color=DIM),
    "table.header":   Style(color=ACCENT, bold=True),
    "alarm.crit":     Style(color=DANGER, bold=True, blink=True),
    "alarm.high":     Style(color=WARN, bold=True),
})
