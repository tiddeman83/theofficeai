#!/usr/bin/env python3
"""
HQ Router (Traffic Cop)
Phase 3b: role-based task delegation.
"""

import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv
import paho.mqtt.client as mqtt


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_ENV = SCRIPT_DIR.parent / ".env"
QUEUE_DIR = Path(os.getenv("HQ_QUEUE_DIR", SCRIPT_DIR / "task_queue"))
PROCESSED_DIR = QUEUE_DIR / "processed"
FAILED_DIR = QUEUE_DIR / "failed"

PERSONAS = {
    # Code-producing categories.
    "frontend": "Pixel",
    "backend": "Linus",
    "architecture": "Ada",
    "qa": "Kent",
    # Project-lifecycle task types. CTO challenges CEO (spec_review),
    # decomposes approved specs (decompose), Pixel scaffolds wireframes,
    # Kent gates UAT, Grace harvests reusable code into the portfolio, and
    # Ada files the board report. Retros are persona-scoped — the project
    # manager MUST set `branch_id` explicitly per persona when dispatching.
    "spec_review": "Linus",
    "decompose": "Linus",
    "wireframe": "Pixel",
    "portfolio_query": "Linus",
    "portfolio_contribute": "Grace",
    "uat": "Kent",
    "report": "Ada",
    "retro": "Ada",
}

# Per-persona MQTT topic routing. When a task is dropped without an explicit
# branch_id, the router consults this mapping to send the work to that
# persona's dedicated daemon. Personas not listed here fall back to
# DEFAULT_BRANCH_ID (currently `branch_1`, the shared generic worker).
#
# Pool routing (Phase B): a single type can map to a list of branch ids so
# the router round-robins across them. Today only Kent has a dedicated
# daemon; once Pixel-1/Pixel-2 ship we flip `wireframe` and `frontend` to
# `["branch_pixel_1", "branch_pixel_2"]` and `route_payload` picks the next
# index from `_POOL_CURSORS`.
PERSONA_TOPICS = {
    "qa": "branch_kent",
    "uat": "branch_kent",
}

_POOL_CURSORS = {}


if not ROOT_ENV.exists():
    print(f"[HQ Router] Error: Root .env file not found at {ROOT_ENV}", file=sys.stderr)
    sys.exit(1)

load_dotenv(dotenv_path=ROOT_ENV)

BROKER_IP = os.getenv("MQTT_BROKER_IP")
BROKER_PORT_STR = os.getenv("MQTT_PORT", "1883")
USERNAME = os.getenv("MQTT_USER")
PASSWORD = os.getenv("MQTT_PASSWORD")
DEFAULT_BRANCH_ID = os.getenv("BRANCH_ID", "branch_1")
DEFAULT_REPO_PATH = os.getenv("DEFAULT_REPO_PATH", ".")
DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TASK_TIMEOUT", "300"))

if not BROKER_IP:
    print("[HQ Router] Error: MQTT_BROKER_IP not set in environment.", file=sys.stderr)
    sys.exit(1)

try:
    BROKER_PORT = int(BROKER_PORT_STR)
except ValueError:
    print(f"[HQ Router] Error: Invalid MQTT_PORT '{BROKER_PORT_STR}'.", file=sys.stderr)
    sys.exit(1)


def build_client():
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION1)
    except ImportError:
        client = mqtt.Client()
    if USERNAME or PASSWORD:
        client.username_pw_set(USERNAME, PASSWORD)
    return client


def validate_task(task):
    if not isinstance(task, dict):
        raise ValueError("task must be a JSON object.")
    task_id = require_string(task, "task_id")
    task_type = require_string(task, "type")
    prompt = require_string(task, "prompt")
    if task_type not in PERSONAS:
        raise ValueError(f"type must be one of {sorted(PERSONAS)}.")
    explicit_branch_id = task.get("branch_id")
    if explicit_branch_id is None:
        # Fall back to persona-specific topic (round-robin if pooled), or the shared default.
        mapped = PERSONA_TOPICS.get(task_type, DEFAULT_BRANCH_ID)
        if isinstance(mapped, list):
            if not mapped:
                raise ValueError(f"PERSONA_TOPICS pool for type '{task_type}' is empty.")
            cursor = _POOL_CURSORS.get(task_type, 0) % len(mapped)
            branch_id = mapped[cursor]
            _POOL_CURSORS[task_type] = cursor + 1
        else:
            branch_id = mapped
    else:
        if not isinstance(explicit_branch_id, str) or not explicit_branch_id.strip():
            raise ValueError("branch_id must be a non-empty string when provided.")
        branch_id = explicit_branch_id
    repo_path = task.get("repo_path", DEFAULT_REPO_PATH)
    if not isinstance(repo_path, str) or not repo_path.strip():
        raise ValueError("repo_path must be a non-empty string when provided.")
    timeout = task.get("timeout", DEFAULT_TIMEOUT)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1 or timeout > 300:
        raise ValueError("timeout must be an integer from 1 to 300.")
    
    workspace_path = task.get("workspace_path")
    if workspace_path is not None:
        if not isinstance(workspace_path, str) or not workspace_path.strip():
            raise ValueError("workspace_path must be a non-empty string when provided.")
        workspace_path = workspace_path.strip()

    return task_id, task_type, prompt, branch_id.strip(), repo_path.strip(), timeout, workspace_path


def require_string(task, key):
    value = task.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string.")
    return value.strip()


def route_payload(task):
    task_id, task_type, prompt, branch_id, repo_path, timeout, workspace_path = validate_task(task)
    persona = PERSONAS[task_type]
    # Caveman prelude inlined. The previous template told agents to read
    # `.ai_agency_protocols.md` which does not exist anywhere in the repo
    # and forced wasted file-search tokens at every wake. Sprint 2 will
    # replace this with persona-specific system prompts via the personas/ dir.
    instruction = (
        f"Protocol: Caveman. Zero pleasantries. Raw logic only. "
        f"Persona: {persona}. Workspace: {workspace_path or repo_path}. "
        f"Task {task_id}. Execute: {prompt}"
    )
    payload = {
        "task_id": task_id,
        "agent": persona,
        "repo_path": repo_path,
        "prompt": instruction,
        "timeout": timeout,
    }
    if workspace_path is not None:
        payload["workspace_path"] = workspace_path
    return branch_id, payload


def publish_task(client, branch_id, payload):
    topic = f"agency/tasks/{branch_id}"
    body = json.dumps(payload)
    result = client.publish(topic, body, qos=1)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"publish failed with MQTT code {result.rc}")
    print(f"[HQ Router] routed task {payload['task_id']} to {topic}")


def process_file(client, path):
    with path.open("r", encoding="utf-8") as handle:
        task = json.load(handle)
    branch_id, payload = route_payload(task)
    publish_task(client, branch_id, payload)
    move_file(path, PROCESSED_DIR)


def move_file(path, target_dir):
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name
    if target.exists():
        target = target_dir / f"{path.stem}.{int(time.time())}{path.suffix}"
    shutil.move(str(path), str(target))


def main():
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)

    client = build_client()
    try:
        client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
    except Exception:
        print(f"[HQ Router] Connection Error: Unable to connect to broker at {BROKER_IP}:{BROKER_PORT}.", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)

    client.loop_start()
    print(f"[HQ Router] Watching file queue: {QUEUE_DIR}")

    try:
        while True:
            for path in sorted(QUEUE_DIR.glob("*.json")):
                try:
                    process_file(client, path)
                except Exception:
                    print(f"[HQ Router] Failed task file {path}:\n{traceback.format_exc()}", file=sys.stderr)
                    move_file(path, FAILED_DIR)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[HQ Router] Shutting down.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
