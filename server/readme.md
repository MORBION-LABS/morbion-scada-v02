# MORBION SCADA v02 — Server

**SCADA server — REST API, WebSocket live data, Alarm Engine, optional Historian and MQTT.**

The server is the integration layer between the process simulations and operator clients. It polls all four processes via Modbus TCP every second, evaluates alarms, maintains plant state, and broadcasts live data to all connected clients over WebSocket. Clients never communicate directly with processes.

---

## Directory Structure

```
server/
├── config.json             Server configuration
├── installer.py            Interactive installer
├── main.py                 Entry point — wires all components, starts Flask
├── server.py               Flask REST API + WebSocket + PLC proxy
├── poller.py               Modbus poll loop — reads all processes each cycle
├── alarm_engine.py         Evaluates alarms from plant state
├── plant_state.py          Thread-safe central state — single source of truth
├── requirements.txt
│
├── alarms/
│   ├── base.py             Abstract base alarm evaluator
│   ├── pumping_station.py  PS alarm rules — level, pressure, fault
│   ├── heat_exchanger.py   HX alarm rules — temperature, efficiency, fault
│   ├── boiler.py           Boiler alarm rules — pressure, level, fault
│   └── pipeline.py         Pipeline alarm rules — pressure, flow, leak, fault
│
├── readers/
│   ├── base.py             Abstract base reader — Modbus TCP read
│   ├── pumping_station.py  Reads 15 PS registers, scales to engineering units
│   ├── heat_exchanger.py   Reads 17 HX registers
│   ├── boiler.py           Reads 15 boiler registers
│   └── pipeline.py         Reads 15 pipeline registers
│
├── modbus/
│   └── client.py           Modbus TCP client — FC03 read, FC06 write (pure socket)
│
├── historian/
│   ├── client.py           InfluxDB client wrapper
│   └── writer.py           Translates plant snapshots to InfluxDB points
│
└── mqtt/
    └── publisher.py        Publishes all process variables to Mosquitto broker
```

---

## Installation

```bash
cd server
pip install -r requirements.txt
python installer.py
```

The installer prompts for:
- **PLC Host IP** — the IP of the machine running `processes/manager.py start`
- **Server Host IP** — the IP of this machine. Use `0.0.0.0` to listen on all interfaces, or a specific IP to bind to one interface only.

This writes `config.json`.

---

## Configuration

`config.json` — edit after installation if needed:

```json
{
  "plc_host": "192.168.100.10",
  "poll_rate_s": 1.0,
  "server_host": "0.0.0.0",
  "server_port": 5000,
  "modbus_timeout_s": 3.0,

  "processes": {
    "pumping_station": { "enabled": true, "port": 502, "register_count": 15 },
    "heat_exchanger":  { "enabled": true, "port": 506, "register_count": 17 },
    "boiler":          { "enabled": true, "port": 507, "register_count": 15 },
    "pipeline":        { "enabled": true, "port": 508, "register_count": 15 }
  },

  "influxdb": {
    "enabled": false,
    "url": "http://localhost:8086",
    "token": "your-token-here",
    "org": "morbion",
    "bucket": "plant_data"
  }
}
```

| Field | Description |
|---|---|
| `plc_host` | IP of the machine running the four process simulations |
| `poll_rate_s` | Modbus poll interval in seconds (default 1.0) |
| `server_host` | IP to bind Flask to — `0.0.0.0` listens on all interfaces |
| `server_port` | REST + WebSocket port (default 5000) |
| `modbus_timeout_s` | Timeout per Modbus read (default 3.0) |

---

## Starting the Server

```bash
cd server
python main.py
```

On startup the server prints:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  MORBION SCADA Server v2.0
  Intelligence. Precision. Vigilance.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PLC host    : 192.168.100.10
  Poll rate   : 1.0s
  Server host : 0.0.0.0:5000
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  REST        : http://0.0.0.0:5000/data
  WebSocket   : ws://0.0.0.0:5000/ws
  Alarms      : http://0.0.0.0:5000/data/alarms
  PLC API     : http://0.0.0.0:5000/plc/<process>/program
  Health      : http://0.0.0.0:5000/health
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

The server waits one full poll cycle before opening Flask, so the first client connection always receives valid data.

---

## REST API Reference

Base URL: `http://<server_host>:5000`

### GET /health

Server status.

```json
{
  "server": "MORBION-v02-SUPERPROXY",
  "status": "online",
  "processes_online": 4,
  "poll_rate_ms": 42.3
}
```

### GET /data

Full plant snapshot — all four processes, active alarms, server metadata.

```json
{
  "pumping_station": {
    "online": true,
    "process": "pumping_station",
    "tank_level_pct": 67.3,
    "pump_running": true,
    "discharge_pressure_bar": 4.82,
    "fault_code": 0,
    "fault_text": "OK",
    ...
  },
  "heat_exchanger": { ... },
  "boiler": { ... },
  "pipeline": { ... },
  "alarms": [ ... ],
  "server_time": "2025-04-23 14:07:29 UTC",
  "poll_count": 8472,
  "poll_rate_ms": 42.3
}
```

### POST /control

Write a Modbus register to a process.

Request body:
```json
{
  "process": "pumping_station",
  "register": 7,
  "value": 1
}
```

Response:
```json
{
  "ok": true,
  "confirmed": true
}
```

`confirmed: true` means FC06 echo matched the written value — the register was physically written. It does not mean the PLC accepted the command. Always verify after 300 ms.

Process names: `pumping_station` · `heat_exchanger` · `boiler` · `pipeline`

Register ranges: `pumping_station` 0–14, `heat_exchanger` 0–16, `boiler` 0–14, `pipeline` 0–14

Values: 0–65535

### GET /data/alarms

Active alarm list with acknowledgment state.

```json
[
  {
    "id": "PS-001",
    "process": "pumping_station",
    "tag": "tank_level_pct",
    "sev": "CRIT",
    "desc": "Tank CRITICAL LOW 4.2% — dry run imminent",
    "ts": "14:07:29",
    "acked": false,
    "acked_at": "",
    "acked_by": ""
  }
]
```

Severity levels: `CRIT` · `HIGH` · `MED` · `LOW`

Alarm IDs by process:

| Process | Alarm IDs |
|---|---|
| pumping_station | PS-001 through PS-006 |
| heat_exchanger | HX-001 through HX-004 |
| boiler | BL-001 through BL-005 |
| pipeline | PL-001 through PL-006 |

### POST /alarms/ack

Acknowledge one alarm or all.

```json
{ "alarm_id": "PS-001", "operator": "OPERATOR" }
```

```json
{ "alarm_id": "all", "operator": "OPERATOR" }
```

### GET /alarms/history

Last 200 alarm events (including cleared and acknowledged alarms).

### GET /plc/\<process\>/program

Returns ST source, runtime status, and variable map in one atomic call.

```json
{
  "process": "boiler",
  "source": "(* BOILER PLC PROGRAM ... *)\n...",
  "status": {
    "loaded": true,
    "scan_count": 84720,
    "last_error": "",
    "program_file": "/path/to/plc_program.st"
  },
  "variables": {
    "inputs": { "drum_pressure_bar": "drum_pressure_bar", ... },
    "outputs": { "burner_cmd": "burner_state", ... },
    "parameters": { "pressure_sp": 8.0, ... }
  }
}
```

### POST /plc/\<process\>/program

Upload new ST source. Validates, writes to file, hot-reloads interpreter.

```json
{ "source": "(* New ST program text *)\n..." }
```

### POST /plc/\<process\>/program/reload

Hot reload ST program from file on disk. Does not require source body.

### GET /plc/\<process\>/status

PLC runtime status only.

### GET /plc/\<process\>/variables

Input/output/parameter variable map only.

---

## WebSocket

```
ws://<server_host>:5000/ws
```

Sends the full plant snapshot JSON every poll cycle (default 1 s). Same format as `GET /data`.

The WebSocket connection is keep-alive — clients send a heartbeat or the connection closes after 60 s of inactivity. The server pings every 20 s.

To connect (Python example):

```python
import websocket, json

def on_message(ws, msg):
    plant = json.loads(msg)
    print(plant["boiler"]["drum_pressure_bar"])

ws = websocket.WebSocketApp(
    "ws://192.168.100.30:5000/ws",
    on_message=on_message
)
ws.run_forever()
```

---

## Internal Architecture

### PlantState

Thread-safe dataclass. Poller writes. Server reads. Never the reverse.

```
PlantState.update()   — atomic update, called by poller once per cycle
PlantState.snapshot() — returns a full copy, never holds lock during JSON serialization
```

### Poller

Background thread. Reads all four processes via Modbus TCP every poll cycle. On read failure, the process is reported as offline (`{"online": false}`). Partial failures (one process unreachable) do not affect others.

### AlarmEngine

Evaluates alarms from the plant snapshot after every poll cycle. Each process has a dedicated evaluator (`alarms/pumping_station.py`, etc.). Evaluators return alarm dicts. The engine sorts by severity (CRIT → HIGH → MED → LOW) and returns a unified list.

Alarm evaluation is stateless per cycle — alarms fire whenever the condition is active, not just on rising edge. Acknowledgment state is maintained in the server's in-memory store (`_alarm_ack_store`), not in the process.

### PLC Proxy (Super-Proxy)

The server proxies `/plc/<process>/...` requests to the per-process HTTP API:

| Process | Secondary HTTP Port |
|---|---|
| pumping_station | 5020 |
| heat_exchanger | 5060 |
| boiler | 5070 |
| pipeline | 5080 |

`GET /plc/<process>/program` is a super-proxy: it fetches source, status, and variables in three parallel calls and returns them combined. This ensures the PLC Programs tab in clients always has complete data.

---

## Alarm Rules

### Pumping Station

| Alarm ID | Tag | Condition | Severity |
|---|---|---|---|
| PS-001 | tank_level_pct | ≥ 90% | CRIT |
| PS-002 | tank_level_pct | ≥ 80% | HIGH |
| PS-003 | tank_level_pct | ≤ 5% | CRIT |
| PS-004 | tank_level_pct | ≤ 10% | HIGH |
| PS-005 | discharge_pressure_bar | ≥ 8.0 bar | HIGH |
| PS-006 | fault_code | ≠ 0 | HIGH |

### Heat Exchanger

| Alarm ID | Tag | Condition | Severity |
|---|---|---|---|
| HX-001 | T_cold_out_C | ≥ 95°C | CRIT |
| HX-002 | T_hot_out_C | ≥ 160°C | HIGH |
| HX-003 | efficiency_pct | < 45% | MED |
| HX-004 | fault_code | ≠ 0 | HIGH |

### Boiler

| Alarm ID | Tag | Condition | Severity |
|---|---|---|---|
| BL-001 | drum_pressure_bar | ≥ 10.0 bar | CRIT |
| BL-002 | drum_pressure_bar | ≤ 6.0 bar | HIGH |
| BL-003 | drum_level_pct | ≤ 20% | CRIT |
| BL-004 | drum_level_pct | ≥ 80% | HIGH |
| BL-005 | fault_code | ≠ 0 | HIGH |

### Pipeline

| Alarm ID | Tag | Condition | Severity |
|---|---|---|---|
| PL-001 | outlet_pressure_bar | ≥ 55 bar | CRIT |
| PL-002 | outlet_pressure_bar | ≤ 30 bar | HIGH |
| PL-003 | inlet_pressure_bar | ≤ 1.0 bar | HIGH |
| PL-004 | flow_rate_m3hr | ≤ 200 m³/hr | MED |
| PL-005 | leak_flag | true | CRIT |
| PL-006 | fault_code | ≠ 0 | HIGH |

---

## Optional Services

### InfluxDB Historian

Enable in `config.json`. Requires `influxdb-client` package.

```bash
pip install influxdb-client
```

The historian writes one InfluxDB point per online process per poll cycle. Tags: `process`, `label`, `location`. Fields: all numeric and boolean process values. String fields (fault_text, etc.) are skipped.

### MQTT Publisher

Add to `config.json`:

```json
"mqtt": {
  "enabled": true,
  "host": "127.0.0.1",
  "port": 1883,
  "topic_prefix": "morbion",
  "keepalive": 60
}
```

```bash
pip install paho-mqtt
```

Topic pattern: `morbion/<process>/<variable>`

Alarm topics: `morbion/alarms/count` · `morbion/alarms/crit_count`
Status topic: `morbion/server/status` (retained — persists for new subscribers)
Will message: `morbion/server/status = offline` (published on ungraceful disconnect)

---

## Requirements

```
flask>=3.0
flask-cors>=4.0
flask-sock>=0.7
influxdb-client>=1.40    (optional — historian only)
paho-mqtt>=1.6           (optional — MQTT only)
```

---

## Troubleshooting

**All processes show offline**
- `plc_host` in `config.json` must point to the machine running `processes/manager.py start`
- Test: `python -c "import socket; s=socket.socket(); s.connect(('<plc_host>', 502)); print('OK')"` 
- Confirm processes are running: `python processes/manager.py status`

**Server starts but WebSocket clients cannot connect**
- `server_host: 0.0.0.0` to listen on all interfaces (not just localhost)
- Check firewall rules for port 5000

**PLC API returns 503**
- The process HTTP API (secondary ports 5020/5060/5070/5080) must be running
- These are hosted by the processes themselves — the processes must be running
- Verify `shared/plc_http.py` is imported and started in each process `main.py`

**Alarm history is empty**
- Alarm history is in-memory only — it resets on server restart
- For persistent history, enable InfluxDB

**CORS errors in browser client**
- Flask-CORS is configured with `origins="*"` — all origins allowed
- If still seeing CORS errors, verify the browser is connecting to the correct server port

---

*MORBION SCADA v02 — Intelligence. Precision. Vigilance.*
