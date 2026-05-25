#!/usr/bin/env python3
"""
HQ Issue Listener
Mirrors hq_status_listener.py architecture. Subscribes agency/issues/#.
Persists each issue to projects/{project_id}/issues/{issue_id}.json
and appends to _history.jsonl.
If severity==block and requires==cto, flips manifest to board_meeting.
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import paho.mqtt.client as mqtt


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_ENV = SCRIPT_DIR.parent / ".env"
PROJECTS_DIR = Path(os.getenv("HQ_PROJECTS_DIR", SCRIPT_DIR / "projects"))
ISSUES_TOPIC = "agency/issues/#"
CLIENT_ID = "hq_issue_listener"

VALID_SEVERITIES = {"info", "question", "block"}
VALID_REQUIRES = {"ceo", "cto"}

# Path traversal: only allow alnum, dash, underscore.
_SAFE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


if not ROOT_ENV.exists():
    print(f"[HQ Issue] Error: Root .env file not found at {ROOT_ENV}", file=sys.stderr)
    sys.exit(1)

load_dotenv(dotenv_path=ROOT_ENV)

BROKER_IP = os.getenv("MQTT_BROKER_IP")
BROKER_PORT_STR = os.getenv("MQTT_PORT", "1883")
USERNAME = os.getenv("MQTT_USER")
PASSWORD = os.getenv("MQTT_PASSWORD")

if not BROKER_IP:
    print("[HQ Issue] Error: MQTT_BROKER_IP not set in environment.", file=sys.stderr)
    sys.exit(1)

try:
    BROKER_PORT = int(BROKER_PORT_STR)
except ValueError:
    print(f"[HQ Issue] Error: Invalid MQTT_PORT '{BROKER_PORT_STR}'.", file=sys.stderr)
    sys.exit(1)


def build_client():
    # clean_session=False: broker queues QoS-1 messages while listener is briefly down.
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION1,
            client_id=CLIENT_ID,
            clean_session=False,
        )
    except ImportError:
        client = mqtt.Client(client_id=CLIENT_ID, clean_session=False)
    if USERNAME or PASSWORD:
        client.username_pw_set(USERNAME, PASSWORD)
    return client


def safe_component(value):
    """Strip any character not in [alnum/-/_]. Reject empty result — path traversal guard."""
    cleaned = "".join(c for c in str(value) if c in _SAFE_CHARS)
    return cleaned or None


def project_from_topic(topic):
    # agency/issues/{project_id}
    parts = topic.split("/")
    return parts[-1] if len(parts) >= 3 else ""


def persist_issue(record):
    """Write issue JSON and append history. Pure function — no MQTT side-effects."""
    project_id = safe_component(record.get("project_id", ""))
    issue_id = safe_component(record.get("issue_id", ""))

    if not project_id:
        print(f"[HQ Issue] Rejected: unsafe project_id '{record.get('project_id')}'", file=sys.stderr)
        return
    if not issue_id:
        print(f"[HQ Issue] Rejected: unsafe issue_id '{record.get('issue_id')}'", file=sys.stderr)
        return

    issues_dir = PROJECTS_DIR / project_id / "issues"
    issues_dir.mkdir(parents=True, exist_ok=True)

    body = json.dumps(record, indent=2)
    issue_path = issues_dir / f"{issue_id}.json"
    tmp_path = issue_path.with_suffix(".json.tmp")
    tmp_path.write_text(body, encoding="utf-8")
    tmp_path.replace(issue_path)  # atomic-ish swap

    history_path = issues_dir / "_history.jsonl"
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")

    print(f"[HQ Issue] persisted project={project_id} issue={issue_id} severity={record.get('severity')} requires={record.get('requires')}")

    # CTO blocker triggers board meeting.
    if record.get("severity") == "block" and record.get("requires") == "cto":
        _flip_manifest_to_board_meeting(project_id, issue_id)


def _flip_manifest_to_board_meeting(project_id, issue_id):
    manifest_path = PROJECTS_DIR / project_id / "manifest.json"
    if not manifest_path.exists():
        print(f"[HQ Issue] WARNING: no manifest for project {project_id}; issue persisted but manifest unchanged.", file=sys.stderr)
        return

    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            old = json.load(handle)
    except Exception:
        print(f"[HQ Issue] Failed to read manifest:\n{traceback.format_exc()}", file=sys.stderr)
        return

    if not isinstance(old, dict):
        print(f"[HQ Issue] Manifest for {project_id} is not a JSON object; skipping flip.", file=sys.stderr)
        return

    # Immutable: build a new dict, never mutate old.
    history = list(old.get("stage_history", []))
    history.append({
        "stage": old.get("stage"),
        "entered_at": datetime.now(timezone.utc).isoformat(),
        "from_stage": old.get("stage"),
        "note": f"issue {issue_id} requested board meeting",
    })

    updated = {**old,
               "status": "board_meeting",
               "open_action": "ceo",
               "updated_at": datetime.now(timezone.utc).isoformat(),
               "stage_history": history}

    tmp = manifest_path.with_name(f".{manifest_path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(updated, handle, indent=2)
            handle.write("\n")
        tmp.replace(manifest_path)
        print(f"[HQ Issue] Manifest {project_id} flipped to board_meeting (issue {issue_id}).")
    except Exception:
        print(f"[HQ Issue] Failed to write manifest:\n{traceback.format_exc()}", file=sys.stderr)
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[HQ Issue] Connected to broker.")
        client.subscribe(ISSUES_TOPIC, qos=1)
        print(f"[HQ Issue] Subscribed to {ISSUES_TOPIC}. Awaiting issues...")
    else:
        print(f"[HQ Issue] Connection failed with code {rc}.", file=sys.stderr)
        os._exit(1)


def on_message(client, userdata, msg):
    raw = msg.payload.decode("utf-8", errors="replace")
    project_id_from_topic = project_from_topic(msg.topic)
    received_at = datetime.now(timezone.utc).isoformat()

    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("payload is not a JSON object")
    except (json.JSONDecodeError, ValueError):
        print(f"[HQ Issue] {project_id_from_topic} non-issue payload: {raw.strip()[:120]}")
        return

    record = {**data, "received_at": received_at}

    try:
        persist_issue(record)
    except Exception:
        print(f"[HQ Issue] Failed to persist issue:\n{traceback.format_exc()}", file=sys.stderr)


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"[HQ Issue] Unexpected disconnect (code {rc}). Reconnecting...", file=sys.stderr)


def main():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    client = build_client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    try:
        client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
    except Exception:
        print(f"[HQ Issue] Connection Error: cannot reach broker at {BROKER_IP}:{BROKER_PORT}.", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)

    print(f"[HQ Issue] Persisting issues to: {PROJECTS_DIR}")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[HQ Issue] Shutting down.")
        client.disconnect()


if __name__ == "__main__":
    main()
