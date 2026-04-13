"""
main.py — Pipeline Pump Station Entry Point
MORBION SCADA v02

KEY CHANGES FROM v01:
  - write_queue: FC06 writes from Modbus server queued here
  - apply_operator_writes(): dequeued at start of every scan cycle
  - PLCRuntime replaces hardcoded PLC Python logic
  - ST program runs every scan with actual dt
  - apply_plc_commands() drives equipment from PLC output image
  - Duty-standby logic lives in ST program with SR latches
"""

import json
import time
import signal
import logging
import sys
import os
from collections import deque
from threading import Lock

from process_state    import ProcessState
from duty_pump        import DutyPump
from standby_pump     import StandbyPump
from inlet_valve      import InletValve
from outlet_valve     import OutletValve
from flow_meter       import FlowMeter
from pressure_sensors import PressureSensors
from modbus_server    import ModbusServer
from plc_runtime      import PLCRuntime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("pipeline")

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATE_PATH  = os.path.join(BASE_DIR, "process_state.json")


def load_config() -> dict:
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def apply_operator_writes(write_queue, queue_lock, state,
                          duty_pump, standby_pump,
                          inlet_valve, outlet_valve):
    """
    Dequeue all pending operator writes and apply them.
    Called at the START of every scan cycle.

    Register map for pipeline:
        0  inlet_pressure   × 100  — inject inlet pressure
        1  outlet_pressure  × 100  — inject outlet pressure
        2  flow_rate        × 10   — inject flow meter
        3  duty_pump_speed  × 1    — set duty pump speed
        5  duty_running     0/1    — force duty pump state
        6  standby_speed    × 1    — set standby pump speed
        7  standby_running  0/1    — force standby pump state
        8  inlet_valve_pos  × 10   — set inlet valve position
        9  outlet_valve_pos × 10   — set outlet valve position
        13 leak_flag        raw    — inject leak flag
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
                    state.inlet_pressure_bar = val / 100.0

            elif reg == 1:
                with state:
                    state.outlet_pressure_bar = val / 100.0

            elif reg == 2:
                with state:
                    state.flow_rate_m3hr = val / 10.0

            elif reg == 3:
                duty_pump.set_speed(float(val))

            elif reg == 5:
                if val == 1:
                    duty_pump.start()
                    duty_pump.set_speed(
                        load_config()["duty_pump"]["setpoint_rpm"])
                else:
                    duty_pump.stop()

            elif reg == 6:
                standby_pump.set_speed(float(val))

            elif reg == 7:
                if val == 1:
                    standby_pump.start()
                    standby_pump.set_speed(
                        load_config()["standby_pump"]["setpoint_rpm"])
                else:
                    standby_pump.stop()

            elif reg == 8:
                inlet_valve.set_position(val / 10.0)

            elif reg == 9:
                outlet_valve.set_position(val / 10.0)

            elif reg == 13:
                with state:
                    state.leak_flag = bool(val)

            elif reg == 14:
                with state:
                    state.fault_code = int(val)

        except Exception as e:
            log.error("Error applying write reg=%d val=%d: %s", reg, val, e)


def apply_plc_commands(state, duty_pump, standby_pump,
                       inlet_valve, outlet_valve):
    """
    Apply PLC output image commands to equipment objects.
    Called AFTER plc_runtime.scan() every cycle.
    """
    config = load_config()

    with state:
        duty_cmd     = state.duty_pump_running
        standby_cmd  = state.standby_pump_running
        inlet_cmd    = state.inlet_valve_open
        outlet_sp    = state.outlet_valve_position_pct

    # Duty pump command
    if duty_cmd and not duty_pump.running:
        duty_pump.start()
        duty_pump.set_speed(config["duty_pump"]["setpoint_rpm"])
    elif not duty_cmd and duty_pump.running:
        duty_pump.stop()

    # Standby pump command
    if standby_cmd and not standby_pump.running:
        standby_pump.start()
        standby_pump.set_speed(config["standby_pump"]["setpoint_rpm"])
    elif not standby_cmd and standby_pump.running:
        standby_pump.stop()

    # Inlet valve command
    if inlet_cmd:
        inlet_valve.open()
    else:
        inlet_valve.close()

    # Outlet valve setpoint
    outlet_valve.set_position(outlet_sp)


def main():
    log.info("═" * 60)
    log.info("  MORBION SCADA v02")
    log.info("  Pipeline Pump Station — Kenya Pipeline Company")
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
    duty_pump    = DutyPump(config)
    standby_pump = StandbyPump(config)
    inlet_valve  = InletValve(config)
    outlet_valve = OutletValve(config)
    flow_meter   = FlowMeter(config)
    pressures    = PressureSensors(config)

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
                              duty_pump, standby_pump,
                              inlet_valve, outlet_valve)

        # 2. Physics update — all equipment
        duty_pump.update(scan_interval,    state)
        standby_pump.update(scan_interval, state)
        inlet_valve.update(scan_interval,  state)
        outlet_valve.update(scan_interval, state)
        flow_meter.update(scan_interval,   state)
        pressures.update(scan_interval,    state)

        # 3. PLC scan — ST interpreter executes plc_program.st
        plc.scan(state, dt=scan_interval)

        # 4. Apply PLC commands to equipment
        apply_plc_commands(state, duty_pump, standby_pump,
                           inlet_valve, outlet_valve)

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

    duty_pump.stop()
    standby_pump.stop()
    modbus.stop()
    state.save(STATE_PATH)
    log.info("Pipeline pump station stopped cleanly")
    sys.exit(0)


if __name__ == "__main__":
    main()
