"""
shell_and_tube.py — Shell and Tube Heat Exchanger Unit
MORBION SCADA v02

PATCH FROM v01:
  Flow units verified throughout.
  v01 had m_hot = flow_hot / 60.0 treating L/min as if density=1 kg/L.
  This is correct for water (density ~1 kg/L) but the comment said
  "L/min → m³/s → kg/s" which was wrong. The actual conversion is:
    flow_hot is in L/min
    m_hot_kgs = flow_hot_lpm / 1000.0 / 60.0  [L/min → m³/min → m³/s]
    For geothermal brine density ~1050 kg/m³:
    m_hot_kgs = flow_hot_lpm * 1.050 / 60.0 / 1000.0 * 1000.0
              = flow_hot_lpm * 1.050 / 60.0

  For simplicity and consistency with config Cp values:
    hot side: geothermal brine, density 1050 kg/m³, Cp 3800 J/kg·K
    cold side: water, density 1000 kg/m³, Cp 4186 J/kg·K

  v01 fouling_factor was hardcoded to 0.0 in config.
  v02 config patches it to 0.0002 m²·K/W — fouling now active.
  U_eff = 1 / (1/U + fouling) = 1/(1/850 + 0.0002) = 781 W/m²·K

NTU-Effectiveness Method (counter-flow):
    C_hot  = m_hot  × Cp_hot   [W/K]
    C_cold = m_cold × Cp_cold  [W/K]
    C_min  = min(C_hot, C_cold)
    C_max  = max(C_hot, C_cold)
    C_r    = C_min / C_max
    NTU    = U_eff × A / C_min
    ε      = (1 - exp(-NTU(1-Cr))) / (1 - Cr×exp(-NTU(1-Cr)))
    Q      = ε × C_min × (T_hot_in - T_cold_in)
    T_hot_out  = T_hot_in  - Q / C_hot
    T_cold_out = T_cold_in + Q / C_cold
"""

import math
import random


class ShellAndTube:

    def __init__(self, config: dict):
        cfg = config["heat_exchanger"]

        self._U          = cfg["U"]              # W/m²·K overall HTC
        self._A          = cfg["A"]              # m² heat transfer area
        self._Cp_hot     = cfg["Cp_hot"]         # J/kg·K geothermal brine
        self._Cp_cold    = cfg["Cp_cold"]        # J/kg·K water
        self._tau        = cfg["tau"]            # s thermal lag
        self._fouling    = cfg["fouling_factor"] # m²·K/W

        # Effective U with fouling
        # 1/U_eff = 1/U + fouling_factor
        if self._fouling > 0:
            self._U_eff = 1.0 / (1.0 / self._U + self._fouling)
        else:
            self._U_eff = self._U

        # Fluid densities for flow unit conversion
        # Hot side: geothermal brine ~1050 kg/m³
        # Cold side: water ~1000 kg/m³
        self._rho_hot  = 1050.0   # kg/m³
        self._rho_cold = 1000.0   # kg/m³

        # Dynamic state — start at reasonable steady-state values
        self.T_hot_out:  float = 95.0    # °C
        self.T_cold_out: float = 73.0    # °C
        self.Q_duty_kW:  float = 0.0
        self.LMTD:       float = 0.0
        self.efficiency: float = 0.0

        self._T_hot_out_ss:  float = 95.0
        self._T_cold_out_ss: float = 73.0

    def _effectiveness(self, NTU: float, C_r: float) -> float:
        """
        Counter-flow heat exchanger effectiveness.
        ε = (1 - exp(-NTU(1-Cr))) / (1 - Cr×exp(-NTU(1-Cr)))
        Special case C_r = 1: ε = NTU / (1 + NTU)
        """
        if C_r >= 1.0:
            return NTU / (1.0 + NTU)
        exp_term = math.exp(-NTU * (1.0 - C_r))
        denom    = 1.0 - C_r * exp_term
        if abs(denom) < 1e-10:
            return 1.0
        return (1.0 - exp_term) / denom

    def _calc_lmtd(self, T_hi: float, T_ho: float,
                   T_ci: float, T_co: float) -> float:
        """
        Log Mean Temperature Difference — counter-flow configuration.
        dT1 = hot_in  - cold_out  (hot end)
        dT2 = hot_out - cold_in   (cold end)
        LMTD = (dT1 - dT2) / ln(dT1/dT2)
        """
        dT1 = T_hi - T_co
        dT2 = T_ho - T_ci
        if dT1 <= 0.0 or dT2 <= 0.0:
            return 0.0
        if abs(dT1 - dT2) < 0.001:
            return dT1
        try:
            return (dT1 - dT2) / math.log(dT1 / dT2)
        except (ValueError, ZeroDivisionError):
            return 0.0

    def update(self, dt: float, state):
        with state:
            T_hi       = state.T_hot_in
            T_ci       = state.T_cold_in
            flow_hot_lpm  = state.flow_hot    # L/min
            flow_cold_lpm = state.flow_cold   # L/min

        # Convert L/min to kg/s using correct densities
        # m_kgs = flow_lpm × rho_kg_m3 / (1000 L/m³ × 60 s/min)
        m_hot  = flow_hot_lpm  * self._rho_hot  / 60000.0   # kg/s
        m_cold = flow_cold_lpm * self._rho_cold / 60000.0   # kg/s

        if m_hot < 0.001 or m_cold < 0.001:
            # No meaningful flow — no heat transfer
            self.Q_duty_kW  = 0.0
            self.LMTD       = 0.0
            self.efficiency = 0.0
            self._write_state(state, T_hi, T_ci)
            return

        # Heat capacity rates [W/K]
        C_hot  = m_hot  * self._Cp_hot
        C_cold = m_cold * self._Cp_cold
        C_min  = min(C_hot, C_cold)
        C_max  = max(C_hot, C_cold)
        C_r    = C_min / C_max

        # Number of Transfer Units
        NTU = self._U_eff * self._A / C_min

        # Effectiveness
        eps = self._effectiveness(NTU, C_r)

        # Actual heat transfer [W]
        Q_W = eps * C_min * (T_hi - T_ci)
        Q_W = max(0.0, Q_W)

        # Steady-state outlet temperatures
        self._T_hot_out_ss  = T_hi - Q_W / C_hot
        self._T_cold_out_ss = T_ci + Q_W / C_cold

        # First order thermal lag toward steady state
        # alpha = 1 - exp(-dt/tau)
        alpha = 1.0 - math.exp(-dt / self._tau)
        self.T_hot_out  += alpha * (self._T_hot_out_ss  - self.T_hot_out)
        self.T_cold_out += alpha * (self._T_cold_out_ss - self.T_cold_out)

        # Clamp to physical limits
        self.T_hot_out  = max(T_ci, min(T_hi, self.T_hot_out))
        self.T_cold_out = max(T_ci, min(T_hi, self.T_cold_out))

        # Performance metrics
        self.Q_duty_kW = Q_W / 1000.0
        self.LMTD      = self._calc_lmtd(
            T_hi, self.T_hot_out, T_ci, self.T_cold_out)

        Q_max          = C_min * (T_hi - T_ci)
        self.efficiency= (Q_W / Q_max * 100.0) if Q_max > 0 else 0.0
        self.efficiency = max(0.0, min(100.0, self.efficiency))

        self._write_state(state, T_hi, T_ci)

    def _write_state(self, state, T_hot_in: float, T_cold_in: float):
        with state:
            state.T_hot_in   = T_hot_in
            state.T_cold_in  = T_cold_in
            state.T_hot_out  = self.T_hot_out  + random.gauss(0, 0.1)
            state.T_cold_out = self.T_cold_out + random.gauss(0, 0.1)
            state.Q_duty_kW  = self.Q_duty_kW
            state.LMTD       = self.LMTD
            state.efficiency = self.efficiency
