"""
tui/widgets/st_editor.py — ST Source Editor with Syntax Highlighting
MORBION SCADA v02

TextArea subclass for IEC 61131-3 Structured Text.
Syntax highlighting via a custom TextAreaTheme:
  Keywords  → cyan
  FB names  → amber
  Comments  → dim
  Numbers   → white
  Strings   → green
Defensive: handles empty source, None source, very long programs.
"""

from textual.widgets import TextArea
from textual.widgets.text_area import TextAreaTheme
from rich.syntax import Syntax
from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text
import re


# ── Colour constants ──────────────────────────────────────────────────────────

_CYAN  = "#00d4ff"
_AMBER = "#ffaa00"
_DIM   = "#4a7a8c"
_WHITE = "#ffffff"
_GREEN = "#00ff88"
_BG    = "#02080a"
_TEXT  = "#d0e8f0"

# ── ST keyword sets ───────────────────────────────────────────────────────────

ST_KEYWORDS = {
    "IF", "THEN", "ELSIF", "ELSE", "END_IF",
    "WHILE", "DO", "END_WHILE",
    "FOR", "TO", "BY", "END_FOR",
    "RETURN", "AND", "OR", "NOT", "XOR",
    "VAR", "END_VAR",
    "TRUE", "FALSE",
    "REAL", "INT", "BOOL",
}

ST_FUNCTION_BLOCKS = {
    "TON", "TOF", "CTU", "SR", "RS",
    "LIMIT", "ABS", "MAX", "MIN", "SQRT",
}

# ── Highlighted read-only viewer ──────────────────────────────────────────────

class STViewer(Widget):
    """
    Read-only ST source viewer with syntax highlighting.
    Uses Rich markup for coloring — rendered in a scrollable widget.
    """

    DEFAULT_CSS = """
    STViewer {
        background: #02080a;
        color: #d0e8f0;
        overflow-y: scroll;
        padding: 0 1;
    }
    """

    def __init__(self, source: str = "", **kwargs):
        super().__init__(**kwargs)
        self._source = source or ""

    def set_source(self, source: str | None) -> None:
        """Update source. None → empty string."""
        self._source = source if isinstance(source, str) else ""
        self.refresh()

    def get_source(self) -> str:
        return self._source

    def render(self) -> Text:
        if not self._source:
            text = Text()
            text.append("(* No source loaded *)", style=_DIM)
            return text

        lines  = self._source.splitlines()
        result = Text()

        for line_num, line in enumerate(lines, 1):
            # Line number
            result.append(f"{line_num:>4}  ", style=_DIM)
            result.append_text(_highlight_st_line(line))
            result.append("\n")

        return result


class STEditor(TextArea):
    """
    Editable ST source editor.
    Uses Textual's built-in TextArea with a dark theme.
    Exposes get_source() and set_source() convenience methods.
    """

    DEFAULT_CSS = """
    STEditor {
        background: #02080a;
        color: #d0e8f0;
        border: solid #0a2229;
    }
    STEditor:focus {
        border: solid #00d4ff;
    }
    """

    def set_source(self, source: str | None) -> None:
        """Load source into editor. None → empty."""
        safe = source if isinstance(source, str) else ""
        self.load_text(safe)

    def get_source(self) -> str:
        """Return current editor content."""
        return self.text


# ── Syntax highlighter ────────────────────────────────────────────────────────

def _highlight_st_line(line: str) -> Text:
    """
    Highlight a single ST source line.
    Returns a Rich Text object.
    Processes: comments, strings, keywords, FB names, numbers, rest.
    """
    result = Text()

    # Full-line comment (* ... *) — simplified: check if line is only comment
    stripped = line.strip()

    # Handle block comment on its own line
    if stripped.startswith("(*") and stripped.endswith("*)"):
        result.append(line, style=_DIM)
        return result

    # Tokenise line character by character for inline highlighting
    i = 0
    n = len(line)

    while i < n:
        # Block comment start
        if line[i:i+2] == "(*":
            end = line.find("*)", i + 2)
            if end == -1:
                result.append(line[i:], style=_DIM)
                break
            else:
                result.append(line[i:end+2], style=_DIM)
                i = end + 2
            continue

        # String literal
        if line[i] == "'":
            end = line.find("'", i + 1)
            if end == -1:
                result.append(line[i:], style=_GREEN)
                break
            result.append(line[i:end+1], style=_GREEN)
            i = end + 1
            continue

        # Identifier or keyword
        if line[i].isalpha() or line[i] == "_":
            j = i
            while j < n and (line[j].isalnum() or line[j] == "_"):
                j += 1
            word = line[i:j]
            if word.upper() in ST_KEYWORDS:
                result.append(word, style=_CYAN)
            elif word.upper() in ST_FUNCTION_BLOCKS:
                result.append(word, style=_AMBER)
            else:
                result.append(word, style=_TEXT)
            i = j
            continue

        # Number
        if line[i].isdigit() or (line[i] == "." and i+1 < n and line[i+1].isdigit()):
            j = i
            has_dot = False
            while j < n and (line[j].isdigit() or (line[j] == "." and not has_dot)):
                if line[j] == ".":
                    has_dot = True
                j += 1
            result.append(line[i:j], style=_WHITE)
            i = j
            continue

        # Everything else
        result.append(line[i], style=_TEXT)
        i += 1

    return result
