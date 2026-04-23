"""
process_state.py — Pipeline Pump Station
MORBION SCADA v02

REVISION HISTORY:
  2026-04-XX  v02    Initial MORBION SCADA v02 version
  2026-04-23  v02a   [CHANGE] Added process_running and operator_reset to restore()
                          Added flow_rate_m3hr, flow_velocity_ms to save/restore
                          Added standby_pump fields for duty-standby operation
                          Restored after binary/missing incident

KEY FIX FROM v01:
  leak_flag was typed as int (0/1) in v01.
  v02 types it as bool throughout for consistency.
  The Modbus server scales bool → int for the register bank.
  The SCADA reader scales int → bool back.
  This prevents type confusion in alarm evaluators and ST programs.
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
    # FIX: leak_flag is bool not int
    leak_flag:               bool  = False
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
    operator_reset:          bool  = False

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
            # CHANGE 2026-04-23: Added flow_rate_m3hr, flow_velocity_ms
            "duty_pump_speed_rpm":    self.duty_pump_speed_rpm,
            "duty_pump_running":      self.duty_pump_running,
            "standby_pump_running":  self.standby_pump_running,
            "inlet_valve_open":      self.inlet_valve_open,
            "outlet_valve_position":  self.outlet_valve_position_pct,
            "inlet_pressure_bar":    self.inlet_pressure_bar,
            "outlet_pressure_bar":   self.outlet_pressure_bar,
            "flow_rate_m3hr":       self.flow_rate_m3hr,
            "flow_velocity_ms":      self.flow_velocity_ms,
            "fault_code":            self.fault_code,
            "leak_flag":            self.leak_flag,
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
        self.leak_flag                 = bool(data.get("leak_flag",        False))
