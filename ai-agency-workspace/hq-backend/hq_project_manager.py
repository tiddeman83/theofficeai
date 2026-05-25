#!/usr/bin/env python3
"""
HQ Project Manager (Vision Layer)

Watches project_queue/ for new CEO intakes and drives each project through
the lifecycle:

  intake -> spec -> wireframe -> poc -> mvp -> uat -> prod -> closed

Each stage produces an artifact under projects/{project_id}/. The CEO is the
only role that can advance a stage (gate approval). The CTO (Linus) is the
only role that can request a board meeting, which pauses dispatch for that
project until the CEO writes a decision.

Sources of truth:
  - project_queue/{file}.intake.json    new CEO briefs (consumed once)
  - projects/{project_id}/manifest.json authoritative project state
  - status_log/{task_id}.json           task completions (read-only here)
  - task_queue/                         normal router-compatible task drops
  - epic_queue/                         epic drops for multi-task stages

The project manager NEVER speaks MQTT directly. It only writes JSON files
that hq_router.py / hq_epic_manager.py already consume. This keeps the
trinity boundary intact and lets the manager be restarted without state
loss.
"""

import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_QUEUE_DIR = Path(os.getenv("HQ_PROJECT_QUEUE_DIR", SCRIPT_DIR / "project_queue"))
PROJECTS_DIR = Path(os.getenv("HQ_PROJECTS_DIR", SCRIPT_DIR / "projects"))
TASK_QUEUE_DIR = Path(os.getenv("HQ_QUEUE_DIR", SCRIPT_DIR / "task_queue"))
EPIC_QUEUE_DIR = Path(os.getenv("HQ_EPIC_QUEUE_DIR", SCRIPT_DIR / "epic_queue"))
STATUS_DIR = Path(os.getenv("HQ_STATUS_DIR", SCRIPT_DIR / "status_log"))
PORTFOLIO_DIR = Path(os.getenv("HQ_PORTFOLIO_DIR", SCRIPT_DIR.parent.parent / "docs" / "portfolio"))
POLL_SECONDS = int(os.getenv("HQ_PROJECT_POLL_SECONDS", "5"))


# Stage progression. Each stage has an owner persona and a dispatched task
# type. CEO gate approval moves to the next stage. Stages whose `kind` is
# `epic` decompose into multi-task epics handled by hq_epic_manager.py.
STAGE_FLOW = [
    {"stage": "spec",      "owner": "Linus", "task_type": "spec_review",          "kind": "task"},
    {"stage": "wireframe", "owner": "Pixel", "task_type": "wireframe",            "kind": "task"},
    {"stage": "poc",       "owner": "Linus", "task_type": "decompose",            "kind": "epic"},
    {"stage": "mvp",       "owner": "Linus", "task_type": "decompose",            "kind": "epic"},
    {"stage": "uat",       "owner": "Kent",  "task_type": "uat",                  "kind": "task"},
    {"stage": "prod",      "owner": "Grace", "task_type": "portfolio_contribute", "kind": "task"},
]

VALID_STATUSES = {
    "awaiting_cto_review",
    "stage_in_progress",
    "stage_pending_approval",
    "awaiting_ceo_answers",
    "spec_approved",
    "board_meeting",
    "closed",
    "failed",
}


def log(message):
    print(f"[HQ Project] {message}", flush=True)


def log_error(message):
    print(f"[HQ Project] {message}", file=sys.stderr, flush=True)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def safe_id(value):
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in str(value))
    return cleaned.strip("-_") or uuid.uuid4().hex[:8]


def read_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except Exception:
        log_error(f"Failed to read {path}:\n{traceback.format_exc()}")
        return None


def write_json_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        tmp.replace(path)
        return True
    except Exception:
        log_error(f"Failed to write {path}:\n{traceback.format_exc()}")
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass
        return False


def ensure_directories():
    for d in (PROJECT_QUEUE_DIR, PROJECTS_DIR, TASK_QUEUE_DIR, EPIC_QUEUE_DIR, STATUS_DIR, PORTFOLIO_DIR):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            log_error(f"Failed to create {d}:\n{traceback.format_exc()}")


def manifest_path(project_id):
    return PROJECTS_DIR / project_id / "manifest.json"


def stage_index(stage_name):
    for i, s in enumerate(STAGE_FLOW):
        if s["stage"] == stage_name:
            return i
    return -1


def next_stage(current):
    idx = stage_index(current)
    if idx < 0 or idx >= len(STAGE_FLOW) - 1:
        return None
    return STAGE_FLOW[idx + 1]


def current_stage_def(manifest):
    for s in STAGE_FLOW:
        if s["stage"] == manifest.get("stage"):
            return s
    return None


def transition(manifest, *, stage=None, status=None, open_action=None, note=None):
    """Immutable-ish state advance: returns a NEW manifest dict (no mutation)."""
    updated = dict(manifest)
    history = list(updated.get("stage_history", []))
    if stage and stage != updated.get("stage"):
        history.append({
            "stage": stage,
            "entered_at": utc_now(),
            "from_stage": updated.get("stage"),
            "note": note,
        })
        updated["stage"] = stage
    if status:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {status}")
        updated["status"] = status
    if open_action is not None:
        updated["open_action"] = open_action
    updated["stage_history"] = history
    updated["updated_at"] = utc_now()
    return updated


def consume_intake(intake_path):
    """Convert an intake JSON drop into a fully-initialized project manifest."""
    data = read_json(intake_path)
    if not isinstance(data, dict):
        log_error(f"Intake {intake_path.name} ignored: not a JSON object.")
        return None

    name = data.get("name")
    brief = data.get("ceo_brief") or data.get("brief")
    workspace_path = data.get("workspace_path")
    if not isinstance(name, str) or not name.strip():
        log_error(f"Intake {intake_path.name} ignored: name required.")
        return None
    if not isinstance(brief, str) or not brief.strip():
        log_error(f"Intake {intake_path.name} ignored: ceo_brief required.")
        return None
    if not isinstance(workspace_path, str) or not workspace_path.strip():
        log_error(f"Intake {intake_path.name} ignored: workspace_path required.")
        return None

    project_id = safe_id(data.get("project_id") or uuid.uuid4().hex[:12])
    project_dir = PROJECTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "wireframes").mkdir(exist_ok=True)
    (project_dir / "issues").mkdir(exist_ok=True)
    (project_dir / "decisions").mkdir(exist_ok=True)
    (project_dir / "retros").mkdir(exist_ok=True)

    (project_dir / "brief.md").write_text(
        f"# {name}\n\n## CEO Brief\n\n{brief.strip()}\n", encoding="utf-8"
    )

    manifest = {
        "project_id": project_id,
        "name": name.strip(),
        "ceo_brief": brief.strip(),
        "workspace_path": workspace_path.strip(),
        "stage": "spec",
        "status": "awaiting_cto_review",
        "open_action": "cto",
        "stage_history": [{
            "stage": "spec",
            "entered_at": utc_now(),
            "from_stage": "intake",
            "note": "CEO intake accepted",
        }],
        "current_task_id": None,
        "current_epic_id": None,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    if not write_json_atomic(manifest_path(project_id), manifest):
        return None

    # Archive the intake file so we never re-consume it.
    processed = PROJECT_QUEUE_DIR / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    try:
        intake_path.replace(processed / intake_path.name)
    except Exception:
        log_error(f"Failed to archive intake {intake_path}:\n{traceback.format_exc()}")
    log(f"Accepted intake -> project {project_id} ({name}).")
    return manifest


def build_stage_prompt(manifest, stage):
    project_id = manifest["project_id"]
    project_dir = PROJECTS_DIR / project_id
    if stage["stage"] == "spec":
        return (
            f"You are the CTO. Read the CEO brief at {project_dir / 'brief.md'}. "
            f"Produce {project_dir / 'spec.md'} with sections: Vision, Scope (in/out), "
            f"Non-Goals, Risks, Stack, Acceptance Criteria. If anything is unclear, "
            f"write the questions to {project_dir / 'open_questions.md'} as a numbered "
            f"list. Before writing, query the portfolio at {PORTFOLIO_DIR} for reusable "
            f"components and reference matches in spec.md. Caveman protocol."
        )
    if stage["stage"] == "wireframe":
        return (
            f"You are Pixel. Read {project_dir / 'spec.md'} and any CEO answers in "
            f"{project_dir / 'ceo_answers.md'}. Produce low-fidelity wireframes as "
            f"Markdown ASCII boxes or SVG snippets under {project_dir / 'wireframes/'}. "
            f"One file per primary screen. Annotate every interactive element with the "
            f"event it fires. No real implementation code."
        )
    if stage["stage"] in ("poc", "mvp"):
        epic_path = project_dir / f"{stage['stage']}_epic.json"
        return (
            f"You are Linus. Read {project_dir / 'spec.md'} and the wireframes under "
            f"{project_dir / 'wireframes/'}. Produce an epic JSON array suitable for "
            f"hq_epic_manager.py at {epic_path}. Each task MUST be small (<=3 files, "
            f"<=120 LOC). Use task types from the router (frontend, backend, qa). Add "
            f"depends_on. Caveman."
        )
    if stage["stage"] == "uat":
        return (
            f"You are Kent. Verify {stage['stage'].upper()} acceptance criteria from "
            f"{project_dir / 'spec.md'}. Write failing tests first; record pass/fail in "
            f"{project_dir / 'uat_report.md'}."
        )
    if stage["stage"] == "prod":
        return (
            f"You are Grace. Promote reusable components from this project into the "
            f"portfolio at {PORTFOLIO_DIR}. For each artifact write "
            f"{PORTFOLIO_DIR}/{{slug}}/manifest.yaml with tags, language, summary, "
            f"originating_project={project_id}."
        )
    return f"Stage {stage['stage']} for project {project_id}."


def dispatch_stage_task(manifest):
    """Drop a router-compatible task for the project's current stage owner."""
    stage = current_stage_def(manifest)
    if stage is None:
        log_error(f"Project {manifest['project_id']} has unknown stage {manifest.get('stage')}.")
        return manifest

    project_id = manifest["project_id"]
    project_dir = PROJECTS_DIR / project_id
    task_id = f"{project_id}-{stage['stage']}-{uuid.uuid4().hex[:6]}"

    prompt = build_stage_prompt(manifest, stage)
    task_payload = {
        "task_id": task_id,
        "type": stage["task_type"],
        "prompt": prompt,
        "workspace_path": str(project_dir),
        "project_id": project_id,
    }

    queue_path = TASK_QUEUE_DIR / f"task_{task_id}.json"
    if not write_json_atomic(queue_path, task_payload):
        log_error(f"Failed to queue task for project {project_id}.")
        return manifest

    log(f"Dispatched {stage['stage']} task {task_id} to {stage['owner']}.")
    updated = transition(
        manifest,
        status="stage_in_progress",
        open_action=stage["owner"].lower(),
        note=f"stage {stage['stage']} dispatched as task {task_id}",
    )
    updated["current_task_id"] = task_id
    return updated


def task_status_for(task_id):
    if not task_id:
        return None
    return read_json(STATUS_DIR / f"{task_id}.json")


def handle_active_project(manifest):
    """Advance any project whose dispatched task has finished."""
    status = manifest.get("status")
    if status != "stage_in_progress":
        return manifest

    task_id = manifest.get("current_task_id")
    record = task_status_for(task_id)
    if record is None:
        return manifest

    project_id = manifest["project_id"]
    project_dir = PROJECTS_DIR / project_id
    task_status = record.get("status")
    stage = current_stage_def(manifest)

    if task_status != "success":
        log(f"Project {project_id} stage {stage['stage']} task {task_id} ended {task_status}; flagging board.")
        return transition(
            manifest,
            status="board_meeting",
            open_action="ceo",
            note=f"task {task_id} returned {task_status}",
        )

    # Spec stage may end with open questions for the CEO.
    if stage["stage"] == "spec" and (project_dir / "open_questions.md").exists():
        log(f"Project {project_id} spec produced open questions; waiting on CEO.")
        return transition(
            manifest,
            status="awaiting_ceo_answers",
            open_action="ceo",
            note="open_questions.md awaiting CEO",
        )

    log(f"Project {project_id} stage {stage['stage']} complete; awaiting CEO gate approval.")
    return transition(
        manifest,
        status="stage_pending_approval",
        open_action="ceo",
        note=f"task {task_id} success",
    )


def handle_ceo_gates(manifest):
    """Look for CEO action files that move the project forward."""
    project_id = manifest["project_id"]
    project_dir = PROJECTS_DIR / project_id
    status = manifest.get("status")

    # CEO answered open questions -> re-run spec_review with answers in context.
    if status == "awaiting_ceo_answers" and (project_dir / "ceo_answers.md").exists():
        log(f"Project {project_id} CEO answers received; re-dispatching spec_review.")
        manifest = transition(manifest, status="stage_in_progress", open_action="cto", note="CEO answers landed")
        return dispatch_stage_task(manifest)

    # CEO approved current stage -> advance to next stage and dispatch.
    if status == "stage_pending_approval" and (project_dir / "ceo_approval.flag").exists():
        try:
            (project_dir / "ceo_approval.flag").unlink()
        except Exception:
            log_error(f"Failed to consume approval flag for {project_id}:\n{traceback.format_exc()}")
        next_def = next_stage(manifest.get("stage"))
        if next_def is None:
            log(f"Project {project_id} fully shipped; marking closed.")
            return transition(manifest, stage="closed", status="closed", open_action=None, note="final stage approved")
        log(f"Project {project_id} advancing {manifest['stage']} -> {next_def['stage']}.")
        manifest = transition(
            manifest,
            stage=next_def["stage"],
            status="stage_in_progress",
            open_action=next_def["owner"].lower(),
            note=f"CEO approved transition into {next_def['stage']}",
        )
        return dispatch_stage_task(manifest)

    return manifest


def run_once():
    ensure_directories()

    # 1. Consume new intakes.
    for intake in sorted(PROJECT_QUEUE_DIR.glob("*.intake.json")):
        try:
            manifest = consume_intake(intake)
            if manifest:
                manifest = dispatch_stage_task(manifest)
                write_json_atomic(manifest_path(manifest["project_id"]), manifest)
        except Exception:
            log_error(f"Intake {intake.name} crashed:\n{traceback.format_exc()}")

    # 2. Drive active projects.
    if not PROJECTS_DIR.exists():
        return
    for project_dir in sorted(p for p in PROJECTS_DIR.iterdir() if p.is_dir()):
        manifest_file = project_dir / "manifest.json"
        manifest = read_json(manifest_file)
        if not isinstance(manifest, dict):
            continue
        try:
            advanced = handle_active_project(manifest)
            advanced = handle_ceo_gates(advanced)
        except Exception:
            log_error(f"Project {project_dir.name} crashed:\n{traceback.format_exc()}")
            continue
        if advanced != manifest:
            write_json_atomic(manifest_file, advanced)


def main():
    ensure_directories()
    log(f"Watching project queue: {PROJECT_QUEUE_DIR}")
    log(f"Projects root:          {PROJECTS_DIR}")
    log(f"Portfolio root:         {PORTFOLIO_DIR}")
    try:
        while True:
            run_once()
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        log("Shutting down.")


if __name__ == "__main__":
    main()
