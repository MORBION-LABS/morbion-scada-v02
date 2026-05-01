"""
server.py — MORBION SCADA Flask Server
MORBION SCADA v02 — FULL RECOVERY
"""
import json, threading, logging, urllib.request, urllib.error
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sock import Sock
from plant_state import PlantState

log = logging.getLogger("server")
app = Flask(__name__); CORS(app, origins="*"); sock = Sock(app)

_state, _plc_host = None, ""
_PORT_MAP = {"pumping_station": 502, "heat_exchanger": 506, "boiler": 507, "pipeline": 508}
_PLC_HTTP_PORTS = {"pumping_station": 5020, "heat_exchanger": 5060, "boiler": 5070, "pipeline": 5080}
_ws_clients, _ws_lock = set(), threading.Lock()
_alarm_ack_store, _ack_lock = {}, threading.Lock()
_alarm_history, _history_lock, _HISTORY_MAX = [], threading.Lock(), 200

def init_server(state, plc_host, **kwargs):
    global _state, _plc_host
    _state, _plc_host = state, plc_host

def broadcast(payload):
    dead = set()
    with _ws_lock:
        for ws in list(_ws_clients):
            try: ws.send(payload)
            except: dead.add(ws)
        _ws_clients.difference_update(dead)

def _update_alarm_history(alarms):
    with _history_lock:
        for a in alarms:
            if not any(x.get("id") == a.get("id") for x in _alarm_history[-50:]):
                _alarm_history.append(dict(a))
                if len(_alarm_history) > _HISTORY_MAX: _alarm_history.pop(0)

def _proxy(proc, end):
    port = _PLC_HTTP_PORTS.get(proc)
    if not port: return None, {"error": "Invalid proc"}, 404
    try:
        with urllib.request.urlopen(f"http://{_plc_host}:{port}{end}", timeout=10) as r:
            d = r.read().decode("utf-8")
            return (d if end == "/plc/program" else json.loads(d)), None, 200
    except Exception as e: return None, {"error": str(e)}, 500

@app.route("/health")
def health(): return jsonify({"server": "MORBION-v02-FIXED", "status": "online"})

@app.route("/data")
def data_all(): return jsonify(_state.snapshot())

@app.route("/plc/<process>/program", methods=["GET"])
def plc_get_program(process):
    src, err, code = _proxy(process, "/plc/program")
    if err: return jsonify(err), code
    stat, _, _ = _proxy(process, "/plc/status")
    return jsonify({"process": process, "source": src, "status": stat or {"loaded":True}})

@app.route("/plc/<process>/status", methods=["GET"])
def plc_get_status(process):
    stat, err, code = _proxy(process, "/plc/status")
    return jsonify(stat) if stat else jsonify(err), code

@app.route("/plc/<process>/variables", methods=["GET"])
def plc_variables(process):
    data, err, code = _proxy(process, "/plc/variables")
    return jsonify(data) if data else jsonify(err), code

@app.route("/control", methods=["POST"])
def control():
    body = request.get_json(silent=True) or {}
    p, r, v = body.get("process"), body.get("register"), body.get("value")
    try:
        from modbus.client import ModbusClient
        c = ModbusClient(_plc_host, _PORT_MAP[p], timeout=3.0)
        return jsonify({"ok": True, "confirmed": c.write_register(r, v)})
    except Exception as e: return jsonify({"ok": False, "error": str(e)}), 500

@sock.route("/ws")
def ws_endpoint(ws):
    with _ws_lock: _ws_clients.add(ws)
    try:
        while True:
            if ws.receive(timeout=60) is None: break
    except: pass
    finally:
        with _ws_lock: _ws_clients.discard(ws)
