"""
pressure_sensors.py — Inlet and Outlet Pressure Transmitters
4-20mA pressure transmitters on inlet and outlet headers.
Inlet: 0-10 bar range
Outlet: 0-80 bar range

Outlet pressure derived from pump head and system curve.
Inlet pressure held at nominal supply pressure with variation.
"""

import random
import math


class PressureSensors:

    def __init__(self, config: dict):
        inlet_cfg  = config["pressure_sensors"]["inlet"]
        outlet_cfg = config["pressure_sensors"]["outlet"]
        pipe_cfg   = config["pipeline"]
        op_cfg     = config["operating_conditions"]

        self._inlet_noise  = inlet_cfg["noise_std"]
        self._outlet_noise = outlet_cfg["noise_std"]
        self._rho          = pipe_cfg["specific_gravity"] * 1000.0
        self._f            = pipe_cfg["friction_factor"]
        self._L            = pipe_cfg["length_m"]
        self._D            = pipe_cfg["diameter_m"]
        self._elev         = pipe_cfg["elevation_m"]
        self._inlet_nominal= op_cfg["inlet_pressure_nominal"]

        self.inlet_pressure_bar:  float = self._inlet_nominal
        self.outlet_pressure_bar: float = 0.0
        self.differential_bar:    float = 0.0

    def update(self, dt: float, state):
        with state:
            pump_head_bar = state.duty_pump_head_bar
            flow_m3hr     = state.flow_rate_m3hr
            running       = state.duty_pump_running or state.standby_pump_running

        # Inlet pressure — supply header with small variation
        self.inlet_pressure_bar = (self._inlet_nominal +
                                   random.gauss(0, self._inlet_noise))
        self.inlet_pressure_bar = max(0.0, self.inlet_pressure_bar)

        if running and flow_m3hr > 0:
            flow_m3s  = flow_m3hr / 3600.0
            A_pipe    = math.pi / 4.0 * self._D ** 2
            velocity  = flow_m3s / A_pipe if A_pipe > 0 else 0.0

            # Darcy-Weisbach friction loss
            dP_friction = (self._f * (self._L / self._D) *
                           (self._rho * velocity ** 2 / 2.0)) / 1e5

            # Elevation head loss
            dP_elevation = (self._rho * 9.81 * self._elev) / 1e5

            # Outlet = inlet + pump head - losses
            self.outlet_pressure_bar = (self.inlet_pressure_bar +
                                        pump_head_bar -
                                        dP_friction -
                                        dP_elevation)
        else:
            self.outlet_pressure_bar = self.inlet_pressure_bar

        self.outlet_pressure_bar = max(0.0, self.outlet_pressure_bar +
                                       random.gauss(0, self._outlet_noise))
        self.differential_bar    = max(0.0,
                                       self.outlet_pressure_bar -
                                       self.inlet_pressure_bar)

        with state:
            state.inlet_pressure_bar    = self.inlet_pressure_bar
            state.outlet_pressure_bar   = self.outlet_pressure_bar
            state.pump_differential_bar = self.differential_bar