"""
shell_and_tube.py — Shell and Tube Heat Exchanger Unit
Counter-flow configuration. Geothermal brine on shell side,
feedwater on tube side.

Governing equations:
    NTU-Effectiveness method
    Q   = ε × C_min × (T_hot_in - T_cold_in)
    ε   = f(NTU, C_r)   counter-flow
    NTU = U × A / C_min
    LMTD = (dT1 - dT2) / ln(dT1/dT2)
"""

import math


class ShellAndTube:
    """
    Counter-flow shell and tube heat exchanger.
    Reads flow and inlet temperatures from ProcessState.
    Calculates outlet temperatures, Q_duty, LMTD, efficiency.
    Writes results back to ProcessState.
    """

    def __init__(self, config: dict):
        cfg = config["heat_exchanger"]

        self._U           = cfg["U"]           # W/m²·K  overall HTC
        self._A           = cfg["A"]           # m²      heat transfer area
        self._Cp_hot      = cfg["Cp_hot"]      # J/kg·K  geothermal brine
        self._Cp_cold     = cfg["Cp_cold"]     # J/kg·K  water
        self._tau         = cfg["tau"]         # s       thermal lag
        self._fouling     = cfg["fouling_factor"]

        # Effective U accounts for fouling
        # 1/U_eff = 1/U + fouling_factor
        self._U_eff = 1.0 / (1.0 / self._U + self._fouling) if self._fouling >= 0 else self._U

        # Dynamic state
        self.T_hot_out:  float = 80.0   # °C  starts at reasonable value
        self.T_cold_out: float = 60.0   # °C
        self.Q_duty_kW:  float = 0.0
        self.LMTD:       float = 0.0
        self.efficiency: float = 0.0

        self._T_hot_out_ss:  float = 80.0
        self._T_cold_out_ss: float = 60.0

    def _effectiveness(self, NTU: float, C_r: float) -> float:
        """Counter-flow heat exchanger effectiveness."""
        if C_r >= 1.0:
            return NTU / (1.0 + NTU)
        exp = math.exp(-NTU * (1.0 - C_r))
        return (1.0 - exp) / (1.0 - C_r * exp)

    def _calc_lmtd(self, T_hi: float, T_ho: float,
                         T_ci: float, T_co: float) -> float:
        """Log mean temperature difference — counter flow."""
        dT1 = T_hi - T_co
        dT2 = T_ho - T_ci
        if dT1 <= 0 or dT2 <= 0:
            return 0.0
        if abs(dT1 - dT2) < 0.001:
            return dT1
        return (dT1 - dT2) / math.log(dT1 / dT2)

    def update(self, dt: float, state):
        """
        Read flows and inlet temps from state.
        Calculate outlet temps and heat duty.
        Write results back to state.
        """
        with state:
            T_hi  = state.T_hot_in
            T_ci  = state.T_cold_in
            m_hot = state.flow_hot  / 60.0   # L/min → m³/s → kg/s (density≈1)
            m_cold= state.flow_cold / 60.0

        if m_hot < 0.01 or m_cold < 0.01:
            # No flow — no heat transfer
            self.Q_duty_kW  = 0.0
            self.LMTD       = 0.0
            self.efficiency = 0.0
            self._write_state(state, T_hi, T_ci)
            return

        C_hot  = m_hot  * self._Cp_hot
        C_cold = m_cold * self._Cp_cold
        C_min  = min(C_hot, C_cold)
        C_max  = max(C_hot, C_cold)
        C_r    = C_min / C_max

        NTU = self._U_eff * self._A / C_min
        eps = self._effectiveness(NTU, C_r)

        Q = eps * C_min * (T_hi - T_ci)

        self._T_hot_out_ss  = T_hi - Q / C_hot
        self._T_cold_out_ss = T_ci + Q / C_cold

        # First order lag toward steady state
        alpha = 1.0 - math.exp(-dt / self._tau)
        self.T_hot_out  += alpha * (self._T_hot_out_ss  - self.T_hot_out)
        self.T_cold_out += alpha * (self._T_cold_out_ss - self.T_cold_out)

        self.Q_duty_kW = Q / 1000.0
        self.LMTD      = self._calc_lmtd(T_hi, self.T_hot_out, T_ci, self.T_cold_out)

        Q_max          = C_min * (T_hi - T_ci)
        self.efficiency= (Q / Q_max * 100.0) if Q_max > 0 else 0.0

        self._write_state(state, T_hi, T_ci)

    def _write_state(self, state, T_hot_in: float, T_cold_in: float):
        with state:
            state.T_hot_in   = T_hot_in
            state.T_cold_in  = T_cold_in
            state.T_hot_out  = self.T_hot_out
            state.T_cold_out = self.T_cold_out
            state.Q_duty_kW  = self.Q_duty_kW
            state.LMTD       = self.LMTD
            state.efficiency = self.efficiency
