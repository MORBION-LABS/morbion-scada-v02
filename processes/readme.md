# MORBION SCADA v02 — Processes

**Four Modbus TCP process simulations with embedded PLC virtual machines.**

Each process is a self-contained Python application running physics, PLC logic, and a Modbus TCP server. They are the plant floor — the processes are real in the sense that thermodynamics and fluid mechanics govern their behaviour. Operator commands arrive as Modbus register writes, are evaluated by the PLC interpreter, and are accepted or rejected based on physics and interlock state.

---

## Directory Structure

```
processes/
├── config.yaml                 Global config — PLC host, server host, ports
├── installer.py                Interactive installer — sets host IPs
├── manager.py                  Lifecycle manager — start/stop/status/logs
├── requirements.txt
├── test_communication.py       Live Modbus register monitor (Rich/Textual TUI)
├── uninstaller.py
│
├── pumping_station/            Nairobi Water — Municipal pumping station
│   ├── main.py                 Entry point — scan loop, operator write queue
│   ├── config.json             Equipment parameters
│   ├── process_state.py        Thread-safe shared state
│   ├── modbus_server.py        Modbus TCP server (FC03/FC06, pure socket)
│   ├── plc_runtime.py          ST interpreter wrapper
│   ├── plc_program.st          IEC 61131-3 Structured Text PLC program
│   ├── plc_variables.yaml      Input/output/parameter map for ST→Python
│   ├── pump.py                 Centrifugal pump with operating point solver
│   ├── tank.py                 Storage tank — mass balance + conservation law
│   ├── inlet_valve.py          On/off motorised inlet valve
│   ├── outlet_valve.py         Modulating outlet valve
│   ├── flow_meter.py           Electromagnetic flow meter
│   ├── level_sensor.py         Ultrasonic level sensor
│   └── pressure_sensor.py      Discharge pressure transmitter
│
├── heat_exchanger/             KenGen Olkaria — Geothermal heat recovery
│   ├── main.py
│   ├── config.json
│   ├── process_state.py
│   ├── modbus_server.py
│   ├── plc_runtime.py
│   ├── plc_program.st
│   ├── plc_variables.yaml
│   ├── shell_and_tube.py       NTU-effectiveness heat transfer model
│   ├── hot_pump.py             Hot side pump — affinity laws
│   ├── cold_pump.py            Cold side pump — affinity laws
│   └── control_valve.py        Hot and cold side control valves
│
├── boiler/                     EABL/Bidco — Industrial steam generation
│   ├── main.py
│   ├── config.json
│   ├── process_state.py
│   ├── modbus_server.py
│   ├── plc_runtime.py
│   ├── plc_program.st
│   ├── plc_variables.yaml
│   ├── drum.py                 Steam drum — Antoine equation, energy/mass balance
│   ├── burner.py               Natural gas burner — combustion physics
│   ├── feedwater_pump.py       Feedwater pump — affinity laws
│   ├── steam_valve.py          Steam outlet control valve
│   ├── feedwater_valve.py      Three-element feedwater control valve
│   └── blowdown_valve.py       Bottom blowdown valve
│
├── pipeline/                   Kenya Pipeline Co. — Petroleum transfer
│   ├── main.py
│   ├── config.json
│   ├── process_state.py
│   ├── modbus_server.py
│   ├── plc_runtime.py
│   ├── plc_program.st
│   ├── plc_variables.yaml
│   ├── duty_pump.py            Duty pump — centrifugal, petroleum duty
│   ├── standby_pump.py         Standby pump — automatic failover
│   ├── inlet_valve.py          On/off inlet isolation valve
│   ├── outlet_valve.py         Modulating pressure control valve
│   ├── flow_meter.py           Turbine flow meter
│   └── pressure_sensors.py     Inlet and outlet pressure transmitters
│
└── shared/
    ├── plc_http.py             Per-process HTTP API — PLC program management
    └── st_runtime/
        ├── __init__.py
        ├── lexer.py            IEC 61131-3 ST tokenizer
        ├── parser.py           Recursive descent parser → AST
        ├── interpreter.py      AST interpreter with stateful FB instances
        └── stdlib.py           TON, TOF, CTU, SR, RS + LIMIT, ABS, MAX, MIN
```

---

## Installation

```bash
cd processes
pip install -r requirements.txt
python installer.py
```

The installer prompts for:
- **PLC Host IP** — the IP address of this machine (where the processes run). Use `127.0.0.1` for local development.
- **SCADA Server Host IP** — the IP of the machine running `server/main.py`. Used in `config.yaml` for reference; the processes do not connect to the server — the server connects to them.

This writes `config.yaml`:

```yaml
settings:
  plc_host: <PLC machine IP>
  server_host: <server machine IP>
  scan_interval_ms: 100
  log_dir: logs
```

---

## Starting and Stopping

```bash
# Start all four processes
python manager.py start

# Check which are running
python manager.py status

# Tail all logs live
python manager.py logs -f

# Show last 50 lines of each log
python manager.py logs

# Stop all
python manager.py stop

# Restart all
python manager.py restart
```

The manager uses `psutil` to track processes by their listening port rather than PID files. A process is considered running if its Modbus TCP port is listening.

To start a single process manually (for debugging):

```bash
cd pumping_station
python main.py
```

---

## Live Monitor

`test_communication.py` reads live Modbus registers from all four processes and displays them in a terminal dashboard.

```bash
# Live monitor — updates every 2 seconds
python test_communication.py monitor

# Single snapshot
python test_communication.py monitor --once

# Quick status (port reachability only)
python test_communication.py status

# Full register read test
python test_communication.py test
```

---

## Process Architecture — Scan Loop

Every process follows the same deterministic scan loop at 100 ms intervals:

```
1. Apply operator writes   — dequeue FC06 writes, apply to state/equipment
2. Physics update          — each equipment object advances by dt seconds
3. PLC scan                — ST interpreter runs plc_program.st
4. Apply PLC commands      — read PLC output image, drive equipment
5. Update Modbus registers — write current state to register bank
6. Sleep                   — remainder of 100 ms interval
```

The operator write queue (`collections.deque`) is the thread-safe bridge between the Modbus server thread (which receives FC06 writes) and the main scan loop. Writes are never applied mid-scan.

---

## PLC Virtual Machine

Each process hosts an IEC 61131-3 Structured Text interpreter. The ST program (`plc_program.st`) is loaded at startup and executed every scan cycle.

The ST runtime supports:
- Data types: BOOL, INT, REAL
- Operators: arithmetic, comparison, logical (AND OR NOT XOR)
- Control flow: IF/THEN/ELSIF/ELSE/END_IF, WHILE/DO/END_WHILE, FOR/TO/BY/END_FOR, RETURN
- Function blocks (stateful, instance-based): TON, TOF, CTU, SR, RS
- Standard functions (stateless): LIMIT, ABS, MAX, MIN, SQRT, INT, REAL, BOOL
- Named and positional function block calls
- Dot notation for FB output access (e.g. `dry_run_timer.Q`)
- VAR...END_VAR blocks for FB instance declarations

### Input/Output Image Separation

The PLC never accesses `ProcessState` directly. `plc_runtime.py` builds an input image from `ProcessState` fields (per `plc_variables.yaml`), passes it to the interpreter, then writes the output image back to `ProcessState`. `main.py` then reads `ProcessState` and drives equipment objects.

This mirrors real PLC architecture: scan reads inputs → executes program → writes outputs.

### Hot Reload

The PLC program can be replaced at runtime without stopping the process:

```
POST /plc/program          — upload new ST source (validates first, rejects on parse error)
POST /plc/program/reload   — reload from file on disk
```

The scan loop continues uninterrupted during reload. The new interpreter replaces the old atomically under a threading lock.

---

## PLC HTTP API

Each process hosts a secondary HTTP server for PLC program management:

| Process | HTTP Port |
|---|---|
| pumping_station | 5020 |
| heat_exchanger | 5060 |
| boiler | 5070 |
| pipeline | 5080 |

| Method | Endpoint | Description |
|---|---|---|
| GET | `/plc/program` | ST source as plain text |
| POST | `/plc/program` | Upload new source `{"source": "..."}` |
| POST | `/plc/program/reload` | Hot reload from file |
| GET | `/plc/status` | `{loaded, scan_count, last_error, program_file}` |
| GET | `/plc/variables` | `{inputs, outputs, parameters}` |
| GET | `/health` | `{"ok": true}` |

The SCADA server proxies all `/plc/<process>/...` requests to these endpoints. Clients do not call them directly.

---

## Modbus Register Maps

### Pumping Station — Port 502 — 15 registers

| Index | Tag | Scale | Unit | Write? |
|---|---|---|---|---|
| 0 | tank_level_pct | ×10 | % | Inject |
| 1 | tank_volume_m3 | ×10 | m³ | No |
| 2 | pump_speed_rpm | ×1 | RPM | Set speed |
| 3 | pump_flow_m3hr | ×10 | m³/hr | Inject |
| 4 | discharge_pressure_bar | ×100 | bar | Inject |
| 5 | pump_current_A | ×10 | A | No |
| 6 | pump_power_kW | ×10 | kW | No |
| 7 | pump_running | raw | 0/1 | 1=start, 0=stop |
| 8 | inlet_valve_pos_pct | ×10 | % | >500=open, ≤500=close |
| 9 | outlet_valve_pos_pct | ×10 | % | Set position |
| 10 | demand_flow_m3hr | ×10 | m³/hr | No |
| 11 | net_flow_m3hr | ×10 | m³/hr | No |
| 12 | pump_starts_today | raw | count | No |
| 13 | level_sensor_mm | ×1 | mm | No |
| 14 | fault_code | raw | 0–4 | Write 0 to clear |

Fault codes: `0=OK` `1=HIGH_LEVEL` `2=LOW_LEVEL` `3=PUMP_FAULT` `4=DRY_RUN`

### Heat Exchanger — Port 506 — 17 registers

| Index | Tag | Scale | Unit | Write? |
|---|---|---|---|---|
| 0 | T_hot_in_C | ×10 | °C | Inject |
| 1 | T_hot_out_C | ×10 | °C | Inject |
| 2 | T_cold_in_C | ×10 | °C | Inject |
| 3 | T_cold_out_C | ×10 | °C | Inject (>950 = overtemp) |
| 4 | flow_hot_lpm | ×10 | L/min | No |
| 5 | flow_cold_lpm | ×10 | L/min | No |
| 6 | pressure_hot_in_bar | ×100 | bar | No |
| 7 | pressure_hot_out_bar | ×100 | bar | No |
| 8 | pressure_cold_in_bar | ×100 | bar | No |
| 9 | pressure_cold_out_bar | ×100 | bar | No |
| 10 | Q_duty_kW | ×1 | kW | No |
| 11 | efficiency_pct | ×10 | % | No |
| 12 | hot_pump_speed_rpm | ×1 | RPM | Set speed |
| 13 | cold_pump_speed_rpm | ×1 | RPM | Set speed |
| 14 | hot_valve_pos_pct | ×10 | % | Set position |
| 15 | cold_valve_pos_pct | ×10 | % | Set position |
| 16 | fault_code | raw | 0–3 | Write 0 to clear |

Fault codes: `0=OK` `1=PUMP_FAULT` `2=SENSOR_FAULT` `3=OVERTEMP`

### Boiler — Port 507 — 15 registers

| Index | Tag | Scale | Unit | Write? |
|---|---|---|---|---|
| 0 | drum_pressure_bar | ×100 | bar | Inject (>1000 = overpressure) |
| 1 | drum_temp_C | ×10 | °C | Inject |
| 2 | drum_level_pct | ×10 | % | Inject (<200 = low water) |
| 3 | steam_flow_kghr | ×10 | kg/hr | Inject |
| 4 | feedwater_flow_kghr | ×10 | kg/hr | No |
| 5 | fuel_flow_kghr | ×10 | kg/hr | No |
| 6 | burner_state | raw | 0/1/2 | 0=OFF 1=LOW 2=HIGH |
| 7 | fw_pump_speed_rpm | ×1 | RPM | Set speed |
| 8 | steam_valve_pos_pct | ×10 | % | Set position |
| 9 | fw_valve_pos_pct | ×10 | % | Set position |
| 10 | blowdown_valve_pos_pct | ×10 | % | Set position |
| 11 | flue_gas_temp_C | ×10 | °C | No |
| 12 | combustion_eff_pct | ×10 | % | No |
| 13 | Q_burner_kW | ×1 | kW | No |
| 14 | fault_code | raw | 0–4 | Write 0 to clear |

Fault codes: `0=OK` `1=LOW_WATER` `2=OVERPRESSURE` `3=FLAME_FAILURE` `4=PUMP_FAULT`

### Pipeline — Port 508 — 15 registers

| Index | Tag | Scale | Unit | Write? |
|---|---|---|---|---|
| 0 | inlet_pressure_bar | ×100 | bar | Inject |
| 1 | outlet_pressure_bar | ×100 | bar | Inject (>5500 = overpressure) |
| 2 | flow_rate_m3hr | ×10 | m³/hr | Inject |
| 3 | duty_pump_speed_rpm | ×1 | RPM | Set speed |
| 4 | duty_pump_current_A | ×10 | A | No |
| 5 | duty_pump_running | raw | 0/1 | 1=start, 0=stop |
| 6 | standby_pump_speed_rpm | ×1 | RPM | Set speed |
| 7 | standby_pump_running | raw | 0/1 | 1=start, 0=stop |
| 8 | inlet_valve_pos_pct | ×10 | % | Set position |
| 9 | outlet_valve_pos_pct | ×10 | % | Set position |
| 10 | pump_differential_bar | ×100 | bar | No |
| 11 | flow_velocity_ms | ×100 | m/s | No |
| 12 | duty_pump_power_kW | ×1 | kW | No |
| 13 | leak_flag | raw | 0/1 | Write 1 to inject leak |
| 14 | fault_code | raw | 0–3 | Write 0 to clear |

Fault codes: `0=OK` `1=DUTY_FAULT` `2=BOTH_FAULT` `3=OVERPRESSURE`

---

## Process Physics Summary

### Pumping Station

Physics model: centrifugal pump with operating point solver. The pump curve (`H_pump = H_shutoff × (1 - Q²/Q_max²)`) intersects the system curve (`H_sys = H_static + k × Q²`) analytically every scan. Flow and head are derived from the intersection — not from rated values. Closing the outlet valve increases system resistance and reduces flow. The tank mass balance runs after all valve positions are updated.

Key interlocks:
- Level < 5%: dry run protection (30 s no-flow delay, then latched fault)
- Level < 20%: low level alarm (CRIT)
- Discharge pressure > 8 bar: high pressure (HIGH alarm)
- Pump fault: latched until operator reset + fault recovery

### Heat Exchanger

Physics model: NTU-effectiveness method for counter-flow shell-and-tube heat exchanger. `NTU = U_eff × A / C_min`. Effectiveness `ε` computed analytically. Fouling factor reduces effective U by approximately 8%. Hot fluid is geothermal brine (ρ = 1050 kg/m³, Cp = 3800 J/kg·K). Cold fluid is water (ρ = 1000 kg/m³, Cp = 4186 J/kg·K). Outlet temperatures lag via first-order thermal lag (τ = 45 s).

Key interlocks:
- T_cold_out > 95°C: immediate hot valve closure (CRIT)
- T_hot_out > 165°C: hot valve modulation (HIGH)
- Efficiency < 45%: tube fouling alarm (MED) — auto-clears on recovery

### Boiler

Physics model: Antoine equation for saturation temperature/pressure (±0.5°C accuracy 1–15 bar). Full energy balance: `dU/dt = Q_burner + Q_feedwater - Q_steam - Q_losses`. Steam flow from Cv equation against drum pressure. Feedwater control: three-element (level error + steam feedforward → feedwater valve). Periodic blowdown every 2 hours (30 s pulse) via TON/TOF timer chain.

Key interlocks (all SR-latched):
- Drum level < 20%: LOW_WATER — burner trip, fault code 1
- Drum pressure > 10 bar: OVERPRESSURE — burner trip, fault code 2
- FW pump fault: PUMP_FAULT — burner trip, fault code 4
- Cold start auto-clear: overpressure latch clears if pressure < 1.0 bar at startup

### Pipeline

Physics model: centrifugal pump affinity laws + Darcy-Weisbach friction loss. Outlet pressure derived from inlet pressure + pump head − friction losses − elevation head. Leak detection: compares expected flow (from pump speed/curve) against measured turbine meter flow. Discrepancy > 50 m³/hr sustained for 10 s → leak flag.

Key interlocks (all SR-latched):
- Outlet pressure > 55 bar: OVERPRESSURE — full shutdown, fault code 3
- Both pumps faulted: emergency shutdown, fault code 2
- Duty pump fault: standby starts after 2 s delay, fault code 1

---

## Fault Clearing Procedure

**Important:** The PLC enforces two conditions simultaneously for latch reset:
1. `operator_reset = True` (write 0 to register 14)
2. Physical condition has recovered

If the physical condition is still active, writing 0 to register 14 has no effect. The SR latch SET input is still asserted, which dominates the RESET input.

Correct procedure:
1. Identify the fault condition (read register 14, read process tags)
2. Resolve the physical condition (e.g. reduce boiler pressure below 9.5 bar)
3. Write 0 to register 14
4. Wait one scan cycle (100 ms)
5. Verify fault_code is now 0

---

## Requirements

```
pyyaml>=6.0
psutil>=5.9.0
typer>=0.9.0
rich>=13.0.0
```

The ST runtime and Modbus server have no external dependencies — pure Python standard library only.

---

## Troubleshooting

**Process starts but Modbus port not listening**
- Check `config.json` in the process directory — verify `port` value
- Another application may be using that port: `ss -tlnp | grep 502`
- Run as a user with permission to bind to port 502 (privileged ports on Linux)

**PLC program not loading**
- Check the process log: `python manager.py logs`
- Parse errors in `plc_program.st` prevent the interpreter from loading
- The Python fallback (`plc_logic.py`) activates if ST load fails — check `[WARN]` messages

**Process exits immediately after start**
- Missing `process_state.json` is not an error — it is created on first run
- Check log file in `logs/<process_name>.log`
- Verify `config.json` exists in the process directory

**manager.py requires sudo on Linux for port binding**
- Ports below 1024 (including 502) require root on most Linux systems
- Either run with `sudo` or use `setcap cap_net_bind_service+ep /usr/bin/python3`
- In development, change process ports to 5020+ in `config.yaml` and `config.json`

---

*MORBION SCADA v02 — Intelligence. Precision. Vigilance.*
