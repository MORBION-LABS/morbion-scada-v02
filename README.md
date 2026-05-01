I hear you. No more conversational text inside the copy-paste area. I will provide the **ROOT REPO README** first, formatted strictly as a single code block so the Markdown structure remains perfect when you paste it into your editor.

### ROOT REPO: `morbion-scada-v02/README.md`

```markdown
# MORBION SCADA v02
> **Intelligence. Precision. Vigilance.**

MORBION SCADA v02 is a professional-grade, full-stack Industrial Control System (ICS) simulation environment. It models four high-fidelity industrial processes using real-world physics, IEC 61131-3 Structured Text (ST) logic, and a robust "Super-Proxy" server architecture. It is designed for cybersecurity research, industrial automation development, and educational laboratory use.

---

## 🏗 System Architecture

The v02 ecosystem is decoupled into three distinct logical layers to simulate a production OT/IT network environment:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MORBION ICS LAB NETWORK                            │
│                                                                             │
│   FIELD LAYER: PLC VIRTUAL MACHINE (<PLC_IP>)                               │
│   ├── PUMPING STATION      :502 (Modbus) :5020 (PLC API)                    │
│   ├── HEAT EXCHANGER       :506 (Modbus) :5060 (PLC API)                    │
│   ├── STEAM BOILER         :507 (Modbus) :5070 (PLC API)                    │
│   └── PETROLEUM PIPELINE   :508 (Modbus) :5080 (PLC API)                    │
│                                  │                                          │
│                                  ▼  Modbus TCP / Threaded HTTP              │
│                                                                             │
│   MIDDLEWARE: SCADA SERVER MACHINE (<SERVER_IP>)                            │
│   ├── MORBION SUPER-PROXY  :5000 (REST API + WebSocket)                     │
│   ├── INFLUXDB HISTORIAN   :8086                                            │
│   └── MOSQUITTO MQTT       :1883                                            │
│                                  │                                          │
│                                  ▼  PyQt Signal/Slot Stream                 │
│                                                                             │
│   SUPERVISORY: OPERATOR WORKSTATION                                         │
│   └── MORBION DESKTOP HMI (Modern Scripting Engine + ST PLC Editor)         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Repository Structure

*   **`processes/`**: The simulation engine. Contains the physics models, Modbus servers, and the Structured Text (ST) interpreters for all four industrial stations.
*   **`server/`**: The central aggregator. Connects to the field layer, evaluates alarms, and provides a unified "Super-Proxy" interface for the HMI.
*   **`desktop-client/`**: The supervisory HMI. A modern PyQt6 application featuring industrial-grade visualization and a crash-proof scripting engine.

---

## 🚀 Cloning & Installation

### Option 1: Full Repository Clone (Standard)
Use this if you are running the entire stack on a single machine or a unified lab network.
```bash
git clone https://github.com/MORBION-LABS/morbion-scada-v02.git
cd morbion-scada-v02
```

### Option 2: Modular Sparse Checkout
Use this to deploy only specific components to dedicated hardware (e.g., only the HMI on a laptop).
```bash
# Initialize sparse clone
git clone --filter=blob:none --no-checkout https://github.com/MORBION-LABS/morbion-scada-v02.git
cd morbion-scada-v02

# Set your desired component: <processes | server | desktop-client>
git sparse-checkout set processes
git checkout main
```

---

## 🛠 Deployment Sequence

To ensure data synchronization and prevent proxy timeouts, initialize the system in this order:

1.  **DEPLOY PROCESSES**: Set up on the "PLC" machine. Run `installer.py` to configure local IPs and start the simulation via `manager.py`.
2.  **DEPLOY SERVER**: Set up on the "Backend" machine. Run `installer.py` to point the server to the PLC VM's IP address.
3.  **DEPLOY CLIENT**: Install on the "Operator" workstation. Run `installer.py` to point the HMI to the SCADA Server's IP address.

---

## 🏥 Global Troubleshooting

| Symptom | Probable Cause | Action |
| :--- | :--- | :--- |
| **HMI Gauges show "-"** | Data Flow Interruption | Verify SCADA Server is running and reachable via `ping <SERVER_IP>`. |
| **PLC Tab hangs on Sync** | Single-Thread Deadlock | Ensure `shared/plc_http.py` is updated to the `ThreadingHTTPServer` version. |
| **Process fails to start** | Port Conflict | Port is likely held by a zombie process. Run `sudo pkill -9 python3`. |
| **HMI closes on command** | Thread Memory Error | Ensure `command_line.py` is using the v02 `print_signal` architecture. |
| **Variables are blank** | Race Condition | Ensure `server/server.py` is using the "Super-Proxy" atomic fetch logic. |

---

## ⚖ License
Industrial Simulation Framework — **MORBION Labs**. Designed for research, educational labs, and security testing.
```
