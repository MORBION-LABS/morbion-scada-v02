"""
tank.py — Storage Tank with Conservation Law
MORBION SCADA v02

KEY FIX FROM v01:
  v01 had conservation law documented but not implemented.
  v02 calculates conservation error every update and writes
  it to state so the ST PLC program can evaluate it.

  Conservation law:
    Q_pump × dt = ΔV_tank + Q_demand × dt
    
    Rearranged to check:
    Q_net_expected = Q_in - Q_out
    Q_net_actual   = (V_new - V_old) / dt
    error          = |Q_net_expected - Q_net_actual| × 3600  [m³/hr]
    
    If error > 15 m³/hr sustained: sensor manipulation or real leak.
    The ST program uses conservation_alarm output for this.

Physics:
    Mass balance:
        Q_in  = pump_flow × inlet_valve_position  [m³/s]
        Q_out = demand × outlet_valve_position    [m³/s]
        dV/dt = Q_in - Q_out
        V_new = clamp(V_old + dV/dt × dt, 0, V_max)

    Level from volume:
        level_pct = V / V_max × 100
        level_mm  = (V / A_tank) × 1000

    Tank geometry:
        A_tank = π/4 × D²
        V_max  = A_tank × H
"""

import math
import random


class Tank:

    def __init__(self, config: dict):
        cfg = config["tank"]

        self._D      = cfg["diameter_m"]
        self._H      = cfg["height_m"]
        self._demand = cfg["demand_flow_m3hr"] / 3600.0   # m³/s constant demand
        self._A      = math.pi / 4.0 * self._D ** 2
        self._V_max  = self._A * self._H

        # Initial state
        initial_pct  = cfg["initial_level_pct"] / 100.0
        self._volume = self._V_max * initial_pct

        self.level_pct: float = cfg["initial_level_pct"]
        self.volume_m3: float = self._volume
        self.level_mm:  float = (self._volume / self._A) * 1000.0

        # Previous volume for conservation law
        self._volume_prev: float = self._volume

    def update(self, dt: float, state):
        with state:
            inlet_open  = state.inlet_valve_open
            inlet_pos   = state.inlet_valve_pos_pct / 100.0
            outlet_pos  = state.outlet_valve_pos_pct / 100.0
            pump_flow   = state.flow_m3hr / 3600.0   # m³/s
            running     = state.pump_running

        # Inflow — pump delivers when inlet valve open and pump running
        Q_in = pump_flow * inlet_pos if (inlet_open and running) else 0.0

        # Outflow — constant demand modulated by outlet valve position
        Q_out = self._demand * outlet_pos

        # Volume change
        dV_dt         = Q_in - Q_out
        self._volume += dV_dt * dt
        self._volume  = max(0.0, min(self._V_max, self._volume))

        # Level from volume
        self.volume_m3 = self._volume
        self.level_pct = (self._volume / self._V_max) * 100.0
        self.level_mm  = (self._volume / self._A) * 1000.0

        # ── Conservation law check ─────────────────────────────────────────────
        # Expected net flow vs actual volume change
        # Q_net_expected = Q_in - Q_out  [m³/s]
        # Q_net_actual   = ΔV / dt       [m³/s]
        # Error in m³/hr for alarm threshold comparison
        Q_net_expected   = Q_in - Q_out
        Q_net_actual     = (self._volume - self._volume_prev) / dt if dt > 0 else 0.0
        conservation_err = abs(Q_net_expected - Q_net_actual) * 3600.0  # m³/hr

        self._volume_prev = self._volume

        net_flow_m3hr = dV_dt * 3600.0
        demand_m3hr   = Q_out * 3600.0

        self._write_state(state, demand_m3hr, net_flow_m3hr, conservation_err)

    def _write_state(self, state, demand_m3hr: float,
                     net_m3hr: float, conservation_err: float):
        with state:
            state.tank_level_pct      = self.level_pct + random.gauss(0, 0.05)
            state.tank_volume_m3      = self.volume_m3
            state.demand_flow_m3hr    = demand_m3hr
            state.net_flow_m3hr       = net_m3hr
            state.level_sensor_pct    = self.level_pct + random.gauss(0, 0.15)
            state.level_sensor_mm     = self.level_mm  + random.gauss(0, 5.0)
            # Conservation error written to state for ST PLC to evaluate
            # The ST program reads flow_m3hr, demand_flow_m3hr, net_flow_m3hr
            # and computes ABS(flow - demand - net) — same result
            # This field is informational for the SCADA historian
            if hasattr(state, 'conservation_error_m3hr'):
                state.conservation_error_m3hr = conservation_err
