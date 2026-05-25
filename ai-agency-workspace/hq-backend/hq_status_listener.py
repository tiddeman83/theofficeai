#!/usr/bin/env python3
"""
HQ Status Listener (The Return Path)
Phase 5: closes the feedback loop.

Branch Daemons publish task results to `agency/status/{branch_id}`. Until now
nothing in HQ consumed them, so the CEO was blind to outcomes. This process
subscribes to every status topic, persists each result to disk, and prints a
terse line per event. The HQ frontend reads the persisted files.

Persistence (under hq-backend/status_log/):
  - {task_id}.json      latest status for that task (overwritten on update)
  - _history.jsonl      append-only event log (one JSON object per line)
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
STATUS_DIR = Path(os.getenv("HQ_STATUS_DIR", SCRIPT_DIR / "status_log"))
HISTORY_FILE = STATUS_DIR / "_history.jsonl"
STATUS_TOPIC = "agency/status/#"
CLIENT_ID = "hq_status_listener"


if not ROOT_ENV.exists():
    print(f"[HQ Status] Error: Root .env file not found at {ROOT_ENV}", file=sys.stderr)
    sys.exit(1)

load_dotenv(dotenv_path=ROOT_ENV)

BROKER_IP = os.getenv("MQTT_BROKER_IP")
BROKER_PORT_STR = os.getenv("MQTT_PORT", "1883")
USERNAME = os.getenv("MQTT_USER")
PASSWORD = os.getenv("MQTT_PASSWORD")

if not BROKER_IP:
    print("[HQ Status] Error: MQTT_BROKER_IP not set in environment.", file=sys.stderr)
    sys.exit(1)

try:
    BROKER_PORT = int(BROKER_PORT_STR)
except ValueError:
    print(f"[HQ Status] Error: Invalid MQTT_PORT '{BROKER_PORT_STR}'.", file=sys.stderr)
    sys.exit(1)


def build_client():
    # clean_session=False so the broker queues QoS 1 status messages for us
    # while the listener is briefly down, instead of dropping them.
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


def safe_task_id(task_id):
    cleaned = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in str(task_id))
    return cleaned or "unknown"


def branch_from_topic(topic):
    # agency/status/{branch_id}
    parts = topic.split("/")
    return parts[-1] if parts else ""


def persist_status(record):
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    body = json.dumps(record, indent=2)
    latest_path = STATUS_DIR / f"{safe_task_id(record['task_id'])}.json"
    tmp_path = latest_path.with_suffix(".json.tmp")
    tmp_path.write_text(body, encoding="utf-8")
    tmp_path.replace(latest_path)  # atomic-ish swap so the frontend never reads a half-written file
    with HISTORY_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[HQ Status] Connected to broker.")
        client.subscribe(STATUS_TOPIC, qos=1)
        print(f"[HQ Status] Subscribed to {STATUS_TOPIC}. Awaiting branch reports...")
    else:
        print(f"[HQ Status] Connection failed with code {rc}.", file=sys.stderr)
        os._exit(1)


def on_message(client, userdata, msg):
    raw = msg.payload.decode("utf-8", errors="replace")
    branch_id = branch_from_topic(msg.topic)
    received_at = datetime.now(timezone.utc).isoformat()

    # Heartbeats and any non-JSON payload are logged but not treated as task results.
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("payload is not a JSON object")
    except (json.JSONDecodeError, ValueError):
        print(f"[HQ Status] {branch_id} non-task payload: {raw.strip()[:120]}")
        return

    record = dict(data)
    record["task_id"] = data.get("task_id", "unknown")
    record["branch_id"] = branch_id
    record["received_at"] = received_at

    try:
        persist_status(record)
    except Exception:
        print(f"[HQ Status] Failed to persist status:\n{traceback.format_exc()}", file=sys.stderr)
        return

    status = record.get("status", "?")
    branch_name = record.get("branch_name", "-")
    commit = (record.get("commit_hash") or "-")[:8]
    print(f"[HQ Status] task={record['task_id']} status={status} branch={branch_name} commit={commit}")


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"[HQ Status] Unexpected disconnect (code {rc}). Reconnecting...", file=sys.stderr)


def main():
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    client = build_client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    try:
        client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
    except Exception:
        print(f"[HQ Status] Connection Error: cannot reach broker at {BROKER_IP}:{BROKER_PORT}.", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)

    print(f"[HQ Status] Persisting results to: {STATUS_DIR}")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[HQ Status] Shutting down.")
        client.disconnect()


if __name__ == "__main__":
    main()
