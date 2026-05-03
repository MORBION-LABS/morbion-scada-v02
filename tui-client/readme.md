# MORBION SCADA v02 — TUI/CLI Client

**Intelligence. Precision. Vigilance.**

Terminal-based client for MORBION SCADA v02. Two modes sharing one engine. Maximum operator power. Runs anywhere Python runs — including over SSH.

---

## What This Is

```
python main.py
```

```
╔══════════════════════════════════════════════╗
║   MORBION SCADA v02                          ║
║   Intelligence. Precision. Vigilance.        ║
╠══════════════════════════════════════════════╣
║   Server:   192.168.100.30:5000              ║
║   Status:   ●ONLINE  4/4 processes           ║
║   Operator: OPERATOR                         ║
╠══════════════════════════════════════════════╣
║                                              ║
║   [1]  TUI  — Full-screen dashboard          ║
║   [2]  CLI  — Scripting shell                ║
║   [i]  Configure server address              ║
║   [q]  Quit                                  ║
║                                              ║
╚══════════════════════════════════════════════╝
```

Press `1` → TUI full-screen dashboard launches. Takes over the terminal completely.
Press `2` → CLI scripting shell launches. Pure text REPL.
Exit either mode → returns to this menu.
One mode at a time. No hybrid state. Clean swap.

---

## Directory Structure

```
tui-client/
├── main.py                    Entry point — main menu + mode launcher
├── config.json                Server IP, port, operator name
├── installer.py               Interactive config writer
├── requirements.txt
│
├── core/                      Shared engine — both modes import this
│   ├── __init__.py
│   ├── rest_client.py         Async httpx REST client
│   ├── ws_client.py           Async WebSocket live data feed
│   ├── commands.py            TAG_MAP + MSL definitions + tab completions
│   ├── executor.py            All command handlers + verified-write logic
│   └── history.py             Disk-persisted command history (500 entries)
│
├── cli/                       Raw scripting shell
│   ├── __init__.py
│   ├── output.py              Rich-formatted terminal output
│   └── shell.py               REPL loop, watch loop, batch runner
│
└── tui/                       Full-screen Textual dashboard
    ├── __init__.py
    ├── app.py                 App + WS feed + REST client + screen routing
    ├── screens/
    │   ├── __init__.py
    │   ├── dashboard.py       2×2 process grid + event log + command bar
    │   ├── process.py         Single process deep view + all tags + sparklines
    │   ├── alarms.py          Alarm table + history + acknowledge
    │   ├── plc.py             ST viewer + upload + reload + download + diff
    │   └── trends.py          All-process 120-point rolling sparklines
    └── widgets/
        ├── __init__.py
        ├── process_panel.py   Dashboard quadrant — one of the four panels
        ├── gauge.py           Horizontal Unicode bar gauge with alarm markers
        ├── sparkline.py       Rolling sparkline — Braille-resolution blocks
        ├── tank.py            ASCII vertical tank level display
        ├── alarm_table.py     Colour-coded DataTable for active alarms
        └── st_editor.py       ST syntax-highlighted source viewer + editor
```

---

## Installation

```bash
cd tui-client
pip install -r requirements.txt
python installer.py
```

The installer prompts for:
- **SCADA Server IP** — IP of the machine running `server/main.py`
- **Server port** — default 5000
- **Operator name** — used for alarm acknowledgment

This writes `config.json`. Run once before first launch.

---

## Requirements

```
textual>=0.57.0
httpx>=0.27.0
websockets>=12.0
pyyaml>=6.0
rich>=13.0.0
```

---

## Running

```bash
python main.py
```

The menu probes the server on every draw. If the server is unreachable, the menu still loads — both modes degrade gracefully showing OFFLINE status.

---

## TUI Mode

Full-screen Textual dashboard. Keyboard-driven. Updates live on every WebSocket push.

### Layout

```
◈ MORBION SCADA v02  ●LIVE  192.168.100.30:5000  14:07:29  ♥84
══════════════════════════════════════════════════════════════════
  PUMPING STATION ●ONLINE   │  HEAT EXCHANGER ●ONLINE
  Tank  [████████░░]  67.3% │  Eff   [██████░░░░]  63.1 %
  Flow  [████░░░░░░]  43.1  │  T Hot  180.2 °C
  Press [████░░░░░░]   4.82 │  T Cold  73.8 °C
  Pump  RUNNING ●           │  Q Duty 2847 kW
  Fault OK                  │  Fault  OK
──────────────────────────────────────────────────────────────────
  BOILER ●ONLINE            │  PIPELINE ●ONLINE
  Drum P [████████░░]  7.82 │  Outlet [████░░░░░░]  42.1
  Level  [████████░░]  52.1%│  Flow   [████████░░] 447.3
  Burner LOW ●              │  Duty   RUNNING ●
  Steam  2841 kg/hr         │  Leak   OK ●
  Fault  OK                 │  Fault  OK
══════════════════════════════════════════════════════════════════
  ⚠ 0 ALARMS   [F2]Process [F3]Alarms [F4]PLC [F5]Trends  [:]Cmd
══════════════════════════════════════════════════════════════════
  EVENT LOG
  14:07:28  boiler          drum_pressure_bar   7.82 → 7.84 bar
  14:07:27  pumping_station pump_running        False → True
══════════════════════════════════════════════════════════════════
```

### Key Bindings

| Key | Action |
|---|---|
| `:` | Open command bar — full MSL inside TUI |
| `F2` | Process deep view — all tags + sparklines |
| `F3` | Alarm management — active + history + acknowledge |
| `F4` | PLC programming — view + upload + reload + download + diff |
| `F5` | Trends — all-process 120-point rolling sparklines |
| `Esc` | Back to dashboard from any screen |
| `Ctrl+Q` | Quit TUI → return to main menu |
| `Tab` | Tab completion in command bar |
| `↑` `↓` | Command history navigation in command bar |

### TUI Features

**♥ Heartbeat counter** — top-right of header. Increments every WebSocket push. If it stops incrementing, the connection is dead before the OFFLINE badge appears.

**Event log** — bottom panel. Every meaningful state change across all four processes logged in real time with timestamp. pump_running False→True, fault_code 0→2, drum_pressure changes — all logged.

**Command bar** — press `:` to open a command input at the bottom. Type any MSL command. Tab completion works. History navigation works. Result flashes in the event log. Esc closes without executing.

**Alarm banner** — appears between header and grid when unacknowledged alarms are active. Red background for any CRIT. Amber for HIGH-only. Shows count and severity breakdown. Press `F3` to go to alarm management.

**Fault borders** — process panel border turns red when `fault_code ≠ 0`. Turns amber when the process is offline. Green (default) when healthy.

**PLC Screen** — view the live ST source with syntax highlighting. Upload a `.st` file from disk. Hot reload from disk. Download current running source. Diff running vs local file — shows line-level differences. `Ctrl+S` to upload, `Ctrl+R` to reload, `Ctrl+D` to download.

**Process Screen** — deep view for any single process. Process selector at top (PS / HX / BL / PL). Left panel: all gauges + all tag values. Right panel: rolling sparklines. Command bar for write/inject/fault commands.

**Trends Screen** — two-column layout. Left: Pumping Station + Heat Exchanger. Right: Boiler + Pipeline. 120-point rolling sparklines with alarm threshold markers.

---

## CLI Mode

Raw scripting shell. Pure text. Full MSL command language. Tab completion. Arrow key history. Ctrl+C cancels watch. Batch script runner. Runs perfectly over SSH.

### Shell Appearance

```
MORBION SCADA v02 — Scripting Shell
Connected: 192.168.100.30:5000  ●ONLINE 4/4
Type help for commands. Tab to complete. ↑↓ for history. exit to return to menu.

morbion › _
```

### Full MSL Command Reference

---

#### `read`

Read live process data from the plant snapshot.

```
read <process>              All tags for process
read <process> <tag>        Single tag value
read all                    All 4 processes compact
```

```
morbion › read boiler
morbion › read boiler drum_pressure_bar
morbion › read all
```

---

#### `write`

Write an engineering-unit value to a process register. The engine converts to raw uint16 using the correct scale factor. After 300 ms, the value is read back and compared.

```
write <process> <tag> <value>
```

```
morbion › write pumping_station pump_running 1
morbion › write pumping_station pump_running 0
morbion › write pumping_station pump_speed_rpm 1200
morbion › write boiler burner_state 2
morbion › write boiler burner_state 0
morbion › write pipeline duty_pump_running 1
morbion › write heat_exchanger hot_pump_speed_rpm 800
morbion › write heat_exchanger hot_valve_pos_pct 80
```

After every write:
- `✓ CONFIRMED` (green) — PLC accepted, value matches
- `⚠ OVERRIDDEN` (amber) — PLC changed the value (interlock active — not an error)
- `WRITE FAILED` (red) — server did not respond

---

#### `inject`

Force a sensor value for fault scenario training. Semantically identical to `write`. Use `inject` to signal that you are overriding a sensor, not commanding equipment.

```
inject <process> <tag> <value>
```

```
morbion › inject boiler drum_pressure_bar 11.0
morbion › inject boiler drum_level_pct 15.0
morbion › inject pumping_station tank_level_pct 3.0
morbion › inject pipeline outlet_pressure_bar 58.0
morbion › inject heat_exchanger T_cold_out_C 96.0
morbion › inject pipeline leak_flag 1
```

---

#### `fault`

Fault management.

```
fault clear <process>           Write 0 to register 14 (operator reset)
fault clear all                 Clear all 4 processes
fault status <process>          Read fault_code + description
fault inject <process> <code>   Force fault code directly (advanced)
```

```
morbion › fault clear boiler
morbion › fault clear all
morbion › fault status pipeline
morbion › fault inject boiler 2
```

**Important:** Latched faults (boiler 1/2/4, all pipeline faults, PS fault 2) only clear when BOTH conditions are met:
1. `fault clear` received (operator_reset pulse)
2. Physical condition has recovered (e.g. pressure < 9.5 bar)

Writing fault clear when the condition is still active does nothing.

---

#### `watch`

Live tag monitoring. Prints a new line every interval. `Ctrl+C` to stop.

```
watch <process> <tag>
watch <process> <tag> --interval <seconds>
watch <process>
watch all
```

```
morbion › watch boiler drum_pressure_bar
morbion › watch boiler drum_pressure_bar --interval 0.5
morbion › watch pumping_station tank_level_pct
morbion › watch pipeline
morbion › watch all
```

Output format:
```
14:07:29  boiler                    drum_pressure_bar          7.82 bar
14:07:30  boiler                    drum_pressure_bar          7.84 bar
```

---

#### `alarms`

Alarm management.

```
alarms                              Active alarms
alarms history                      Last 20 alarm events
alarms acknowledge <alarm_id>       Acknowledge one alarm
alarms acknowledge all              Acknowledge all active
alarms filter <CRIT|HIGH|MED|LOW>   Filter by severity
alarms filter <process>             Filter by process name
```

```
morbion › alarms
morbion › alarms history
morbion › alarms acknowledge BL-002
morbion › alarms acknowledge all
morbion › alarms filter CRIT
morbion › alarms filter boiler
```

Alarm IDs: `PS-001`–`PS-006` · `HX-001`–`HX-004` · `BL-001`–`BL-005` · `PL-001`–`PL-006`

---

#### `plc`

PLC program management.

```
plc <process> status                Runtime status, scan count, last error
plc <process> source                Print full ST source to terminal
plc <process> reload                Hot reload from file on disk
plc <process> upload <filepath>     Upload .st file — validates then applies
plc <process> validate <filepath>   Validate .st file (applies if valid)
plc <process> download <filepath>   Save current running source to file
plc <process> diff <filepath>       Line-level diff: running vs local file
plc <process> variables             Show input/output/parameter variable map
```

```
morbion › plc boiler status
morbion › plc boiler source
morbion › plc boiler reload
morbion › plc boiler upload /home/user/boiler_v2.st
morbion › plc boiler validate /home/user/test.st
morbion › plc boiler download /tmp/boiler_backup.st
morbion › plc boiler diff /home/user/boiler_local.st
morbion › plc pipeline variables
```

---

#### `modbus`

Raw Modbus register access. Uses server `/data` endpoint — not direct TCP.
For raw Modbus TCP, use a dedicated tool connected to the PLC ports directly.

```
modbus read <process> <start_reg> <count>    Show registers start to start+count-1
modbus write <process> <register> <raw>      Write raw uint16 value
modbus dump <process>                        All registers — raw + decoded side by side
```

```
morbion › modbus dump boiler
morbion › modbus read pipeline 0 5
morbion › modbus write boiler 6 2
```

Dump output format:
```
REG  RAW      ENG VALUE            UNIT        TAG
  0   782      7.82                 bar         drum_pressure_bar
  1  1743    174.3                 °C           drum_temp_C
  ...
```

---

#### `snapshot`

Save or print the full plant state.

```
snapshot                        Print full plant JSON to terminal
snapshot --file <filepath>      Save full plant JSON to file
```

```
morbion › snapshot
morbion › snapshot --file /tmp/plant_20250423_1407.json
```

---

#### `diff`

Shortcut for `plc <process> diff`. Compares running ST source against a local file.

```
diff <process> <filepath>
```

```
morbion › diff boiler /home/user/boiler_local.st
```

---

#### `batch`

Run a `.morbion` batch script. Commands execute sequentially. `#` for comments. Continues on error — does not abort batch.

```
batch <filepath>
```

Script format:
```
# boiler overpressure fault scenario
inject boiler drum_pressure_bar 11.0
watch boiler fault_code --interval 0.5
fault clear boiler
read boiler fault_code
```

```
morbion › batch /home/user/scenarios/boiler_overpressure.morbion
```

---

#### `status`

Server health and process online count.

```
status                   Server health + all 4 processes
status <process>         One process — all tags compact
```

---

#### `connect`

Reconnect to a different server. Saves to `config.json`. Restart CLI to apply.

```
connect <ip>:<port>
```

```
morbion › connect 192.168.100.30:5000
```

---

#### `history`

Command history.

```
history                  Last 50 commands
history <n>              Last N commands
history search <term>    Search history for term
```

Up/Down arrow keys navigate history in the input line.
History persists to `~/.morbion_history` between sessions (500 entries max).

---

#### `help`

```
help                        Full command list
help <verb>                 Detailed help for one verb
help register <process>     Full register map for process
help faults <process>       Fault code table for process
```

---

#### `cls` / `exit`

```
cls     Clear terminal output
exit    Return to main menu
```

---

## Register Maps

### Pumping Station — Port 502

| Reg | Tag | Scale | Unit | Writable |
|---|---|---|---|---|
| 0 | tank_level_pct | ×10 | % | inject |
| 1 | tank_volume_m3 | ×10 | m³ | no |
| 2 | pump_speed_rpm | ×1 | RPM | set speed |
| 3 | pump_flow_m3hr | ×10 | m³/hr | inject |
| 4 | discharge_pressure_bar | ×100 | bar | inject |
| 5 | pump_current_A | ×10 | A | no |
| 6 | pump_power_kW | ×10 | kW | no |
| 7 | pump_running | raw | 0/1 | 1=start 0=stop |
| 8 | inlet_valve_pos_pct | ×10 | % | >500=open ≤500=close |
| 9 | outlet_valve_pos_pct | ×10 | % | set position |
| 10 | demand_flow_m3hr | ×10 | m³/hr | no |
| 11 | net_flow_m3hr | ×10 | m³/hr | no |
| 12 | pump_starts_today | raw | count | no |
| 13 | level_sensor_mm | ×1 | mm | no |
| 14 | fault_code | raw | 0–4 | write 0 to clear |

Fault codes: `0=OK` `1=HIGH_LEVEL` `2=LOW_LEVEL` `3=PUMP_FAULT` `4=DRY_RUN`

**Special — inlet_valve_pos_pct:** raw value > 500 opens the valve, ≤ 500 closes it.
`write pumping_station inlet_valve_pos_pct 100` → opens (raw 1000 > 500)
`write pumping_station inlet_valve_pos_pct 0` → closes (raw 0 ≤ 500)

### Heat Exchanger — Port 506

| Reg | Tag | Scale | Unit | Writable |
|---|---|---|---|---|
| 0 | T_hot_in_C | ×10 | °C | inject |
| 1 | T_hot_out_C | ×10 | °C | inject |
| 2 | T_cold_in_C | ×10 | °C | inject |
| 3 | T_cold_out_C | ×10 | °C | inject (>95 = overtemp) |
| 4 | flow_hot_lpm | ×10 | L/min | no |
| 5 | flow_cold_lpm | ×10 | L/min | no |
| 6 | pressure_hot_in_bar | ×100 | bar | no |
| 7 | pressure_hot_out_bar | ×100 | bar | no |
| 8 | pressure_cold_in_bar | ×100 | bar | no |
| 9 | pressure_cold_out_bar | ×100 | bar | no |
| 10 | Q_duty_kW | ×1 | kW | no |
| 11 | efficiency_pct | ×10 | % | no |
| 12 | hot_pump_speed_rpm | ×1 | RPM | set speed |
| 13 | cold_pump_speed_rpm | ×1 | RPM | set speed |
| 14 | hot_valve_pos_pct | ×10 | % | set position |
| 15 | cold_valve_pos_pct | ×10 | % | set position |
| 16 | fault_code | raw | 0–3 | write 0 to clear |

Fault codes: `0=OK` `1=PUMP_FAULT` `2=SENSOR_FAULT` `3=OVERTEMP`
Fault 3 auto-clears when temperatures recover for 10 s — no operator reset needed.

### Boiler — Port 507

| Reg | Tag | Scale | Unit | Writable |
|---|---|---|---|---|
| 0 | drum_pressure_bar | ×100 | bar | inject (>10 = overpressure) |
| 1 | drum_temp_C | ×10 | °C | inject |
| 2 | drum_level_pct | ×10 | % | inject (<20 = low water) |
| 3 | steam_flow_kghr | ×10 | kg/hr | inject |
| 4 | feedwater_flow_kghr | ×10 | kg/hr | no |
| 5 | fuel_flow_kghr | ×10 | kg/hr | no |
| 6 | burner_state | raw | 0/1/2 | 0=OFF 1=LOW 2=HIGH |
| 7 | fw_pump_speed_rpm | ×1 | RPM | set speed |
| 8 | steam_valve_pos_pct | ×10 | % | set position |
| 9 | fw_valve_pos_pct | ×10 | % | set position |
| 10 | blowdown_valve_pos_pct | ×10 | % | set position |
| 11 | flue_gas_temp_C | ×10 | °C | no |
| 12 | combustion_eff_pct | ×10 | % | no |
| 13 | Q_burner_kW | ×1 | kW | no |
| 14 | fault_code | raw | 0–4 | write 0 to clear |

Fault codes: `0=OK` `1=LOW_WATER` `2=OVERPRESSURE` `3=FLAME_FAILURE` `4=PUMP_FAULT`
Faults 1, 2, 4 are SR-latched. Require operator reset AND physical condition recovery.

### Pipeline — Port 508

| Reg | Tag | Scale | Unit | Writable |
|---|---|---|---|---|
| 0 | inlet_pressure_bar | ×100 | bar | inject |
| 1 | outlet_pressure_bar | ×100 | bar | inject (>55 = overpressure) |
| 2 | flow_rate_m3hr | ×10 | m³/hr | inject |
| 3 | duty_pump_speed_rpm | ×1 | RPM | set speed |
| 4 | duty_pump_current_A | ×10 | A | no |
| 5 | duty_pump_running | raw | 0/1 | 1=start 0=stop |
| 6 | standby_pump_speed_rpm | ×1 | RPM | set speed |
| 7 | standby_pump_running | raw | 0/1 | 1=start 0=stop |
| 8 | inlet_valve_pos_pct | ×10 | % | set position |
| 9 | outlet_valve_pos_pct | ×10 | % | set position |
| 10 | pump_differential_bar | ×100 | bar | no |
| 11 | flow_velocity_ms | ×100 | m/s | no |
| 12 | duty_pump_power_kW | ×1 | kW | no |
| 13 | leak_flag | raw | 0/1 | write 1 to inject |
| 14 | fault_code | raw | 0–3 | write 0 to clear |

Fault codes: `0=OK` `1=DUTY_FAULT` `2=BOTH_FAULT` `3=OVERPRESSURE`
All pipeline faults SR-latched. Require operator reset AND condition recovery.

---

## Fault Clearing Procedure

All latched faults follow this procedure:

1. Identify the fault: `fault status <process>`
2. Resolve the physical condition (e.g. reduce boiler pressure below 9.5 bar)
3. Clear the fault: `fault clear <process>`
4. Wait one scan cycle (100 ms)
5. Verify: `read <process> fault_code`

If the condition is still active at step 3, the SR latch SET input dominates RESET and the fault remains. Fix the process first.

---

## Verify-After-Write

Every `write` and `inject` command follows this pattern:

1. Send `POST /control` to server
2. Server confirms FC06 echo from process
3. Wait 300 ms (one full PLC scan + physics update)
4. Read tag value from live plant snapshot (WebSocket)
5. Compare actual vs expected (2% tolerance + 0.1 absolute)
6. Report CONFIRMED or OVERRIDDEN

OVERRIDDEN is not a failure. It means the PLC correctly enforced a safety interlock or control loop. The process rejected the command for a legitimate reason. Check the fault code and process conditions.

---

## Batch Scripting

Create `.morbion` script files for repeatable fault scenarios and test procedures.

```
# fault_scenario_boiler_overpressure.morbion
# Step 1 — inject overpressure
inject boiler drum_pressure_bar 11.0
# Step 2 — verify interlock trips
read boiler fault_code
read boiler burner_state
# Step 3 — reduce pressure (let physics recover)
inject boiler drum_pressure_bar 7.5
# Step 4 — clear fault
fault clear boiler
# Step 5 — verify cleared
read boiler fault_code
```

Run it:
```
morbion › batch /home/user/scenarios/boiler_overpressure.morbion
```

---

## SSH Usage

The TUI and CLI both run over SSH with no changes needed.

```bash
ssh user@192.168.100.10
cd /opt/morbion-scada-v02/tui-client
python main.py
```

TUI requires the SSH terminal to support 256 colours and Unicode box-drawing characters. Most modern terminals do. If the TUI layout breaks, use CLI mode instead — it works in any terminal.

---

## Troubleshooting

**Menu shows `○OFFLINE` but server is running**
- Check `config.json` — `server_host` must be the server's IP, not the PLC IP
- Test connectivity: `curl http://<server_host>:5000/health`
- Press `i` to reconfigure the server address

**CLI shows `●ONLINE 0/4`**
- Server is reachable but processes are offline
- On the PLC machine: `cd processes && python manager.py status`
- Start processes: `python manager.py start`

**Tab completion not working in CLI**
- `readline` is required on Unix. Install: `pip install readline` (usually built-in)
- On Windows: `pip install pyreadline3`

**TUI layout broken in terminal**
- Ensure terminal supports Unicode and 256 colours
- Try: `export TERM=xterm-256color` before launching
- If still broken, use CLI mode — it works in any terminal

**`write` always returns OVERRIDDEN**
- A safety interlock is active: `fault status <process>`
- Resolve the fault condition first, then retry the command
- Some tags are read-only — check `help register <process>`

**PLC source shows empty / `plc status` returns error**
- The process HTTP API (ports 5020/5060/5070/5080) is hosted by the processes
- Processes must be running for PLC API to work
- Verify: `python manager.py status` on the PLC machine

**Batch script stops at first error**
- The batch runner logs errors and continues — it does not abort
- Check the output for `ERROR:` lines to identify which commands failed

---

## Colour Reference

| Colour | Hex | Meaning |
|---|---|---|
| Cyan | `#00d4ff` | Active, selected, command echo, titles |
| Green | `#00ff88` | Online, running, confirmed, OK |
| Red | `#ff3333` | Fault, offline, CRIT alarm, error |
| Amber | `#ffaa00` | Warning, HIGH alarm, overridden |
| White | `#ffffff` | Data values |
| Dim | `#4a7a8c` | Labels, metadata, timestamps |

---

*MORBION SCADA v02 — Intelligence. Precision. Vigilance.*
*Jeremiah Praise — BSc Mechanical Engineering*
