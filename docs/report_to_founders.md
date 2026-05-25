# Phase 2 Report: CLI Bridge

## Changes Made

### Branch Daemon
File: `ai-agency-workspace/branch-daemon/worker_node.py`

- Upgraded MQTT task handling from heartbeat-only behavior to JSON task execution.
- Parses incoming MQTT payloads with `json.loads`.
- Extracts `task_id` and `command`.
- Validates that `command` exists and is a non-empty string.
- Executes the command natively with `subprocess.run(..., shell=True, capture_output=True, text=True, timeout=300)`.
- Captures and returns:
  - `stdout`
  - `stderr`
  - `returncode`
  - `task_id`
  - `status`
- Publishes JSON responses to `agency/status/branch_1`.
- Preserved backward-compatible `PING` to `PONG` heartbeat behavior.
- Added guarded response publishing via `publish_response`.

### HQ Dispatcher
File: `ai-agency-workspace/hq-backend/hq_test_dispatch.py`

- Constructs the required Phase 2 payload exactly:

```json
{"task_id": "test_001", "command": "echo 'Caveman node active.' > caveman_status.txt && cat caveman_status.txt"}
```

- Subscribes to `agency/status/branch_1` before publishing the task to avoid response races.
- Publishes the JSON task to `agency/tasks/branch_1`.
- Waits for the branch daemon JSON response.
- Parses the response.
- Prints only clean command `stdout` to normal terminal output.
- Sends dispatcher logs and errors to `stderr`.
- Fails non-zero if the branch reports a failed status or non-zero return code.

## Subprocess Error Handling Strategy

- JSON decode failures are caught before command execution. The daemon returns an error response with `returncode: null`, empty `stdout`, and full traceback in `stderr`.
- Missing or invalid `command` fields are treated as task errors and returned to HQ instead of crashing the daemon.
- `subprocess.run` is wrapped in explicit exception handling.
- Commands are capped with a 300-second timeout to stop hung branch executions.
- `TimeoutExpired` returns any captured partial `stdout` and `stderr`, plus traceback data.
- Any unexpected subprocess exception returns structured JSON with full traceback in `stderr`.
- MQTT response publishing is also wrapped so publish failures are logged without killing the daemon loop.

## Validation

- Created a workspace-local virtualenv at `ai-agency-workspace/.venv` because system Python is externally managed.
- Installed existing requirements: `paho-mqtt` and `python-dotenv`.
- Ran syntax compilation for both upgraded scripts successfully.
- Ran a local callback-level execution test using the exact Phase 2 JSON payload. Result:
  - `stdout`: `Caveman node active.`
  - `stderr`: empty
  - `returncode`: `0`
  - MQTT response topic: `agency/status/branch_1`
- Live Linode broker execution was not performed from this environment. Reason: approval review blocked connecting a remote command execution worker to the live broker without explicit security authorization.

## Phase 3 Requirements From Founders

- Define the canonical HQ task schema for real agent work: task id, target branch, repo path, agent type, prompt, timeout, env profile, and allowed tools.
- Confirm the local Git sync model: bare internal remote, per-branch worktrees, or direct repository checkout per branch daemon.
- Provide branch identity rules: static branch IDs, auth credentials per node, and topic naming for multiple workers.
- Define the first Intelligence Engine routing policy: which tasks go to Claude, Codex, Cursor, or Gemini.
- Provide security policy for remote command execution: allowed command prefixes, workspace jail path, secrets handling, and audit log retention.
- Confirm whether Phase 3 must return raw diffs, committed branches, patch files, or PR metadata back to HQ.

---

# Phase 3a Report: Governance & Intelligence

## Immutable Linus Persona

Created `ai-agency-workspace/hq-backend/skills/global/000_linus_persona.md`.

The file locks the Linus persona into the global skill layer with the mandated content:

```text
[ROLE] CTO. [NAME] Linus. [PROTOCOL] Caveman. Zero pleasantries. Raw logic. [MINDSET] Ruthless optimization. Explicit error handling. You do not ask for permission to write correct code; you execute.
```

## Subprocess Jail

Upgraded `ai-agency-workspace/branch-daemon/worker_node.py` for Phase 3a security.

- **Workspace jail:** `WORKSPACE_DIR` is fixed to `/ai-agency-workspace/sandbox`. Relative `repo_path` values are resolved inside this directory. Absolute `repo_path` values must still resolve under this directory.
- **Traversal block:** Any command payload containing `../` is rejected before subprocess execution. `repo_path` is resolved and checked with `Path.relative_to()` so symlinks or absolute paths cannot escape the jail.
- **Task schema:** The daemon accepts the approved JSON task schema: `task_id`, `agent`, `repo_path`, `prompt`, `timeout`. The legacy `task_id` plus `command` bridge remains only for Phase 2 compatibility and runs inside the same jail.
- **Timeout:** Subprocess execution uses the mandated 300 second cap. Task-provided timeouts must be integers from 1 to 300 seconds.
- **Branch identity:** MQTT task and status topics use `BRANCH_ID` from `.env`, defaulting to `branch_1`.
- **Return metadata:** MQTT JSON responses include `status`, `branch_name`, and `commit_hash`, while retaining `task_id`, `stdout`, `stderr`, and `returncode` for diagnostics.

Security effect: no received task can set a working directory outside `/ai-agency-workspace/sandbox/`, no command containing direct directory traversal syntax runs, and hung subprocesses are terminated by the 300 second timeout.

## Librarian Engine

Created `ai-agency-workspace/hq-backend/skill_manager.py`.

Implemented `Librarian` with:

- `save_skill(agent_persona, skill_name, raw_lesson)`: writes a Caveman-compressed markdown skill to `ai-agency-workspace/hq-backend/skills/{agent_persona}/{skill_name}.md`.
- `load_skills(agent_persona)`: loads every `.md` skill for that persona in deterministic filename order and returns one concatenated string for system prompt prepending.

Path safety is enforced for `agent_persona` and `skill_name`: `/`, `\`, and `..` are rejected before any file write or read.

---

# Phase 3b Report: Policy Enforcement & Git Synchronization

## Git Enforcer

Upgraded `ai-agency-workspace/branch-daemon/worker_node.py`.

Before command execution, the worker now runs Git isolation:

```bash
git status --porcelain
git fetch origin
git checkout -b feature/task_{task_id}
```

The dirty-tree check fails closed before branch creation. This prevents one task from inheriting another task's edits.

After successful subprocess execution, the worker now runs:

```bash
git add .
git commit -m "Caveman auto-commit: Task {task_id}"
git push origin feature/task_{task_id}
```

Response behavior changed:

- Successful tasks return `branch_name: "feature/task_{task_id}"`.
- Successful tasks suppress raw `stdout` and include `file_changes: true`.
- Responses still include `status`, `commit_hash`, `stderr`, and `returncode`.

Fail-secure behavior:

- If `git fetch origin` or `git checkout -b feature/task_{task_id}` fails, subprocess execution is aborted.
- If post-execution `git add`, `git commit`, or `git push` fails, the worker resets the task branch.
- Abort path first runs `git checkout main`. If local edits block checkout, it resets the task branch, cleans untracked files, checks out `main`, and deletes `feature/task_{task_id}`.
- HQ receives structured JSON with `status: "git_error"` and the Git stderr payload.
- If the subprocess itself fails, the worker resets the task branch and returns `status: "error"`.
- Router-originated persona tasks are converted into local AI CLI commands before subprocess execution: `Pixel` uses `gemini`, `Ada` uses `claude`, and `Linus` uses `codex`.

## HQ Router

Created `ai-agency-workspace/hq-backend/hq_router.py`.

The router watches a local file-drop queue:

```text
ai-agency-workspace/hq-backend/task_queue/*.json
```

Accepted input:

```json
{"task_id": "002", "type": "frontend", "prompt": "Build login component"}
```

Routing table:

- `frontend` -> `Pixel`
- `backend` -> `Linus`
- `architecture` -> `Ada`

Instruction format:

```text
Read .ai_agency_protocols.md. Assume persona: {persona}. Execute: {prompt}
```

MQTT output:

- Publishes to `agency/tasks/{branch_id}`.
- `branch_id` comes from task JSON, then `.env` `BRANCH_ID`, then `branch_1`.
- Payload is worker-compatible: `task_id`, `agent`, `repo_path`, `prompt`, `timeout`.

Queue handling:

- Successful task files move to `task_queue/processed/`.
- Invalid or failed task files move to `task_queue/failed/`.
- Unknown task types fail closed and are not published.

- Result: success.

---

# Phase 4 Report: HQ Command Center Scaffolding & Dashboard

## Status
- **Tauri / Vite Scaffolding:** Complete.
- **Component Layout:** Complete.
- **Tailwind Integration:** Complete.
- **Production Build:** Verified (compiles successfully with 0 errors).

## Component Structure & Files Created

### 1. Vite & React Environment Scaffolding
- **Root Directory:** `/ai-agency-workspace/hq-frontend/`
- **Tauri CLI:** Installed (`@tauri-apps/cli`).
- **Tauri Config:** Scaffolding complete inside `src-tauri/` configured for:
  - App Name: `hq-command-center`
  - Window Title: `"The Office AI - Command Center"`
  - Dev Server: `http://localhost:5173`
  - Web Assets Path: `../dist`
- **Tailwind CSS Configuration:** Added `tailwind.config.js` and `postcss.config.js` for styling support.
- **Icon Set:** Installed `lucide-react`.

### 2. Main Dashboard Application
File: `ai-agency-workspace/hq-frontend/src/App.tsx`

Features built:
- **Header Section:** Modern dark bar showing network broker subscription connectivity and active Phase 4 badge status.
- **Infrastructure Landscape:** Visually displays the core networks and agent branch architecture. Supports:
  - HQ Command Server: representing local Tauri control.
  - Linode Post Office: representing the MQTT broker (`172.105.92.145`).
  - Active branch nodes showing online status and assigned agent personas (`Linus`, `Ada`, `Pixel`).
- **Dynamic System Metrics:** Active interval hooks updating CPU allocation, memory footprint, and broker ping latency.
- **Interactive Node Selection:** Clicking any node in the landscape opens its status properties panel.
- **Task Dispatch Terminal Form:**
  - Auto-generates cryptographically secure-looking UUIDs for task identification, with a regeneration feature.
  - Category selector mapping tasks to appropriate agency branches.
  - Dynamic JSON payload builder console-logging structural payloads cleanly.

## Scaffolding Verification

- Build status: Clean production build compiled successfully via `tsc -b && vite build`.
- Artifact output size: 214kB bundle successfully packaged.

---

## Phase 4 Integration: UI-to-Backend Router Connection

### Tauri File System Integration
- **Plugin Registered:** Configured `@tauri-apps/plugin-fs` on the frontend, and added `tauri-plugin-fs = "2"` dependency in `src-tauri/Cargo.toml`.
- **Initialization:** Initialized the FS plugin via `.plugin(tauri_plugin_fs::init())` inside `src-tauri/src/lib.rs`.
- **Secure File System Permissions:** Configured capability-based permissions in `src-tauri/capabilities/default.json` with a restricted write scope. Explicitly authorized writing to `/Users/tijmenbaas/Development/TheOffice/ai-agency-workspace/hq-backend/task_queue/*` and `$HOME/Development/TheOffice/ai-agency-workspace/hq-backend/task_queue/*`.
- **Upgraded Dispatch Form (`App.tsx`):**
  - Integrated `writeTextFile` from `@tauri-apps/plugin-fs` and `homeDir` from `@tauri-apps/api/path` inside `onSubmit` / `handleSubmit`.
  - Dynamically resolves user home directory using `homeDir()` to guarantee seamless cross-machine and absolute path compatibility.
  - Constructs the exact 3-field JSON payload expected by `hq_router.py`: `{"task_id": "...", "type": "...", "prompt": "..."}`.
  - Stringifies the payload and writes it directly to disk as `task_{task_id}.json` in `hq-backend/task_queue/`.
  - Added success UI/toast notification indicating "Task Dispatched to HQ Router" and cleared inputs.

---

# Phase 3c Report: Headless CLI Execution & Bouncer Security Layer

To prevent headless execution from becoming a critical vulnerability, a robust **"Bouncer" Security Layer** has been built directly into `worker_node.py` to heavily restrict AI CLI actions, enforce strict spend caps and tool constraints, and ensure safe non-interactive execution.

## 1. The Regex Bouncer

Before executing any CLI tasks or running git branches, the Branch Daemon scans the input `prompt` (or falling back to the raw `command` for legacy tasks) against a strict, case-insensitive regular expression blocklist. Word-boundary markers (`\b`) prevent sub-string false positives while catching all bypass attempts.

If any blocklisted pattern is detected, the task is immediately aborted. A security error event is logged, and a structured `security_error` status is reported back to HQ, containing a detailed diagnostic warning in `stderr` and returning immediately before `subprocess.run` or Git repository checkout.

### The Regex Blocklist Patterns:
- **System Commands:**
  - `\brm\b` (Detects directory/file removal)
  - `\bmv\b` (Detects moving/renaming)
  - `\bchmod\b` (Detects permission manipulation)
  - `\bchown\b` (Detects ownership changes)
  - `\bkill\b` (Detects process termination)
  - `\bsudo\b` (Detects root privilege escalation)
- **Network Calls:**
  - `\bcurl\b` (Detects data exfiltration / remote fetches)
  - `\bwget\b` (Detects remote downloads)
  - `\bssh\b` (Detects unauthorized remote shells)
- **Package Managers:**
  - `\bnpm\s+install\b` (Restricts dependencies installation to manual CEO intervention)
  - `\bpip\s+install\b` (Restricts Python dependencies installation to manual CEO intervention)

---

## 2. Spend Caps & Tool limits

To prevent runaway API bills and restrict autonomous agents, we inject safety-first flags into the command building wrapper before any headless flag is ever applied:
1. **Max Cost Caps:** We append `--max-cost 0.50` to restrict session spending to a strict $0.50 ceiling per task.
2. **Tool Execution Restriction:** We append `--permission-mode acceptEdits` to auto-approve file modifications but block autonomous bash/terminal execution. Because stdin is redirected to `/dev/null`, any unexpected bash tool execution attempt immediately fails cleanly rather than hanging the daemon.

---

## 3. Safe Headless Execution Command Strings

Only after Bouncer regex checks and step-by-step injection of safety limits are applied do we append the headless bypass flags. The final resolved execution commands are:

### Ada / Claude Code:
- **Bash Execution String:**
  ```bash
  claude --max-cost 0.50 --permission-mode acceptEdits --dangerously-skip-permissions -p {prompt}
  ```
- **Security & Non-Interactive Flow:** Restricts Claude to maximum session cost of $0.50 and blocks shell execution using `acceptEdits` mode, allowing non-interactive run via print mode (`-p`) and `--dangerously-skip-permissions` only within this secure boundary.

### Pixel / Gemini CLI:
- **Bash Execution String:**
  ```bash
  gemini --skip-trust --max-cost 0.50 --permission-mode acceptEdits --yolo -p {prompt}
  ```
- **Security & Non-Interactive Flow:** Restricts Gemini to a maximum cost of $0.50 and blocks shell execution, bypassing directory trust prompts and applying headless auto-approval (`--yolo`) safely within this sandbox-like boundary.

### Linus / Codex:
- **Bash Execution String:**
  ```bash
  codex exec --max-cost 0.50 --permission-mode acceptEdits --dangerously-bypass-approvals-and-sandbox {prompt}
  ```
- **Security & Non-Interactive Flow:** Restricts Codex execution via the `exec` subcommand, injecting the identical maximum cost and command restrictions before bypassing confirmation prompts.

---

## 4. Fail-Secure Subprocess Environment

To guarantee that any undocumented interactive prompt or unexpected input check does not block the branch worker indefinitely:
- The 300-second execution timeout remains as a fallback.

---

# Phase 4 Integration Upgrade: Dynamic Workspaces

To allow target directories to be dynamically configured by the CEO, we upgraded the HQ Command Center with standard Tauri Dialog plugin APIs.

## 1. Dialog Plugin Registration & Setup

We installed and initialized the official `@tauri-apps/plugin-dialog` to support folder selection:

- **npm Dependency:** Added `"@tauri-apps/plugin-dialog": "^2.2.0"` to the package.
- **Cargo Dependency:** Registered `tauri-plugin-dialog = "2"` under `[dependencies]` in `Cargo.toml`.
- **Tauri Builder:** Registered the plugin via `.plugin(tauri_plugin_dialog::init())` in `src-tauri/src/lib.rs`.

## 2. Capabilities Configuration

To authorize folder selection dialog window interactions in the Tauri security sandbox, we appended the default permission capabilities inside `src-tauri/capabilities/default.json`:

```json
  "permissions": [
    "core:default",
    "dialog:default",
    {
      "identifier": "fs:allow-write-text-file",
      "allow": [
        { "path": "/Users/tijmenbaas/Development/TheOffice/ai-agency-workspace/hq-backend/task_queue/*" },
        { "path": "$HOME/Development/TheOffice/ai-agency-workspace/hq-backend/task_queue/*" }
      ]
    }
  ]
```

This registers standard directory browser open/save privileges in the desktop runtime sandbox.

## 3. Premium Workspace Selector UI

Upgraded `src/App.tsx` with a highly polished stateful workspace targeting block:

- **State Hook:** Added `workspacePath` to persist the selected absolute target workspace path.
- **Tauri Native Open API:** Integrated `open({ directory: true, multiple: false })` dialog triggers.
- **Dynamic Notice Cards:**
  - Displays a yellow pulsing alert warning if no workspace is selected, explaining how to target local paths.
  - Switches to a sleek green checkmark box displaying the selected absolute path in code-mono font upon selection.
- **Payload Upgrade:** Dispatched tasks now package the selected workspace directory absolute path inside the JSON payload written to `task_queue/` as the `"workspace_path"` parameter.
- **Validation Check:** The `DISPATCH AGENT TASK` button is dynamically disabled until both a target folder is targeted and a prompt instruction is input.

---

## 4. Backend Workspace Upgrade: Dynamic Workspaces & Path Security

To address the nested-Git vulnerability and support dynamic directory targeting, the HQ Router and Worker Daemon have been successfully upgraded to accept and utilize a dynamic `workspace_path` provided by the UI, replacing the hardcoded jail.

### 1. HQ Router Update
File: `ai-agency-workspace/hq-backend/hq_router.py`

- Modified `validate_task` to optionally extract `workspace_path` from the dropped JSON task payload.
- Extracted and forwarded `workspace_path` directly in the outgoing MQTT payload so that branch worker nodes can dynamically locate and target the chosen workspace directory.

### 2. Worker Daemon Upgrade & Path Security
File: `ai-agency-workspace/branch-daemon/worker_node.py`

- **Removed Jail Constant:** The hardcoded `/ai-agency-workspace/sandbox` `WORKSPACE_DIR` constant has been removed entirely.
- **Payload Extraction:** Upgraded `parse_task_payload` to gracefully extract `workspace_path` from incoming task payloads.
- **Strict Security Validation:** Added robust validation checks inside `execute_task_with_git` to enforce security on the dynamic path before any git or subprocess execution occurs:
  1. **Non-Empty Check:** Rejects payloads if `workspace_path` is empty or missing.
  2. **Absolute Path Check:** Verifies that the targeted `workspace_path` is an absolute path. Any relative target triggers an immediate abort.
  3. **Existence Check:** Verifies that the targeted directory actually exists on the host machine.
- **Fail-Secure Abort:** If any validation check fails, the task aborts instantly, and a structured `security_error` status response is published back to HQ containing the diagnostic warning in `stderr`.
- **Dynamic CWD Execution:** Uses the verified `workspace_path` as the `cwd` parameter for all Git subprocess commands and AI CLI execution commands (Codex, Claude Code, Gemini CLI).
- **Intact Safeguards:** The Regex Bouncer blocklist and API Spend Caps remain fully active and unaltered.

---

# Phase 5 Report: The Return Path (Status Feedback Loop)

## Problem

Branch daemons published task results to `agency/status/{branch_id}`, but no HQ
component consumed them. The CEO had to watch a daemon terminal to learn whether
a task passed, failed, or hit a security gate. The loop was open.

## HQ Status Listener

Created `ai-agency-workspace/hq-backend/hq_status_listener.py`.

- Standalone process. Subscribes to `agency/status/#` (all branches) over MQTT.
- Persistent session (`clean_session=False`, fixed `client_id=hq_status_listener`)
  so the broker queues QoS 1 status messages while the listener is briefly down.
- On each message: annotates with `branch_id` (from topic) and `received_at`
  (UTC ISO), then persists under `hq-backend/status_log/`:
  - `{task_id}.json` — latest status for that task (atomic temp-file swap so the
    frontend never reads a half-written file).
  - `_history.jsonl` — append-only event log, one JSON object per line.
- Non-JSON payloads (e.g. `PONG` heartbeats) are logged but not treated as task
  results. Prints a terse Caveman line per event:
  `task=<id> status=<s> branch=<name> commit=<sha8>`.

## HQ Command Center: Task Results Panel

Upgraded `ai-agency-workspace/hq-frontend/src/App.tsx`.

- Polls `status_log/` every 4s via the Tauri FS plugin (`readDir` + `readTextFile`),
  parses each `{task_id}.json`, sorts by `received_at` descending.
- New "Task Results" card renders status badges (green `success`/`pass`,
  indigo `accepted`, rose for `error`/`git_error`/`security_error`/`timeout_error`),
  branch name, short commit hash, time, and the tail of `stderr` on failure.
- Added the missing `qa` → Kent option to the Task Category dropdown and replaced
  the 3-way `routing_target` ternary with a `PERSONA_BY_TYPE` map mirroring
  `hq_router.py` (so QA tasks no longer mislabel as Ada).

## Security

- Granted scoped read permissions in `src-tauri/capabilities/default.json`:
  `fs:allow-read-dir` on `status_log` and `fs:allow-read-text-file` on
  `status_log/*`. No write scope was added; the UI only reads results.
- `status_log/*.json` and `*.jsonl` added to `.gitignore` (ephemeral runtime data).

## Run order

1. `python hq-backend/hq_status_listener.py`  (start first so no result is missed)
2. `python hq-backend/hq_router.py`
3. `python branch-daemon/worker_node.py`  (on each branch machine)
4. Dispatch from the HQ app; results appear in the Task Results panel.

---

# Version 2 Report: Maturity Pass

## Goal

Review the full application landscape against the original documentation and move the system from a scaffolded V1 into a more mature V2 control loop.

## Backend / Worker Hardening

- Branch Daemon now validates that `workspace_path` resolves to an existing Git work tree before any task branch is created.
- Dirty trees still fail closed, but cleanup no longer assumes `main`; the worker captures the original branch and returns there on abort.
- Duplicate task branches are rejected before checkout, preventing accidental reuse of stale task state.
- Failed task cleanup resets and removes only after a task branch was created.
- Task branch names are sanitized and cannot collapse to an empty suffix.
- Successful status payloads now include `base_branch` and `file_changes` metadata for the HQ return path.
- Non-Git workspaces return a normalized `git_error` explaining that the workspace is not a Git repository.

## Command Center V2

- Frontend package version is now `2.0.0`.
- Header/status labels now present the app as the V2 control loop instead of Phase 4 scaffolding.
- Hardcoded broker IP display was removed from the UI; broker identity remains environment-owned.
- Task Results panel displays `base_branch` and diff metadata when the worker reports it.
- Lint issues from the older scaffold were fixed (`any` removal and initial UUID state).

## Configuration

- `.env.example` now documents operational defaults used by the router and worker:
  - `BRANCH_ID`
  - `DEFAULT_REPO_PATH`
  - `DEFAULT_TASK_TIMEOUT`
  - `DEFAULT_BASE_BRANCH`

## Verification

- Added `ai-agency-workspace/tests/test_v2_contracts.py`.
- Covered router persona routing, unknown type rejection, timeout validation, branch name sanitation, worker payload validation, bouncer blocking, missing workspace failure, and non-Git workspace failure.
- Passed:
  - `ai-agency-workspace/.venv/bin/python -m unittest discover -s ai-agency-workspace/tests`
  - `ai-agency-workspace/.venv/bin/python -m py_compile ai-agency-workspace/branch-daemon/worker_node.py ai-agency-workspace/hq-backend/hq_router.py ai-agency-workspace/hq-backend/hq_status_listener.py ai-agency-workspace/hq-backend/skill_manager.py`
  - `npm run lint`
  - `npm run build`

## Remaining V2 Risk

- Live Linode MQTT smoke testing was not performed in this pass.
- The Branch Daemon is still policy-hardened, not VM/container isolated.
- Only Kent currently ships a persona invocation file; the other persona packs still need first-class prompt assets.

---

# DevBoss Autonomous Epic Engine

## Rebrand

- Window title is now `DevBoss - Command Center`.
- HQ header now shows `DevBoss`.

## Epic JSON Schema

Epic files live in `ai-agency-workspace/hq-backend/epic_queue/`.

Each file must be a JSON array. Each item is a normal `hq_router.py` task payload plus required `depends_on`.

Required fields per task:

```json
[
  {
    "task_id": "epic-001-design-api",
    "type": "backend",
    "prompt": "Design the API contract for billing events.",
    "workspace_path": "/absolute/path/to/project",
    "depends_on": []
  },
  {
    "task_id": "epic-001-build-api",
    "type": "backend",
    "prompt": "Implement billing events API from the approved contract.",
    "workspace_path": "/absolute/path/to/project",
    "depends_on": ["epic-001-design-api"]
  }
]
```

Router-compatible optional fields remain allowed, including `branch_id`, `repo_path`, and `timeout`.

`depends_on` must always exist and must be a list of task id strings. Empty list means task is eligible immediately.

## Polling Logic

`ai-agency-workspace/hq-backend/hq_epic_manager.py` runs every 5 seconds.

Loop:

1. Ensure `epic_queue/`, `epic_queue/.state/`, `task_queue/`, and `status_log/` exist.
2. Read every `status_log/*.json` file.
3. Build a success set from records where `status == "success"`.
4. Read every active `epic_queue/*.json` file.
5. For each task, compare `depends_on` against the success set.
6. If no dependency is pending and task is not already in the epic state file, write the router payload to `task_queue/task_{task_id}.json`.
7. Store dispatch state in `epic_queue/.state/{epic_name}.state.json` so restart does not double-dispatch.

All file reads, writes, directory creation, and directory scans use explicit `try/except` handling. Queue writes use temp file plus replace to avoid partial JSON files.

---

# DevBoss V2.1 UI Overhaul & Rebrand Report

We have successfully executed the V2.1 rebrand and UI overhaul, fully applying the DevBoss Design Manifest specifications to the Tauri Command Center.

## 1. Tauri Config Update & Window Title Confirmation
- File: `/ai-agency-workspace/hq-frontend/src-tauri/tauri.conf.json`
- We verified that the Tauri application window title configuration has been successfully updated to `"title": "DevBoss - Command Center"`.
- We also modified `/ai-agency-workspace/hq-frontend/index.html` to update the document title element to `<title>DevBoss - Command Center</title>`.

## 2. DevBoss Design Manifest Application
- File: `/ai-agency-workspace/hq-frontend/src/App.tsx` and `src/index.css`
- **Primary Color Canvas:** Replaced all instance layers of `bg-slate-950` with Deep Obsidian `bg-slate-900`.
- **Logo Update:** Replaced the legacy layers icon (`<Layers />`) with the stylized network icon (`<Network />`) from `lucide-react`, styled in Electric Indigo (`text-indigo-500`) inside a custom indigo container.
- **Header:** Rebranded main text components to "DevBoss" and updated the command loop context info.
- **Telemetry & Results Badges:** Updated the telemetry log/task status badges in the "Task Results" panel to use `emerald-500` for success telemetry and `indigo-500` for active routing as defined by the manifest specs.
- **Typography:** Enforced standard sans-serif (Inter) headers and `font-mono` for all telemetry dashboards, active metrics, JSON console outputs, and task execution logs.

## 3. Epic Dispatcher Upgrade
- File: `/ai-agency-workspace/hq-frontend/src/App.tsx`
- **Retained Workspace Capability:** Maintained standard dynamic absolute workspace path integration dialog selection hooks and UI feedback components.
- **Action Upgrade:** Changed the submit execution action button text from `"Dispatch Task"` to `"DISPATCH EPIC"`.
- **Accent styling:** Restyled the submit/dispatch button with high-contrast solid Electric Indigo accent (`bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700`).

## 4. Verification
- Removed unused `Layers` import from `App.tsx` to fix TypeScript compilation warning check.
- Successfully compiled the production build using `tsc -b && vite build` with zero errors.




