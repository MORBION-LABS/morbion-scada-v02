"""
modbus_server.py — Boiler Modbus TCP Server
MORBION SCADA v02

Pure socket implementation. No pymodbus.
FC06 writes trigger write_callback immediately — operator control works.

Register Map:
    40001  drum_pressure        bar × 100
    40002  drum_temp            °C × 10
    40003  drum_level           % × 10
    40004  steam_flow           kg/hr × 10
    40005  feedwater_flow       kg/hr × 10
    40006  fuel_flow            kg/hr × 10
    40007  burner_state         0=OFF 1=LOW 2=HIGH
    40008  fw_pump_speed        RPM
    40009  steam_valve_pos      % × 10
    40010  feedwater_valve_pos  % × 10
    40011  blowdown_valve_pos   % × 10
    40012  flue_gas_temp        °C × 10
    40013  combustion_efficiency % × 10
    40014  Q_burner_kW          kW
    40015  fault_code           0=OK 1=LOW_WATER 2=OVERPRESSURE
                                3=FLAME_FAILURE 4=PUMP_FAULT
"""

import socket
import struct
import threading
import logging
from typing import Callable, Optional

log = logging.getLogger("modbus_server.boiler")


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
                0:  self._scale(state.drum_pressure_bar,      100.0),
                1:  self._scale(state.drum_temp_C,             10.0),
                2:  self._scale(state.drum_level_pct,          10.0),
                3:  self._scale(state.steam_flow_kghr,         10.0),
                4:  self._scale(state.feedwater_flow_kghr,     10.0),
                5:  self._scale(state.fuel_flow_kghr,          10.0),
                6:  int(state.burner_state),
                7:  self._scale(state.fw_pump_speed_rpm,        1.0),
                8:  self._scale(state.steam_valve_pos_pct,     10.0),
                9:  self._scale(state.fw_valve_pos_pct,        10.0),
                10: self._scale(state.blowdown_valve_pos_pct,  10.0),
                11: self._scale(state.flue_gas_temp_C,         10.0),
                12: self._scale(state.combustion_efficiency,   10.0),
                13: self._scale(state.Q_burner_kW,              1.0),
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