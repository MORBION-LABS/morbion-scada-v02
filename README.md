📜 MORBION SCADA v02 — Master Documentation
code
Markdown
# MORBION SCADA v02
> **Intelligence. Precision. Vigilance.**

MORBION SCADA v02 is a professional-grade, full-stack Industrial Control System (ICS) simulation environment. It models four high-fidelity industrial processes using real-world physics, IEC 61131-3 Structured Text (ST) logic, and a robust "Super-Proxy" server architecture.

---

## 🏗 System Architecture

The v02 ecosystem is decoupled into three distinct VMs/logical layers to simulate a production OT/IT environment:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MORBION ICS LAB NETWORK                            │
│                                                                             │
│   PLC VIRTUAL MACHINE (<PLC_IP>)                                            │
│   ├── PUMPING STATION      :502 (Modbus) :5020 (HTTP API)                   │
│   ├── HEAT EXCHANGER       :506 (Modbus) :5060 (HTTP API)                   │
│   ├── STEAM BOILER         :507 (Modbus) :5070 (HTTP API)                   │
│   └── PETROLEUM PIPELINE   :508 (Modbus) :5080 (HTTP API)                   │
│                                  │                                          │
│                                  ▼  Modbus TCP / Threaded HTTP              │
│                                                                             │
│   SCADA SERVER MACHINE (<SERVER_IP>)                                        │
│   ├── MORBION SUPER-PROXY  :5000 (REST + WebSocket)                         │
│   ├── INFLUXDB HISTORIAN   :8086                                            │
│   └── MOSQUITTO MQTT       :1883                                            │
│                                  │                                          │
│                                  ▼  Signal/Slot WebSocket Stream            │
│                                                                             │
│   OPERATOR WORKSTATION (<CLIENT_IP>)                                        │
│   └── MORBION DESKTOP HMI (Modern Scripting Engine + ST PLC Editor)         │
└─────────────────────────────────────────────────────────────────────────────┘
🚀 Installation Guide
Option 1: Full Repository Clone (Total Stack)
Recommended for local dev or single-machine lab setups.
code
Bash
git clone https://github.com/MORBION-LABS/morbion-scada-v02.git
cd morbion-scada-v02
Option 2: Modular Installation (Sparse Checkout)
Deploy only the component required for a specific machine.
Field Processes (PLC VM):
code
Bash
git clone --filter=blob:none --no-checkout https://github.com/MORBION-LABS/morbion-scada-v02.git
cd morbion-scada-v02
git sparse-checkout set processes
git checkout main
SCADA Server (Aggregation VM):
code
Bash
git sparse-checkout set server
git checkout main
Desktop Client (HMI Workstation):
code
Bash
git sparse-checkout set desktop-client
git checkout main
🛠 Component Setup
1. Processes (Field Layer)
The processes simulate industrial equipment and execute ST logic.
Setup:
code
Bash
cd processes
pip install -r requirements.txt
python3 installer.py  # Interactive: Set PLC and Server IPs
Management:
code
Bash
sudo python3 manager.py start    # Starts all 4 industrial processes
python3 manager.py status        # Verify PIDs and Port health
2. SCADA Server (Middleware Layer)
The v02 Server uses a Super-Proxy model, aggregating Program Source, Status, and Variables into atomic JSON packages.
Setup:
code
Bash
cd server
pip install -r requirements.txt
python3 installer.py  # Point to the PLC VM IP
Start:
code
Bash
python3 main.py
3. Desktop Client (Supervisory Layer)
A modern grade HMI with a built-in Variable Watchlist and Crash-Proof Scripting Engine.
Setup:
code
Bash
cd desktop-client
pip install -r requirements.txt
python installer.py  # Point to the SCADA Server IP
Start:
code
Bash
python main.py
🕹 Industrial Commands (Scripting Engine)
The v02 engine enforces Full Industrial Nomenclature. Abbreviations are prohibited for safety.
Command	Description
read pumping_station	Returns full JSON state of the station.
write boiler pressure 8.5	Writes 8.5 bar to Register 0 with 350ms verification.
plc pipeline status	Checks the health of the ST runtime on the pipeline.
plc boiler source	Fetches the live Structured Text code to the terminal.
cls	Clears the scripting console.
🏥 Troubleshooting
1. HMI Gauges are Blank / "UNKNOWN"
Cause: The SCADA Server is likely offline or misconfigured.
Fix: Ensure server/config.json has the correct plc_host. Restart server/main.py.
2. Processes fail to start (Port Error)
Cause: Zombie processes from a previous crash holding ports 502-508.
Fix: Run sudo pkill -9 python3 on the PLC VM, then run manager.py start.
3. PLC Tab hangs on "Syncing..."
Cause: The PLC process is using a single-threaded server.
Fix: Verify processes/shared/plc_http.py is using ThreadingHTTPServer.
4. Application closes instantly on command
Cause: Threading memory violation (PyQt signal error).
Fix: Ensure widgets/command_line.py uses print_signal.emit() rather than direct UI calls.
🧪 Physics & Conservation Laws
Every process maintains mathematical integrity. Violations are flagged by the SCADA Alarm Engine:
Pumping Station: Flow In - Flow Out = ΔVolume.
Heat Exchanger: Q_hot (brine energy) = Q_cold (water energy).
Steam Boiler: Feedwater Mass = Steam Mass + Blowdown.
Petroleum Pipeline: Pump Curve Expected Flow = Flow Meter Reading.
MORBION Labs v02
The Software meets the Physics.
