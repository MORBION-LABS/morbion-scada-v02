"""
server.py — MORBION SCADA Flask Server
MORBION SCADA v02 — FULL SURGICAL REBOOT (COMPLETE)

Fixes: 
1. Restores 'broadcast' and '_update_alarm_history' for main.py.
2. Increases proxy timeouts for large ST files.
3. Explicit UTF-8 decoding for Windows compatibility.
"""

import json
import threading
import logging
import urllib.request
import urllib.error
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sock import Sock
from plant_state import PlantState

log = logging.getLogger("server")

app = Flask(__name__)
CORS(app, origins="*")
sock = Sock(app)

# ── Global State ──────────────────────────────────────────────────────────────
_state:    PlantState = None
_plc_host: str        = ""
_mqtt:     object     = None

# WebSocket clients
_ws_clients: set            = set()
_ws_lock:    threading.Lock = threading.Lock()

# Alarm management
_alarm_ack_store: dict          = {}
_ack_lock:        threading.Lock = threading.Lock()
_alarm_history:   list           = []
_history_lock:    threading.Lock = threading.Lock()
_HISTORY_MAX = 200

# Constants
_PORT_MAP = {
    "pumping_station": 502, "heat_exchanger": 506,
    "boiler": 507,          "pipeline": 508
}
_PLC_HTTP_PORTS = {
    "pumping_station": 5020, "heat_exchanger": 5060,
    "boiler": 5070,          "pipeline": 5080
}

# ── Required by main.py ───────────────────────────────────────────────────────

def init_server(state: PlantState, plc_host: str, mqtt_publisher=None, **kwargs) -> None:
    global _state, _plc_host, _mqtt
    _state    = state
    _plc_host = plc_host
    _mqtt     = mqtt_publisher

def broadcast(payload: str) -> None:
    """Broadcasts plant data to all connected WebSocket clients."""
    dead = set()
    with _ws_lock:
        for ws in list(_ws_clients):
            try:
                ws.send(payload)
            except Exception:
                dead.add(ws)
        _ws_clients.difference_update(dead)

def _update_alarm_history(alarms: list) -> None:
    """Maintains a rolling log of recent alarms."""
    with _history_lock:
        for alarm in alarms:
            aid = alarm.get("id")
            if aid and not any(a.get("id") == aid for a in _alarm_history[-50:]):
                _alarm_history.append(dict(alarm))
                if len(_alarm_history) > _HISTORY_MAX:
                    _alarm_history.pop(0)

# ── Robust Proxy Logic ────────────────────────────────────────────────────────

def _proxy_get(process: str, endpoint: str):
    """Hits the PLC VM and handles timeouts/encoding gracefully."""
    port = _PLC_HTTP_PORTS.get(process)
    if not port: 
        return None, {"error": f"Unknown process: {process}"}, 404

    url = f"http://{_plc_host}:{port}{endpoint}"
    try:
        # 15s timeout to handle multi-threaded hits on the PLC VM
        with urllib.request.urlopen(url, timeout=15) as r:
            raw_bytes = r.read()
            text_data = raw_bytes.decode("utf-8")
            if endpoint == "/plc/program":
                return text_data, None, 200
            return json.loads(text_data), None, 200
    except Exception as e:
        log.error(f"Proxy GET {url} failed: {e}")
        return None, {"error": str(e)}, 500

def _proxy_post(process: str, endpoint: str, body: dict):
    """Proxies control/upload requests to the PLC VM."""
    port = _PLC_HTTP_PORTS.get(process)
    if not port: return None, {"error": "Invalid process"}, 404

    url = f"http://{_plc_host}:{port}{endpoint}"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8")), None, 200
    except Exception as e:
        return None, {"error": str(e)}, 500

# ── API Routes ────────────────────────────────────────────────────────────────

@app.route("/")
def root():
    return jsonify({"name": "MORBION SCADA Server", "status": "online"})

@app.route("/health")
def health():
    return jsonify({
        "server": "MORBION SCADA v2.0",
        "processes_online": _state.processes_online() if _state else 0,
        "server_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    })

@app.route("/data")
def data_all():
    return jsonify(_state.snapshot())

@app.route("/data/alarms")
def data_alarms():
    snap = _state.snapshot()
    alarms = snap.get("alarms", [])
    with _ack_lock:
        for a in alarms:
            a["acked"] = _alarm_ack_store.get(a.get("id"), {}).get("acked", False)
    return jsonify(alarms)

@app.route("/control", methods=["POST"])
def control():
    body = request.get_json(silent=True) or {}
    process, register, value = body.get("process"), body.get("register"), body.get("value")
    if process not in _PORT_MAP: return jsonify({"ok": False, "error": "Unknown process"}), 400
    try:
        from modbus.client import ModbusClient
        client = ModbusClient(_plc_host, _PORT_MAP[process], timeout=3.0)
        confirmed = client.write_register(register, value)
        return jsonify({"ok": True, "confirmed": confirmed})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── PLC Program Proxy Endpoints ───────────────────────────────────────────────

@app.route("/plc/<process>/program", methods=["GET"])
def plc_get_program(process):
    # Sequential proxying for the HMI tab
    source, err, code = _proxy_get(process, "/plc/program")
    if err: return jsonify(err), code
    status, _, _ = _proxy_get(process, "/plc/status")
    return jsonify({"process": process, "source": source, "status": status or {"loaded":True}})

@app.route("/plc/<process>/variables", methods=["GET"])
def plc_variables(process):
    data, err, code = _proxy_get(process, "/plc/variables")
    return jsonify(data) if data else jsonify(err), code

@app.route("/plc/<process>/program/reload", methods=["POST"])
def plc_reload(process):
    data, err, code = _proxy_post(process, "/plc/program/reload", {})
    return jsonify(data) if data else jsonify(err), code

@app.route("/alarms/ack", methods=["POST"])
def alarms_ack():
    body = request.get_json(silent=True) or {}
    aid = body.get("alarm_id")
    with _ack_lock:
        _alarm_ack_store[aid] = {"acked": True, "at": datetime.utcnow().isoformat()}
    return jsonify({"ok": True})

@app.route("/alarms/history")
def alarms_history():
    with _history_lock: return jsonify(list(_alarm_history))

# ── WebSocket ─────────────────────────────────────────────────────────────────

@sock.route("/ws")
def ws_endpoint(ws):
    with _ws_lock:
        _ws_clients.add(ws)
    try:
        ws.send(json.dumps(_state.snapshot()))
        while True:
            if ws.receive(timeout=60) is None: break
    except: pass
    finally:
        with _ws_lock:
            _ws_clients.discard(ws)
