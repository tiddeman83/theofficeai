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
- Stack: Tauri + Vite + React 19 + Tailwind for the UI; Python for five daemons (router, epic_manager, project_manager, status_listener, issue_listener).
- Job: Accept CEO intakes and drive them through the project lifecycle. Boot with `bash hq-backend/start_hq_daemons.sh`. Each stage owns a persona, decomposes to epics for multi-task work, routes tasks to the broker, and monitors completion.

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

**Seniors** (lead decision-makers):

| Persona       | Role                        | Tool                | Notes                                                               |
|---------------|-----------------------------|---------------------|--------------------------------------------------------------------|
| **Tijmen**    | CEO / Human                 | N/A                 | Owns intake, approval gates, merge button, and board decisions.     |
| **Linus**     | CTO / Backend Lead          | Codex               | Python, infra, specs, decomposition. Owns spec_review / decompose. |
| **Ada**       | Chief Architect             | Claude Code         | System design, orchestration, reports. Owns architecture / retro.   |
| **Pixel**     | Frontend Lead               | Cursor              | React, Tailwind, wireframes. Owns wireframe stage.                  |
| **Grace**     | DevOps / Infrastructure     | Antigravity         | Deployment, portfolio harvesting, prod promotion.                   |
| **Kent**      | QA / Test Engineer          | Codex               | Sandbox-locked. TDD-first. Owns UAT gate.                           |
| **SteveJobs** | Lead Engineer               | Claude Code         | Architecture decisions, code review, pair with CEO.                 |
| **Jocelyn**   | Engineering Manager / CoS   | Claude Code         | Cascades decisions, handles escalations.                            |

**Assistants** (pool members — process work in parallel):

| Persona    | Role                  | Tool         | Reports To | Notes                                    |
|------------|-----------------------|--------------|------------|------------------------------------------|
| **Donald** | Backend Engineer      | Codex        | Linus      | Parallel backend task pickup.            |
| **Brendan**| Frontend Engineer     | Cursor       | Pixel      | Parallel frontend task pickup.           |
| **Margaret**| Architect Assistant   | Claude Code  | Ada        | Architecture subwork, design review.     |
| **Tim**    | Infrastructure Ops    | Antigravity  | Grace      | Portfolio harvesting, infrastructure.    |
| **Barbara**| QA Automation         | Codex        | Kent       | Single-instance (explicit branch_id).    |

**Specialists** (available for dispatch but not pooled):

| Persona    | Role                  | Tool     | Notes                                    |
|------------|-----------------------|----------|------------------------------------------|
| **Bruce**  | Security Engineer     | Codex    | On-demand security review.               |
| **Don**    | UX Designer           | Gemini   | On-demand design critique.               |
| **Edsger** | Data / Algorithms     | Codex    | On-demand perf analysis.                 |
| **Jeff**   | Technical Writer      | Claude Code | On-demand documentation.             |
| **Andy**   | Mobile Engineer       | Codex    | On-demand mobile work.                   |
| **Stewart**| Product Manager       | Claude Code | On-demand product strategy.           |

Personas live as folders under `ai-agency-workspace/hq-backend/personas/` — each holds a `persona.md`, a `contract.md`, a `bootstrap.md`, and (optionally) a `codex_invocation.md` that the worker prepends to the prompt at dispatch time. LinkedIn-style bios live in `docs/team/{name}.linkedin.md` for seniors.

---

## The Project Lifecycle

Projects move through a seven-stage pipeline. Each stage has an owner persona, a gate condition, and an artifact. The CEO is the only role that can approve stage transitions. Board meetings (triggered by `severity=block, requires=cto` issue posts) pause dispatch until the CEO issues a decision.

```
intake → spec (Linus) → wireframe (Pixel) → poc → mvp → uat (Kent) → prod (Grace) → closed
                ↓                              ↑↑↑↑↑↑↑
          open_questions.md      decompose_epic → epic_queue → dispatched to pool
```

**Stage definitions:**

| Stage     | Owner | Task Type | Kind | Gate Condition | Artifact |
|-----------|-------|-----------|------|---|---|
| spec      | Linus | spec_review | task | CEO approves or provides answers | `spec.md` + (optional) `open_questions.md` |
| wireframe | Pixel | wireframe | task | CEO approves | `wireframes/*.md` (ASCII/SVG screens) |
| poc       | Linus | decompose | epic | CEO approves | `poc_epic.json` → multi-task dispatch |
| mvp       | Linus | decompose | epic | CEO approves | `mvp_epic.json` → multi-task dispatch |
| uat       | Kent  | uat | task | Test criteria pass | `uat_report.md` (pass/fail per spec) |
| prod      | Grace | portfolio_contribute | task | CEO approves | Portfolio artifacts + manifests |
| closed    | —     | —     | — | All stages complete | Project archived, retros collected |

**Board meetings:** Any persona can post an issue with `severity=block, requires=cto` to `agency/issues/{project_id}`. The project_manager pauses dispatch (sets status=board_meeting) until the CEO writes a decision.

---

## The Caveman Protocol

Agent-to-agent and agent-to-system communication runs through Caveman: no pleasantries, no narration, no "Sure! Let me help you with that." Only data, code, and logic. Context windows are sacred. The README and team LinkedIn profiles are allowed to be friendly. The agents are not.

This is enforced socially (in every persona file) and structurally (the HQ Router prepends a Caveman directive to every dispatched prompt).

---

## Repository Layout

```
TheOffice/
├── README.md                       ← you are here
├── CONTRIBUTING.md
├── LICENSE.md
├── CLAUDE.md                       ← project agent instructions
├── docs/                           ← human-facing docs
│   ├── architecture.md             ← the Trinity, in detail
│   ├── build_instructions.md       ← bootstrap order
│   ├── development.md              ← methodology
│   ├── company_joining_instructions.md  ← read this if you are an agent
│   ├── the_board_discussion.md     ← design notes
│   ├── report_to_founders.md       ← async CTO log
│   ├── team/                       ← LinkedIn-style profiles (seniors only)
│   ├── portfolio/                  ← reusable components library
│   ├── board_reports/              ← per-project stage reports
│   └── example_tasks/              ← reference JSON payloads
├── env_variables/                  ← templates for required env files
└── ai-agency-workspace/
    ├── .env.example                ← MQTT broker config
    ├── branch-daemon/
    │   ├── worker_node.py          ← MQTT subscriber + CLI bridge + git enforcer
    │   ├── start_kent.sh           ← boots Kent's sandbox-locked worker (demo)
    │   ├── stop_kent.sh            ← stops Kent daemon
    │   └── requirements.txt
    ├── hq-backend/
    │   ├── hq_router.py            ← task_queue/*.json → agency/tasks/{branch}
    │   ├── hq_epic_manager.py      ← epic_queue/*.json → task_queue/*.json (DAG dripper)
    │   ├── hq_project_manager.py   ← project_queue/*.intake.json → projects/{id}/
    │   ├── hq_status_listener.py   ← agency/status/# → status_log/*.json
    │   ├── hq_issue_listener.py    ← agency/issues/# → projects/{id}/issues/
    │   ├── start_hq_daemons.sh     ← boots all five HQ daemons
    │   ├── stop_hq_daemons.sh      ← stops all HQ daemons
    │   ├── personas/               ← one folder per persona (seniors, assistants, specialists)
    │   ├── skills/                 ← Caveman-compressed lesson library
    │   ├── projects/               ← {project_id}/manifest.json + artifacts per stage
    │   ├── project_queue/          ← CEO intakes land here
    │   ├── epic_queue/             ← epic_manager picks these up
    │   ├── task_queue/             ← normal router-compatible task drops
    │   ├── status_log/             ← task results (read by HQ UI)
    │   └── requirements.txt
    └── hq-frontend/                ← Tauri + Vite + React + Tailwind command center
```

---

## How work flows through the system

**Single-task stages (spec, wireframe, uat, prod):**
1. **Project Manager** dispatches a stage task to `task_queue/{id}.json`.
2. **HQ Router** validates, attaches persona, wraps Caveman prelude, publishes to `agency/tasks/{branch_id}` over MQTT.
3. **Branch Daemon** receives, validates, checks out `feature/task_{id}`, shells to the right CLI, captures output, commits, and pushes.
4. **Status JSON** returns on `agency/status/{branch_id}`.
5. **Project Manager** reads status, advances project state. If successful, gates to CEO approval. If failed, triggers board meeting.
6. **CEO reviews**, approves, advances to next stage (or denies and opens issue).

**Multi-task stages (poc, mvp):**
1. **Project Manager** dispatches a `decompose` task to Linus.
2. Linus reads spec/wireframes, produces `{stage}_epic.json` with task array (each task has `{task_id, type, prompt, workspace_path, depends_on}`).
3. **Project Manager** reads epic file, validates, copies to `epic_queue/`.
4. **Epic Manager** picks up epic, respects dependency order, drips tasks into `task_queue/` as dependencies complete.
5. Branch workers claim tasks via round-robin pool routing. Parallel execution.
6. **Project Manager** monitors all epic task statuses; advances to UAT only if all succeed.

**Board meetings:**
- Any persona can post `{severity: "block", requires: "cto", subject, body}` to `agency/issues/{project_id}`.
- **Issue Listener** persists to `projects/{id}/issues/`.
- **Project Manager** detects, sets status=board_meeting, stops dispatch.
- CEO reviews issue, writes decision to `projects/{id}/decisions/{id}.md`.
- Project resumes on next poll cycle.

The merge step is deliberately manual. Agents write, test, and report. Only a human approves stage transitions and ships.

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

### 3. Run the HQ Daemons

```bash
cd ai-agency-workspace
python -m venv .venv && source .venv/bin/activate
pip install -r hq-backend/requirements.txt
bash hq-backend/start_hq_daemons.sh
```

This boots all five daemons:
- **router**: watches `task_queue/*.json`, publishes to MQTT.
- **epic_manager**: drips multi-task epics from `epic_queue/` into `task_queue/` respecting dependencies.
- **project_manager**: consumes intakes from `project_queue/`, drives lifecycle stages, gates on CEO approval.
- **status_listener**: subscribes to `agency/status/#`, persists to `status_log/` for the UI.
- **issue_listener**: subscribes to `agency/issues/#`, persists to `projects/{id}/issues/` for board meetings.

Watch logs:
```bash
tail -f /tmp/the_office_*.log
```

Stop all daemons:
```bash
bash hq-backend/stop_hq_daemons.sh
```

### 4. Run Branch Daemons

For each persona/CLI combination, on the host where the CLI is installed:

```bash
cd ai-agency-workspace
source .venv/bin/activate
pip install -r branch-daemon/requirements.txt
BRANCH_ID=branch_pixel    BRANCH_PERSONA=pixel    python branch-daemon/worker_node.py
BRANCH_ID=branch_brendan  BRANCH_PERSONA=brendan  python branch-daemon/worker_node.py
BRANCH_ID=branch_linus    BRANCH_PERSONA=linus    python branch-daemon/worker_node.py
BRANCH_ID=branch_donald   BRANCH_PERSONA=donald   python branch-daemon/worker_node.py
# ... etc per persona (seniors + pool members that are running)
```

`BRANCH_PERSONA` tells the daemon to load its own persona invocation (e.g., Donald's Codex invocation) instead of the senior's. Without it, all daemons load the senior mapping.

Each daemon will log `Successfully connected to MQTT Broker!` and `Subscribed to topic: agency/tasks/{branch_id}`.

### 5. Try a Project Intake

Create an intake JSON in `hq-backend/project_queue/`:

```json
{
  "name": "StudiBuddy V1",
  "project_id": "studiebuddy-v1",
  "ceo_brief": "Build a Vite + React web app for collaborative study sessions. Real-time sync via WebSocket. Dark mode theme.",
  "workspace_path": "/Users/you/Development/StudiBuddy"
}
```

The **Project Manager** will:
- Create `projects/studiebuddy-v1/manifest.json` (status: awaiting_cto_review).
- Dispatch a `spec_review` task to Linus.
- Poll for completion.

When Linus finishes:
- Project moves to status: stage_pending_approval.
- CEO approves by writing `ceo_approval.flag`.
- Project advances to wireframe, dispatches Pixel.

(To try a one-off task instead of a full project, drop a JSON into `task_queue/` as before.)

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
