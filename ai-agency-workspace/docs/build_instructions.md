# Build Instructions

## Stage 1: The Post Office (Linode)
1. Provision a lightweight Ubuntu instance on Linode.
2. Secure the server (UFW firewall, SSH keys only).
3. Install and configure Eclipse Mosquitto (MQTT Broker).
4. Configure username/password authentication for the MQTT broker (do not leave open to the public).
5. Open port 1883 (or 8883 for TLS) in the Linode firewall.

## Stage 2: Local Scaffolding
1. Create root directory: `ai-agency-workspace`.
2. Initialize sub-directories:
   - `/hq-backend` (Python FastApi / Orchestrator)
   - `/hq-frontend` (React/Tailwind UI)
   - `/branch-daemon` (Lightweight Python worker script)
3. Initialize Git repository.

## Stage 3: The Antigravity Bootstrap
1. Use local `antigravity`, Codex, and Claude Code to scaffold the `branch-daemon`.
2. Write the MQTT listener script in the `branch-daemon` directory.
3. Test connection to the Linode server.

## Stage 4: Execution Loop
1. Scaffold the CLI execution bridge in the `branch-daemon`.
2. Pass a hardcoded Caveman prompt through the Linode broker to the daemon.
3. Verify the daemon successfully triggers Claude/Cursor locally and reports back.