"""
server.py — MORBION SCADA Flask Server
MORBION SCADA v02 — SURGICAL REBOOT (ROBUST PROXY)

Standardizes the proxy logic. If the PLC Process is busy, 
the server will now wait up to 15 seconds instead of timing out at 5.
"""
import json
import threading
import logging
import urllib.request
import urllib.error
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from plant_state import PlantState

log = logging.getLogger("server")
app = Flask(__name__)
CORS(app, origins="*")

# State holders
_state, _plc_host = None, ""
_PORT_MAP = {"pumping_station": 502, "heat_exchanger": 506, "boiler": 507, "pipeline": 508}
_PLC_HTTP_PORTS = {"pumping_station": 5020, "heat_exchanger": 5060, "boiler": 5070, "pipeline": 5080}

def init_server(state, plc_host, **kwargs):
    global _state, _plc_host
    _state, _plc_host = state, plc_host

def _proxy_get(process, endpoint):
    """Robust Proxy GET to the PLC VM."""
    port = _PLC_HTTP_PORTS.get(process)
    if not port: return None, {"error": f"No port for {process}"}, 404
    
    url = f"http://{_plc_host}:{port}{endpoint}"
    try:
        # SURGICAL CHANGE: Increased timeout to 15 seconds
        with urllib.request.urlopen(url, timeout=15) as r:
            raw = r.read().decode("utf-8")
            if endpoint == "/plc/program":
                return raw, None, 200 # Return raw text for the code editor
            return json.loads(raw), None, 200
    except Exception as e:
        log.error(f"Proxy error {process}{endpoint}: {e}")
        return None, {"error": str(e)}, 500

@app.route("/health")
def health(): return jsonify({"server": "MORBION v02-ROBUST", "status": "online"})

@app.route("/data")
def data_all(): return jsonify(_state.snapshot())

@app.route("/plc/<process>/program", methods=["GET"])
def plc_get_program(process):
    """Fetches both source and status in one go for the UI."""
    source, err, code = _proxy_get(process, "/plc/program")
    if err: return jsonify(err), code
    status, _, _ = _proxy_get(process, "/plc/status")
    return jsonify({"process": process, "source": source, "status": status or {"loaded": True, "scan_count": 0}})

@app.route("/plc/<process>/variables", methods=["GET"])
def plc_variables(process):
    data, err, code = _proxy_get(process, "/plc/variables")
    return jsonify(data) if data else jsonify(err), code

@app.route("/control", methods=["POST"])
def control():
    body = request.get_json(silent=True) or {}
    process, reg, val = body.get("process"), body.get("register"), body.get("value")
    if process not in _PORT_MAP: return jsonify({"ok": False, "error": "Invalid process"}), 400
    try:
        from modbus.client import ModbusClient
        c = ModbusClient(_plc_host, _PORT_MAP[process], timeout=3.0)
        res = c.write_register(reg, val)
        return jsonify({"ok": True, "confirmed": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# WebSocket listener
from flask_sock import Sock
sock = Sock(app)
@sock.route("/ws")
def ws_endpoint(ws):
    try:
        while True:
            if ws.receive(timeout=10) is None: break
    except: pass
