"""
main.py — Boiler Steam Generation Entry Point
MORBION SCADA v02

KEY CHANGES FROM v01:
  - write_queue: FC06 writes from Modbus server queued here
  - apply_operator_writes(): dequeued at start of every scan cycle
  - PLCRuntime replaces hardcoded PLC Python logic
  - ST program runs every scan with actual dt
  - apply_plc_commands() drives equipment from PLC output image
  - Burner commanded via burner_state field in ProcessState
  - Safety interlocks live in ST program, latched via SR flip-flops
"""

import json
import time
import signal
import logging
import sys
import os
from collections import deque
from threading import Lock

from process_state   import ProcessState
from burner          import Burner
from drum            import Drum
from feedwater_pump  import FeedwaterPump
from steam_valve     import SteamValve
from feedwater_valve import FeedwaterValve
from blowdown_valve  import BlowdownValve
from modbus_server   import ModbusServer
from plc_runtime     import PLCRuntime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("boiler")

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATE_PATH  = os.path.join(BASE_DIR, "process_state.json")


def load_config() -> dict:
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def apply_operator_writes(write_queue, queue_lock, state, burner,
                          fw_pump, steam_valve, fw_valve, blowdown_valve):
    """
    Dequeue all pending operator writes and apply them.
    Called at the START of every scan cycle.

    Register map for boiler:
        0  drum_pressure    × 100  — inject pressure sensor
        1  drum_temp        × 10   — inject temp sensor
        2  drum_level       × 10   — inject level sensor
        3  steam_flow       × 10   — inject steam flow
        6  burner_state     raw    — force burner state 0/1/2
        7  fw_pump_speed    × 1    — set fw pump speed
        8  steam_valve_pos  × 10   — set steam valve position
        9  fw_valve_pos     × 10   — set fw valve position
        10 blowdown_pos     × 10   — set blowdown valve position
        14 fault_code       raw    — operator reset (write 0)
    """
    with queue_lock:
        pending = list(write_queue)
        write_queue.clear()

    for reg, val in pending:
        log.info("Applying operator write: reg=%d val=%d", reg, val)
        try:
            if reg == 0:
                with state:
                    state.drum_pressure_bar = val / 100.0

            elif reg == 1:
                with state:
                    state.drum_temp_C = val / 10.0

            elif reg == 2:
                with state:
                    state.drum_level_pct = val / 10.0

            elif reg == 3:
                with state:
                    state.steam_flow_kghr = val / 10.0

            elif reg == 6:
                # Force burner state — operator override
                burner.command(int(val))
                with state:
                    state.burner_state = int(val)

            elif reg == 7:
                fw_pump.set_speed(float(val))

            elif reg == 8:
                steam_valve.set_position(val / 10.0)

            elif reg == 9:
                fw_valve.set_position(val / 10.0)

            elif reg == 10:
                blowdown_valve.set_position(val / 10.0)

            # REPLACE WITH THIS:
            elif reg == 14:
                with state:
                    state.fault_code     = int(val)
                    # If operator writes 0 — pulse operator_reset for one scan
                    # This triggers SR latch RESET in ST program correctly
                    state.operator_reset = (int(val) == 0)
        except Exception as e:
            log.error("Error applying write reg=%d val=%d: %s", reg, val, e)


def apply_plc_commands(state, burner, fw_pump,
                       steam_valve, fw_valve, blowdown_valve):
    """
    Apply PLC output image commands to equipment objects.
    Called AFTER plc_runtime.scan() every cycle.

    The PLC writes command fields into ProcessState.
    This function reads those and drives physical equipment.
    """
    with state:
        burner_cmd       = state.burner_state
        fw_pump_cmd      = state.fw_pump_running
        steam_valve_cmd  = state.steam_valve_pos_pct
        fw_valve_cmd     = state.fw_valve_pos_pct
        blowdown_cmd     = state.blowdown_valve_pos_pct

    # Burner state command
    burner.command(burner_cmd)

    # Feedwater pump command
    if fw_pump_cmd and not fw_pump.running:
        fw_pump.start()
        fw_pump.set_speed(load_config()["feedwater_pump"]["setpoint_rpm"])
    elif not fw_pump_cmd and fw_pump.running:
        fw_pump.stop()

    # Valve position commands
    steam_valve.set_position(steam_valve_cmd)
    fw_valve.set_position(fw_valve_cmd)
    blowdown_valve.set_position(blowdown_cmd)


def main():
    log.info("═" * 60)
    log.info("  MORBION SCADA v02")
    log.info("  Boiler Steam Generation — EABL/Bidco")
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
    burner         = Burner(config)
    drum           = Drum(config)
    fw_pump        = FeedwaterPump(config)
    steam_valve    = SteamValve(config)
    fw_valve       = FeedwaterValve(config)
    blowdown_valve = BlowdownValve(config)

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
        apply_operator_writes(write_queue, queue_lock, state, burner,
                              fw_pump, steam_valve, fw_valve, blowdown_valve)

        # 2. Physics update — all equipment
        burner.update(scan_interval,         state)
        fw_pump.update(scan_interval,        state)
        steam_valve.update(scan_interval,    state)
        fw_valve.update(scan_interval,       state)
        blowdown_valve.update(scan_interval, state)
        drum.update(scan_interval,           state)

        # 3. PLC scan — ST interpreter executes plc_program.st
        plc.scan(state, dt=scan_interval)
        # Clear operator_reset after one scan — it is a one-shot pulse
        # SR latches in ST program saw it. Now clear it.
        with state:
            if state.operator_reset:
                state.operator_reset = False

        # 4. Apply PLC commands to equipment
        apply_plc_commands(state, burner, fw_pump,
                           steam_valve, fw_valve, blowdown_valve)

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

    burner.command(0)
    fw_pump.stop()
    modbus.stop()
    state.save(STATE_PATH)
    log.info("Boiler steam generation stopped cleanly")
    sys.exit(0)


if __name__ == "__main__":
    main()
