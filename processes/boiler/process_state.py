"""
process_state.py — Boiler Steam Generation
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

    # ── Burner ────────────────────────────────────────────────────
    burner_state:           int   = 0      # 0=OFF 1=LOW 2=HIGH
    burner_firing:          bool  = False
    burner_fault:           bool  = False
    fuel_flow_kghr:         float = 0.0
    flue_gas_temp_C:        float = 20.0
    combustion_efficiency:  float = 0.0
    Q_burner_kW:            float = 0.0

    # ── Drum ──────────────────────────────────────────────────────
    drum_pressure_bar:      float = 0.0
    drum_temp_C:            float = 20.0
    drum_level_pct:         float = 50.0
    steam_flow_kghr:        float = 0.0
    h_fg_kJkg:              float = 2048.0

    # ── Feedwater Pump ────────────────────────────────────────────
    fw_pump_speed_rpm:      float = 0.0
    fw_pump_running:        bool  = False
    fw_pump_fault:          bool  = False
    fw_pump_current_A:      float = 0.0
    feedwater_flow_kghr:    float = 0.0

    # ── Steam Valve ───────────────────────────────────────────────
    steam_valve_pos_pct:    float = 0.0
    steam_valve_cmd_pct:    float = 0.0

    # ── Feedwater Valve ───────────────────────────────────────────
    fw_valve_pos_pct:       float = 0.0
    fw_valve_cmd_pct:       float = 0.0

    # ── Blowdown Valve ────────────────────────────────────────────
    blowdown_valve_pos_pct: float = 0.0
    blowdown_valve_cmd_pct: float = 0.0
    blowdown_flow_kghr:     float = 0.0

    # ── Alarms ────────────────────────────────────────────────────
    alarm_pressure_high:    bool  = False
    alarm_pressure_low:     bool  = False
    alarm_level_low:        bool  = False
    alarm_level_high:       bool  = False
    alarm_flame_failure:    bool  = False
    alarm_pump_fault:       bool  = False

    # ── Process Status ────────────────────────────────────────────
    process_running:        bool  = False
    fault_code:             int   = 0
    operator_reset:      bool  = False 
    # 0=OK 1=LOW_WATER 2=OVERPRESSURE 3=FLAME_FAILURE 4=PUMP_FAULT

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
            "drum_pressure_bar": self.drum_pressure_bar,
            "drum_temp_C":       self.drum_temp_C,
            "drum_level_pct":    self.drum_level_pct,
            "fw_pump_speed_rpm": self.fw_pump_speed_rpm,
            "fault_code":        self.fault_code
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
        self.drum_pressure_bar = data.get("drum_pressure_bar", 0.0)
        self.drum_temp_C       = data.get("drum_temp_C",       20.0)
        self.drum_level_pct    = data.get("drum_level_pct",    50.0)
        self.fw_pump_speed_rpm = data.get("fw_pump_speed_rpm", 0.0)
        self.fault_code        = data.get("fault_code",        0)
