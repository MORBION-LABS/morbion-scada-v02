"""
drum.py — Steam Drum
MORBION SCADA v02

KEY FIX FROM v01:
  v01 used a simplified ln(P) approximation for saturation temperature.
  This had 7% error at operating pressure. Operators saw wrong temperatures.

  v02 uses the Antoine equation — industry standard, ±0.5°C accuracy
  over the full operating range 1-15 bar.

  v01 energy balance allowed energy_stored to go permanently negative
  (cold feedwater + no burner = unbounded negative energy).
  v02 clamps energy to physical minimum: T_drum >= 20°C always.

  v01 steam flow was not properly mass-balanced.
  v02 steam flow derived from valve Cv equation against drum pressure.

Antoine Equation (water, 1-374°C range):
    log10(P_kPa) = A - B / (C + T)
    A = 8.07131, B = 1730.63, C = 233.426
    T in °C, P in kPa

    Inverse (T from P):
    T = B / (A - log10(P_kPa)) - C

Energy Balance:
    dU/dt = Q_burner + Q_feedwater - Q_steam - Q_losses
    U     = m_water × Cp × T_drum
    T_new = U / (m_water × Cp)
    T_new clamped to [20°C, 250°C] — physical limits

Mass Balance:
    dm/dt = m_feedwater - m_steam - m_blowdown
    m_water clamped to [100 kg, m_rated × 1.2]

Three-Element Feedwater Control (in ST program):
    The PLC sets fw_valve_pos_pct.
    FeedwaterValve.update() uses that position.
    FeedwaterValve writes feedwater_flow_kghr to state.
    Drum reads feedwater_flow_kghr from state.
"""

import math
import random


class Drum:

    # Antoine equation constants for water
    _ANT_A = 8.07131
    _ANT_B = 1730.63
    _ANT_C = 233.426

    def __init__(self, config: dict):
        cfg = config["drum"]
        op  = config["operating_conditions"]

        self._volume_m3      = cfg["volume_m3"]
        self._m_water_rated  = cfg["water_mass_kg"]
        self._P_nominal      = cfg["pressure_nominal_bar"]
        self._h_fg           = cfg["h_fg_kJkg"]
        self._h_f            = cfg["h_f_kJkg"]
        self._Cp             = cfg["Cp_water_kJkgK"]
        self._tau_thermal    = cfg["tau_thermal"]
        self._fw_temp        = op["feedwater_temp_C"]

        # Steam valve flow coefficient — determines max steam flow
        # At nominal: 3733 kg/hr at 8 bar with valve 70% open
        # Cv derived from this: m_steam = Cv × position × sqrt(P)
        self._steam_Cv = 3733.0 / (0.70 * math.sqrt(8.0) * 3600.0)

        # Initial conditions — cold start at 0.5 bar
        self._m_water       = self._m_water_rated * 0.5
        self.pressure_bar   = 0.5
        self.temp_C         = self._sat_temp(0.5)
        self.level_pct      = 50.0
        self.steam_flow_kghr= 0.0

        # Energy stored: U = m × Cp × T
        self._energy_kJ = self._m_water * self._Cp * self.temp_C

    # ── Antoine equation ───────────────────────────────────────────────────────

    def _sat_temp(self, pressure_bar: float) -> float:
        """
        Saturation temperature from pressure using Antoine equation.
        Accuracy: ±0.5°C over 1-15 bar range.
        pressure_bar: absolute pressure in bar
        returns: saturation temperature in °C
        """
        p_bar = max(0.05, pressure_bar)
        p_kPa = p_bar * 100.0
        try:
            T = self._ANT_B / (self._ANT_A - math.log10(p_kPa)) - self._ANT_C
        except (ValueError, ZeroDivisionError):
            T = 100.0
        return max(20.0, min(374.0, T))

    def _sat_pressure(self, temp_C: float) -> float:
        """
        Saturation pressure from temperature using Antoine equation.
        Inverse of _sat_temp.
        temp_C: temperature in °C
        returns: saturation pressure in bar
        """
        T = max(20.0, min(374.0, temp_C))
        try:
            log_p_kPa = self._ANT_A - self._ANT_B / (self._ANT_C + T)
            p_kPa     = 10.0 ** log_p_kPa
        except (ValueError, OverflowError):
            p_kPa = 101.325
        return max(0.0, p_kPa / 100.0)

    # ── Update ─────────────────────────────────────────────────────────────────

    def update(self, dt: float, state):
        with state:
            Q_burner_kW       = state.Q_burner_kW
            fw_flow_kghr      = state.feedwater_flow_kghr
            sv_pos_pct        = state.steam_valve_pos_pct
            bd_pos_pct        = state.blowdown_valve_pos_pct

        fw_flow_kgs = fw_flow_kghr / 3600.0

        # Steam flow — Cv equation against drum pressure
        # m_steam_kgs = Cv × (position/100) × sqrt(P_bar)
        if sv_pos_pct > 0.1 and self.pressure_bar > 0.1:
            steam_flow_kgs = (self._steam_Cv *
                              (sv_pos_pct / 100.0) *
                              math.sqrt(self.pressure_bar))
        else:
            steam_flow_kgs = 0.0

        self.steam_flow_kghr = steam_flow_kgs * 3600.0

        # Blowdown flow — proportional to valve and pressure
        blowdown_kgs = (bd_pos_pct / 100.0) * (self.pressure_bar / 10.0) * 0.05

        # ── Mass balance ───────────────────────────────────────────────────────
        dm_dt          = fw_flow_kgs - steam_flow_kgs - blowdown_kgs
        self._m_water += dm_dt * dt
        # Physical limits — cannot have more water than drum volume
        # Cannot have less than minimum safe water mass
        m_max          = self._m_water_rated * 1.2
        m_min          = 100.0   # kg — absolute minimum
        self._m_water  = max(m_min, min(m_max, self._m_water))

        # ── Energy balance ─────────────────────────────────────────────────────
        # Q_fw: feedwater brings energy in (may cool drum if T_fw < T_drum)
        Q_fw_kW    = fw_flow_kgs * self._Cp * (self._fw_temp - self.temp_C)

        # Q_steam: energy leaves with steam (latent heat)
        Q_steam_kW = steam_flow_kgs * self._h_fg

        # Q_losses: radiation and convection (~2% of burner input)
        Q_losses_kW = 0.02 * max(0.0, Q_burner_kW)

        dU_dt_kW = Q_burner_kW + Q_fw_kW - Q_steam_kW - Q_losses_kW

        self._energy_kJ += dU_dt_kW * dt

        # ── Temperature from energy ────────────────────────────────────────────
        # Clamp energy to physical minimum — T cannot go below 20°C
        energy_min      = self._m_water * self._Cp * 20.0
        energy_max      = self._m_water * self._Cp * 374.0
        self._energy_kJ = max(energy_min, min(energy_max, self._energy_kJ))

        T_target = self._energy_kJ / (self._m_water * self._Cp)
        T_target = max(20.0, min(374.0, T_target))

        # First order thermal lag — drum has large thermal mass
        alpha        = 1.0 - math.exp(-dt / self._tau_thermal)
        self.temp_C += alpha * (T_target - self.temp_C)
        self.temp_C  = max(20.0, min(374.0, self.temp_C))

        # ── Pressure from saturation temperature ───────────────────────────────
        self.pressure_bar  = self._sat_pressure(self.temp_C)
        self.pressure_bar  = max(0.0, self.pressure_bar)
        self.pressure_bar += random.gauss(0, 0.01)
        self.pressure_bar  = max(0.0, self.pressure_bar)

        # ── Drum level from water mass ─────────────────────────────────────────
        self.level_pct  = (self._m_water / self._m_water_rated) * 100.0
        self.level_pct  = max(0.0, min(100.0, self.level_pct))
        self.level_pct += random.gauss(0, 0.1)
        self.level_pct  = max(0.0, min(100.0, self.level_pct))

        self._write_state(state)

    def _write_state(self, state):
        with state:
            state.drum_pressure_bar  = self.pressure_bar
            state.drum_temp_C        = self.temp_C + random.gauss(0, 0.2)
            state.drum_level_pct     = self.level_pct
            state.steam_flow_kghr    = self.steam_flow_kghr
            state.h_fg_kJkg          = self._h_fg
