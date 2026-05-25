# UAT Guide — TheOffice V2

Hands-on acceptance test for the CEO. Drives a project from intake to spec sign-off in under 10 minutes. Exercises every V2 surface: project manager, router, status feedback, issue channel, board meetings, frontend Projects tab.

---

## 0. Prerequisites

- Repo cloned at `~/Development/TheOffice/`.
- Python venv at `ai-agency-workspace/.venv/` with `paho-mqtt` and `python-dotenv` installed (`pip install -r branch-daemon/requirements.txt`).
- `ai-agency-workspace/.env` populated with `MQTT_BROKER_IP`, `MQTT_PORT`, `MQTT_USER`, `MQTT_PASSWORD`. Broker reachable.
- Node 20+ for the Tauri frontend.
- At least one CLI coding agent installed on `PATH` for the branch worker that will run the spec_review task. For demo purposes the simplest path is `claude` or `codex`. (The router calls `claude --permission-mode acceptEdits -p ...` for Ada and `codex exec --dangerously-bypass-approvals-and-sandbox ...` for Linus.)

---

## 1. Boot the HQ stack

```bash
cd ~/Development/TheOffice/ai-agency-workspace
bash hq-backend/start_hq_daemons.sh
```

Expected: five `[OK]` lines for router, epic_manager, project_manager, status_listener, issue_listener with pidfiles in `/tmp/the_office_*.pid`.

Tail logs (separate terminal):
```bash
tail -f /tmp/the_office_router.log /tmp/the_office_project_manager.log /tmp/the_office_status_listener.log /tmp/the_office_issue_listener.log
```

---

## 2. Boot at least one branch worker (Linus)

In a new terminal:
```bash
cd ~/Development/TheOffice/ai-agency-workspace
BRANCH_ID=branch_linus BRANCH_PERSONA=linus PYTHONUNBUFFERED=1 \
  .venv/bin/python branch-daemon/worker_node.py
```

Expected: `[Branch Daemon] Successfully connected to MQTT Broker!` then `Subscribed to topic: agency/tasks/branch_linus`.

(For full pool coverage repeat for `branch_donald`, `branch_pixel`, `branch_brendan`, etc. UAT only requires `branch_linus` for the spec stage.)

---

## 3. Launch the HQ Command Center

```bash
cd ~/Development/TheOffice/ai-agency-workspace/hq-frontend
npm install     # only first run
npm run tauri dev
```

Window opens (1440×900, "DevBoss - Command Center"). Header shows `BROKER: Connected`.

---

## 4. Dispatch a project intake

1. Click **Select Workspace Folder** → choose any local dir (will not be touched in this UAT, but the manifest requires it).
2. Switch the dispatch tab to **Projects** (third pill, amber accent).
3. Fill:
   - **Project Name**: `Login Module UAT`
   - **CEO Brief**: `Build a passwordless email-link login. Single screen. Mobile-first.`
4. Click **DISPATCH PROJECT INTAKE**.

Toast: "Project Dispatched to HQ Project Manager."

---

## 5. Watch the project advance

In the left column, the **Active Projects** panel polls every 4 s.

Within ~5 s you should see one card titled `Login Module UAT`:
- Stage chip: `spec`
- Status chip: `stage in progress`
- Action chip: `linus`

In `tail -f` of `the_office_project_manager.log`:
```
[HQ Project] Accepted intake -> project login-module-uat (Login Module UAT).
[HQ Project] Dispatched spec task login-module-uat-spec-XXXXXX to Linus.
```

In `the_office_router.log`:
```
[HQ Router] routed task login-module-uat-spec-XXXXXX to agency/tasks/branch_linus
```

In the branch worker terminal:
```
[Branch Daemon] >>> Received payload on [agency/tasks/branch_linus]: {...}
```

---

## 6. Linus runs and reports

When the CLI agent finishes producing `projects/{id}/spec.md` (and optionally `open_questions.md`):
- Branch worker pushes a branch + publishes status to `agency/status/branch_linus`.
- status_listener writes `status_log/{task_id}.json`.
- project_manager observes success and either:
  - **(a) flips to `awaiting_ceo_answers`** if `open_questions.md` exists. The Projects card now shows an inline textarea: "CEO Answers Required." Type answers, click **Submit Answers**.
  - **(b) flips to `stage_pending_approval`** if no open questions. The card shows an amber **Approve Stage** button.

---

## 7. Approve the spec → wireframe stage starts

Click **Approve Stage**. The card transitions to:
- Stage: `wireframe`
- Status: `stage in progress`
- Action: `pixel`

If you don't have a Pixel branch worker running, the task sits in `task_queue/` waiting. Expected and visible proof routing is correct.

---

## 8. Trigger a board meeting (optional but recommended)

From any terminal, send a blocking issue manually to exercise the pause loop:
```bash
mosquitto_pub -h $MQTT_BROKER_IP -p $MQTT_PORT -u $MQTT_USER -P $MQTT_PASSWORD \
  -t "agency/issues/login-module-uat" \
  -m '{"issue_id":"iss-test","project_id":"login-module-uat","from_agent":"Linus","task_id":"-","severity":"block","subject":"Need clarification on auth provider","body":"Magic link via what SMTP?","requires":"cto","created_at":"2026-05-25T12:00:00+00:00"}'
```

Within 4 s:
- issue_listener writes `projects/{id}/issues/iss-test.json` + appends `_history.jsonl`.
- Project manifest flips to `status: board_meeting`, `open_action: ceo`.
- Projects card shows the purple **Board Meeting Open** textarea.
- Issues subsection appears at the bottom of the card (`Issues (1, 1 block)` with the dot indicator).

Type a decision (e.g. "Use Resend for SMTP, magic-link only") → click **Close Meeting**. Card returns to `stage_pending_approval`.

---

## 9. Stop

```bash
bash hq-backend/stop_hq_daemons.sh
# Ctrl+C the branch worker and Tauri dev.
```

---

## Pass criteria

UAT is **PASS** if all of these hold:

- [ ] Five HQ daemons booted with `[OK]` and no crashes in the first 30 s.
- [ ] Tauri window opened at 1440×900, three dispatch tabs visible (Single / Epic / Projects).
- [ ] Project intake created a manifest at `ai-agency-workspace/hq-backend/projects/{slug}/manifest.json`.
- [ ] Spec task appeared at `agency/tasks/branch_linus` (visible in router log).
- [ ] Branch worker received the task and reported back to `agency/status/branch_linus`.
- [ ] status_listener persisted `status_log/{task_id}.json`.
- [ ] project_manager advanced the project to `stage_pending_approval` (or `awaiting_ceo_answers` if Linus produced open questions).
- [ ] Clicking **Approve Stage** in the UI transitioned the project to the next stage and dispatched the next task.
- [ ] (Optional) Publishing a `severity=block, requires=cto` issue flipped status to `board_meeting`; Closing the meeting returned to `stage_pending_approval`.
- [ ] No errors in any of the five daemon logs.

If any box is unticked, file a board-meeting issue against the project and we re-run.

---

## Known limits in this UAT

- Pool routing currently uses round-robin in-memory; restarting the router resets the cursor (acceptable for V2 demo).
- UAT (Kent) and PROD (Grace) stages require their respective branch workers + sandbox setup. Spec/wireframe is enough to certify the lifecycle end-to-end.
- Reporting is fire-and-forget; the board report will land in `docs/board_reports/{project}_{stage}.md` only if a branch worker for `branch_ada` is online to consume the dispatched `report` task. Absence does not fail UAT.
