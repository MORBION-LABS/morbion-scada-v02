"""
process_state.py — Heat Exchanger Station
Central shared state. All equipment classes read from and write to this.
Live in-memory communication only. Persistence handled separately.
"""

import threading
import json
import os
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ProcessState:
    """
    Single source of truth for the entire heat exchanger process.
    All equipment owns its section. PLC reads everything.
    Thread-safe via lock.
    """

    # ── Hot Side Pump ─────────────────────────────────────────────
    hot_pump_speed_rpm:   float = 0.0
    hot_pump_running:     bool  = False
    hot_pump_fault:       bool  = False
    hot_pump_current_A:   float = 0.0

    # ── Cold Side Pump ────────────────────────────────────────────
    cold_pump_speed_rpm:  float = 0.0
    cold_pump_running:    bool  = False
    cold_pump_fault:      bool  = False
    cold_pump_current_A:  float = 0.0

    # ── Hot Side Valve ────────────────────────────────────────────
    hot_valve_position_pct:  float = 0.0   # 0-100%
    hot_valve_commanded_pct: float = 0.0

    # ── Cold Side Valve ───────────────────────────────────────────
    cold_valve_position_pct:  float = 0.0
    cold_valve_commanded_pct: float = 0.0

    # ── Heat Exchanger Unit ───────────────────────────────────────
    T_hot_in:    float = 180.0   # °C
    T_hot_out:   float = 0.0     # °C  calculated
    T_cold_in:   float = 25.0    # °C
    T_cold_out:  float = 0.0     # °C  calculated
    flow_hot:    float = 0.0     # L/min
    flow_cold:   float = 0.0     # L/min
    Q_duty_kW:   float = 0.0     # kW
    LMTD:        float = 0.0     # °C
    efficiency:  float = 0.0     # %

    # ── Pressure Sensors ──────────────────────────────────────────
    pressure_hot_in:   float = 0.0   # bar
    pressure_hot_out:  float = 0.0   # bar
    pressure_cold_in:  float = 0.0   # bar
    pressure_cold_out: float = 0.0   # bar

    # ── Modbus Register Cache (raw uint16 values) ─────────────────
    registers: Dict[int, int] = field(default_factory=dict)

    # ── Alarms ────────────────────────────────────────────────────
    alarm_T_hot_out_high:  bool = False
    alarm_T_cold_out_high: bool = False
    alarm_efficiency_low:  bool = False
    alarm_hot_pump_fault:  bool = False
    alarm_cold_pump_fault: bool = False

    # ── Process Status ────────────────────────────────────────────
    process_running: bool  = False
    fault_code:      int   = 0    # 0=OK 1=PUMP_FAULT 2=SENSOR_FAULT 3=OVERTEMP

    # ── Thread Lock ───────────────────────────────────────────────
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def acquire(self):
        self._lock.acquire()

    def release(self):
        self._lock.release()

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, *args):
        self._lock.release()

    # ── Persistence ───────────────────────────────────────────────
    def save(self, path: str):
        """Save state to JSON for restore on next start."""
        data = {
            "hot_pump_speed_rpm":      self.hot_pump_speed_rpm,
            "cold_pump_speed_rpm":     self.cold_pump_speed_rpm,
            "hot_valve_position_pct":  self.hot_valve_position_pct,
            "cold_valve_position_pct": self.cold_valve_position_pct,
            "T_hot_in":                self.T_hot_in,
            "T_cold_in":               self.T_cold_in,
            "fault_code":              self.fault_code
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def restore(self, path: str):
        """Restore state from JSON on startup."""
        if not os.path.exists(path):
            return
        with open(path, 'r') as f:
            data = json.load(f)
        self.hot_pump_speed_rpm      = data.get("hot_pump_speed_rpm",      0.0)
        self.cold_pump_speed_rpm     = data.get("cold_pump_speed_rpm",     0.0)
        self.hot_valve_position_pct  = data.get("hot_valve_position_pct",  0.0)
        self.cold_valve_position_pct = data.get("cold_valve_position_pct", 0.0)
        self.T_hot_in                = data.get("T_hot_in",                180.0)
        self.T_cold_in               = data.get("T_cold_in",               25.0)
        self.fault_code              = data.get("fault_code",              0)