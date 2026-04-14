"""
test_communication.py — MORBION Process Monitor
MORBION SCADA v02

Real-time CLI monitor using Typer and Rich.
Reads live Modbus registers from all four processes.
Decodes and displays in engineering units.

KEY FIX FROM v01:
  Register decode was wrong — boiler and pipeline used
  incorrect offsets for several tags.
  v02 uses explicit register maps matching modbus_server.py exactly.

Usage:
    python3 test_communication.py monitor
    python3 test_communication.py monitor --interval 1
    python3 test_communication.py status
    python3 test_communication.py test
"""

import os
import sys
import socket
import struct
import time
from datetime import datetime
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table   import Table
from rich.live    import Live
from rich.panel   import Panel
from rich.text    import Text

app     = typer.Typer(help="MORBION v02 Process Monitor")
console = Console()


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def read_registers(host: str, port: int,
                   start: int, count: int) -> Optional[list]:
    """Read holding registers via Modbus TCP. Returns None on failure."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((host, port))

        pdu     = struct.pack('>BHH', 0x03, start, count)
        request = struct.pack('>HHHB', 1, 0, 1 + len(pdu), 1) + pdu
        s.sendall(request)

        response = s.recv(512)
        s.close()

        if len(response) < 9:
            return None

        byte_count = response[8]
        expected   = byte_count // 2
        registers  = list(struct.unpack(
            f'>{expected}H', response[9:9 + byte_count]))
        return registers

    except Exception:
        return None


def decode_pumping_station(regs: list) -> dict:
    """Decode pumping station registers to engineering units."""
    return {
        "tank_level_pct":         regs[0]  / 10.0,
        "tank_volume_m3":         regs[1]  / 10.0,
        "pump_speed_rpm":         regs[2],
        "pump_flow_m3hr":         regs[3]  / 10.0,
        "discharge_pressure_bar": regs[4]  / 100.0,
        "pump_current_A":         regs[5]  / 10.0,
        "pump_power_kW":          regs[6]  / 10.0,
        "pump_running":           bool(regs[7]),
        "inlet_valve_pos_pct":    regs[8]  / 10.0,
        "outlet_valve_pos_pct":   regs[9]  / 10.0,
        "demand_flow_m3hr":       regs[10] / 10.0,
        "net_flow_m3hr":          regs[11] / 10.0,
        "pump_starts_today":      regs[12],
        "level_sensor_mm":        regs[13],
        "fault_code":             regs[14],
    }


def decode_heat_exchanger(regs: list) -> dict:
    """Decode heat exchanger registers to engineering units."""
    return {
        "T_hot_in_C":            regs[0]  / 10.0,
        "T_hot_out_C":           regs[1]  / 10.0,
        "T_cold_in_C":           regs[2]  / 10.0,
        "T_cold_out_C":          regs[3]  / 10.0,
        "flow_hot_lpm":          regs[4]  / 10.0,
        "flow_cold_lpm":         regs[5]  / 10.0,
        "pressure_hot_in_bar":   regs[6]  / 100.0,
        "pressure_hot_out_bar":  regs[7]  / 100.0,
        "pressure_cold_in_bar":  regs[8]  / 100.0,
        "pressure_cold_out_bar": regs[9]  / 100.0,
        "Q_duty_kW":             regs[10],
        "efficiency_pct":        regs[11] / 10.0,
        "hot_pump_speed_rpm":    regs[12],
        "cold_pump_speed_rpm":   regs[13],
        "hot_valve_pos_pct":     regs[14] / 10.0,
        "cold_valve_pos_pct":    regs[15] / 10.0,
        "fault_code":            regs[16],
    }


def decode_boiler(regs: list) -> dict:
    """Decode boiler registers to engineering units."""
    burner_map = {0: "OFF", 1: "LOW", 2: "HIGH"}
    return {
        "drum_pressure_bar":     regs[0]  / 100.0,
        "drum_temp_C":           regs[1]  / 10.0,
        "drum_level_pct":        regs[2]  / 10.0,
        "steam_flow_kghr":       regs[3]  / 10.0,
        "feedwater_flow_kghr":   regs[4]  / 10.0,
        "fuel_flow_kghr":        regs[5]  / 10.0,
        "burner_state":          burner_map.get(regs[6], "?"),
        "fw_pump_speed_rpm":     regs[7],
        "steam_valve_pos_pct":   regs[8]  / 10.0,
        "fw_valve_pos_pct":      regs[9]  / 10.0,
        "blowdown_valve_pos_pct":regs[10] / 10.0,
        "flue_gas_temp_C":       regs[11] / 10.0,
        "combustion_eff_pct":    regs[12] / 10.0,
        "Q_burner_kW":           regs[13],
        "fault_code":            regs[14],
    }


def decode_pipeline(regs: list) -> dict:
    """Decode pipeline registers to engineering units."""
    fault_map = {0: "OK", 1: "DUTY", 2: "BOTH", 3: "OVERPRESSURE"}
    return {
        "inlet_pressure_bar":    regs[0]  / 100.0,
        "outlet_pressure_bar":   regs[1]  / 100.0,
        "flow_rate_m3hr":        regs[2]  / 10.0,
        "duty_pump_speed_rpm":   regs[3],
        "duty_pump_current_A":   regs[4]  / 10.0,
        "duty_pump_running":     bool(regs[5]),
        "standby_pump_speed_rpm":regs[6],
        "standby_pump_running":  bool(regs[7]),
        "inlet_valve_pos_pct":   regs[8]  / 10.0,
        "outlet_valve_pos_pct":  regs[9]  / 10.0,
        "pump_differential_bar": regs[10] / 100.0,
        "flow_velocity_ms":      regs[11] / 100.0,
        "duty_pump_power_kW":    regs[12],
        "leak_flag":             bool(regs[13]),
        "fault_code":            fault_map.get(regs[14], str(regs[14])),
    }


DECODERS = {
    502: decode_pumping_station,
    506: decode_heat_exchanger,
    507: decode_boiler,
    508: decode_pipeline,
}

REG_COUNTS = {502: 15, 506: 17, 507: 15, 508: 15}


def get_process_data(host: str, port: int) -> dict:
    """Read and decode one process. Returns status + decoded values."""
    count  = REG_COUNTS.get(port, 15)
    regs   = read_registers(host, port, 0, count)

    if regs is None or len(regs) < count:
        return {"status": "OFFLINE"}

    decoder = DECODERS.get(port)
    if decoder is None:
        return {"status": "UNKNOWN"}

    data           = decoder(regs)
    data["status"] = "ONLINE"
    return data


def build_table(processes: list, host: str) -> Table:
    """Build Rich table with live process data."""
    table = Table(
        title       = f"MORBION v02 — {datetime.now().strftime('%H:%M:%S')}",
        show_header = True,
        header_style= "bold cyan",
    )
    table.add_column("Process",     style="cyan",  width=22)
    table.add_column("Status",                     width=10)
    table.add_column("Key Metrics", style="white", min_width=50)

    for name, port in processes:
        data = get_process_data(host, port)

        if data["status"] == "OFFLINE":
            table.add_row(name, "[red]OFFLINE[/red]",
                          "[dim]No response[/dim]")
            continue

        if port == 502:
            metrics = (
                f"Tank: {data.get('tank_level_pct', 0):.1f}% | "
                f"Flow: {data.get('pump_flow_m3hr', 0):.1f} m³/hr | "
                f"Pump: {'[green]RUN[/green]' if data.get('pump_running') else '[red]STOP[/red]'} | "
                f"P: {data.get('discharge_pressure_bar', 0):.2f} bar | "
                f"Fault: {int(data.get('fault_code', 0))}"
            )
        elif port == 506:
            metrics = (
                f"T_hot_in: {data.get('T_hot_in_C', 0):.1f}°C | "
                f"T_cold_out: {data.get('T_cold_out_C', 0):.1f}°C | "
                f"Eff: {data.get('efficiency_pct', 0):.1f}% | "
                f"Q: {data.get('Q_duty_kW', 0)} kW | "
                f"Fault: {int(data.get('fault_code', 0))}"
            )
        elif port == 507:
            metrics = (
                f"P: {data.get('drum_pressure_bar', 0):.2f} bar | "
                f"Level: {data.get('drum_level_pct', 0):.1f}% | "
                f"Burner: {data.get('burner_state', 'OFF')} | "
                f"Steam: {data.get('steam_flow_kghr', 0):.0f} kg/hr | "
                f"Fault: {int(data.get('fault_code', 0))}"
            )
        elif port == 508:
            metrics = (
                f"Outlet: {data.get('outlet_pressure_bar', 0):.1f} bar | "
                f"Flow: {data.get('flow_rate_m3hr', 0):.1f} m³/hr | "
                f"Pump: {'[green]RUN[/green]' if data.get('duty_pump_running') else '[red]STOP[/red]'} | "
                f"Leak: {'[red]YES[/red]' if data.get('leak_flag') else '[green]NO[/green]'} | "
                f"Fault: {data.get('fault_code', 'OK')}"
            )
        else:
            metrics = "—"

        table.add_row(name, "[green]ONLINE[/green]", metrics)

    return table


@app.command()
def monitor(
    interval: int  = typer.Option(2,     "--interval", "-i",
                                  help="Update interval in seconds"),
    once:     bool = typer.Option(False,  "--once",     "-1",
                                  help="Run once and exit"),
):
    """Real-time MORBION process monitor."""
    config   = load_config()
    plc_host = config.get("settings", {}).get("plc_host", "127.0.0.1")

    processes = [
        ("Pumping Station", 502),
        ("Heat Exchanger",  506),
        ("Boiler",          507),
        ("Pipeline",        508),
    ]

    console.print(Panel.fit(
        Text("MORBION v02 Process Monitor", justify="center",
             style="bold cyan"),
        border_style="cyan",
    ))

    if once:
        table = build_table(processes, plc_host)
        console.print(table)
        return

    console.print(f"[dim]Polling {plc_host} every {interval}s — Ctrl+C to exit[/dim]\n")

    with Live(console=console, refresh_per_second=2) as live:
        while True:
            try:
                live.update(build_table(processes, plc_host))
                time.sleep(interval)
            except KeyboardInterrupt:
                break


@app.command()
def status():
    """Show current status of all processes."""
    config   = load_config()
    plc_host = config.get("settings", {}).get("plc_host", "127.0.0.1")

    processes = [
        ("Pumping Station", 502),
        ("Heat Exchanger",  506),
        ("Boiler",          507),
        ("Pipeline",        508),
    ]

    console.print("\n[bold cyan]MORBION v02 — Process Status[/bold cyan]\n")

    for name, port in processes:
        regs = read_registers(plc_host, port, 0, 1)
        if regs is not None:
            console.print(f"[green]✓[/green] {name:<22} [green]ONLINE[/green]  "
                          f"port {port}")
        else:
            console.print(f"[red]✗[/red] {name:<22} [red]OFFLINE[/red] "
                          f"port {port}")

    console.print()


@app.command()
def test():
    """Test connectivity to all processes."""
    config   = load_config()
    plc_host = config.get("settings", {}).get("plc_host", "127.0.0.1")

    processes = [
        ("Pumping Station", 502),
        ("Heat Exchanger",  506),
        ("Boiler",          507),
        ("Pipeline",        508),
    ]

    console.print("\n[bold cyan]MORBION v02 — Connectivity Test[/bold cyan]\n")

    all_ok = True
    for name, port in processes:
        count = REG_COUNTS.get(port, 15)
        regs  = read_registers(plc_host, port, 0, count)
        if regs and len(regs) >= count:
            console.print(
                f"[green]✓[/green] {name:<22} port {port}  "
                f"[green]OK[/green]  {count} registers read")
        else:
            console.print(
                f"[red]✗[/red] {name:<22} port {port}  "
                f"[red]FAILED[/red]")
            all_ok = False

    console.print()
    if all_ok:
        console.print("[green]All processes reachable.[/green]")
    else:
        console.print("[red]Some processes unreachable.[/red]")


if __name__ == "__main__":
    app()
