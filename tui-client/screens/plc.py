"""
plc.py — PLC Programming and Logic Screen
MORBION SCADA v02

Interface for editing and uploading IEC 61131-3 Structured Text.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical, Horizontal, Container
from textual.widgets import Header, Footer, Label, Button, Select, Static
from textual.binding import Binding

from widgets.st_editor import STEditor

class PLCScreen(Screen):
    """
    PLC Logic Engineering terminal.
    """
    DEFAULT_CSS = """
    PLCScreen #main-container {
        padding: 1;
        background: #02080a;
    }

    .plc-header {
        height: 3;
        border-bottom: double #00d4ff;
        margin-bottom: 1;
    }

    #editor-container {
        height: 1fr;
        border: solid #0a2229;
    }

    #sidebar {
        width: 30;
        border-right: solid #0a2229;
        padding: 1;
    }

    .status-item {
        margin-bottom: 1;
    }

    .status-label {
        color: #4a7a8c;
        font-size: 80%;
    }

    .status-value {
        color: #d0e8f0;
    }

    #controls {
        height: 3;
        padding: 0 1;
        background: #051014;
        border-top: solid #0a2229;
        dock: bottom;
        content-align: left middle;
    }
    """

    BINDINGS = [
        Binding("f5", "sync", "Sync Status", show=True),
        Binding("ctrl+s", "upload", "Upload Logic", show=True),
    ]

    def __init__(self, rest_client, **kwargs):
        super().__init__(**kwargs)
        self.rest = rest_client
        self.current_process = "pumping_station"

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            with Horizontal(classes="plc-header"):
                yield Label("PLC LOGIC ENGINEERING", classes="process-title")
                yield Select(
                    [(p.replace('_',' ').title(), p) for p in ["pumping_station", "heat_exchanger", "boiler", "pipeline"]],
                    value="pumping_station",
                    id="process-selector"
                )

            with Horizontal():
                with Vertical(id="sidebar"):
                    yield Label("RUNTIME STATUS", classes="section-label")
                    
                    with Container(classes="status-item"):
                        yield Label("LOADED", classes="status-label")
                        yield Label("—", id="status-loaded", classes="status-value")

                    with Container(classes="status-item"):
                        yield Label("SCAN COUNT", classes="status-label")
                        yield Label("—", id="status-scans", classes="status-value")

                    with Container(classes="status-item"):
                        yield Label("LAST ERROR", classes="status-label")
                        yield Label("NONE", id="status-error", classes="status-value")
                    
                    yield Label("VARIABLE MAP", classes="section-label")
                    yield Static("", id="var-map-display")

                with Vertical(id="editor-container"):
                    yield STEditor(id="st-editor")

            with Horizontal(id="controls"):
                yield Button("UPLOAD TO PLC (Ctrl+S)", variant="success", id="btn-upload")
                yield Button("RELOAD DISK", variant="warning", id="btn-reload")
                yield Button("SYNC", variant="primary", id="btn-sync")

        yield Footer()

    async def on_mount(self) -> None:
        await self.action_sync()

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "process-selector":
            self.current_process = str(event.value)
            await self.action_sync()

    async def action_sync(self) -> None:
        """Fetch program and status from the server."""
        self.notify(f"Syncing {self.current_process}...", title="PLC API")
        res = await self.rest.get_plc_program(self.current_process)
        
        if res.get("process"):
            # Update Status
            stat = res.get("status", {})
            self.query_one("#status-loaded").update("YES" if stat.get("loaded") else "NO")
            self.query_one("#status-scans").update(str(stat.get("scan_count", 0)))
            self.query_one("#status-error").update(str(stat.get("last_error", "NONE"))[:25])
            
            # Update Editor
            self.query_one("#st-editor", STEditor).load_program(res.get("source", ""))
            
            # Update Variables (Summary)
            vars_obj = res.get("variables", {}).get("variables", {})
            inputs = len(vars_obj.get("inputs", {}))
            outputs = len(vars_obj.get("outputs", {}))
            self.query_one("#var-map-display").update(f"I: {inputs} | O: {outputs}")
        else:
            self.notify("Failed to connect to PLC API", severity="error")

    async def action_upload(self) -> None:
        """Send current editor text to the process PLC."""
        source = self.query_one("#st-editor", STEditor).text
        res = await self.rest.post_plc_program(self.current_process, source)
        
        if res.get("ok"):
            self.notify("Upload Successful - Logic Running", severity="information")
            await self.action_sync()
        else:
            self.notify(f"Compile Error: {res.get('error')}", severity="error")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-upload":
            await self.action_upload()
        elif event.button.id == "btn-reload":
            await self.rest.reload_plc(self.current_process)
            await self.action_sync()
        elif event.button.id == "btn-sync":
            await self.action_sync()

    # Handle custom messages from the STEditor widget
    async def on_st_editor_save_requested(self, message: STEditor.SaveRequested) -> None:
        await self.action_upload()

    async def on_st_editor_reload_requested(self, message: STEditor.ReloadRequested) -> None:
        await self.action_sync()
