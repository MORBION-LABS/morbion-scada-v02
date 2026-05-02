"""
tui/screens/plc.py — PLC Program Editor Screen
MORBION SCADA v02

Process selector + status panel + ST editor.
Upload, reload, validate, download, diff.
Defensive: file I/O errors, server errors, empty source.
"""

import asyncio
import os
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Label, Button, Input
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.binding import Binding

from tui.widgets.st_editor import STViewer, STEditor
from core.commands import PROCESS_NAMES

_CYAN  = "#00d4ff"
_GREEN = "#00ff88"
_RED   = "#ff3333"
_AMBER = "#ffaa00"
_DIM   = "#4a7a8c"
_TEXT  = "#d0e8f0"


class PLCScreen(Screen):
    """PLC program viewer and editor."""

    BINDINGS = [
        Binding("escape", "go_back",   "Dashboard", show=True),
        Binding("f2",     "goto_proc", "Process",   show=True),
        Binding("f3",     "goto_alarms","Alarms",   show=True),
        Binding("ctrl+s", "upload",    "Upload",    show=True),
        Binding("ctrl+r", "reload",    "Reload",    show=True),
        Binding("ctrl+d", "download",  "Download",  show=True),
    ]

    DEFAULT_CSS = """
    PLCScreen {
        background: #02080a;
    }
    #plc-header {
        height: 1;
        background: #051014;
        padding: 0 2;
        border-bottom: solid #0a2229;
    }
    #plc-selector {
        height: 3;
        background: #051014;
        padding: 0 1;
        border-bottom: solid #0a2229;
    }
    #plc-body {
        height: 1fr;
        layout: horizontal;
    }
    #plc-left {
        width: 28;
        border-right: solid #0a2229;
        padding: 1;
        overflow-y: scroll;
    }
    #plc-right {
        width: 1fr;
        overflow-y: scroll;
    }
    #plc-toolbar {
        height: 3;
        background: #051014;
        border-top: solid #0a2229;
        padding: 0 1;
    }
    #plc-feedback {
        height: 1;
        background: #051014;
        padding: 0 2;
    }
    #filepath-input {
        background: #02080a;
        border: solid #0a2229;
        color: #d0e8f0;
        width: 40;
    }
    Button {
        background: #051014;
        border: solid #0a2229;
        color: #d0e8f0;
        margin: 0 1;
        min-width: 10;
    }
    Button:hover {
        border: solid #00d4ff;
        color: #00d4ff;
    }
    Button.-danger {
        border: solid #ff3333;
        color: #ff3333;
    }
    Button.-success {
        border: solid #00ff88;
        color: #00ff88;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current = "boiler"
        self._source  = ""

    def compose(self) -> ComposeResult:
        yield Label(
            f"[{_CYAN}]◈ PLC PROGRAMMING[/{_CYAN}]",
            id="plc-header"
        )

        # Process selector
        with Horizontal(id="plc-selector"):
            for p in PROCESS_NAMES:
                short = {"pumping_station":"PS","heat_exchanger":"HX",
                         "boiler":"BL","pipeline":"PL"}.get(p, p[:2].upper())
                yield Button(short, id=f"plc-sel-{p}")

        with Horizontal(id="plc-body"):
            # Left — status + variables
            with ScrollableContainer(id="plc-left"):
                yield Label(f"[{_CYAN}]STATUS[/{_CYAN}]")
                yield Label("", id="plc-loaded")
                yield Label("", id="plc-scans")
                yield Label("", id="plc-error")
                yield Label("", id="plc-file")
                yield Label(f"\n[{_CYAN}]INPUTS[/{_CYAN}]")
                yield Label("", id="plc-inputs")
                yield Label(f"\n[{_CYAN}]OUTPUTS[/{_CYAN}]")
                yield Label("", id="plc-outputs")
                yield Label(f"\n[{_CYAN}]PARAMETERS[/{_CYAN}]")
                yield Label("", id="plc-params")

            # Right — ST source viewer
            with ScrollableContainer(id="plc-right"):
                yield STViewer(id="plc-viewer")

        # Toolbar
        with Horizontal(id="plc-toolbar"):
            yield Button("SYNC",     id="btn-sync")
            yield Button("RELOAD",   id="btn-reload",   classes="-success")
            yield Button("UPLOAD",   id="btn-upload",   classes="-success")
            yield Button("DOWNLOAD", id="btn-download")
            yield Button("DIFF",     id="btn-diff")
            yield Input(
                placeholder="/path/to/file.st",
                id="filepath-input"
            )

        yield Label("", id="plc-feedback")

    def on_mount(self) -> None:
        self._load_process("boiler")

    # ── Process loading ───────────────────────────────────────────────────────

    def _load_process(self, proc: str) -> None:
        """Switch to process and fetch PLC data."""
        if proc not in PROCESS_NAMES:
            return
        self._current = proc
        self._feedback(f"Syncing {proc}...", _DIM)
        self.app.call_later(self._fetch_plc_data)

    async def _fetch_plc_data(self) -> None:
        """Fetch PLC program, status, variables from server."""
        proc = self._current
        try:
            rest = getattr(self.app, "_rest", None)
            if not rest:
                self._feedback("No REST client", _RED)
                return

            data = await rest.plc_get_program(proc)
            if not data:
                self._feedback(f"No data for {proc}", _RED)
                return

            # Source
            source = data.get("source", "")
            self._source = source if isinstance(source, str) else ""
            try:
                self.query_one("#plc-viewer", STViewer).set_source(self._source)
            except Exception:
                pass

            # Status
            status = data.get("status", {}) or {}
            loaded = status.get("loaded", False)
            scans  = status.get("scan_count", 0)
            err    = status.get("last_error", "") or ""
            pfile  = status.get("program_file", "") or ""

            try:
                self.query_one("#plc-loaded", Label).update(
                    f"[{_GREEN}]Loaded: YES[/{_GREEN}]" if loaded
                    else f"[{_RED}]Loaded: NO[/{_RED}]"
                )
                self.query_one("#plc-scans", Label).update(
                    f"[{_DIM}]Scans: {scans}[/{_DIM}]"
                )
                self.query_one("#plc-error", Label).update(
                    f"[{_RED}]Error: {err[:30]}[/{_RED}]" if err
                    else f"[{_DIM}]Error: none[/{_DIM}]"
                )
                self.query_one("#plc-file", Label).update(
                    f"[{_DIM}]{os.path.basename(pfile)}[/{_DIM}]"
                )
            except Exception:
                pass

            # Variables
            var_data = data.get("variables", {}) or {}
            inner    = var_data.get("variables", var_data)

            def _fmt_vars(section: str) -> str:
                items = inner.get(section, {}) or {}
                if not items:
                    return f"[{_DIM}](none)[/{_DIM}]"
                lines = []
                for k in list(items.keys())[:12]:
                    lines.append(f"[{_DIM}]{k}[/{_DIM}]")
                if len(items) > 12:
                    lines.append(f"[{_DIM}]+{len(items)-12} more[/{_DIM}]")
                return "\n".join(lines)

            try:
                self.query_one("#plc-inputs",  Label).update(_fmt_vars("inputs"))
                self.query_one("#plc-outputs", Label).update(_fmt_vars("outputs"))
                self.query_one("#plc-params",  Label).update(_fmt_vars("parameters"))
            except Exception:
                pass

            self._feedback(f"Synced — {proc}  ({len(self._source)} chars)", _GREEN)

        except Exception as e:
            self._feedback(f"Fetch error: {e}", _RED)

    # ── Buttons ───────────────────────────────────────────────────────────────

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        # Process selector
        if btn_id.startswith("plc-sel-"):
            proc = btn_id[8:]
            self._load_process(proc)
            return

        if btn_id == "btn-sync":
            await self._fetch_plc_data()

        elif btn_id == "btn-reload":
            await self._do_reload()

        elif btn_id == "btn-upload":
            await self._do_upload()

        elif btn_id == "btn-download":
            await self._do_download()

        elif btn_id == "btn-diff":
            await self._do_diff()

    async def _do_reload(self) -> None:
        """Hot reload from disk."""
        try:
            rest   = getattr(self.app, "_rest", None)
            result = await rest.plc_reload(self._current)
            if result and result.get("ok"):
                self._feedback(f"✓ Reloaded {self._current}", _GREEN)
                await self._fetch_plc_data()
            else:
                err = result.get("error","unknown") if result else "no response"
                self._feedback(f"Reload failed: {err}", _RED)
        except Exception as e:
            self._feedback(f"Reload error: {e}", _RED)

    async def _do_upload(self) -> None:
        """Upload from file path in input."""
        filepath = self._get_filepath()
        if not filepath:
            self._feedback("Enter filepath in the input field first", _AMBER)
            return
        if not os.path.exists(filepath):
            self._feedback(f"File not found: {filepath}", _RED)
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
            rest   = getattr(self.app, "_rest", None)
            result = await rest.plc_upload(self._current, source)
            if result and result.get("ok"):
                self._feedback(f"✓ Uploaded {filepath} → {self._current}", _GREEN)
                await self._fetch_plc_data()
            else:
                err = result.get("error","unknown") if result else "no response"
                self._feedback(f"Upload failed: {err}", _RED)
        except OSError as e:
            self._feedback(f"File error: {e}", _RED)
        except Exception as e:
            self._feedback(f"Upload error: {e}", _RED)

    async def _do_download(self) -> None:
        """Download current source to file."""
        filepath = self._get_filepath()
        if not filepath:
            self._feedback("Enter filepath in the input field first", _AMBER)
            return
        if not self._source:
            self._feedback("No source loaded — sync first", _AMBER)
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self._source)
            self._feedback(f"✓ Saved to {filepath}", _GREEN)
        except OSError as e:
            self._feedback(f"Save error: {e}", _RED)

    async def _do_diff(self) -> None:
        """Diff running source vs local file."""
        filepath = self._get_filepath()
        if not filepath:
            self._feedback("Enter filepath in the input field first", _AMBER)
            return

        executor = getattr(self.app, "_executor", None)
        if not executor:
            self._feedback("No executor", _RED)
            return

        result = await executor.cmd_plc([self._current, "diff", filepath])
        if result:
            for text, style in result.lines:
                if text and not text.startswith("__"):
                    colour_map = {
                        "green":_GREEN,"red":_RED,"amber":_AMBER,
                        "cyan":_CYAN,"dim":_DIM,
                    }
                    c = colour_map.get(style, _TEXT)
                    self._feedback(text[:120], c)
                    break

    def _get_filepath(self) -> str:
        """Get and expand filepath from input widget."""
        try:
            raw = self.query_one("#filepath-input", Input).value.strip()
            return os.path.expanduser(raw) if raw else ""
        except Exception:
            return ""

    # ── Key actions ───────────────────────────────────────────────────────────

    def action_upload(self) -> None:
        self.app.call_later(self._do_upload)

    def action_reload(self) -> None:
        self.app.call_later(self._do_reload)

    def action_download(self) -> None:
        self.app.call_later(self._do_download)

    def _feedback(self, text: str, colour: str) -> None:
        try:
            self.query_one("#plc-feedback", Label).update(
                f"[{colour}]{text[:120]}[/{colour}]"
            )
        except Exception:
            pass

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_goto_proc(self) -> None:
        self.app.push_screen("process")

    def action_goto_alarms(self) -> None:
        self.app.push_screen("alarms")
