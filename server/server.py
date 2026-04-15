"""
server.py — MORBION SCADA Flask HTTP + WebSocket Layer
MORBION SCADA v02

KEY CHANGES FROM v01:
  - /data/alarms route fixed — was returning 404 in v01
    because it was defined AFTER /data/<process> which
    captured "alarms" as a process name first.
    Fixed by defining /data/alarms BEFORE /data/<process>.

  - PLC API endpoints added:
    GET  /plc/<process>/program         — get ST source
    POST /plc/<process>/program         — upload new ST source
    POST /plc/<process>/program/reload  — hot reload from file
    GET  /plc/<process>/status          — runtime status
    GET  /plc/<process>/variables       — variable map

  - Alarm acknowledgment endpoints:
    POST /alarms/ack                    — acknowledge alarm(s)
    GET  /alarms/history                — recent alarm history

  - MQTT publisher wired in via init_server()

Architecture:
  Thin layer. Reads from PlantState. Writes to PLC via Modbus.
  No business logic here. No physics. No alarm evaluation.
  Those live in poller.py, alarm_engine.py, and the processes.
"""

import json
import threading
import logging
from datetime import datetime

from flask      import Flask, jsonify, request
from flask_cors import CORS
from flask_sock import Sock
from plant_state import PlantState

log = logging.getLogger("server")

app  = Flask(__name__)
CORS(app, origins="*")
sock = Sock(app)

# Module-level refs — set by init_server()
_state:      PlantState  = None
_plc_host:   str         = ""
_mqtt:       object      = None   # MQTTPublisher or None
_plc_runtimes: dict      = {}     # process_name → PLCRuntime (optional, for API)

# WebSocket client registry
_ws_clients: set            = set()
_ws_lock:    threading.Lock = threading.Lock()

# Alarm acknowledgment store
# key: alarm_id, value: {"acked": bool, "acked_at": str, "acked_by": str}
_alarm_ack_store: dict      = {}
_ack_lock:        threading.Lock = threading.Lock()

# Alarm history — last 200 alarms
_alarm_history: list        = []
_history_lock:  threading.Lock = threading.Lock()
_HISTORY_MAX = 200

_PORT_MAP = {
    "pumping_station": 502,
    "heat_exchanger":  506,
    "boiler":          507,
    "pipeline":        508,
}

_MAX_REG = {
    "pumping_station": 14,
    "heat_exchanger":  16,
    "boiler":          14,
    "pipeline":        14,
}


def init_server(state: PlantState, plc_host: str,
                mqtt_publisher=None, plc_runtimes: dict = None) -> None:
    global _state, _plc_host, _mqtt, _plc_runtimes
    _state        = state
    _plc_host     = plc_host
    _mqtt         = mqtt_publisher
    _plc_runtimes = plc_runtimes or {}


def broadcast(payload: str) -> None:
    """Push JSON string to all connected WebSocket clients."""
    dead = set()
    with _ws_lock:
        for ws in list(_ws_clients):
            try:
                ws.send(payload)
            except Exception:
                dead.add(ws)
        _ws_clients.difference_update(dead)


def _update_alarm_history(alarms: list) -> None:
    """Called by poller or broadcast loop to maintain alarm history."""
    with _history_lock:
        for alarm in alarms:
            aid = alarm.get("id")
            if aid and not any(a.get("id") == aid for a in _alarm_history[-50:]):
                _alarm_history.append(dict(alarm))
                if len(_alarm_history) > _HISTORY_MAX:
                    _alarm_history.pop(0)


# ── REST — System ──────────────────────────────────────────────────────────────

@app.route("/")
def root():
    return jsonify({
        "name":    "MORBION SCADA Server",
        "version": "2.0",
        "endpoints": [
            "GET  /health",
            "GET  /data",
            "GET  /data/alarms",
            "GET  /data/<process>",
            "POST /control",
            "POST /alarms/ack",
            "GET  /alarms/history",
            "GET  /plc/<process>/program",
            "POST /plc/<process>/program",
            "POST /plc/<process>/program/reload",
            "GET  /plc/<process>/status",
            "GET  /plc/<process>/variables",
            "WS   /ws",
        ],
    })


@app.route("/health")
def health():
    snap = _state.snapshot()
    return jsonify({
        "server":           "MORBION SCADA v2.0",
        "status":           "online",
        "processes_online": _state.processes_online(),
        "processes_total":  4,
        "poll_count":       snap["poll_count"],
        "poll_rate_ms":     snap["poll_rate_ms"],
        "server_time":      snap["server_time"],
    })


# ── REST — Data ────────────────────────────────────────────────────────────────

@app.route("/data")
def data_all():
    return jsonify(_state.snapshot())


# CRITICAL: /data/alarms MUST be defined BEFORE /data/<process>
# Flask matches routes in definition order.
# If /data/<process> comes first, "alarms" is captured as process name
# and returns 404 because "alarms" is not a valid process.
@app.route("/data/alarms")
def data_alarms():
    snap   = _state.snapshot()
    alarms = snap.get("alarms", [])

    # Annotate with acknowledgment status
    with _ack_lock:
        annotated = []
        for alarm in alarms:
            a    = dict(alarm)
            aid  = a.get("id", "")
            ack  = _alarm_ack_store.get(aid, {})
            a["acked"]    = ack.get("acked", False)
            a["acked_at"] = ack.get("acked_at", "")
            annotated.append(a)

    return jsonify(annotated)


@app.route("/data/<process>")
def data_process(process: str):
    valid = tuple(_PORT_MAP.keys())
    if process not in valid:
        return jsonify({"error": f"Unknown process '{process}'"}), 404
    return jsonify(_state.snapshot().get(process, {}))


# ── REST — Control ─────────────────────────────────────────────────────────────

@app.route("/control", methods=["POST"])
def control():
    """
    Write a single Modbus register via FC06.
    Body: {process, register, value}
    This is the endpoint the desktop client and web client both use.
    """
    if not request.is_json:
        return jsonify({"ok": False,
                        "error": "Content-Type must be application/json"}), 400

    body = request.get_json(silent=True)
    if not body:
        return jsonify({"ok": False, "error": "Empty or invalid JSON body"}), 400

    process  = body.get("process")
    register = body.get("register")
    value    = body.get("value")

    if process is None or register is None or value is None:
        return jsonify({"ok": False,
                        "error": "Required: process, register, value"}), 400

    if process not in _PORT_MAP:
        return jsonify({"ok": False,
                        "error": f"Unknown process '{process}'. "
                                 f"Valid: {list(_PORT_MAP.keys())}"}), 400

    if not isinstance(register, int) or not isinstance(value, int):
        return jsonify({"ok": False,
                        "error": "register and value must be integers"}), 400

    if not (0 <= register <= _MAX_REG[process]):
        return jsonify({"ok": False,
                        "error": f"register {register} out of range "
                                 f"for {process} (0-{_MAX_REG[process]})"}), 400

    if not (0 <= value <= 65535):
        return jsonify({"ok": False,
                        "error": "value must be 0-65535"}), 400

    port = _PORT_MAP[process]
    try:
        from modbus.client import ModbusClient, ModbusError
        client    = ModbusClient(_plc_host, port, timeout=3.0)
        confirmed = client.write_register(register, value)
        log.info("CONTROL %s reg=%d val=%d confirmed=%s",
                 process, register, value, confirmed)
        return jsonify({
            "ok":        True,
            "process":   process,
            "port":      port,
            "register":  register,
            "value":     value,
            "confirmed": confirmed,
        })
    except Exception as e:
        log.error("CONTROL FAILED %s reg=%d val=%d: %s",
                  process, register, value, e)
        return jsonify({
            "ok":      False,
            "process": process,
            "register":register,
            "value":   value,
            "error":   str(e),
        }), 500


# ── REST — Alarm Acknowledgment ────────────────────────────────────────────────

@app.route("/alarms/ack", methods=["POST"])
def alarms_ack():
    """
    Acknowledge one alarm or all active alarms.
    Body: {"alarm_id": "PS-001"} or {"alarm_id": "all"}
    Optional: {"operator": "JohnDoe"}
    """
    body = request.get_json(silent=True) or {}
    alarm_id = body.get("alarm_id", "")
    operator = body.get("operator", "OPERATOR")

    if not alarm_id:
        return jsonify({"ok": False,
                        "error": "alarm_id required"}), 400

    now  = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    snap = _state.snapshot()
    active_alarms = snap.get("alarms", [])

    acked_ids = []

    with _ack_lock:
        if alarm_id.lower() == "all":
            for alarm in active_alarms:
                aid = alarm.get("id", "")
                if aid:
                    _alarm_ack_store[aid] = {
                        "acked":    True,
                        "acked_at": now,
                        "acked_by": operator,
                    }
                    acked_ids.append(aid)
        else:
            _alarm_ack_store[alarm_id] = {
                "acked":    True,
                "acked_at": now,
                "acked_by": operator,
            }
            acked_ids.append(alarm_id)

    log.info("ALARM ACK by %s: %s", operator, acked_ids)
    return jsonify({"ok": True, "acked": acked_ids, "operator": operator})


@app.route("/alarms/history")
def alarms_history():
    """Return recent alarm history — last 200 alarm events."""
    with _history_lock:
        return jsonify(list(_alarm_history))


# ── REST — PLC API ─────────────────────────────────────────────────────────────

@app.route("/plc/<process>/program", methods=["GET"])
def plc_get_program(process: str):
    """Get ST program source for a process."""
    if process not in _PORT_MAP:
        return jsonify({"error": f"Unknown process '{process}'"}), 404

    runtime = _plc_runtimes.get(process)
    if runtime is None:
        return jsonify({"error": "PLC runtime not available for this process"}), 503

    return jsonify({
        "process": process,
        "source":  runtime.program_source,
        "status":  runtime.status,
    })


@app.route("/plc/<process>/program", methods=["POST"])
def plc_upload_program(process: str):
    """
    Upload new ST program source.
    Validates syntax before applying.
    Body: {"source": "...ST program text..."}
    """
    if process not in _PORT_MAP:
        return jsonify({"error": f"Unknown process '{process}'"}), 404

    runtime = _plc_runtimes.get(process)
    if runtime is None:
        return jsonify({"error": "PLC runtime not available"}), 503

    body = request.get_json(silent=True) or {}
    source = body.get("source", "")

    if not source:
        return jsonify({"ok": False, "error": "source field required"}), 400

    success = runtime.upload_program(source)

    if success:
        log.info("PLC program uploaded for %s", process)
        return jsonify({"ok": True, "process": process,
                        "status": runtime.status})
    else:
        return jsonify({"ok": False, "process": process,
                        "error": runtime.status.get("last_error", "Upload failed"),
                        "status": runtime.status}), 400


@app.route("/plc/<process>/program/reload", methods=["POST"])
def plc_reload_program(process: str):
    """Hot reload ST program from file on disk."""
    if process not in _PORT_MAP:
        return jsonify({"error": f"Unknown process '{process}'"}), 404

    runtime = _plc_runtimes.get(process)
    if runtime is None:
        return jsonify({"error": "PLC runtime not available"}), 503

    runtime.reload()
    log.info("PLC program reloaded for %s", process)
    return jsonify({"ok": True, "process": process,
                    "status": runtime.status})


@app.route("/plc/<process>/status", methods=["GET"])
def plc_status(process: str):
    """Get PLC runtime status for a process."""
    if process not in _PORT_MAP:
        return jsonify({"error": f"Unknown process '{process}'"}), 404

    runtime = _plc_runtimes.get(process)
    if runtime is None:
        return jsonify({"error": "PLC runtime not available"}), 503

    return jsonify({"process": process, "status": runtime.status})


@app.route("/plc/<process>/variables", methods=["GET"])
def plc_variables(process: str):
    """Get PLC variable map (inputs/outputs/parameters) for a process."""
    if process not in _PORT_MAP:
        return jsonify({"error": f"Unknown process '{process}'"}), 404

    runtime = _plc_runtimes.get(process)
    if runtime is None:
        return jsonify({"error": "PLC runtime not available"}), 503

    return jsonify({"process": process, "variables": runtime.variables})


# ── WebSocket ──────────────────────────────────────────────────────────────────

@sock.route("/ws")
def ws_endpoint(ws):
    """
    WebSocket endpoint.
    On connect: send current state immediately.
    Stays open: client sends keep-alive pings, server ignores content.
    On disconnect: remove from registry.
    """
    with _ws_lock:
        _ws_clients.add(ws)

    try:
        ws.send(json.dumps(_state.snapshot()))
    except Exception:
        pass

    try:
        while True:
            msg = ws.receive(timeout=60)
            if msg is None:
                break
    except Exception:
        pass
    finally:
        with _ws_lock:
            _ws_clients.discard(ws)

      
