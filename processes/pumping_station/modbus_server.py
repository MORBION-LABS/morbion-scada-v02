"""
modbus_server.py — Pumping Station Modbus TCP Server
MORBION SCADA v02

Pure socket implementation. No pymodbus.
KEY CHANGE FROM v01: FC06 writes now trigger write_callback immediately.
The callback queues the write into the main scan loop via write_queue.
This is the mechanism that makes operator control actually work.

Register Map:
    40001  tank_level_pct        % × 10
    40002  tank_volume_m3        m³ × 10
    40003  pump_speed_rpm        RPM
    40004  pump_flow_m3hr        m³/hr × 10
    40005  discharge_pressure    bar × 100
    40006  pump_current_A        A × 10
    40007  pump_power_kW         kW × 10
    40008  pump_running          0/1
    40009  inlet_valve_pos_pct   % × 10
    40010  outlet_valve_pos_pct  % × 10
    40011  demand_flow_m3hr      m³/hr × 10
    40012  net_flow_m3hr         m³/hr × 10
    40013  pump_starts_today     count
    40014  level_sensor_mm       mm
    40015  fault_code            0=OK 1=HIGH 2=LOW 3=PUMP 4=DRY_RUN
"""

import socket
import struct
import threading
import logging
from typing import Callable, Optional

log = logging.getLogger("modbus_server.pumping_station")


class ModbusServer:
    """
    Modbus TCP server for pumping station.

    write_callback: called immediately on every FC06 write.
                    Signature: callback(register_index: int, value: int)
                    The main loop queues this and applies it next scan.
    """

    REGISTER_COUNT = 64

    def __init__(self, config: dict,
                 write_callback: Optional[Callable[[int, int], None]] = None):
        self._host           = "0.0.0.0"
        self._port           = config["process"]["port"]
        self._uid            = config["process"]["unit_id"]
        self._registers      = [0] * self.REGISTER_COUNT
        self._lock           = threading.Lock()
        self._running        = False
        self._server         = None
        self._write_callback = write_callback

    def update_from_state(self, state):
        """Pull live values from ProcessState. Called every scan cycle."""
        with state:
            regs = {
                0:  self._scale(state.tank_level_pct,          10.0),
                1:  self._scale(state.tank_volume_m3,          10.0),
                2:  self._scale(state.pump_speed_rpm,           1.0),
                3:  self._scale(state.flow_m3hr,               10.0),
                4:  self._scale(state.discharge_pressure_bar, 100.0),
                5:  self._scale(state.pump_current_A,          10.0),
                6:  self._scale(state.pump_power_kW,           10.0),
                7:  int(state.pump_running),
                8:  self._scale(state.inlet_valve_pos_pct,     10.0),
                9:  self._scale(state.outlet_valve_pos_pct,    10.0),
                10: self._scale(state.demand_flow_m3hr,        10.0),
                11: self._scale(state.net_flow_m3hr,           10.0),
                12: int(state.pump_starts_today),
                13: self._scale(state.level_sensor_mm,          1.0),
                14: int(state.fault_code),
            }
        with self._lock:
            for idx, val in regs.items():
                self._registers[idx] = val

    @staticmethod
    def _scale(value: float, factor: float) -> int:
        return max(0, min(65535, int(round(value * factor))))

    def start(self):
        self._running = True
        t = threading.Thread(target=self._serve, daemon=True)
        t.start()
        log.info("Modbus TCP listening on port %d", self._port)

    def stop(self):
        self._running = False
        if self._server:
            try:
                self._server.close()
            except Exception:
                pass

    def _serve(self):
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self._host, self._port))
        self._server.listen(5)
        while self._running:
            try:
                conn, addr = self._server.accept()
                log.info("Client connected: %s", addr)
                t = threading.Thread(
                    target=self._handle_client,
                    args=(conn, addr),
                    daemon=True)
                t.start()
            except OSError:
                break

    def _handle_client(self, conn, addr):
        with conn:
            while self._running:
                try:
                    header = self._recv_exact(conn, 7)
                    if not header:
                        break
                    tid, pid, length, uid = struct.unpack('>HHHB', header)
                    pdu          = self._recv_exact(conn, length - 1)
                    response_pdu = self._process_pdu(pdu)
                    resp_length  = 1 + len(response_pdu)
                    response     = struct.pack('>HHHB', tid, pid,
                                               resp_length, uid)
                    response    += response_pdu
                    conn.sendall(response)
                except (ConnectionError, struct.error, OSError):
                    break
        log.info("Client disconnected: %s", addr)

    def _process_pdu(self, pdu):
        fc = pdu[0]
        if fc == 0x03:
            return self._fc03(pdu)
        elif fc == 0x06:
            return self._fc06(pdu)
        else:
            return bytes([fc | 0x80, 0x01])

    def _fc03(self, pdu):
        addr, count = struct.unpack('>HH', pdu[1:5])
        if addr + count > self.REGISTER_COUNT:
            return bytes([0x83, 0x02])
        with self._lock:
            values = self._registers[addr:addr + count]
        data = struct.pack(f'>{count}H', *values)
        return bytes([0x03, len(data)]) + data

    def _fc06(self, pdu):
        addr, value = struct.unpack('>HH', pdu[1:5])
        if addr >= self.REGISTER_COUNT:
            return bytes([0x86, 0x02])
        with self._lock:
            self._registers[addr] = value
        log.info("FC06 Write: reg %d = %d", addr, value)

        # ── THE KEY v02 CHANGE ────────────────────────────────────────────────
        # Fire callback immediately. Main loop applies on next scan.
        if self._write_callback is not None:
            try:
                self._write_callback(addr, value)
            except Exception as e:
                log.error("write_callback error: %s", e)

        return pdu   # echo back per Modbus spec

    @staticmethod
    def _recv_exact(conn, n):
        data = b''
        while len(data) < n:
            chunk = conn.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Client disconnected")
            data += chunk
        return data