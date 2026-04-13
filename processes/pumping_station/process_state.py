"""
process_state.py — Pumping Station
Central shared state. All equipment reads from and writes to this.
Live in-memory communication. Persistence handled separately.
Thread-safe via context manager.
"""

import threading
import json
import os
from dataclasses import dataclass, field


@dataclass
class ProcessState:

    # ── Pump ──────────────────────────────────────────────────────
    pump_speed_rpm:      float = 0.0
    pump_running:        bool  = False
    pump_fault:          bool  = False
    pump_current_A:      float = 0.0
    pump_power_kW:       float = 0.0
    pump_head_m:         float = 0.0
    pump_starts_today:   int   = 0

    # ── Tank ──────────────────────────────────────────────────────
    tank_level_pct:      float = 50.0
    tank_volume_m3:      float = 25.0
    demand_flow_m3hr:    float = 0.0
    net_flow_m3hr:       float = 0.0

    # ── Inlet Valve ───────────────────────────────────────────────
    inlet_valve_open:    bool  = False
    inlet_valve_pos_pct: float = 0.0

    # ── Outlet Valve ──────────────────────────────────────────────
    outlet_valve_pos_pct: float = 0.0
    outlet_valve_cmd_pct: float = 0.0

    # ── Flow Meter ────────────────────────────────────────────────
    flow_m3hr:           float = 0.0

    # ── Pressure Sensor ───────────────────────────────────────────
    discharge_pressure_bar: float = 0.0

    # ── Level Sensor ──────────────────────────────────────────────
    level_sensor_pct:    float = 50.0
    level_sensor_mm:     float = 2000.0

    # ── Alarms ────────────────────────────────────────────────────
    alarm_level_high:    bool  = False
    alarm_level_low:     bool  = False
    alarm_level_low_low: bool  = False
    alarm_no_flow:       bool  = False
    alarm_pressure_high: bool  = False
    alarm_dry_run:       bool  = False

    # ── Process Status ────────────────────────────────────────────
    process_running:     bool  = False
    fault_code:          int   = 0
    # 0=OK 1=HIGH_LEVEL 2=LOW_LEVEL 3=PUMP_FAULT 4=DRY_RUN

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
            "tank_level_pct":       self.tank_level_pct,
            "tank_volume_m3":       self.tank_volume_m3,
            "pump_speed_rpm":       self.pump_speed_rpm,
            "pump_starts_today":    self.pump_starts_today,
            "discharge_pressure_bar": self.discharge_pressure_bar,
            "fault_code":           self.fault_code
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
        self.tank_level_pct         = data.get("tank_level_pct",        50.0)
        self.tank_volume_m3         = data.get("tank_volume_m3",         25.0)
        self.pump_speed_rpm         = data.get("pump_speed_rpm",          0.0)
        self.pump_starts_today      = data.get("pump_starts_today",         0)
        self.discharge_pressure_bar = data.get("discharge_pressure_bar",  0.0)
        self.fault_code             = data.get("fault_code",               0)