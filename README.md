# MORBION SCADA v02
> **Intelligence. Precision. Vigilance.**

MORBION SCADA v02 is a robust, full-stack Industrial Control System (ICS) simulation environment. It is designed to bridge the gap between theoretical physics-based modeling and practical SCADA/HMI implementation. The system provides an end-to-end data pipeline: from field-level Modbus TCP registers and Structured Text PLC logic to a centralized middleware aggregator and a modern, high-performance Desktop HMI.

---

## 🏗 System Architecture

The platform is architected as a decoupled, modular ecosystem consisting of three primary tiers:

### 1. The Processes (`processes/`)
The "Field Layer." Four independent industrial stations running physics-based simulations. 
*   **Protocol:** Modbus TCP (Data) & Threaded HTTP (PLC Management).
*   **Logic:** IEC 61131-3 Structured Text (ST) runtimes.
*   **Physics:** Real-time modeling of mass/energy balance, affinity laws, and thermodynamics.

### 2. The SCADA Server (`server/`)
The "Middleware Layer." A centralized hub that aggregates data and handles high-level logic.
*   **Aggregator:** Continuous polling of field processes.
*   **Super-Proxy:** Provides atomic JSON snapshots (Source + Status + Variables) for the HMI.
*   **Streaming:** WebSocket interface for real-time telemetry.

### 3. The Desktop Client (`desktop-client/`)
The "Supervisory Layer." A professional PyQt6-based HMI.
*   **Nomenclature:** Strictly full industrial naming (no abbreviations).
*   **Scripting:** Built-in industrial terminal with a Live Tag Watchlist.
*   **IDE:** Non-blocking PLC code editor with syntax highlighting and hot-reloading.

---

## 🚀 Cloning & Installation

### Option A: Complete Stack (Standard)
Recommended for laboratory environments where the entire system is hosted on one network or machine.
```bash
# Clone the full repository
git clone https://github.com/MORBION-LABS/morbion-scada-v02.git
cd morbion-scada-v02
Option B: Modular Checkout (Advanced)
Use this option if you are deploying specific components to dedicated hardware (e.g., deploying the HMI to an operator workstation).
code
Bash
# Initialize modular clone
git clone --filter=blob:none --no-checkout https://github.com/MORBION-LABS/morbion-scada-v02.git
cd morbion-scada-v02

# Set your target component
git sparse-checkout set <processes | server | desktop-client>
git checkout main
🛠 Deployment Sequence
To maintain data integrity and prevent proxy timeouts, initialize the system in the following order:
Field Processes: Deploy to the PLC VM. Use the interactive installer.py to define local network IPs. Start via manager.py.
SCADA Server: Deploy to the Backend VM. Use installer.py to point the server to the PLC VM's IP address. Start via main.py.
Desktop HMI: Install on the workstation. Use installer.py to point the client to the SCADA Server's IP address. Start via main.py.
🏥 Global Troubleshooting
Symptom	Probable Cause	Corrective Action
HMI Gauges show "-"	Aggregator Downtime	Verify SCADA Server is running and reachable via ping.
PLC Tab remains blank	Threading Deadlock	Ensure the PLC VM is running the ThreadingHTTPServer fix in shared/plc_http.py.
Process fails to start	Socket Binding Error	Port is likely held by a zombie process. Run sudo pkill -9 python3.
HMI closes on command	Memory Violation	Ensure the Desktop Client is using Signal/Slot architecture for thread-to-UI communication.
Command Logic Error	Naming Ambiguity	Use full process names (e.g., pumping_station) instead of aliases (e.g., ps).
⚖ License
MORBION Labs Industrial Framework. Proprietary Simulation Environment. Designed for research and educational purposes.
