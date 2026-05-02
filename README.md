# MORBION SCADA v02

**Intelligence. Precision. Vigilance.**

A virtual Industrial Control System laboratory simulating four real Kenyan industrial processes over Modbus TCP. Built for learning Operational Technology — PLC logic, SCADA architecture, HMI design, alarm management, and process physics — without touching real plant equipment.

---

## Architecture Overview

```
morbion-scada-v02/
├── processes/          Four Modbus TCP process simulations with PLC VM
├── server/             SCADA server — REST + WebSocket + Alarm Engine
├── desktop-client/     PyQt6 desktop HMI
├── web-client/         React + Vite web HMI  (planned)
└── tui-client/         Textual TUI HMI       (planned)
```

The three layers never skip each other. Clients connect to the server only. The server polls the processes via Modbus TCP. The processes run physics and PLC logic locally and expose Modbus registers.

```
[Process VM]  ←── Modbus TCP ───→  [SCADA Server]  ←── REST/WebSocket ───→  [Clients]
  port 502/506/507/508                port 5000                              desktop/web/tui
```

---

## The Four Processes

| Process | Real-World Reference | Modbus Port | Registers |
|---|---|---|---|
| Pumping Station | Nairobi City Water — Municipal pumping | 502 | 15 |
| Heat Exchanger | KenGen Olkaria — Geothermal heat recovery | 506 | 17 |
| Boiler | EABL / Bidco — Industrial steam generation | 507 | 15 |
| Pipeline | Kenya Pipeline Company — Petroleum transfer | 508 | 15 |

Each process runs an IEC 61131-3 Structured Text PLC program every 100 ms. The interpreter enforces physics-derived interlocks. Operator commands written via Modbus are evaluated by the PLC on the next scan and may be overridden if process conditions forbid them.

---

## Repository Structure

```
morbion-scada-v02/
│
├── processes/
│   ├── config.yaml                 Global config — PLC host IP, server host IP
│   ├── installer.py                Interactive installer
│   ├── manager.py                  Process lifecycle manager (start/stop/status/logs)
│   ├── requirements.txt
│   ├── test_communication.py       Live Modbus monitor (Textual/Rich TUI)
│   ├── pumping_station/            Process simulation + PLC VM
│   ├── heat_exchanger/
│   ├── boiler/
│   ├── pipeline/
│   └── shared/
│       ├── plc_http.py             Per-process HTTP API for PLC program management
│       └── st_runtime/             IEC 61131-3 ST lexer, parser, interpreter
│
├── server/
│   ├── config.json                 Server config — PLC host, server host, poll rate
│   ├── installer.py                Interactive installer
│   ├── main.py                     Server entry point
│   ├── server.py                   Flask REST + WebSocket + proxy
│   ├── poller.py                   Modbus poll loop
│   ├── alarm_engine.py             Alarm evaluation
│   ├── plant_state.py              Thread-safe plant state
│   ├── requirements.txt
│   ├── alarms/                     Per-process alarm evaluators
│   ├── readers/                    Per-process Modbus readers
│   ├── modbus/                     Modbus TCP client (pure socket)
│   ├── historian/                  InfluxDB writer (optional)
│   └── mqtt/                       MQTT publisher (optional)
│
└── desktop-client/
    ├── config.json                 Client config — server IP, operator name
    ├── installer.py                Interactive installer
    ├── main.py                     Entry point
    ├── main_window.py              Main window — tabs + scripting engine
    ├── splash.py                   Connection splash screen
    ├── theme.py                    All colours, fonts, QSS
    ├── requirements.txt
    ├── connection/                 REST client + WebSocket thread
    ├── views/                      Per-tab process views
    └── widgets/                    Reusable display and control widgets
```

---

## Prerequisites

- Python 3.11 or higher (3.12 recommended)
- Two machines recommended: one running processes + server, one running client
- Single-machine deployment works for development/learning

---

## Installation — Full System

### Step 1 — Clone the repository

```bash
git clone https://github.com/<your-username>/morbion-scada-v02.git
cd morbion-scada-v02
```

### Step 2 — Install processes

```bash
cd processes
pip install -r requirements.txt
python installer.py
# Enter PLC host IP (the machine running processes — often 127.0.0.1 for local)
# Enter SCADA server host IP (the machine running the server)
```

### Step 3 — Install server

```bash
cd ../server
pip install -r requirements.txt
python installer.py
# Enter PLC host IP (where processes are running)
# Enter server host IP (this machine's IP — use 0.0.0.0 to listen on all interfaces)
```

### Step 4 — Install desktop client

```bash
cd ../desktop-client
pip install -r requirements.txt
python installer.py
# Enter server IP and port
```

---

## Running the System

### Start processes (on PLC machine)

```bash
cd processes
python manager.py start
python manager.py status   # verify all four are running
```

### Start server (on server machine)

```bash
cd server
python main.py
```

### Start desktop client (on operator machine)

```bash
cd desktop-client
python main.py
```

---

## Cloning a Single Sub-Repository

MORBION uses a monorepo layout. To work with a single component using sparse checkout:

```bash
git clone --no-checkout https://github.com/<your-username>/morbion-scada-v02.git
cd morbion-scada-v02
git sparse-checkout init --cone
git sparse-checkout set server
git checkout main
```

Replace `server` with `processes`, `desktop-client`, etc.

Or simply clone the full repository and work in the subdirectory — the components are independent.

---

## Network Topology

```
┌─────────────────────────────────────────────────────────────────┐
│  PLC Machine (e.g. 192.168.100.10)                              │
│                                                                 │
│  processes/pumping_station/main.py  → Modbus TCP :502          │
│  processes/heat_exchanger/main.py   → Modbus TCP :506          │
│  processes/boiler/main.py           → Modbus TCP :507          │
│  processes/pipeline/main.py         → Modbus TCP :508          │
│                                                                 │
│  PLC HTTP APIs:  :5020  :5060  :5070  :5080                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Modbus TCP (FC03 read, FC06 write)
┌───────────────────────────▼─────────────────────────────────────┐
│  SCADA Server Machine (e.g. 192.168.100.30)                     │
│                                                                 │
│  server/main.py                                                 │
│    REST API      http://<server>:5000/                          │
│    WebSocket     ws://<server>:5000/ws                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST / WebSocket
┌───────────────────────────▼─────────────────────────────────────┐
│  Operator Machine                                               │
│                                                                 │
│  desktop-client/main.py   → PyQt6 HMI                          │
│  web-client (browser)     → React HMI                          │
│  tui-client/main.py       → Textual TUI                        │
└─────────────────────────────────────────────────────────────────┘
```

Single-machine deployment: all IPs become `127.0.0.1`.

---

## Server API Reference

Base URL: `http://<server_host>:5000`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Server status, processes online count |
| GET | `/data` | Full plant snapshot — all four processes |
| GET | `/data/alarms` | Active alarm list with acknowledgment state |
| POST | `/control` | Write a Modbus register |
| GET | `/alarms/history` | Last 200 alarm events |
| POST | `/alarms/ack` | Acknowledge alarm(s) |
| WS | `/ws` | Live plant data stream (1 s interval) |
| GET | `/plc/<process>/program` | ST source + status + variable map |
| POST | `/plc/<process>/program` | Upload new ST source |
| POST | `/plc/<process>/program/reload` | Hot reload ST from file |
| GET | `/plc/<process>/status` | PLC runtime status |
| GET | `/plc/<process>/variables` | Input/output/parameter map |

### Control write body

```json
{
  "process": "pumping_station",
  "register": 7,
  "value": 1
}
```

Process names: `pumping_station` · `heat_exchanger` · `boiler` · `pipeline`

---

## Register Maps

### Pumping Station — Port 502

| Index | Tag | Scale | Unit | Notes |
|---|---|---|---|---|
| 0 | tank_level_pct | ×10 | % | Write to inject level |
| 1 | tank_volume_m3 | ×10 | m³ | Read only |
| 2 | pump_speed_rpm | ×1 | RPM | Write to set speed |
| 3 | pump_flow_m3hr | ×10 | m³/hr | Write to inject flow |
| 4 | discharge_pressure_bar | ×100 | bar | Write to inject pressure |
| 5 | pump_current_A | ×10 | A | Read only |
| 6 | pump_power_kW | ×10 | kW | Read only |
| 7 | pump_running | raw | 0/1 | Write 1=start 0=stop |
| 8 | inlet_valve_pos_pct | ×10 | % | Write >500 open ≤500 close |
| 9 | outlet_valve_pos_pct | ×10 | % | Write position |
| 10 | demand_flow_m3hr | ×10 | m³/hr | Read only |
| 11 | net_flow_m3hr | ×10 | m³/hr | Read only |
| 12 | pump_starts_today | raw | count | Read only |
| 13 | level_sensor_mm | ×1 | mm | Read only |
| 14 | fault_code | raw | 0–4 | Write 0 to clear |

Fault codes: `0=OK` `1=HIGH_LEVEL` `2=LOW_LEVEL` `3=PUMP_FAULT` `4=DRY_RUN`

### Heat Exchanger — Port 506

| Index | Tag | Scale | Unit | Notes |
|---|---|---|---|---|
| 0 | T_hot_in_C | ×10 | °C | Write to inject |
| 1 | T_hot_out_C | ×10 | °C | Write to inject |
| 2 | T_cold_in_C | ×10 | °C | Write to inject |
| 3 | T_cold_out_C | ×10 | °C | Write >950 for overtemp |
| 4 | flow_hot_lpm | ×10 | L/min | Read only |
| 5 | flow_cold_lpm | ×10 | L/min | Read only |
| 6 | pressure_hot_in_bar | ×100 | bar | Read only |
| 7 | pressure_hot_out_bar | ×100 | bar | Read only |
| 8 | pressure_cold_in_bar | ×100 | bar | Read only |
| 9 | pressure_cold_out_bar | ×100 | bar | Read only |
| 10 | Q_duty_kW | ×1 | kW | Read only |
| 11 | efficiency_pct | ×10 | % | Read only |
| 12 | hot_pump_speed_rpm | ×1 | RPM | Write to set speed |
| 13 | cold_pump_speed_rpm | ×1 | RPM | Write to set speed |
| 14 | hot_valve_pos_pct | ×10 | % | Write position |
| 15 | cold_valve_pos_pct | ×10 | % | Write position |
| 16 | fault_code | raw | 0–3 | Write 0 to clear |

Fault codes: `0=OK` `1=PUMP_FAULT` `2=SENSOR_FAULT` `3=OVERTEMP`
Fault 3 auto-clears when temperatures recover for 10 s — no operator reset needed.

### Boiler — Port 507

| Index | Tag | Scale | Unit | Notes |
|---|---|---|---|---|
| 0 | drum_pressure_bar | ×100 | bar | Write >1000 for overpressure |
| 1 | drum_temp_C | ×10 | °C | Write to inject |
| 2 | drum_level_pct | ×10 | % | Write <200 for low water |
| 3 | steam_flow_kghr | ×10 | kg/hr | Write to inject |
| 4 | feedwater_flow_kghr | ×10 | kg/hr | Read only |
| 5 | fuel_flow_kghr | ×10 | kg/hr | Read only |
| 6 | burner_state | raw | 0/1/2 | Write 0=OFF 1=LOW 2=HIGH |
| 7 | fw_pump_speed_rpm | ×1 | RPM | Write to set speed |
| 8 | steam_valve_pos_pct | ×10 | % | Write position |
| 9 | fw_valve_pos_pct | ×10 | % | Write position |
| 10 | blowdown_valve_pos_pct | ×10 | % | Write position |
| 11 | flue_gas_temp_C | ×10 | °C | Read only |
| 12 | combustion_eff_pct | ×10 | % | Read only |
| 13 | Q_burner_kW | ×1 | kW | Read only |
| 14 | fault_code | raw | 0–4 | Write 0 to clear |

Fault codes: `0=OK` `1=LOW_WATER` `2=OVERPRESSURE` `3=FLAME_FAILURE` `4=PUMP_FAULT`
Faults 1, 2, 4 are SR-latched — require operator_reset AND physical condition recovery.
Fault 2 auto-clears on cold start (drum pressure < 1.0 bar).

### Pipeline — Port 508

| Index | Tag | Scale | Unit | Notes |
|---|---|---|---|---|
| 0 | inlet_pressure_bar | ×100 | bar | Write to inject |
| 1 | outlet_pressure_bar | ×100 | bar | Write >5500 for overpressure |
| 2 | flow_rate_m3hr | ×10 | m³/hr | Write to inject flow |
| 3 | duty_pump_speed_rpm | ×1 | RPM | Write to set speed |
| 4 | duty_pump_current_A | ×10 | A | Read only |
| 5 | duty_pump_running | raw | 0/1 | Write 1=start 0=stop |
| 6 | standby_pump_speed_rpm | ×1 | RPM | Write to set speed |
| 7 | standby_pump_running | raw | 0/1 | Write 1=start 0=stop |
| 8 | inlet_valve_pos_pct | ×10 | % | Write position |
| 9 | outlet_valve_pos_pct | ×10 | % | Write position |
| 10 | pump_differential_bar | ×100 | bar | Read only |
| 11 | flow_velocity_ms | ×100 | m/s | Read only |
| 12 | duty_pump_power_kW | ×1 | kW | Read only |
| 13 | leak_flag | raw | 0/1 | Write 1 to inject leak |
| 14 | fault_code | raw | 0–3 | Write 0 to clear |

Fault codes: `0=OK` `1=DUTY_FAULT` `2=BOTH_FAULT` `3=OVERPRESSURE`
All pipeline faults are SR-latched — require operator_reset AND condition recovery.

---

## Operator Reset Mechanism

Writing `0` to register 14 on any process triggers the operator reset sequence:

1. The Modbus server receives the FC06 write
2. The write is queued into the main scan loop
3. `apply_operator_writes()` dequeues it and sets `state.operator_reset = True`
4. The PLC ST program evaluates SR latch RESET conditions on this scan
5. `operator_reset` is cleared after one scan (100 ms) — it is a one-shot pulse
6. The latch only clears if the physical condition has also recovered (e.g. pressure < 9.5 bar for overpressure)

Writing fault clear when the condition is still active does nothing. Fix the process first, then reset.

---

## PLC Physics Reality — Critical

The PLC re-evaluates every 100 ms and enforces real constraints. Writing to a register does not guarantee the outcome.

| Write | Potential Override | Reason |
|---|---|---|
| Start pump | PLC stops it | Tank level < 5% (dry run imminent) |
| Burner HIGH | PLC cuts immediately | Low water latch active |
| Open outlet valve | PLC modulates back | Maintaining target pressure |
| Clear fault | No effect | Physical condition not yet recovered |

All clients implement verify-after-write: write → wait 300 ms → read back → compare. A mismatch is not an error — it is the PLC correctly doing its job.

---

## Optional Services

### InfluxDB Historian

Edit `server/config.json`:

```json
"influxdb": {
  "enabled": true,
  "url": "http://localhost:8086",
  "token": "your-influxdb-token",
  "org": "your-org",
  "bucket": "plant_data"
}
```

### MQTT Publisher

Add to `server/config.json`:

```json
"mqtt": {
  "enabled": true,
  "host": "localhost",
  "port": 1883,
  "topic_prefix": "morbion",
  "keepalive": 60
}
```

Topic pattern: `morbion/<process>/<variable>`
Examples: `morbion/boiler/drum_pressure_bar` · `morbion/pipeline/leak_flag`

---

## Troubleshooting

**Processes show OFFLINE in client**
- Confirm processes are running: `cd processes && python manager.py status`
- Check PLC host IP in `server/config.json` matches the machine running processes
- Verify Modbus ports 502, 506, 507, 508 are not firewalled

**Server cannot connect to PLC**
- `plc_host` in `server/config.json` must be the IP of the machine running `processes/manager.py start`
- Test connectivity: `python processes/test_communication.py status`

**Desktop client shows "SERVER UNREACHABLE"**
- Check `server_host` in `desktop-client/config.json`
- Ensure server is running: `python server/main.py`
- Verify port 5000 is reachable from the client machine

**PLC Programs tab shows no source / returns 503**
- Each process must be running — it hosts its own HTTP API on secondary ports (5020, 5060, 5070, 5080)
- The server proxies these through `/plc/<process>/program`
- Confirm `shared/plc_http.py` is imported and started in each `main.py`

**Fault clear has no effect**
- The physical condition must recover first (e.g. boiler pressure must drop below 9.5 bar before overpressure latch clears)
- Write 0 to register 14 only after the process has physically recovered

**Alarm never clears**
- SR-latched alarms (boiler faults 1, 2, 4; all pipeline faults; pumping station fault 2) require both: operator reset AND physical recovery
- HX fault 3 (overtemp) auto-clears — no operator action needed

---

## Project Identity

```
MORBION SCADA v02
INDUSTRIAL CONTROL SYSTEM
Intelligence. Precision. Vigilance.
```

Built as a virtual ICS laboratory for OT ENGINEERS and OT Security professionals learning operational technology, process control, and SCADA systems.

---

