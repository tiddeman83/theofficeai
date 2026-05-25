# Development Methodology & Roadmap

## Core Principles
1.  **Caveman First:** All agent-to-agent and agent-to-system communication must run through the Caveman protocol to minimize token bloat. No pleasantries, only data.
2.  **Local Execution, Global Orchestration:** API costs are deferred by utilizing existing subscription CLIs (Claude, Cursor, Codex) running natively on branch machines.
3.  **Human-in-the-Loop:** Agents can write and test, but only the CEO (Human) can merge and release.

## Iterative Build Phases

### Phase 1: The Heartbeat (Infrastructure)
*   Stand up the Linode MQTT Broker.
*   Build a dummy Python HQ script that sends a "Ping".
*   Build a dummy Python Branch script that receives the "Ping" and returns a "Pong".

### Phase 2: The CLI Bridge
*   Upgrade the Branch script to accept a task payload.
*   Implement `subprocess` logic to execute a headless local CLI (e.g., `claude "build this"`).
*   Capture the exit code and file diff, and route it back to HQ.

### Phase 3: The Intelligence Engine (HQ)
*   Build the Python routing logic at HQ.
*   Implement the "Skill Library" (compressing agent learnings via Caveman and injecting them into future system prompts).
*   Implement the internal Git server for code syncing.

### Phase 4: The Command Center
*   Build the React/Tailwind frontend.
*   Implement the 2D landscape visualization (HQ, Post Office, Branch Offices).
*   Wire the UI to the Python HQ backend.

### Version 2: Mature Control Loop
*   Close the return path with `hq_status_listener.py` and a persisted `status_log/` feed.
*   Require explicit workspace targeting from the HQ Command Center.
*   Add QA routing to Kent's dedicated branch topic.
*   Harden Branch Daemon Git lifecycle handling: verify Git workspace, refuse dirty trees, refuse duplicate task branches, restore the original base branch on abort, and report `base_branch` / `file_changes` metadata.
*   Add fast contract tests for router validation and worker security behavior.
