"""
main.py — Heat Exchanger Station Entry Point
MORBION SCADA v02

KEY CHANGES FROM v01:
  - write_queue: FC06 writes from Modbus server queued here
  - apply_operator_writes(): dequeued at start of every scan cycle
  - PLCRuntime replaces hardcoded PLC Python logic
  - ST program runs every scan with actual dt
  - apply_plc_commands() drives equipment from PLC output image
"""

import json
import time
import signal
import logging
import sys
import os
from collections import deque
from threading import Lock

from process_state  import ProcessState
from hot_pump       import HotPump
from cold_pump      import ColdPump
from control_valve  import ControlValve
from shell_and_tube import ShellAndTube
from modbus_server  import ModbusServer
from plc_runtime    import PLCRuntime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("heat_exchanger")

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATE_PATH  = os.path.join(BASE_DIR, "process_state.json")


def load_config() -> dict:
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def apply_operator_writes(write_queue, queue_lock, state,
                          hot_pump, cold_pump, hot_valve, cold_valve):
    """
    Dequeue all pending operator writes and apply them.
    Called at the START of every scan cycle.

    Register map for heat exchanger:
        0  T_hot_in        × 10  — inject hot inlet temperature
        1  T_hot_out       × 10  — inject hot outlet temperature
        2  T_cold_in       × 10  — inject cold inlet temperature
        3  T_cold_out      × 10  — inject cold outlet temperature
        12 hot_pump_speed  × 1   — set hot pump speed
        13 cold_pump_speed × 1   — set cold pump speed
        14 hot_valve_pos   × 10  — set hot valve position
        15 cold_valve_pos  × 10  — set cold valve position
        16 fault_code      raw   — operator reset (write 0)
    """
    with queue_lock:
        pending = list(write_queue)
        write_queue.clear()

    for reg, val in pending:
        log.info("Applying operator write: reg=%d val=%d", reg, val)
        try:
            if reg == 0:
                with state:
                    state.T_hot_in = val / 10.0

            elif reg == 1:
                with state:
                    state.T_hot_out = val / 10.0

            elif reg == 2:
                with state:
                    state.T_cold_in = val / 10.0

            elif reg == 3:
                with state:
                    state.T_cold_out = val / 10.0

            elif reg == 12:
                hot_pump.set_speed(float(val))

            elif reg == 13:
                cold_pump.set_speed(float(val))

            elif reg == 14:
                hot_valve.set_position(val / 10.0)

            elif reg == 15:
                cold_valve.set_position(val / 10.0)

            elif reg == 16:
                with state:
                    state.fault_code = int(val)

        except Exception as e:
            log.error("Error applying write reg=%d val=%d: %s", reg, val, e)


def apply_plc_commands(state, hot_pump, cold_pump, hot_valve, cold_valve):
    """
    Apply PLC output image commands to equipment objects.
    Called AFTER plc_runtime.scan() every cycle.
    """
    with state:
        hot_pump_cmd   = state.hot_pump_running
        cold_pump_cmd  = state.cold_pump_running
        hot_valve_cmd  = state.hot_valve_position_pct
        cold_valve_cmd = state.cold_valve_position_pct

    if hot_pump_cmd and not hot_pump.running:
        hot_pump.start()
        hot_pump.set_speed(load_config()["hot_pump"]["setpoint_rpm"])
    elif not hot_pump_cmd and hot_pump.running:
        hot_pump.stop()

    if cold_pump_cmd and not cold_pump.running:
        cold_pump.start()
        cold_pump.set_speed(load_config()["cold_pump"]["setpoint_rpm"])
    elif not cold_pump_cmd and cold_pump.running:
        cold_pump.stop()

    hot_valve.set_position(hot_valve_cmd)
    cold_valve.set_position(cold_valve_cmd)


def main():
    log.info("═" * 60)
    log.info("  MORBION SCADA v02")
    log.info("  Heat Exchanger Station — KenGen Olkaria")
    log.info("═" * 60)

    config        = load_config()
    scan_interval = config["process"]["scan_interval_ms"] / 1000.0
    log.info("Port: %d | Scan: %dms",
             config["process"]["port"],
             config["process"]["scan_interval_ms"])

    # ── State ─────────────────────────────────────────────────────
    state = ProcessState()
    state.restore(STATE_PATH)
    log.info("Process state restored")

    # ── Write queue ───────────────────────────────────────────────
    write_queue = deque()
    queue_lock  = Lock()

    def on_modbus_write(register: int, value: int):
        with queue_lock:
            write_queue.append((register, value))

    # ── Equipment ─────────────────────────────────────────────────
    hot_pump   = HotPump(config)
    cold_pump  = ColdPump(config)
    hot_valve  = ControlValve("hot_valve",  config)
    cold_valve = ControlValve("cold_valve", config)
    exchanger  = ShellAndTube(config)

    # ── PLC Runtime ───────────────────────────────────────────────
    plc = PLCRuntime()
    if not plc.status["loaded"]:
        log.error("PLC program failed to load: %s", plc.status["last_error"])

    # ── Modbus Server ─────────────────────────────────────────────
    modbus = ModbusServer(config, write_callback=on_modbus_write)
    modbus.start()

    # ── Start ─────────────────────────────────────────────────────
    with state:
        state.process_running = True

    log.info("Process started — all equipment initialising")

    # ── Shutdown Handler ──────────────────────────────────────────
    running = [True]

    def shutdown(sig, frame):
        log.info("Shutdown signal received")
        running[0] = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT,  shutdown)

    # ── Scan Loop ─────────────────────────────────────────────────
    last_save = time.time()

    while running[0]:
        t_start = time.time()

        # 1. Apply pending operator writes FIRST
        apply_operator_writes(write_queue, queue_lock, state,
                              hot_pump, cold_pump, hot_valve, cold_valve)

        # 2. Physics update
        hot_pump.update(scan_interval,   state)
        cold_pump.update(scan_interval,  state)
        hot_valve.update(scan_interval)
        cold_valve.update(scan_interval)
        exchanger.update(scan_interval,  state)

        # 3. PLC scan
        plc.scan(state, dt=scan_interval)

        # 4. Apply PLC commands to equipment
        apply_plc_commands(state, hot_pump, cold_pump, hot_valve, cold_valve)

        # 5. Update Modbus register bank
        modbus.update_from_state(state)

        # 6. Periodic state persistence
        if time.time() - last_save > 30:
            state.save(STATE_PATH)
            last_save = time.time()

        # 7. Sleep remainder of scan interval
        elapsed = time.time() - t_start
        time.sleep(max(0.0, scan_interval - elapsed))

    # ── Shutdown ──────────────────────────────────────────────────
    log.info("Stopping process...")
    with state:
        state.process_running = False

    hot_pump.stop()
    cold_pump.stop()
    modbus.stop()
    state.save(STATE_PATH)
    log.info("Heat exchanger station stopped cleanly")
    sys.exit(0)


if __name__ == "__main__":
    main()
