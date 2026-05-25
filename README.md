# The Office AI

> A distributed, multi-agent software agency that runs on your own machines. One human CEO, a roster of AI personas, and a message broker keeping them in sync.

The Office AI is an orchestration system that turns a CEO (you) plus a handful of installed CLI coding agents (Claude Code, Codex, Cursor, Gemini, Antigravity) into a small virtual software company. You describe work in a desktop command center; named AI personas pick it up on whatever machine they happen to live on; finished diffs come back as git branches for you to review and merge.

This repo is the V2 working implementation. It is intentionally small, intentionally hackable, and intentionally human-in-the-loop on the merge step.

---

## Why this exists

Most "autonomous agent" frameworks try to be either a hosted SaaS (Devin, Paperclip) or a single-process loop on one machine. Neither of those fit if you:

- Already pay for multiple CLI coding subscriptions and want to actually use them.
- Run several side projects in parallel and want background work to continue while you sleep, teach, or consult.
- Refuse to hand your code or your API budget to a third-party cloud.
- Want the merge button to stay under a human finger.

The Office AI is what you build when you decide the orchestrator should be yours, the workers should be the CLIs you already own, and the only thing in the cloud is a thin pub/sub broker.

---

## The Trinity Architecture

The system has exactly three environments. Keeping them physically separate is the point.

```
   ┌──────────────────────┐        ┌─────────────────────┐        ┌──────────────────────┐
   │  HQ (Command Center) │        │  Post Office (Bus)  │        │ Branch Office(s)     │
   │  Tauri + React UI    │ ─────► │  Linode + Mosquitto │ ─────► │ Python worker daemon │
   │  Python HQ Router    │        │  MQTT pub/sub       │        │ Local CLI agents     │
   │  task_queue/*.json   │ ◄───── │  agency/tasks/*     │ ◄───── │ Git branch + push    │
   └──────────────────────┘        └─────────────────────┘        └──────────────────────┘
            CEO                          The wire                       The developers
```

### 1. HQ — the brain
- Location: your laptop (Docker-ready, currently a native dev build).
- Stack: Tauri + Vite + React 19 + Tailwind for the UI; Python for the router and skill manager.
- Job: Accept tickets from the CEO, translate them into Caveman-compressed prompts, persist them as JSON files in `task_queue/`, and publish them to the broker.

### 2. The Post Office — the wire
- Location: a tiny Ubuntu box on Linode (or anywhere reachable).
- Stack: Eclipse Mosquitto MQTT broker, locked down with username/password and a firewall.
- Job: Hold tasks on `agency/tasks/{branch_id}` until a Branch Office connects and claims them. Carry status replies back on `agency/status/{branch_id}`.

### 3. Branch Offices — the developers
- Location: any host machine where a CLI coding agent is installed and logged in.
- Stack: a single Python script (`worker_node.py`) plus whichever CLIs (`claude`, `codex`, `gemini`) are on `PATH`.
- Job: Subscribe to its topic, validate the payload, isolate work on a `feature/task_{id}` branch, shell out to the right CLI, capture stdout/stderr, commit the diff, push the branch, and report back.

---

## The Roster

Personas are an abstraction over "which CLI tool runs this task." Every persona has a fixed mandate so prompts and skills can be tailored to it.

| Persona      | Role                          | Tool                            | Notes                                                                     |
|--------------|-------------------------------|---------------------------------|---------------------------------------------------------------------------|
| **Linus**    | CTO / Backend                 | Codex                           | Python, infrastructure, architectural integrity.                          |
| **Ada**      | Lead Architect / PM           | Claude Code                     | System design, orchestration, task decomposition.                         |
| **Pixel**    | Frontend Lead                 | Cursor / Gemini                 | React, Tailwind, UI/UX.                                                   |
| **Grace**    | DevOps                        | Antigravity                     | Environment setup, deployment, integration glue.                          |
| **Kent**     | QA Engineer                   | Codex                           | TDD-first. Sandbox-locked. Writes failing tests, runs them, reports JSON. |
| **SteveJobs**| Lead Engineer / Cofounder     | Claude Code (CEO sparring mode) | Architecture decisions and review on agent-generated diffs.               |

Personas live as folders under `ai-agency-workspace/hq-backend/personas/` — each holds a `persona.md`, a `contract.md`, a `bootstrap.md`, and (optionally) a `codex_invocation.md` that the worker prepends to the prompt at dispatch time.

---

## The Caveman Protocol

Agent-to-agent and agent-to-system communication runs through Caveman: no pleasantries, no narration, no "Sure! Let me help you with that." Only data, code, and logic. Context windows are sacred. The README is allowed to be friendly. The agents are not.

This is enforced socially (in every persona file) and structurally (the HQ Router prepends a one-line Caveman directive to every dispatched prompt).

---

## Repository Layout

```
TheOffice/
├── README.md                       ← you are here
├── CONTRIBUTING.md
├── LICENSE.md
├── docs/                           ← human-facing docs
│   ├── architecture.md             ← the Trinity, in detail
│   ├── build_instructions.md       ← bootstrap order (Linode → local → execution loop)
│   ├── development.md              ← iterative phases + methodology
│   ├── company_joining_instructions.md  ← read this if you are an agent
│   ├── the_founders.md             ← the incubation transcript
│   ├── report_to_founders.md       ← async log from CTO Linus to the founders
│   └── example_tasks/              ← reference JSON payloads
├── env_variables/                  ← templates for required env files
└── ai-agency-workspace/
    ├── .env.example                ← MQTT broker config
    ├── branch-daemon/
    │   ├── worker_node.py          ← MQTT subscriber + CLI bridge + git enforcer
    │   └── requirements.txt
    ├── hq-backend/
    │   ├── hq_router.py            ← watches task_queue/*.json, publishes to MQTT
    │   ├── hq_status_listener.py   ← subscribes to agency/status/#, persists results
    │   ├── skill_manager.py        ← Librarian (compresses lessons into reusable skills)
    │   ├── personas/               ← one folder per persona
    │   ├── skills/                 ← Caveman-compressed lesson library
    │   ├── status_log/             ← task results land here for the HQ UI to read
    │   └── task_queue/             ← drop JSON tasks here; HQ Router does the rest
    └── hq-frontend/                ← Tauri + Vite + React + Tailwind command center
```

---

## How a task moves through the system

1. **CEO drafts a ticket** in the HQ UI (or writes a JSON file by hand and drops it in `task_queue/`).
2. **HQ Router** picks up the file, validates the schema, attaches the right persona, wraps the prompt in the Caveman prelude, and publishes to `agency/tasks/{branch_id}` over MQTT.
3. **A Branch Daemon** holding that `BRANCH_ID` receives the payload, runs it through the Regex Bouncer (blocks `rm`, `mv`, `sudo`, `curl`, `wget`, `ssh`, `npm install`, `pip install`, and friends), validates the absolute workspace path, and — for Kent — enforces the sandbox-root allowlist.
4. **Daemon checks out a fresh `feature/task_{id}` branch**, shells out to the right CLI (`claude`, `codex`, or `gemini`) with the prompt, captures stdout/stderr, commits the diff, and pushes the branch.
5. **Status JSON** comes back on `agency/status/{branch_id}` with `{task_id, status, branch_name, commit_hash, stdout, stderr, returncode}`.
6. **CEO reviews the PR**, merges if it passes, and ships.

The merge step is deliberately manual. Agents can write and test. Only a human releases.

---

## Quick Start

> **Heads up.** V1 is in active testing. The pieces work in isolation; the end-to-end flow is being shaken out as we speak. Expect rough edges, and read [docs/build_instructions.md](docs/build_instructions.md) for the canonical bootstrap order.

### Prerequisites

- A Linode (or any) Ubuntu instance for the MQTT broker — small is fine, this thing barely breathes.
- Python 3.11+ on every machine that will run HQ or a Branch Daemon.
- Node 20+ and the Rust toolchain on the machine that will run the HQ desktop app (Tauri requirement).
- At least one of: `claude` (Claude Code), `codex` (Codex CLI), `gemini` (Gemini CLI), logged in and on `PATH`, on every Branch Office machine.

### 1. Stand up the Post Office

```bash
# On your Linode box
sudo apt update && sudo apt install -y mosquitto mosquitto-clients ufw
sudo mosquitto_passwd -c /etc/mosquitto/passwd branch_worker   # set a real password
sudo chown mosquitto:mosquitto /etc/mosquitto/passwd
sudo ufw allow 1883/tcp                                        # or 8883 for TLS
sudo systemctl enable --now mosquitto
```

Add `allow_anonymous false` and `password_file /etc/mosquitto/passwd` to `/etc/mosquitto/mosquitto.conf`, then `sudo systemctl restart mosquitto`.

### 2. Configure environment

Copy the template and fill it in on every machine that runs HQ or a Branch:

```bash
cp ai-agency-workspace/.env.example ai-agency-workspace/.env
$EDITOR ai-agency-workspace/.env
```

```env
MQTT_BROKER_IP=your.linode.ip.or.domain
MQTT_PORT=1883
MQTT_USER=branch_worker
MQTT_PASSWORD=your_mosquitto_password
BRANCH_ID=branch_1            # unique per Branch Office machine
```

### 3. Run the Branch Daemon

```bash
cd ai-agency-workspace
python -m venv .venv && source .venv/bin/activate
pip install -r branch-daemon/requirements.txt
python branch-daemon/worker_node.py
```

You should see `Successfully connected to MQTT Broker!` and `Subscribed to topic: agency/tasks/branch_1`.

### 4. Run the HQ Router

```bash
cd ai-agency-workspace
source .venv/bin/activate
pip install -r hq-backend/requirements.txt
python hq-backend/hq_router.py
```

Anything you drop into `ai-agency-workspace/hq-backend/task_queue/*.json` now gets published to MQTT within a second.

### 4b. Run the HQ Status Listener

```bash
cd ai-agency-workspace
source .venv/bin/activate
python hq-backend/hq_status_listener.py
```

Start this before dispatching so no result is missed. It subscribes to `agency/status/#`, prints a terse line per task result, and persists each one to `hq-backend/status_log/` — which the HQ desktop app reads to populate its **Task Results** panel.

### 5. Try a task

Use one of the reference payloads:

```bash
cp docs/example_tasks/first_v1_test.json \
   ai-agency-workspace/hq-backend/task_queue/
```

Watch the Branch Daemon's terminal. It will:
- check out `feature/task_studiebuddy-arch-001`,
- run the corresponding CLI (`claude` for Ada, `codex` for Linus/Kent, `gemini` for Pixel),
- commit the result, push the branch, and report status.

### 6. (Optional) Run the HQ desktop app

```bash
cd ai-agency-workspace/hq-frontend
npm install
npm run dev               # browser preview
# or:
npx tauri dev             # full desktop command center
```

---

## Security model

V2 ships with four layers of guardrails on the Branch Daemon, and treats the broker as untrusted transport (no secrets ever ride the wire):

1. **Regex Bouncer.** Hard blocklist on prompts and commands: `rm`, `mv`, `chmod`, `chown`, `kill`, `sudo`, `curl`, `wget`, `ssh`, `npm install`, `pip install`.
2. **Absolute-path workspace validation.** Relative paths and non-existent directories are rejected with `security_error` before any subprocess fires.
3. **Per-persona sandbox roots.** Kent (QA) is locked to `~/Development/Sandbox_TheOffice` so destructive test runs cannot escape into a real project.
4. **Git lifecycle checks.** The daemon verifies that the workspace is a Git repository, refuses dirty trees, refuses duplicate task branches, returns to the original branch on abort, and includes `base_branch` / `file_changes` metadata in task results.

Additionally: every task gets its own `feature/task_{id}` branch; the daemon refuses to start work on a dirty tree; failed tasks abort and clean up their branch; a 300-second execution cap applies to every CLI invocation.

This is V2. It is not a sandbox in the security-research sense. If you wire The Office AI into untrusted code or untrusted prompts, add real isolation (containers, VMs, gVisor) before you do anything you'd regret.

---

## Status

V2 has landed as a maturity pass over the first working loop:

- HQ Router accepts task files, routes by persona, and sends QA work to Kent's dedicated branch topic by default.
- Branch Daemon validates workspaces, creates isolated task branches, runs CLI agents, commits/pushes successful diffs, and reports structured status back to HQ.
- HQ Status Listener persists branch reports into `status_log/` for the desktop app.
- HQ Command Center dispatches tasks, targets local workspaces, shows live task results, and carries v2 status metadata.
- Regression tests cover the router/worker contract boundaries.

Remaining work: live end-to-end broker smoke tests across all operational personas, stronger real isolation for untrusted workspaces, and broader per-persona prompt packs beyond Kent.

See [docs/report_to_founders.md](docs/report_to_founders.md) for the rolling status log from CTO Linus.

---

## Contributing

This is a small public project run by a solo founder plus a roster of AI personas. PRs are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for how to file an issue, what the commit conventions look like, and the Caveman rules that apply to agent-authored changes.

---

## License

MIT — see [LICENSE.md](LICENSE.md). Use it, fork it, ship something weird with it.

---

## Credits

Built by Tijmen Baas as a learning-in-public experiment in running a one-person software agency staffed by AI agents. Named after the very organizational chart the system pretends to be: an office full of stubborn specialists who never come to meetings.
