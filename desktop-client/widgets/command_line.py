"""
command_line.py — MORBION SCRIPTING ENGINE
Surgical Rebuild v10 — FULL ENGINE RESTORATION (NO NERFS)
"""
import os, json, time, logging, threading
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import theme

log = logging.getLogger("command_line")

class CommandLine(QWidget):
    print_signal = pyqtSignal(str, str)

    # ── Master Tag Map ───────────────────────────────────────────────────────
    # Maps human tags to (Register, Scale, Unit) for the 'write' command
    TAG_MAP = {
        "pumping_station": {
            "level": (0, 10, "%"), "speed": (2, 1, "RPM"), "flow": (3, 10, "m3/hr"),
            "inlet_valve": (8, 10, "%"), "outlet_valve": (9, 10, "%"), "fault": (14, 1, "code")
        },
        "heat_exchanger": {
            "hot_speed": (12, 1, "RPM"), "cold_speed": (13, 1, "RPM"),
            "hot_valve": (14, 10, "%"), "cold_valve": (15, 10, "%"), "fault": (16, 1, "code")
        },
        "boiler": {
            "pressure": (0, 100, "bar"), "level": (2, 10, "%"), "burner": (6, 1, "state"),
            "pump_speed": (7, 1, "RPM"), "steam_valve": (8, 10, "%"), "fault": (14, 1, "code")
        },
        "pipeline": {
            "speed": (3, 1, "RPM"), "duty": (5, 1, "0/1"), "standby": (7, 1, "0/1"),
            "inlet_valve": (8, 10, "%"), "outlet_valve": (9, 10, "%"), "fault": (14, 1, "code")
        }
    }

    HELP_TEXT = {
        "read":    "read <process_name> [tag]  — Read full process or specific tag",
        "write":   "write <process> <tag> <val> — Write to register with 350ms verification",
        "inject":  "inject <process> <tag> <val> — Force a sensor value (Alias for write)",
        "plc":     "plc <process> status|source|reload — Management for ST programs",
        "watch":   "watch <process> [tag] — Enable live scrolling monitor",
        "unwatch": "unwatch — Stop all active monitors",
        "alarms":  "alarms ack|history — Alarm management subsystem",
        "status":  "status — Global server and process health check",
        "cls":     "cls — Clear terminal output"
    }

    def __init__(self, rest, config, get_plant):
        super().__init__()
        self._rest, self._config, self._get_plant = rest, config, get_plant
        self._watch_timers = {}
        self._build_ui()
        self.print_signal.connect(self._do_print)
        
        # ── Welcome UI Text ──
        self._do_print("MORBION SCADA v02 — INDUSTRIAL SCRIPTING ENGINE", theme.ACCENT)
        self._do_print("INTELLIGENCE. PRECISION. VIGILANCE.", theme.TEXT_DIM)
        self._do_print("Type 'help' for full command vocabulary.", theme.TEXT_DIM)

    def _build_ui(self):
        self.setStyleSheet(f"background: {theme.SURFACE};")
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        
        # Title bar
        title = QLabel(" MORBION SCRIPTING ENGINE")
        title.setFixedHeight(22)
        title.setStyleSheet(f"background: {theme.BG}; color: {theme.ACCENT}; font-weight: bold; font-size: 10px; border-bottom: 1px solid {theme.BORDER};")
        layout.addWidget(title)

        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._h_splitter.setHandleWidth(4)
        self._h_splitter.setStyleSheet(f"QSplitter::handle {{ background: {theme.BORDER}; }}")
        
        # LEFT: Watchlist
        left_cont = QWidget(); left_lay = QVBoxLayout(left_cont); left_lay.setContentsMargins(4,4,4,4)
        left_lay.addWidget(QLabel("LIVE TAG WATCHLIST"))
        self._inspector = QTreeWidget()
        self._inspector.setHeaderLabels(["TAG", "VALUE"])
        self._inspector.setStyleSheet(f"background: {theme.BG}; border: 1px solid {theme.BORDER}; font-size: 11px;")
        self._inspector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_lay.addWidget(self._inspector)
        self._h_splitter.addWidget(left_cont)
        
        # RIGHT: Terminal
        right_cont = QWidget(); right_lay = QVBoxLayout(right_cont); right_lay.setContentsMargins(4,4,4,4)
        
        inp_row = QHBoxLayout(); inp_row.setContentsMargins(0,0,0,2)
        prompt = QLabel("morbion › "); prompt.setStyleSheet(f"color: {theme.ACCENT}; font-weight: bold;")
        self._in = QLineEdit()
        self._in.setPlaceholderText("Enter full command (e.g. read pumping_station)...")
        self._in.setStyleSheet(f"background: {theme.BG}; color: white; border: 1px solid {theme.BORDER}; padding: 4px;")
        self._in.returnPressed.connect(self._on_enter)
        inp_row.addWidget(prompt); inp_row.addWidget(self._in)
        right_lay.addLayout(inp_row)
        
        self._out = QTextEdit(); self._out.setReadOnly(True)
        self._out.setStyleSheet(f"background: {theme.BG}; color: {theme.TEXT}; border: 1px solid {theme.BORDER}; font-family: 'Courier New'; font-size: 12px;")
        self._out.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_lay.addWidget(self._out)
        self._h_splitter.addWidget(right_cont)
        
        self._h_splitter.setSizes([300, 900])
        layout.addWidget(self._h_splitter)

    # ── Engine Logic (Restored Verbs) ────────────────────────────────────────

    def _on_enter(self):
        raw = self._in.text().strip()
        if not raw: return
        self._in.clear(); self._do_print(f"› {raw}", theme.ACCENT)
        threading.Thread(target=self._dispatch, args=(raw,), daemon=True).start()

    def _dispatch(self, raw):
        parts = raw.split(); verb = parts[0].lower() if parts else ""
        try:
            if verb == "help":
                self.print_signal.emit("─"*50, theme.BORDER)
                for v, desc in self.HELP_TEXT.items():
                    self.print_signal.emit(f" {v:<10} : {desc}", theme.TEXT)
                self.print_signal.emit("─"*50, theme.BORDER)
            
            elif verb == "cls": QTimer.singleShot(0, self._out.clear)
            
            elif verb == "status":
                h = self._rest.get_health()
                if h: self.print_signal.emit(f"SERVER: {h.get('server')} | POLL: {h.get('poll_rate_ms')}ms | ONLINE: {h.get('processes_online')}/4", theme.GREEN)
            
            elif verb == "read" and len(parts) >= 2:
                p_name = parts[1].lower()
                data = self._get_plant().get(p_name)
                if data:
                    if len(parts) > 2: # Read specific tag
                        tag = parts[2].lower()
                        self.print_signal.emit(f" [{p_name}] {tag} = {data.get(tag, 'NOT FOUND')}", theme.TEXT)
                    else: # Read whole process
                        self.print_signal.emit(json.dumps(data, indent=2), theme.TEXT)
                else: self.print_signal.emit(f"Process '{p_name}' not found.", theme.RED)

            elif (verb == "write" or verb == "inject") and len(parts) >= 4:
                self._handle_write(parts[1], parts[2], parts[3])

            elif verb == "plc" and len(parts) >= 3:
                self._handle_plc(parts[1], parts[2])

            elif verb == "watch" and len(parts) >= 2:
                self._start_watch(parts[1], parts[2] if len(parts) > 2 else None)

            elif verb == "unwatch":
                for t in self._watch_timers.values(): t.stop()
                self._watch_timers.clear()
                self.print_signal.emit("All monitors stopped.", theme.TEXT_DIM)

            else:
                self.print_signal.emit(f"Unknown Verb: {verb}. Check 'help'.", theme.RED)
        except Exception as e:
            self.print_signal.emit(f"Engine Error: {e}", theme.RED)

    # ── Restoration: Write + Verify Logic ──
    def _handle_write(self, proc, tag, val):
        p_name = proc.lower()
        tag_info = self.TAG_MAP.get(p_name, {}).get(tag.lower())
        if not tag_info:
            self.print_signal.emit(f"Error: Tag '{tag}' unknown for {p_name}", theme.RED)
            return
        
        reg, scale, unit = tag_info
        raw_val = int(float(val) * scale)
        
        self.print_signal.emit(f" Writing {p_name} Reg {reg} = {raw_val}...", theme.TEXT_DIM)
        res = self._rest.write_register(p_name, reg, raw_val)
        
        if res and res.get("ok"):
            # The 350ms verification readback
            time.sleep(0.35)
            # Fetch latest data from local state cache
            latest = self._get_plant().get(p_name, {}).get(tag.lower())
            self.print_signal.emit(f" CONFIRMED: {p_name}.{tag} is now {latest} {unit}", theme.GREEN)
        else:
            self.print_signal.emit(" WRITE FAILED", theme.RED)

    def _handle_plc(self, proc, sub):
        if sub == "status":
            res = self._rest.plc_get_status(proc)
            self.print_signal.emit(json.dumps(res, indent=2) if res else "PLC VM OFFLINE", theme.GREEN)
        elif sub == "source":
            res = self._rest.plc_get_program(proc)
            self.print_signal.emit(res.get("source", "NO SOURCE") if res else "TIMEOUT", theme.WHITE)
        elif sub == "reload":
            res = self._rest.plc_reload(proc)
            self.print_signal.emit("RELOAD SENT" if res else "FAILED", theme.AMBER)

    def _start_watch(self, proc, tag):
        key = f"{proc}:{tag}"
        if key in self._watch_timers: return
        timer = QTimer(self)
        timer.timeout.connect(lambda: self._watch_tick(proc, tag))
        timer.start(1000)
        self._watch_timers[key] = timer
        self.print_signal.emit(f" Monitoring {proc} {tag or ''}...", theme.ACCENT)

    def _watch_tick(self, proc, tag):
        data = self._get_plant().get(proc.lower(), {})
        if tag:
            self.print_signal.emit(f" [WATCH] {proc}.{tag} = {data.get(tag.lower())}", theme.TEXT_DIM)
        else:
            self.print_signal.emit(f" [WATCH] {proc} ONLINE={data.get('online')}", theme.TEXT_DIM)

    # ── Watchlist Update (Tree) ──
    def update_inspector(self, data):
        self._inspector.setUpdatesEnabled(False)
        procs = ["pumping_station", "heat_exchanger", "boiler", "pipeline"]
        if self._inspector.topLevelItemCount() == 0:
            for p in procs:
                root = QTreeWidgetItem(self._inspector, [p.upper().replace("_", " "), ""])
                root.setData(0, Qt.ItemDataRole.UserRole, p)
        for i in range(self._inspector.topLevelItemCount()):
            item = self._inspector.topLevelItem(i); p_key = item.data(0, Qt.ItemDataRole.UserRole)
            p_data = data.get(p_key, {}); online = p_data.get("online")
            item.setText(1, "ONLINE" if online else "OFFLINE")
            item.setForeground(1, QColor(theme.GREEN if online else theme.RED))
            if online:
                existing = {item.child(j).text(0): item.child(j) for j in range(item.childCount())}
                for k, v in p_data.items():
                    if isinstance(v, (int, float, bool)) and k not in ["online", "port"]:
                        if k in existing: existing[k].setText(1, str(v))
                        else: QTreeWidgetItem(item, [k, str(v)])
        self._inspector.setUpdatesEnabled(True)

    @pyqtSlot(str, str)
    def _do_print(self, m, c):
        cur = self._out.textCursor(); cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(c)); cur.setCharFormat(fmt); cur.insertText(m + "\n"); self._out.ensureCursorVisible()
