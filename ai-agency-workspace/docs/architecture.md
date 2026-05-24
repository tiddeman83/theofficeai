# System Architecture: Virtual AI Agency

## The Trinity Architecture
The system is divided into three distinct environments to ensure portability, security, and parallel processing.

### 1. The HQ (Central Command)
*   **Environment:** Docker Container (Local or Self-Hosted)
*   **Core Components:**
    *   **React/Tailwind UI:** The 2D Isometric "SimCity" command center.
    *   **Orchestrator Engine (Python):** Manages task breakdowns, AI persona definitions, and skill databases.
    *   **Git Manager:** The only component with external GitHub credentials. Handles merging and releases.
*   **Role:** The "Brain" and "CEO". Defines tasks, reviews PRs, and ships code.

### 2. The Post Office (Message Broker)
*   **Environment:** Linode Cloud Server (Ubuntu)
*   **Core Components:**
    *   **MQTT Broker (Mosquitto):** Lightweight pub/sub messaging system.
*   **Role:** The central router. Holds tasks in queues until Branch Offices come online to claim them.

### 3. The Branch Offices (Worker Daemons)
*   **Environment:** Native Host OS (Desktop, Laptop, etc.)
*   **Core Components:**
    *   **Worker Daemon (Python):** A lightweight background script listening to the Linode MQTT broker.
    *   **CLI Bridge:** Uses OS `subprocess` to trigger local installations of Claude Code, Cursor, Codex, and Gemini CLI.
*   **Role:** The "Developers". Executes the code generation, utilizes the Caveman protocol for token compression, and sends diffs back to HQ.

## Data Flow
1. **CEO (User)** creates a ticket in the HQ UI.
2. **HQ** translates the ticket to a Caveman-compressed prompt and publishes to Linode MQTT.
3. **Branch Office** connects to Linode, claims the task, and fires up a local CLI agent.
4. **Agent** writes code natively, commits to a local branch, and sends the diff back via MQTT.
5. **HQ** runs AI QA. If passed, alerts CEO for manual merge approval.
6. **HQ** pushes the final release to the public GitHub repository.