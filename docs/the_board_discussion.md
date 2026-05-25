# FILE: the_board_discussion.md
# CONTEXT: The Office AI - V1 Architecture Incubation Log
# PROTOCOL: Caveman

## [PHASE 1] THE HEARTBEAT
- **Issue:** Mosquitto MQTT failed (status=13). 
- **Resolution:** Fixed `/etc/mosquitto/passwd` ownership (mosquitto:mosquitto). 
- **State:** Linode broker online. PING/PONG established.

## [PHASE 2] THE CLI BRIDGE
- **Action:** Upgraded `worker_node.py` and `hq_test_dispatch.py` to JSON payloads.
- **Mechanics:** Subprocess executes remote shell commands. Captures stdout/stderr.
- **CTO Appointed:** Codex designated as Linus. `report_to_founders.md` async feedback loop established.

## [PHASE 3A] GOVERNANCE & INTELLIGENCE
- **Security:** Subprocess Jail implemented. Fixed `WORKSPACE_DIR`. 300s execution timeout.
- **Memory:** Librarian Engine (`skill_manager.py`) built. Compresses agent lessons to markdown.
- **Alignment:** Roster locked. Linus (Codex/CTO), Ada (Claude Code/PM), Pixel (Cursor/UI), Grace (Antigravity/QA). `company_joining_instructions.md` seeded as global rules.

## [PHASE 3B] POLICY ENFORCEMENT & GIT SYNC
- **Git Enforcer:** Worker nodes block direct main branch edits. Auto-fetch, auto-branch (`feature/task_{id}`), auto-commit, auto-push to `theofficeai.git`.
- **HQ Router:** Python daemon watches `task_queue/*.json`. Maps tasks (frontend->Pixel, backend->Linus, arch->Ada). Formats Caveman prompt. Publishes to MQTT.

## [PHASE 4] COMMAND CENTER
- **Stack:** Tauri + Vite + React + Tailwind (`hq-frontend`).
- **Features:** Visual infrastructure dashboard. UUID generation. Dynamic metrics.
- **Integration:** Tauri File System Plugin writes dispatch JSON directly to `hq-backend/task_queue/` bypassing network overhead.

## [PHASE 3C] HEADLESS EXECUTION & BOUNCER
- **Vulnerability:** CLI tools (Claude/Gemini) hanging on interactive TTY prompts.
- **Security Guardrails:** Regex Bouncer rejects OS commands (rm, mv, sudo) and unapproved network/package managers (curl, npm).
- **Execution:** Enforced $0.50 max-cost caps. Enabled headless bypass flags (`-p`, `--yolo`). Redirected stdin to DEVNULL to crash on unexpected prompts.

## [V1 IMMORTALIZATION]
- **Front Door:** Ada generated root `README.md`.
- **Vault Locked:** Master `.gitignore` applied to protect `.env` and sandboxes. 
- **Deployment:** V1 infrastructure pushed to GitHub `main`.
- **Testbed Selected:** "StudieBuddy" (VWO2 homework planner) designated for maiden voyage.

## [ACTIVE PIVOT] DYNAMIC WORKSPACES
- **Issue:** Nested Git repositories break tracking. Hardcoded sandbox too rigid.
- **Resolution Path:** 1. Pixel upgrading Tauri UI with directory picker API.
  2. Linus upgrading HQ router/Worker to accept dynamic `workspace_path` with absolute path security validation.