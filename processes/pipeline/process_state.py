"""
process_state.py — Pipeline Pump Station
Central shared state. All equipment reads from and writes to this.
Live in-memory communication. Persistence handled separately.
Thread-safe via context manager.
"""

import threading
import json
import os
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ProcessState:

    # ── Duty Pump ─────────────────────────────────────────────────
    duty_pump_speed_rpm:     float = 0.0
    duty_pump_running:       bool  = False
    duty_pump_fault:         bool  = False
    duty_pump_current_A:     float = 0.0
    duty_pump_power_kW:      float = 0.0
    duty_pump_head_bar:      float = 0.0

    # ── Standby Pump ──────────────────────────────────────────────
    standby_pump_speed_rpm:  float = 0.0
    standby_pump_running:    bool  = False
    standby_pump_fault:      bool  = False
    standby_pump_current_A:  float = 0.0

    # ── Inlet Valve ───────────────────────────────────────────────
    inlet_valve_open:        bool  = False
    inlet_valve_position:    float = 0.0

    # ── Outlet Valve ──────────────────────────────────────────────
    outlet_valve_position_pct:  float = 0.0
    outlet_valve_commanded_pct: float = 0.0

    # ── Flow Meter ────────────────────────────────────────────────
    flow_rate_m3hr:          float = 0.0
    flow_velocity_ms:        float = 0.0

    # ── Pressure Sensors ──────────────────────────────────────────
    inlet_pressure_bar:      float = 2.0
    outlet_pressure_bar:     float = 0.0
    pump_differential_bar:   float = 0.0

    # ── Leak Detection ────────────────────────────────────────────
    leak_flag:               int   = 0
    flow_balance_error:      float = 0.0

    # ── Alarms ────────────────────────────────────────────────────
    alarm_outlet_high:       bool  = False
    alarm_outlet_low:        bool  = False
    alarm_inlet_low:         bool  = False
    alarm_flow_low:          bool  = False
    alarm_leak:              bool  = False

    # ── Process Status ────────────────────────────────────────────
    process_running:         bool  = False
    fault_code:              int   = 0

    # ── Thread Lock ───────────────────────────────────────────────
    _lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False)

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, *args):
        self._lock.release()

    def save(self, path: str):
        data = {
            "duty_pump_speed_rpm":    self.duty_pump_speed_rpm,
            "inlet_valve_open":       self.inlet_valve_open,
            "outlet_valve_position":  self.outlet_valve_position_pct,
            "inlet_pressure_bar":     self.inlet_pressure_bar,
            "outlet_pressure_bar":    self.outlet_pressure_bar,
            "fault_code":             self.fault_code
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def restore(self, path: str):
        if not os.path.exists(path):
            return
        if os.path.getsize(path) == 0:
            return
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return
        self.duty_pump_speed_rpm       = data.get("duty_pump_speed_rpm",   0.0)
        self.inlet_valve_open          = data.get("inlet_valve_open",      False)
        self.outlet_valve_position_pct = data.get("outlet_valve_position", 0.0)
        self.inlet_pressure_bar        = data.get("inlet_pressure_bar",    2.0)
        self.outlet_pressure_bar       = data.get("outlet_pressure_bar",   0.0)
        self.fault_code                = data.get("fault_code",            0)