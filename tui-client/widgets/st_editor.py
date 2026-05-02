"""
st_editor.py — Structured Text Code Editor
MORBION SCADA v02

TextArea widget configured for IEC 61131-3 logic editing.
"""

from textual.widgets import TextArea
from textual.binding import Binding

class STEditor(TextArea):
    """
    A code editor specifically for MORBION PLC logic.
    """
    
    BINDINGS = [
        Binding("ctrl+s", "save", "Save/Upload", show=True),
        Binding("ctrl+r", "reload", "Reload from Disk", show=True),
    ]

    def on_mount(self) -> None:
        self.theme = "vscode_dark" # Closest standard theme
        self.show_line_numbers = True
        self.tab_behavior = "indent"
        
        # Apply industrial theme overrides via inline styles
        self.styles.background = "#02080a" # BG
        self.styles.color = "#d0e8f0"      # TEXT
        self.styles.border = ("solid", "#0a2229") # BORDER

    def load_program(self, source: str):
        """Load PLC source code into the editor."""
        self.load_text(source)

    def get_program(self) -> str:
        """Retrieve current editor content for upload."""
        return self.text

    def action_save(self) -> None:
        """Triggered by Ctrl+S - handled by the PLC Screen."""
        self.post_message(self.SaveRequested(self.text))

    def action_reload(self) -> None:
        """Triggered by Ctrl+R - handled by the PLC Screen."""
        self.post_message(self.ReloadRequested())

    class SaveRequested(TextArea.Changed):
        """Custom message for PLC upload."""
        def __init__(self, text: str):
            self.text = text
            super().__init__(None)

    class ReloadRequested(TextArea.Changed):
        """Custom message for PLC reload."""
        def __init__(self):
            super().__init__(None)
