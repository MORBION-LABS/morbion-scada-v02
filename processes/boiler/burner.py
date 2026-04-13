"""
burner.py — Boiler Burner
Natural gas burner. Converts fuel flow to heat release.
Two firing states: LOW (50% fuel) and HIGH (100% fuel).
Flame detection modeled — loss of flame = fault.

Physics:
    Q_burner = m_fuel × LHV × η_combustion
    m_fuel in kg/s, LHV in kJ/kg → Q in kW

    Flue gas temperature:
        Rises with firing rate
        Drops when burner off
        Excess air dilutes and cools flue gas

    Combustion efficiency:
        η = 1 - (Q_flue_loss / Q_input)
        Decreases with excess air, flue gas temperature
"""

import random
import math


class Burner:

    STATE_OFF  = 0
    STATE_LOW  = 1
    STATE_HIGH = 2

    def __init__(self, config: dict):
        cfg = config["burner"]

        self._fuel_rated_kghr  = cfg["fuel_flow_rated_kghr"]
        self._LHV              = cfg["LHV_kJkg"]
        self._eta              = cfg["eta_combustion"]
        self._tau_ignition     = cfg["tau_ignition"]
        self._tau_modulation   = cfg["tau_modulation"]
        self._flue_high        = cfg["flue_gas_temp_high"]
        self._flue_low         = cfg["flue_gas_temp_low"]
        self._excess_air       = cfg["excess_air_pct"]

        # State
        self.state:                 int   = self.STATE_OFF
        self.firing:                bool  = False
        self.fault:                 bool  = False
        self.fuel_flow_kghr:        float = 0.0
        self.flue_gas_temp_C:       float = 20.0
        self.combustion_efficiency: float = 0.0
        self.Q_burner_kW:           float = 0.0

        self._commanded_state:      int   = self.STATE_OFF
        self._fuel_flow_target:     float = 0.0

    def command(self, state: int):
        """PLC commands burner state: OFF, LOW, HIGH."""
        self._commanded_state = state

    def update(self, dt: float, state):
        if self.fault:
            self._write_state(state)
            return

        # Determine fuel flow target from commanded state
        if self._commanded_state == self.STATE_OFF:
            self._fuel_flow_target = 0.0
            self.firing            = False
        elif self._commanded_state == self.STATE_LOW:
            self._fuel_flow_target = self._fuel_rated_kghr * 0.5
            self.firing            = True
        elif self._commanded_state == self.STATE_HIGH:
            self._fuel_flow_target = self._fuel_rated_kghr
            self.firing            = True

        self.state = self._commanded_state

        # First order lag on fuel flow (valve response)
        tau = self._tau_ignition if self.state != self.STATE_OFF else self._tau_modulation
        error = self._fuel_flow_target - self.fuel_flow_kghr
        self.fuel_flow_kghr += (error / tau) * dt
        self.fuel_flow_kghr  = max(0.0, self.fuel_flow_kghr)

        # Heat release
        fuel_kgs         = self.fuel_flow_kghr / 3600.0
        self.Q_burner_kW = fuel_kgs * self._LHV * self._eta

        # Flue gas temperature — rises with firing rate
        firing_ratio = self.fuel_flow_kghr / self._fuel_rated_kghr if self._fuel_rated_kghr > 0 else 0.0
        flue_target  = (self._flue_low + (self._flue_high - self._flue_low) * firing_ratio
                        if self.firing else 20.0)
        self.flue_gas_temp_C += ((flue_target - self.flue_gas_temp_C) / 30.0) * dt
        self.flue_gas_temp_C += random.gauss(0, 0.5)

        # Combustion efficiency
        if self.firing and self.fuel_flow_kghr > 1.0:
            flue_loss_pct        = 0.005 * self.flue_gas_temp_C + 0.001 * self._excess_air
            self.combustion_efficiency = max(0.0, min(100.0, (1.0 - flue_loss_pct) * 100.0))
        else:
            self.combustion_efficiency = 0.0

        self._write_state(state)

    def _write_state(self, state):
        with state:
            state.burner_state          = self.state
            state.burner_firing         = self.firing
            state.burner_fault          = self.fault
            state.fuel_flow_kghr        = self.fuel_flow_kghr
            state.flue_gas_temp_C       = self.flue_gas_temp_C
            state.combustion_efficiency = self.combustion_efficiency
            state.Q_burner_kW           = self.Q_burner_kW