"""
server/server.py — MORBION SCADA Flask HTTP + WebSocket Layer
MORBION SCADA v02 — REWRITTEN FOR PROXY TIMEOUT FIX
"""

import json
import threading
import logging
import urllib.request
import urllib.error
from datetime import datetime

from flask      import Flask, jsonify, request
from flask_cors import CORS
from flask_sock import Sock
from plant_state import PlantState

log = logging.getLogger("server")

app  = Flask(__name__)
CORS(app, origins="*")
sock = Sock(app)

_state:    PlantState = None
_plc_host: str        = ""
_mqtt:     object     = None

_ws_clients: set            = set()
_ws_lock:    threading.Lock = threading.Lock()

_alarm_ack_store: dict          = {}
_ack_lock:        threading.Lock = threading.Lock()

_alarm_history: list           = []
_history_lock:  threading.Lock = threading.Lock()
_HISTORY_MAX = 200

_PORT_MAP = {
    "pumping_station": 502, "heat_exchanger": 506,
    "boiler": 507, "pipeline": 508,
}

_MAX_REG = {
    "pumping_station": 14, "heat_exchanger": 16,
    "boiler": 14, "pipeline": 14,
}

_PLC_HTTP_PORTS = {
    "pumping_station": 5020, "heat_exchanger": 5060,
    "boiler": 5070, "pipeline": 5080,
}

def init_server(state: PlantState, plc_host: str,
                mqtt_publisher=None, plc_runtimes: dict = None) -> None:
    global _state, _plc_host, _mqtt
    _state    = state
    _plc_host = plc_host
    _mqtt     = mqtt_publisher

def broadcast(payload: str) -> None:
    dead = set()
    with _ws_lock:
        for ws in list(_ws_clients):
            try:
                ws.send(payload)
            except Exception:
                dead.add(ws)
        _ws_clients.difference_update(dead)

def _update_alarm_history(alarms: list) -> None:
    with _history_lock:
        for alarm in alarms:
            aid = alarm.get("id")
            if aid and not any(a.get("id") == aid for a in _alarm_history[-50:]):
                _alarm_history.append(dict(alarm))
                if len(_alarm_history) > _HISTORY_MAX:
                    _alarm_history.pop(0)

# ── PLC Proxy Helper ───────────────────────────────────────────────────────────

def _plc_proxy_get(process: str, endpoint: str):
    port = _PLC_HTTP_PORTS.get(process)
    if port is None:
        return None, {"error": f"No PLC HTTP port for {process}"}, 404

    url = f"http://{_plc_host}:{port}{endpoint}"
    try:
        req  = urllib.request.Request(url, method="GET")
        # FIX: Increased timeout from 5 to 15 for heavy program strings
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            if endpoint == "/plc/program":
                return raw, None, 200
            return json.loads(raw), None, 200
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try: return None, json.loads(body), e.code
        except Exception: return None, {"error": body}, e.code
    except urllib.error.URLError as e:
        return None, {"error": f"Process unreachable: {e.reason}"}, 503
    except Exception as e:
        return None, {"error": str(e)}, 500

def _plc_proxy_post(process: str, endpoint: str, body: dict = None):
    port = _PLC_HTTP_PORTS.get(process)
    if port is None:
        return None, {"error": f"No PLC HTTP port for {process}"}, 404

    url      = f"http://{_plc_host}:{port}{endpoint}"
    payload  = json.dumps(body or {}).encode("utf-8")
    try:
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
        )
        # FIX: Increased timeout from 10 to 20 for uploads
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8")), None, 200
    except urllib.error.HTTPError as e:
        body_raw = e.read().decode("utf-8")
        try: return None, json.loads(body_raw), e.code
        except Exception: return None, {"error": body_raw}, e.code
    except urllib.error.URLError as e:
        return None, {"error": f"Process unreachable: {e.reason}"}, 503
    except Exception as e:
        return None, {"error": str(e)}, 500

# ... (rest of the routes are identical, keeping server.py complete) ...

@app.route("/")
def root():
    return jsonify({"name": "MORBION SCADA Server", "version": "2.0"})

@app.route("/health")
def health():
    snap = _state.snapshot()
    return jsonify({
        "server": "MORBION SCADA v2.0",
        "status": "online",
        "processes_online": _state.processes_online(),
        "poll_rate_ms": snap["poll_rate_ms"],
        "server_time": snap["server_time"],
    })

@app.route("/data")
def data_all():
    return jsonify(_state.snapshot())

@app.route("/data/alarms")
def data_alarms():
    snap   = _state.snapshot()
    alarms = snap.get("alarms", [])
    with _ack_lock:
        annotated = []
        for alarm in alarms:
            a = dict(alarm)
            ack = _alarm_ack_store.get(a.get("id", ""), {})
            a["acked"] = ack.get("acked", False)
            annotated.append(a)
    return jsonify(annotated)

@app.route("/data/<process>")
def data_process(process: str):
    if process not in _PORT_MAP:
        return jsonify({"error": f"Unknown process '{process}'"}), 404
    return jsonify(_state.snapshot().get(process, {}))

@app.route("/control", methods=["POST"])
def control():
    body = request.get_json(silent=True) or {}
    process, register, value = body.get("process"), body.get("register"), body.get("value")
    if process not in _PORT_MAP: return jsonify({"ok": False, "error": "Unknown process"}), 400
    port = _PORT_MAP[process]
    try:
        from modbus.client import ModbusClient
        client = ModbusClient(_plc_host, port, timeout=3.0)
        confirmed = client.write_register(register, value)
        return jsonify({"ok": True, "confirmed": confirmed})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/alarms/ack", methods=["POST"])
def alarms_ack():
    body = request.get_json(silent=True) or {}
    alarm_id, operator = body.get("alarm_id", ""), body.get("operator", "OPERATOR")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    with _ack_lock:
        _alarm_ack_store[alarm_id] = {"acked": True, "acked_at": now, "acked_by": operator}
    return jsonify({"ok": True})

@app.route("/alarms/history")
def alarms_history():
    with _history_lock: return jsonify(list(_alarm_history))

@app.route("/plc/<process>/program", methods=["GET"])
def plc_get_program(process: str):
    source, err, code = _plc_proxy_get(process, "/plc/program")
    if err: return jsonify(err), code
    status, _, _ = _plc_proxy_get(process, "/plc/status")
    return jsonify({"process": process, "source": source, "status": status or {}})

@app.route("/plc/<process>/program", methods=["POST"])
def plc_upload_program(process: str):
    body = request.get_json(silent=True) or {}
    data, err, code = _plc_proxy_post(process, "/plc/program", {"source": body.get("source", "")})
    if err: return jsonify(err), code
    return jsonify(data)

@app.route("/plc/<process>/program/reload", methods=["POST"])
def plc_reload_program(process: str):
    data, err, code = _plc_proxy_post(process, "/plc/program/reload")
    if err: return jsonify(err), code
    return jsonify(data)

@app.route("/plc/<process>/status", methods=["GET"])
def plc_status(process: str):
    data, err, code = _plc_proxy_get(process, "/plc/status")
    if err: return jsonify(err), code
    return jsonify({"process": process, "status": data})

@app.route("/plc/<process>/variables", methods=["GET"])
def plc_variables(process: str):
    data, err, code = _plc_proxy_get(process, "/plc/variables")
    if err: return jsonify(err), code
    return jsonify({"process": process, "variables": data})

@sock.route("/ws")
def ws_endpoint(ws):
    with _ws_lock: _ws_clients.add(ws)
    try:
        ws.send(json.dumps(_state.snapshot()))
        while True:
            if ws.receive(timeout=60) is None: break
    except Exception: pass
    finally:
        with _ws_lock: _ws_clients.discard(ws)
