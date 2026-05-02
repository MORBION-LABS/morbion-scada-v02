# MORBION SCADA v02 — Desktop Client

**PyQt6 industrial HMI. Full read and write access. Maximum operator control.**

The desktop client is the primary operator interface. It connects to the SCADA server via REST and WebSocket, displays live process data across eight tabs, and provides a full scripting engine for direct register manipulation, PLC program management, and alarm control.

---

## Directory Structure

```
desktop-client/
├── config.json             Client configuration — server IP, operator name
├── installer.py            Interactive installer
├── main.py                 Entry point — loads config, launches splash
├── main_window.py          Main window — splitter layout, tab routing
├── splash.py               Connection splash — WebSocket connect + timeout
├── theme.py                All colours, fonts, QSS stylesheets
├── requirements.txt
│
├── connection/
│   ├── rest_client.py      REST API client (urllib, no external deps)
│   └── ws_thread.py        WebSocket background thread (auto-reconnect)
│
├── views/
│   ├── base_view.py        Base class — horizontal splitter, data/control panels
│   ├── overview_view.py    System Overview — four process cards
│   ├── pumping_view.py     Pumping Station — full data + operator control
│   ├── hx_view.py          Heat Exchanger — full data + operator control
│   ├── boiler_view.py      Boiler — full data + operator control
│   ├── pipeline_view.py    Pipeline — full data + operator control
│   ├── alarms_view.py      Alarm management — active + history tables
│   ├── plc_view.py         PLC Programming — ST editor + upload/reload
│   └── trends_view.py      Historical Trends — 120-point sparklines
│
└── widgets/
    ├── command_line.py     Scripting Engine — live tag inspector + terminal
    ├── control_panel.py    RegisterWriteRow, FaultClearButton, ControlButton
    ├── gauge_widget.py     Horizontal bar gauge with alarm markers
    ├── sparkline_widget.py Mini trend sparkline (120-point rolling)
    ├── status_badge.py     Online/Offline/Fault status badge
    ├── tank_widget.py      Vertical tank level display
    ├── value_label.py      Large numeric value with unit and alarm colouring
    └── valve_bar.py        Horizontal valve position indicator
```

---

## Installation

```bash
cd desktop-client
pip install -r requirements.txt
python installer.py
```

The installer prompts for:
- **SCADA Server IP** — IP of the machine running `server/main.py`
- **Server port** — default 5000
- **Operator name** — used for alarm acknowledgment (e.g. your name)
- **Logo filename** — filename of the MORBION logo PNG in this directory

This writes `config.json`.

---

## Running

```bash
cd desktop-client
python main.py
```

On first launch, a splash screen appears and attempts WebSocket connection to the configured server. If connection succeeds, the main window opens. If it times out (8 s), a retry panel appears with an IP input field.

---

## Configuration

`config.json`:

```json
{
  "server_host": "192.168.100.30",
  "server_port": 5000,
  "operator": "OPERATOR",
  "logo_path": "MORBION-LOGO.png"
}
```

| Field | Description |
|---|---|
| `server_host` | IP of the SCADA server |
| `server_port` | Port of the SCADA server (default 5000) |
| `operator` | Name used for alarm acknowledgments |
| `logo_path` | PNG logo filename — must be in the same directory as `main.py` |

The splash screen allows editing the server IP at runtime and saves it back to `config.json`.

---

## Tab Overview

| Tab | Description | Control |
|---|---|---|
| SYSTEM OVERVIEW | Four process cards — status, key gauges, critical values | Read only |
| PUMPING STATION | Full PS data + operator control panel | Full read/write |
| HEAT EXCHANGER | Full HX data + operator control panel | Full read/write |
| STEAM BOILER | Full boiler data + operator control panel | Full read/write |
| PETROLEUM PIPELINE | Full pipeline data + operator control panel | Full read/write |
| PLC PROGRAMMING | ST editor — view, upload, reload, download PLC programs | Read/upload |
| HISTORICAL TRENDS | 120-point rolling sparklines for all key tags | Read only |

Each process tab has a left/right splitter (default 70/30). Left panel: live data. Right panel: operator control. The splitter is draggable.

The main window has a vertical splitter between the tab area and the scripting engine at the bottom. Both sections are resizable by dragging the handle.

---

## Scripting Engine

The scripting engine is the lower panel of the main window. It has two sections split horizontally:

**Left: Live Tag Watchlist** — tree view showing all four processes and their live numeric values, updated every WebSocket push.

**Right: Terminal** — command input and output.

### Command Reference

```
read <process> [tag]
```
Read all values for a process, or a single tag.
```
read pumping_station
read boiler drum_pressure_bar
read all
```

```
write <process> <tag> <value>
inject <process> <tag> <value>
```
Write to a register using the human-readable tag name. `inject` is an alias for `write`.
```
write pumping_station speed 1200
write boiler burner 2
write pipeline duty 1
inject boiler pressure 11
```

```
plc <process> status|source|reload
```
Query or manage the PLC program.
```
plc boiler status
plc boiler source
plc boiler reload
```

```
watch <process> [tag]
```
Start live 1 s monitoring of a process or tag. Output scrolls in the terminal.
```
watch pumping_station tank_level_pct
watch boiler
```

```
unwatch
```
Stop all active watch monitors.

```
alarms [ack|history]
```
Show active alarms, acknowledge all, or show history.
```
alarms
alarms ack
alarms history
```

```
status
```
Global server and process health check.

```
cls
```
Clear terminal output.

```
help
```
Show all commands with descriptions.

### Tag Map (for write/inject commands)

**pumping_station:**
- `level` — reg 0, ×10, % (inject)
- `speed` — reg 2, ×1, RPM
- `flow` — reg 3, ×10, m³/hr (inject)
- `inlet_valve` — reg 8, ×10, %
- `outlet_valve` — reg 9, ×10, %
- `fault` — reg 14, ×1, code

**heat_exchanger:**
- `hot_speed` — reg 12, ×1, RPM
- `cold_speed` — reg 13, ×1, RPM
- `hot_valve` — reg 14, ×10, %
- `cold_valve` — reg 15, ×10, %
- `fault` — reg 16, ×1, code

**boiler:**
- `pressure` — reg 0, ×100, bar (inject)
- `level` — reg 2, ×10, % (inject)
- `burner` — reg 6, ×1, state (0/1/2)
- `pump_speed` — reg 7, ×1, RPM
- `steam_valve` — reg 8, ×10, %
- `fault` — reg 14, ×1, code

**pipeline:**
- `speed` — reg 3, ×1, RPM
- `duty` — reg 5, ×1, 0/1
- `standby` — reg 7, ×1, 0/1
- `inlet_valve` — reg 8, ×10, %
- `outlet_valve` — reg 9, ×10, %
- `fault` — reg 14, ×1, code

### Output Colour Coding

| Colour | Meaning |
|---|---|
| Cyan | Command echo |
| Green | Success, CONFIRMED, online |
| Red | Error, fault, offline |
| Amber | Warning, alarm |
| White | Data values |
| Dim | Metadata, timestamps |

---

## PLC Programming Tab

The PLC Programming tab connects to the server's PLC proxy API.

**Left panel:**
- Process selector — click to switch between processes
- Runtime status — Loaded indicator, scan count, last error
- Variable map — list of ST inputs, outputs, and parameters

**Right panel:**
- ST source editor with IEC 61131-3 syntax highlighting
  - Keywords (IF, THEN, FOR, etc.) — cyan
  - Function blocks (TON, TOF, SR, etc.) — amber
  - Comments `(* ... *)` — dim
- Line numbers
- VALIDATE — parse check only, returns errors without applying
- UPLOAD — validate and apply (confirmation dialog)
- RELOAD FROM DISK — hot reload from file, no editor needed
- DOWNLOAD — save current source to a local `.st` file

Upload procedure:
1. Edit the ST source in the editor
2. Click VALIDATE — fix any parse errors shown
3. Click UPLOAD — confirm the dialog
4. Watch the scan count increment — this confirms the new program is running

The PLC re-evaluates every 100 ms. Changes take effect on the next scan after upload.

---

## Operator Control Panels

Each process tab has a right-side control panel.

**Pump/Burner/Valve controls:** large coloured buttons for common state changes (START/STOP, BURNER OFF/LOW/HIGH, OPEN/CLOSE).

**Register Write Rows:** label + numeric input + WRITE button + feedback. Feedback shows CONFIRMED (green), UNVERIFIED (amber), or error (red) after a 350 ms read-back.

**Fault Management:** CLEAR FAULT / OPERATOR RESET button — writes 0 to register 14.

**Inject/Simulate section:** direct register injection for fault scenario training (e.g. inject high drum pressure to test boiler overpressure interlock).

---

## Verify-After-Write Behaviour

All control writes follow this pattern:

1. Write is sent via `POST /control`
2. Server confirms FC06 echo
3. After 350 ms, the register is read back from live state
4. If match: **CONFIRMED** (green)
5. If mismatch: **OVERRIDDEN** (amber) — the PLC legitimately overrode the command

An OVERRIDDEN result is not an error. It means a safety interlock or control loop rejected the command. Check the fault code and process conditions.

Example: commanding pump start when tank level is 3% will result in OVERRIDDEN because the low-level interlock trips the pump before the next read-back.

---

## Theme and Colours

All colours are defined in `theme.py`. Do not hardcode colours elsewhere.

| Constant | Hex | Purpose |
|---|---|---|
| `BG` | `#02080a` | Main background |
| `SURFACE` | `#051014` | Panel/card background |
| `BORDER` | `#0a2229` | Borders, separators |
| `ACCENT` | `#00d4ff` | Cyan — active, selected, titles |
| `TEXT` | `#d0e8f0` | Primary text |
| `TEXT_DIM` | `#4a7a8c` | Labels, metadata |
| `GREEN` | `#00ff88` | Online, running, confirmed |
| `RED` | `#ff3333` | Fault, offline, error |
| `AMBER` | `#ffaa00` | Warning, alarm |
| `WHITE` | `#ffffff` | Data values in sparklines |

Font: `Courier New` / `Consolas` / monospace throughout. Industrial control systems use monospaced fonts everywhere.

---

## Requirements

```
PyQt6>=6.6
websocket-client>=1.7
```

Python 3.11 or higher required.

---

## Troubleshooting

**Splash screen shows "SERVER UNREACHABLE"**
- Confirm server is running: `python server/main.py`
- Check `config.json` — `server_host` must be the server's IP
- Verify port 5000 is reachable: `curl http://<server_host>:5000/health`
- Use the splash screen IP input to try a different address

**Logo not displayed**
- `logo_path` in `config.json` must be the filename of a PNG in the same directory as `main.py`
- Confirm the file exists: `ls desktop-client/MORBION-LOGO.png`
- The fallback is a cyan hexagon SVG — if you see that, the PNG path is wrong

**PLC Programs tab shows no source**
- The process HTTP API ports (5020, 5060, 5070, 5080) must be reachable from the server
- Confirm processes are running on the PLC machine: `python processes/manager.py status`
- Test the server proxy: `curl http://<server_host>:5000/plc/boiler/program`

**All gauges show 0 / all badges show OFFLINE**
- WebSocket is not receiving data — check the server is broadcasting
- The ws_thread logs errors to the Python console — run from terminal to see them
- Verify processes are online: `curl http://<server_host>:5000/health`

**Scripting engine — write returns OVERRIDDEN**
- This is correct behaviour — the PLC rejected the command
- Check the fault code: `read <process> fault_code`
- Resolve the fault condition first, then retry the command

**Window layout stuck / tabs unresponsive**
- The main splitter (tabs vs scripting engine) is draggable — grab the horizontal bar
- Each process view has a left/right splitter — grab the vertical bar between data and control panels
- Minimum heights are set to prevent panels from collapsing entirely (50 px)

---

*MORBION SCADA v02 — Intelligence. Precision. Vigilance.*
