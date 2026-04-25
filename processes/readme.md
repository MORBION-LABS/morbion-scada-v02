# MORBION SCADA v02 — Processes

**Industrial Control System Simulation**  
Kenya Pipeline Co. · KenGen Olkaria · Nairobi Water · EABL/Bidco

---

## Overview

The `processes/` directory contains four independent industrial process simulations. Each process runs as a standalone Python application on the PLC virtual machine. Each exposes a Modbus TCP server on its assigned port. The SCADA server polls all four continuously.

```
morbion-scada-v02/
├── processes/          ← You are here
│   ├── manager.py      ← Start, stop, restart, status, logs
│   ├── config.yaml     ← PLC host, server host, scan intervals
│   ├── installer.py    ← First-time setup
│   ├── boiler/         ← EABL/Bidco Steam Generation (port 507)
│   ├── heat_exchanger/ ← KenGen Olkaria Geothermal (port 506)
│   ├── pipeline/       ← Kenya Pipeline Co. Petroleum (port 508)
│   ├── pumping_station/← Nairobi Water Municipal (port 502)
│   └── shared/         ← ST runtime (lexer, parser, interpreter)
├── server/             ← SCADA server (REST + WebSocket)
└── clients/            ← Desktop and web SCADA clients
```

Each part — processes, server, clients — is independent. The processes run on a dedicated PLC VM. The server runs on a separate server VM. Clients run anywhere on the network.

---

## Architecture

```
┌─────────────────────────────────────┐
│         PLC MACHINE                 │
│         <plc ip>                    │
│                                     │
│  ┌────────┐  ┌────────┐             │
│  │Pumping │  │  Heat  │             │
│  │Station │  │ Exch.  │             │
│  │ :502   │  │  :506  │             │
│  └────────┘  └────────┘             │
│  ┌────────┐  ┌────────┐             │
│  │Boiler  │  │Pipeline│             │
│  │  :507  │  │  :508  │             │
│  └────────┘  └────────┘             │
│                                     │
│  manager.py ← controls all four     │
└─────────────────────────────────────┘
         │ Modbus TCP
         ▼
┌─────────────────────────────────────┐
│       Server MACHINE                │
│         <server ip>                 │
│                                     │
│  SCADA Server :5000                 │
│  REST + WebSocket + Alarm Engine    │
└─────────────────────────────────────┘
         │ HTTP / WebSocket
         ▼
┌─────────────────────────────────────┐
│         Client                      │
│         <client ip>                 │
│                                     │
│  Desktop SCADA Client               │
│  Web Browser Client                 │
│  Lab Connectors (Python/C/C++/C#)  │
└─────────────────────────────────────┘
```

---

## The Four Processes

### Pumping Station — Port 502
**Nairobi Water Municipal Pumping Station**

A centrifugal pump fills a storage tank against constant demand. Level-based PLC control starts the pump at 20% tank level and stops it at 80%. Dry run protection, conservation law monitoring, and latched fault codes.

```
Key variables:
  Tank Level        0-100 %
  Pump Flow         0-120 m³/hr
  Discharge P       0-8 bar
  Inlet Valve       on/off
  Outlet Valve      0-100 % (demand)

Normal cycle:
  50% → drains to 20% → pump starts → fills to 80% → pump stops → repeat
```

### Heat Exchanger — Port 506
**KenGen Olkaria Geothermal Heat Recovery**

Geothermal brine (180°C) transfers heat to process water (25°C) through a shell-and-tube exchanger. NTU-Effectiveness method governs heat transfer. Overtemp protection modulates hot valve. Efficiency monitoring detects fouling.

```
Key variables:
  T Hot In          ~180 °C (geothermal brine)
  T Cold Out        ~71-85 °C (heated process water)
  Efficiency        ~50-75 %
  Q Duty            ~2000-2500 kW
  Both pumps        running continuously

Normal operation:
  Both pumps start → valves open → heat transfers → temperatures stabilise
```

### Boiler — Port 507
**EABL/Bidco Industrial Steam Generation**

Natural gas burner heats a steam drum. Antoine equation governs pressure-temperature relationship. Three-element feedwater control maintains drum level. Safety interlocks (low water, overpressure, pump fault) are latched and require operator reset.

```
Key variables:
  Drum Pressure     0-10 bar (nominal 8 bar)
  Drum Temp         ~170 °C at 8 bar
  Drum Level        20-80 % (three-element control)
  Burner State      OFF / LOW / HIGH
  Steam Flow        ~3733 kg/hr nominal

Cold start sequence:
  0.5 bar → burner HIGH → pressure rises → 6 bar → steam valve opens
  → 8 bar → burner cycles LOW/OFF → steady state ~10 minutes
```

### Pipeline — Port 508
**Kenya Pipeline Company — Petroleum Transfer**

High-voltage (6600V) centrifugal pump transfers petroleum product (SG=0.85) through a 15km, 356mm pipeline with 50m elevation change. Duty-standby arrangement. Outlet valve modulates delivery pressure. Leak detection compares expected vs measured flow.

```
Key variables:
  Outlet Pressure   ~34-38 bar (nominal 40 bar)
  Flow Rate         ~400-600 m³/hr
  Duty Pump         1480 RPM (normal)
  Standby Pump      at rest (auto-starts on duty fault)
  Leak Flag         clear / suspected

Normal operation:
  Duty pump at rated speed → outlet ~38 bar → standby at rest
  On duty fault → 2s delay → standby starts automatically
```

---

## Prerequisites

**PLC VM (ubuntu-plc):**
- Ubuntu 22.04 LTS
- Python 3.10 or later
- pip packages: `pyyaml psutil`

**Network:**
- PLC VM: 192.168.100.20
- Server VM: 192.168.100.30
- Host: 192.168.100.10

---

## First-Time Setup

### 1. Clone the repository

```bash
git sparse https://github.com/MORBION-LABS/morbion-scada-v02.git
cd morbion-scada-v02/processes
```

### 2. Install Python dependencies

```bash
pip3 install -r requirements
```

### 3. Run the installer

```bash
python3 installer.py
```

The installer prompts for:
- **PLC Host IP** — IP of the machine running these processes (192.168.100.20)
- **SCADA Server Host IP** — IP of the server VM (192.168.100.30)

This writes `config.yaml` and creates the `logs/` directory.

### 4. Start all processes

```bash
sudo python3 manager.py start
```

---

## Manager — Process Lifecycle

All process management goes through `manager.py`. Do not start processes manually with `python3 boiler/main.py` — the manager handles PID tracking, logging, and port health checks.

```bash
# Start all enabled processes
sudo python3 manager.py start

# Stop all processes
sudo python3 manager.py stop

# Restart all processes
sudo python3 manager.py restart

# Check status of all processes
sudo python3 manager.py status

# View last 50 lines of all logs
sudo python3 manager.py logs

# Follow logs live (Ctrl+C to exit)
sudo python3 manager.py logs -f
```

**Status output example:**
```
═══════════════════════════════════════════════════════
  MORBION SCADA v02 — Process Status
═══════════════════════════════════════════════════════
  NAME                   STATUS       PORT     PID
  ─────────────────────────────────────────────────
  ● pumping_station      RUNNING      502      7504
  ● heat_exchanger       RUNNING      506      7498
  ● boiler               RUNNING      507      7501
  ● pipeline             RUNNING      508      7500
═══════════════════════════════════════════════════════
```

---

## Configuration

### `config.yaml`

```yaml
processes:
  boiler:
    description: EABL/Bidco Industrial Steam Generation
    enabled: true
    folder: boiler
    name: Boiler
    port: 507
  heat_exchanger:
    description: KenGen Olkaria Geothermal Heat Recovery
    enabled: true
    folder: heat_exchanger
    name: Heat Exchanger
    port: 506
  pipeline:
    description: Kenya Pipeline Co. Petroleum Transfer
    enabled: true
    folder: pipeline
    name: Pipeline
    port: 508
  pumping_station:
    description: Nairobi Water Municipal Pumping Station
    enabled: true
    folder: pumping_station
    name: Pumping Station
    port: 502
settings:
  auto_restart_on_failure: false
  log_dir: logs
  log_lines: 50
  plc_host: 192.168.100.20
  scan_interval_ms: 100
  server_host: 192.168.100.30
```

To disable a process, set `enabled: false`. The manager will skip it.

### Per-Process Config

Each process has its own `config.json` with physics parameters:

```
boiler/config.json          — burner ratings, drum geometry, valve Cv values
heat_exchanger/config.json  — U value, area, pump ratings, setpoints
pipeline/config.json        — pipe geometry, pump ratings, alarm limits
pumping_station/config.json — tank geometry, pump ratings, control setpoints
```

---

## PLC Programs — Structured Text

Each process runs an IEC 61131-3 Structured Text program that executes every scan cycle (100ms). Programs are in:

```
boiler/plc_program.st
heat_exchanger/plc_program.st
pipeline/plc_program.st
pumping_station/plc_program.st
```

The ST interpreter (in `shared/st_runtime/`) supports:
- IF / ELSIF / ELSE / END_IF
- WHILE / END_WHILE
- FOR / TO / BY / END_FOR
- VAR / END_VAR blocks
- Function blocks: TON, TOF, SR, RS, CTU
- Standard functions: LIMIT, ABS, MAX, MIN, SQRT
- Dot notation: `timer.Q`, `latch.Q1`

**To modify a PLC program:**
1. Edit the `.st` file
2. Restart the process — PLCRuntime loads fresh on startup
3. Or use the hot-reload endpoint if server is connected

**Critical:** VAR blocks must use only `(*` and `*)` for comments. The `#` character is not valid ST and will crash the loader silently.

---

## Variable Maps — `plc_variables.yaml`

Each process has a variable map that connects ST program variables to Python ProcessState fields:

```yaml
inputs:
  level_sensor_pct: level_sensor_pct   # ST variable ← ProcessState field
  fault_code:       fault_code

outputs:
  pump_run_cmd:     pump_running       # ST variable → ProcessState field
  outlet_valve_sp:  outlet_valve_pos_pct

parameters:
  level_start: 20.0                   # injected as ST constants
  level_stop:  80.0
```

Inputs are read from ProcessState at the start of each scan. Outputs are written back after the ST program executes. Parameters are constants injected into the ST environment.

---

## Modbus TCP — Register Maps

All registers are 0-based holding registers (FC03 read, FC06 write). Scale factors convert between raw uint16 and engineering units.

### Pumping Station — Port 502

| Index | Tag | Scale | Unit | R/W |
|-------|-----|-------|------|-----|
| 0 | tank_level_pct | ×10 | % | R/W |
| 1 | tank_volume_m3 | ×10 | m³ | R |
| 2 | pump_speed_rpm | ×1 | RPM | R/W |
| 3 | pump_flow_m3hr | ×10 | m³/hr | R/W |
| 4 | discharge_pressure_bar | ×100 | bar | R/W |
| 5 | pump_current_A | ×10 | A | R |
| 6 | pump_power_kW | ×10 | kW | R |
| 7 | pump_running | raw | 0/1 | R/W |
| 8 | inlet_valve_pos_pct | ×10 | % | R/W |
| 9 | outlet_valve_pos_pct | ×10 | % | R/W |
| 10 | demand_flow_m3hr | ×10 | m³/hr | R |
| 11 | net_flow_m3hr | ×10 | m³/hr | R |
| 12 | pump_starts_today | raw | count | R |
| 13 | level_sensor_mm | ×1 | mm | R |
| 14 | fault_code | raw | 0-4 | R/W |

**Fault codes:** 0=OK 1=HIGH_LEVEL 2=LOW_LEVEL 3=PUMP_FAULT 4=DRY_RUN  
**Write reg 14 = 0** to clear fault and pulse operator_reset  
**Write reg 8 > 500** to open inlet valve, ≤ 500 to close

### Heat Exchanger — Port 506

| Index | Tag | Scale | Unit | R/W |
|-------|-----|-------|------|-----|
| 0 | T_hot_in_C | ×10 | °C | R/W |
| 1 | T_hot_out_C | ×10 | °C | R/W |
| 2 | T_cold_in_C | ×10 | °C | R/W |
| 3 | T_cold_out_C | ×10 | °C | R/W |
| 4 | flow_hot_lpm | ×10 | L/min | R |
| 5 | flow_cold_lpm | ×10 | L/min | R |
| 6 | pressure_hot_in_bar | ×100 | bar | R |
| 7 | pressure_hot_out_bar | ×100 | bar | R |
| 8 | pressure_cold_in_bar | ×100 | bar | R |
| 9 | pressure_cold_out_bar | ×100 | bar | R |
| 10 | Q_duty_kW | ×1 | kW | R |
| 11 | efficiency_pct | ×10 | % | R |
| 12 | hot_pump_speed_rpm | ×1 | RPM | R/W |
| 13 | cold_pump_speed_rpm | ×1 | RPM | R/W |
| 14 | hot_valve_pos_pct | ×10 | % | R/W |
| 15 | cold_valve_pos_pct | ×10 | % | R/W |
| 16 | fault_code | raw | 0-3 | R/W |

**Fault codes:** 0=OK 1=PUMP_FAULT 2=SENSOR_FAULT 3=OVERTEMP  
**Overtemp auto-clears** when temperatures drop below limits for 10 seconds

### Boiler — Port 507

| Index | Tag | Scale | Unit | R/W |
|-------|-----|-------|------|-----|
| 0 | drum_pressure_bar | ×100 | bar | R/W |
| 1 | drum_temp_C | ×10 | °C | R/W |
| 2 | drum_level_pct | ×10 | % | R/W |
| 3 | steam_flow_kghr | ×10 | kg/hr | R/W |
| 4 | feedwater_flow_kghr | ×10 | kg/hr | R |
| 5 | fuel_flow_kghr | ×10 | kg/hr | R |
| 6 | burner_state | raw | 0/1/2 | R/W |
| 7 | fw_pump_speed_rpm | ×1 | RPM | R/W |
| 8 | steam_valve_pos_pct | ×10 | % | R/W |
| 9 | fw_valve_pos_pct | ×10 | % | R/W |
| 10 | blowdown_valve_pos_pct | ×10 | % | R/W |
| 11 | flue_gas_temp_C | ×10 | °C | R |
| 12 | combustion_eff_pct | ×10 | % | R |
| 13 | Q_burner_kW | ×1 | kW | R |
| 14 | fault_code | raw | 0-4 | R/W |

**Fault codes:** 0=OK 1=LOW_WATER 2=OVERPRESSURE 3=FLAME_FAILURE 4=PUMP_FAULT  
**Burner states:** 0=OFF 1=LOW(50%) 2=HIGH(100%)  
**Write reg 14 = 0** to clear fault and pulse operator_reset

### Pipeline — Port 508

| Index | Tag | Scale | Unit | R/W |
|-------|-----|-------|------|-----|
| 0 | inlet_pressure_bar | ×100 | bar | R/W |
| 1 | outlet_pressure_bar | ×100 | bar | R/W |
| 2 | flow_rate_m3hr | ×10 | m³/hr | R/W |
| 3 | duty_pump_speed_rpm | ×1 | RPM | R/W |
| 4 | duty_pump_current_A | ×10 | A | R |
| 5 | duty_pump_running | raw | 0/1 | R/W |
| 6 | standby_pump_speed_rpm | ×1 | RPM | R/W |
| 7 | standby_pump_running | raw | 0/1 | R/W |
| 8 | inlet_valve_pos_pct | ×10 | % | R/W |
| 9 | outlet_valve_pos_pct | ×10 | % | R/W |
| 10 | pump_differential_bar | ×100 | bar | R |
| 11 | flow_velocity_ms | ×100 | m/s | R |
| 12 | duty_pump_power_kW | ×1 | kW | R |
| 13 | leak_flag | raw | 0/1 | R/W |
| 14 | fault_code | raw | 0-3 | R/W |

**Fault codes:** 0=OK 1=DUTY_FAULT 2=BOTH_FAULT 3=OVERPRESSURE  
**Write reg 14 = 0** to clear fault and pulse operator_reset

---

## Lab Connectors

The `lab-connectors/` directory contains Modbus client libraries for four languages. These connect directly to the PLC VM and provide both raw register access and high-level control functions.

See `lab-connectors/README.md` for usage.

**Quick start — Python:**
```python
import morbion_lab as lab

# Read all pumping station values
data = lab.ps_read()
print(f"Tank level: {data['tank_level_pct']:.1f}%")

# Start the pump
lab.ps_set_pump(True)

# Clear a fault
lab.ps_clear_fault()
```

---

## Verify Communication

Use the built-in test monitor:

```bash
# One-shot status check
python3 test_communication.py test

# Show current values from all processes
python3 test_communication.py status

# Live monitor — updates every 2 seconds
python3 test_communication.py monitor

# Live monitor — update every 1 second
python3 test_communication.py monitor --interval 1
```

---

## Logs

All process logs go to `processes/logs/`:

```
logs/
├── boiler.log
├── heat_exchanger.log
├── pipeline.log
└── pumping_station.log
```

Each log captures stdout and stderr from the process. On crash, the error and traceback are in the log file.

```bash
# View pipeline log
tail -100 logs/pipeline.log

# Follow live
tail -f logs/pipeline.log

# Follow all logs with process prefix
sudo python3 manager.py logs -f
```

---

## Troubleshooting

### Process shows STOPPED after `manager.py start`

```bash
# Check the log for the crashed process
tail -50 logs/pipeline.log

# Common causes:
# 1. Port already in use — another instance running
# 2. ST program parse error — check plc_program.st for # characters
# 3. process_state.json corrupt — delete it, process will regenerate
# 4. Python import error — check all files are present
```

### PLC program not loading — no control logic running

```bash
# Test ST program load directly
cd processes
python3 -c "
from pipeline.plc_runtime import PLCRuntime
import sys
sys.path.insert(0, '.')
plc = PLCRuntime()
print(plc.status)
"
```

If `loaded: False` — the ST program has a syntax error. Check:
- No `#` characters in VAR blocks (use `(* comment *)` instead)
- No Unicode/special characters (copy-paste corruption)
- All FB instances declared in VAR block before use

### Process running but values wrong

```bash
# Check actual Modbus registers
python3 test_communication.py test
```

If registers read correctly but SCADA shows wrong values — check server is polling the right IP in `server/config.json`.

### Boiler stuck at 0.5 bar with fault

```bash
# Delete stale state file — process will start clean
rm processes/boiler/process_state.json
sudo python3 manager.py restart
```

---

## Scan Loop — How Each Process Runs

Every process follows the same 100ms scan cycle:

```
1. Apply operator writes   (Modbus FC06 writes from SCADA)
2. Physics update          (equipment objects: pumps, valves, tanks)
3. PLC scan                (ST interpreter executes plc_program.st)
4. Clear operator_reset    (one-shot pulse — seen by ST, now cleared)
5. Apply PLC commands      (PLC output image → equipment objects)
6. Update Modbus registers (write current state to register bank)
7. Sleep remainder         (maintain 100ms cycle time)
```

The ST interpreter maintains state between scans. TON timers accumulate real `dt`. SR latches hold their state. This is what makes control logic correct.

---

## Process State Persistence

Each process saves its state to `process_state.json` every 30 seconds. On restart, the state is restored. This means:

- Tank level persists across restarts
- Fault codes persist across restarts
- Drum pressure persists across restarts

**If a fault was active when the process crashed**, it will restore with that fault. Delete the `.json` file to start clean:

```bash
rm processes/boiler/process_state.json
rm processes/pumping_station/process_state.json
rm processes/pipeline/process_state.json
rm processes/heat_exchanger/process_state.json  # if it exists
```

---

## Shared ST Runtime

The `shared/st_runtime/` package is used by all four processes. It contains:

```
shared/st_runtime/
├── __init__.py     — exports Interpreter, parse_st, TON, TOF, SR, RS
├── lexer.py        — tokenizes ST source text
├── parser.py       — recursive descent parser → AST
├── interpreter.py  — executes AST against variable dict
└── stdlib.py       — TON, TOF, CTU, SR, RS, LIMIT, ABS, MAX, MIN
```

The `processes/` directory is added to `PYTHONPATH` by the manager so all processes can import `from shared.st_runtime.interpreter import Interpreter`.

---

*MORBION SCADA v02 — Intelligence. Precision. Vigilance.*






