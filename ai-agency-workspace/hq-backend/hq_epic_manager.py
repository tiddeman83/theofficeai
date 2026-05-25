#!/usr/bin/env python3
"""
HQ Epic Manager (Autopilot)

Watches epic_queue/*.json for high-level epics. Each epic is a JSON array of
router-compatible task objects with an added depends_on list. Ready tasks are
dripped into task_queue for hq_router.py.
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
EPIC_QUEUE_DIR = Path(os.getenv("HQ_EPIC_QUEUE_DIR", SCRIPT_DIR / "epic_queue"))
STATE_DIR = Path(os.getenv("HQ_EPIC_STATE_DIR", EPIC_QUEUE_DIR / ".state"))
TASK_QUEUE_DIR = Path(os.getenv("HQ_QUEUE_DIR", SCRIPT_DIR / "task_queue"))
STATUS_DIR = Path(os.getenv("HQ_STATUS_DIR", SCRIPT_DIR / "status_log"))
POLL_SECONDS = 5


def log(message):
    print(f"[HQ Epic] {message}", flush=True)


def log_error(message):
    print(f"[HQ Epic] {message}", file=sys.stderr, flush=True)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def safe_name(value):
    cleaned = "".join(char if char.isalnum() or char in ("-", "_") else "-" for char in str(value))
    return cleaned.strip("-_") or "unknown"


def ensure_directories():
    for directory in (EPIC_QUEUE_DIR, STATE_DIR, TASK_QUEUE_DIR, STATUS_DIR):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except Exception:
            log_error(f"Failed to create directory {directory}:\n{traceback.format_exc()}")


def read_json_file(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        log_error(f"Failed to read JSON file {path}:\n{traceback.format_exc()}")
        return None


def write_json_atomic(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        log_error(f"Failed to create parent directory for {path}:\n{traceback.format_exc()}")
        return False

    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        tmp_path.replace(path)
        return True
    except Exception:
        log_error(f"Failed to write JSON file {path}:\n{traceback.format_exc()}")
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            log_error(f"Failed to remove temp file {tmp_path}:\n{traceback.format_exc()}")
        return False


def list_epic_files():
    try:
        return sorted(path for path in EPIC_QUEUE_DIR.glob("*.json") if path.is_file())
    except Exception:
        log_error(f"Failed to list epic queue {EPIC_QUEUE_DIR}:\n{traceback.format_exc()}")
        return []


def validate_epic(epic_path, epic):
    if not isinstance(epic, list):
        log_error(f"Epic {epic_path} ignored: root must be a JSON array.")
        return []

    tasks = []
    seen = set()
    for index, task in enumerate(epic):
        if not isinstance(task, dict):
            log_error(f"Epic {epic_path} task[{index}] ignored: task must be an object.")
            continue

        task_id = task.get("task_id")
        depends_on = task.get("depends_on")
        if not isinstance(task_id, str) or not task_id.strip():
            log_error(f"Epic {epic_path} task[{index}] ignored: task_id must be a non-empty string.")
            continue
        if not isinstance(depends_on, list) or not all(isinstance(item, str) and item.strip() for item in depends_on):
            log_error(f"Epic {epic_path} task {task_id} ignored: depends_on must be a list of task_id strings.")
            continue
        if task_id in seen:
            log_error(f"Epic {epic_path} task {task_id} ignored: duplicate task_id.")
            continue

        seen.add(task_id)
        normalized = dict(task)
        normalized["task_id"] = task_id.strip()
        normalized["depends_on"] = [item.strip() for item in depends_on]
        tasks.append(normalized)

    validate_dag(epic_path, tasks)
    return tasks


def validate_dag(epic_path, tasks):
    task_ids = {task["task_id"] for task in tasks}
    visiting = set()
    visited = set()

    def visit(task_id, path):
        if task_id in visiting:
            cycle = " -> ".join([*path, task_id])
            log_error(f"Epic {epic_path} contains dependency cycle: {cycle}.")
            return
        if task_id in visited:
            return

        visiting.add(task_id)
        task = next((item for item in tasks if item["task_id"] == task_id), None)
        if task:
            for dep_id in task["depends_on"]:
                if dep_id in task_ids:
                    visit(dep_id, [*path, task_id])
        visiting.remove(task_id)
        visited.add(task_id)

    for task in tasks:
        visit(task["task_id"], [])


def state_path_for(epic_path):
    return STATE_DIR / f"{epic_path.stem}.state.json"


def path_exists(path):
    try:
        return path.exists()
    except Exception:
        log_error(f"Failed to check path {path}:\n{traceback.format_exc()}")
        return False


def load_state(epic_path):
    state_path = state_path_for(epic_path)
    if not path_exists(state_path):
        return {"epic_file": epic_path.name, "dispatched": {}, "errors": []}

    state = read_json_file(state_path)
    if not isinstance(state, dict):
        return {"epic_file": epic_path.name, "dispatched": {}, "errors": []}
    if not isinstance(state.get("dispatched"), dict):
        state["dispatched"] = {}
    if not isinstance(state.get("errors"), list):
        state["errors"] = []
    state["epic_file"] = epic_path.name
    return state


def save_state(epic_path, state):
    state["updated_at"] = utc_now()
    return write_json_atomic(state_path_for(epic_path), state)


def load_successful_statuses():
    successful = {}
    try:
        status_files = sorted(path for path in STATUS_DIR.glob("*.json") if path.is_file())
    except Exception:
        log_error(f"Failed to list status log {STATUS_DIR}:\n{traceback.format_exc()}")
        return successful

    for status_path in status_files:
        record = read_json_file(status_path)
        if not isinstance(record, dict):
            continue
        task_id = record.get("task_id")
        status = record.get("status")
        if isinstance(task_id, str) and status == "success":
            successful[task_id] = record
    return successful


def dependencies_cleared(task, successful_statuses):
    return [task_id for task_id in task["depends_on"] if task_id not in successful_statuses]


def received_at_sort_key(record):
    received_at = record.get("received_at")
    if not isinstance(received_at, str) or not received_at.strip():
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(received_at.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def latest_dependency_branch(task, successful_statuses):
    dependency_records = [
        successful_statuses[task_id]
        for task_id in task["depends_on"]
        if task_id in successful_statuses
    ]
    if not dependency_records:
        return None

    latest_record = max(dependency_records, key=received_at_sort_key)
    branch_name = latest_record.get("branch_name")
    if isinstance(branch_name, str) and branch_name.strip():
        return branch_name.strip()
    return None


def task_payload(task, successful_statuses):
    payload = dict(task)
    payload.pop("depends_on", None)
    base_branch = latest_dependency_branch(task, successful_statuses)
    if base_branch:
        payload["base_branch"] = base_branch
    return payload


def dispatch_task(epic_path, task, state, successful_statuses):
    task_id = task["task_id"]
    dispatch_record = {
        "task_id": task_id,
        "state": "dispatched",
        "queued_at": utc_now(),
    }
    state["dispatched"][task_id] = dispatch_record
    if not save_state(epic_path, state):
        log_error(f"Task {task_id} not queued: failed to persist dispatch state.")
        return

    queue_path = TASK_QUEUE_DIR / f"task_{safe_name(task_id)}.json"
    if write_json_atomic(queue_path, task_payload(task, successful_statuses)):
        log(f"Dispatched {task_id} from {epic_path.name} to {queue_path.name}.")
        return

    dispatch_record["state"] = "queue_write_failed"
    dispatch_record["error_at"] = utc_now()
    state["errors"].append({
        "task_id": task_id,
        "error": "queue_write_failed",
        "at": utc_now(),
    })
    save_state(epic_path, state)


def process_epic(epic_path, successful_statuses):
    epic = read_json_file(epic_path)
    tasks = validate_epic(epic_path, epic)
    if not tasks:
        return

    state = load_state(epic_path)
    dispatched = state.get("dispatched", {})
    for task in tasks:
        task_id = task["task_id"]
        if task_id in dispatched:
            continue

        pending = dependencies_cleared(task, successful_statuses)
        if pending:
            continue

        dispatch_task(epic_path, task, state, successful_statuses)


def run_once():
    ensure_directories()
    successful_statuses = load_successful_statuses()
    for epic_path in list_epic_files():
        try:
            process_epic(epic_path, successful_statuses)
        except Exception:
            log_error(f"Failed to process epic {epic_path}:\n{traceback.format_exc()}")


def main():
    ensure_directories()
    log(f"Watching epic queue: {EPIC_QUEUE_DIR}")
    log(f"Polling status log: {STATUS_DIR}")
    try:
        while True:
            run_once()
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        log("Shutting down.")


if __name__ == "__main__":
    main()
