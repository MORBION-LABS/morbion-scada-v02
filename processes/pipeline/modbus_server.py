"""
modbus_server.py — Pipeline Pump Station Modbus TCP Server
MORBION SCADA v02

Pure socket implementation. No pymodbus.
FC06 writes trigger write_callback immediately — operator control works.

Register Map:
    40001  inlet_pressure      bar × 100
    40002  outlet_pressure     bar × 100
    40003  flow_rate           m³/hr × 10
    40004  duty_pump_speed     RPM
    40005  duty_pump_current   A × 10
    40006  duty_pump_running   0/1
    40007  standby_pump_speed  RPM
    40008  standby_pump_running 0/1
    40009  inlet_valve_pos     % × 10
    40010  outlet_valve_pos    % × 10
    40011  pump_differential   bar × 100
    40012  flow_velocity       m/s × 100
    40013  duty_pump_power_kW  kW
    40014  leak_flag           0=OK 1=SUSPECTED
    40015  fault_code          0=OK 1=DUTY 2=BOTH 3=OVERPRESSURE
"""

import socket
import struct
import threading
import logging
from typing import Callable, Optional

log = logging.getLogger("modbus_server.pipeline")


class ModbusServer:

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
                0:  self._scale(state.inlet_pressure_bar,    100.0),
                1:  self._scale(state.outlet_pressure_bar,   100.0),
                2:  self._scale(state.flow_rate_m3hr,         10.0),
                3:  self._scale(state.duty_pump_speed_rpm,     1.0),
                4:  self._scale(state.duty_pump_current_A,    10.0),
                5:  int(state.duty_pump_running),
                6:  self._scale(state.standby_pump_speed_rpm,  1.0),
                7:  int(state.standby_pump_running),
                8:  self._scale(state.inlet_valve_position,   10.0),
                9:  self._scale(state.outlet_valve_position_pct, 10.0),
                10: self._scale(state.pump_differential_bar,  100.0),
                11: self._scale(state.flow_velocity_ms,       100.0),
                12: self._scale(state.duty_pump_power_kW,       1.0),
                13: int(state.leak_flag),
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

        if self._write_callback is not None:
            try:
                self._write_callback(addr, value)
            except Exception as e:
                log.error("write_callback error: %s", e)

        return pdu

    @staticmethod
    def _recv_exact(conn, n):
        data = b''
        while len(data) < n:
            chunk = conn.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Client disconnected")
            data += chunk
        return data