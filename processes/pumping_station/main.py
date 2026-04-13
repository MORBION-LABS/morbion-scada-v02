"""
main.py — Pumping Station Entry Point
MORBION SCADA v02

KEY CHANGES FROM v01:
  - write_queue: FC06 writes from Modbus server are queued here
  - apply_operator_writes(): dequeued at start of every scan cycle
  - PLCRuntime replaces hardcoded PLC Python logic
  - ST program runs every scan with actual dt
  - Equipment commanded via ProcessState command fields
    pump_running, inlet_valve_open, outlet_valve_pos_pct
    which main.py applies to equipment objects
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
from pump             import Pump
from tank             import Tank
from inlet_valve      import InletValve
from outlet_valve     import OutletValve
from flow_meter       import FlowMeter
from level_sensor     import LevelSensor
from pressure_sensor  import PressureSensor
from modbus_server    import ModbusServer
from plc_runtime      import PLCRuntime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("pumping_station")

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATE_PATH  = os.path.join(BASE_DIR, "process_state.json")


def load_config() -> dict:
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def apply_operator_writes(write_queue, queue_lock, state, pump,
                          inlet_valve, outlet_valve):
    """
    Dequeue all pending operator writes and apply them.
    Called at the START of every scan cycle — before physics, before PLC.
    This guarantees operator commands take effect within one scan (100ms).

    Register map for pumping station:
        0  tank_level_pct     × 10  — inject sensor value
        2  pump_speed_rpm     × 1   — set pump speed
        3  pump_flow_m3hr     × 10  — inject flow sensor
        4  discharge_pressure × 100 — inject pressure sensor
        7  pump_running       0/1   — force pump state
        8  inlet_valve_pos    × 10  — force inlet valve
        9  outlet_valve_pos   × 10  — force outlet valve
        14 fault_code         raw   — operator reset (write 0)
    """
    with queue_lock:
        pending = list(write_queue)
        write_queue.clear()

    for reg, val in pending:
        log.info("Applying operator write: reg=%d val=%d", reg, val)
        try:
            if reg == 0:
                # Inject tank level sensor reading
                with state:
                    state.tank_level_pct   = val / 10.0
                    state.level_sensor_pct = val / 10.0

            elif reg == 2:
                # Set pump speed setpoint
                pump.set_speed(float(val))

            elif reg == 3:
                # Inject flow meter reading
                with state:
                    state.flow_m3hr = val / 10.0

            elif reg == 4:
                # Inject pressure sensor reading
                with state:
                    state.discharge_pressure_bar = val / 100.0

            elif reg == 7:
                # Force pump running state
                if val == 1:
                    pump.start()
                    pump.set_speed(load_config()["pump"]["setpoint_rpm"])
                else:
                    pump.stop()

            elif reg == 8:
                # Force inlet valve position
                pos = val / 10.0
                inlet_valve.set_position(pos)

            elif reg == 9:
                # Force outlet valve position
                pos = val / 10.0
                outlet_valve.set_position(pos)

            elif reg == 14:
                # Operator fault reset — write 0 to clear
                with state:
                    state.fault_code = int(val)

        except Exception as e:
            log.error("Error applying write reg=%d val=%d: %s", reg, val, e)


def apply_plc_commands(state, pump, inlet_valve, outlet_valve):
    """
    Apply PLC output image commands to equipment objects.
    Called AFTER plc_runtime.scan() every cycle.

    The PLC writes command fields into ProcessState.
    This function reads those command fields and drives equipment.
    This is the input/output image separation — PLC sets commands,
    main.py applies them to physical equipment objects.
    """
    with state:
        pump_cmd        = state.pump_running
        inlet_cmd       = state.inlet_valve_open
        outlet_sp       = state.outlet_valve_pos_pct

    # Pump command
    if pump_cmd and not pump.running:
        pump.start()
    elif not pump_cmd and pump.running:
        pump.stop()

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
    log.info("  Pumping Station — Nairobi Water")
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

    # ── Write queue — thread-safe operator command buffer ─────────
    write_queue = deque()
    queue_lock  = Lock()

    def on_modbus_write(register: int, value: int):
        """Called from Modbus server thread on every FC06 write."""
        with queue_lock:
            write_queue.append((register, value))

    # ── Equipment ─────────────────────────────────────────────────
    pump            = Pump(config)
    tank            = Tank(config)
    inlet_valve     = InletValve(config)
    outlet_valve    = OutletValve(config)
    flow_meter      = FlowMeter(config)
    level_sensor    = LevelSensor(config)
    pressure_sensor = PressureSensor(config)

    # ── PLC Runtime ───────────────────────────────────────────────
    plc = PLCRuntime()
    if not plc.status["loaded"]:
        log.error("PLC program failed to load: %s", plc.status["last_error"])
        log.error("Process will run without PLC logic")

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
                              pump, inlet_valve, outlet_valve)

        # 2. Physics update — all equipment
        pump.update(scan_interval,            state)
        tank.update(scan_interval,            state)
        inlet_valve.update(scan_interval,     state)
        outlet_valve.update(scan_interval,    state)
        flow_meter.update(scan_interval,      state)
        level_sensor.update(scan_interval,    state)
        pressure_sensor.update(scan_interval, state)

        # 3. PLC scan — ST interpreter executes plc_program.st
        plc.scan(state, dt=scan_interval)

        # 4. Apply PLC commands to equipment
        apply_plc_commands(state, pump, inlet_valve, outlet_valve)

        # 5. Update Modbus register bank for SCADA poller
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

    pump.stop()
    modbus.stop()
    state.save(STATE_PATH)
    log.info("Pumping station stopped cleanly")
    sys.exit(0)


if __name__ == "__main__":
    main()
