MORBION SCADA v02
Intelligence. Precision. Vigilance.
MORBION SCADA v02 is a full-stack Industrial Control System (ICS) simulation environment designed for educational labs, security research, and industrial software development. It features high-fidelity physics-based simulations, a centralized aggregation server, and a modern, professional-grade Desktop HMI.
🏗 System Architecture
The platform is built upon three independent layers:
PROCESSES: Four high-fidelity industrial simulations (Pumping Station, Heat Exchanger, Steam Boiler, and Petroleum Pipeline) running as independent Modbus TCP servers with real-time IEC 61131-3 logic.
SERVER: A robust middleware layer that polls field processes, evaluates alarms, maintains a historian, and provides a unified "Super-Proxy" REST and WebSocket API.
DESKTOP CLIENT: A modern PyQt6 HMI with a side-by-side industrial scripting engine, live tag watchlist, and a full Structured Text (ST) PLC programming interface.
🚀 Installation & Setup
Option A: Full Repository Clone
Ideal for users running the entire stack on a single machine or setting up a complete lab environment.
code
Bash
# Clone the entire project
git clone https://github.com/MORBION-LABS/morbion-scada-v02.git
cd morbion-scada-v02
Option B: Modular Installation (Sparse Checkout)
Ideal for deploying components to different machines (e.g., Client on a workstation, Server on a VM, Processes on a PLC controller).
code
Bash
# Initialize sparse checkout
git clone --filter=blob:none --no-checkout https://github.com/MORBION-LABS/morbion-scada-v02.git
cd morbion-scada-v02

# Choose the component you need
git sparse-checkout set <processes | server | desktop-client>
git checkout
🛠 Deployment Sequence
For system integrity, components should be initialized in this specific order:
DEPLOY PROCESSES: Set up on the "Field" machine. Run the interactive installer.py to set local network parameters and start the manager.
DEPLOY SERVER: Set up on the "Backend" machine. Run installer.py to point the aggregator to the Processes' IP address.
DEPLOY CLIENT: Set up on the "Operator" machine. Run installer.py to point the HMI to the SCADA Server's IP address.
🏥 Global Troubleshooting
Symptom	Probable Cause	Action
"UNKNOWN" Gauges	Data flow interruption.	Verify the SCADA Server is running and reachable via ping.
PLC Tab is Blank	Communication Timeout.	Ensure processes/shared/plc_http.py is using the Threaded server fix.
Terminal Crash	Thread Violation.	Ensure the client uses the Signal/Slot architecture for UI updates.
Command Rejected	Naming Mismatch.	Use full process names (e.g., boiler) instead of abbreviations.
⚖ License
Industrial Simulation Framework — Morbion Labs. Internal use and research only.
