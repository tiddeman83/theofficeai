#!/usr/bin/env python3
"""
HQ Dispatcher (The Commander)
Phase 2: CLI Bridge implementation.
"""

import os
import sys
import time
import json
import traceback
from pathlib import Path
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

# 1. Load credentials from the root .env file
script_dir = Path(__file__).resolve().parent
root_env = script_dir.parent / ".env"

if not root_env.exists():
    print(f"[HQ Dispatcher] Error: Root .env file not found at {root_env}", file=sys.stderr)
    sys.exit(1)

load_dotenv(dotenv_path=root_env)

# Retrieve configuration parameters
broker_ip = os.getenv("MQTT_BROKER_IP")
broker_port_str = os.getenv("MQTT_PORT", "1883")
username = os.getenv("MQTT_USER")
password = os.getenv("MQTT_PASSWORD")

if not broker_ip:
    print("[HQ Dispatcher] Error: MQTT_BROKER_IP not set in environment.", file=sys.stderr)
    sys.exit(1)

try:
    broker_port = int(broker_port_str)
except ValueError:
    print(f"[HQ Dispatcher] Error: Invalid MQTT_PORT '{broker_port_str}'.", file=sys.stderr)
    sys.exit(1)

# Thread-safe variable to capture the parsed JSON response
received_response = None

# Connection Callback
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[HQ Dispatcher] Successfully connected to MQTT Broker!", file=sys.stderr)
        
        # Subscribe to agency/status/branch_1 BEFORE publishing to prevent race condition
        status_topic = "agency/status/branch_1"
        client.subscribe(status_topic, qos=1)
        print(f"[HQ Dispatcher] Subscribed to topic: {status_topic}", file=sys.stderr)
        
        # Construct JSON payload exactly as requested
        payload_data = {
            "task_id": "test_001",
            "command": "echo 'Caveman node active.' > caveman_status.txt && cat caveman_status.txt"
        }
        json_payload = json.dumps(payload_data)
        
        # Publish the JSON payload to the topic agency/tasks/branch_1
        task_topic = "agency/tasks/branch_1"
        print(f"[HQ Dispatcher] >>> Publishing CLI command task to [{task_topic}]...", file=sys.stderr)
        print(f"[HQ Dispatcher] Payload: {json_payload}", file=sys.stderr)
        publish_result = client.publish(task_topic, json_payload, qos=1)
        if publish_result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[HQ Dispatcher] Publish failed with MQTT code {publish_result.rc}", file=sys.stderr)
    else:
        print(f"[HQ Dispatcher] Connection failed with code {rc}", file=sys.stderr)
        if rc == 4:
            print("[HQ Dispatcher] Error: Bad username or password.", file=sys.stderr)
        os._exit(1)

# Message Callback
def on_message(client, userdata, msg):
    global received_response
    try:
        payload = msg.payload.decode('utf-8')
    except UnicodeDecodeError:
        payload = str(msg.payload)
    
    print(f"[HQ Dispatcher] <<< Received message response on [{msg.topic}]", file=sys.stderr)
    
    # Parse the returned JSON response
    try:
        received_response = json.loads(payload)
    except Exception:
        error = traceback.format_exc()
        print(f"[HQ Dispatcher] Error: Could not parse incoming payload as JSON:\n{error}", file=sys.stderr)
        received_response = {
            "task_id": "unknown",
            "status": "error",
            "stdout": "",
            "stderr": f"Failed to parse payload: {payload}\n{error}",
            "returncode": None
        }

def main():
    print(f"[HQ Dispatcher] Initializing Commander Client...", file=sys.stderr)
    print(f"[HQ Dispatcher] Target Broker: {broker_ip}:{broker_port}", file=sys.stderr)
    
    # Initialize client supporting both paho-mqtt v1.x and v2.x
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION1)
    except ImportError:
        client = mqtt.Client()

    # Assign credentials if specified
    if username or password:
        client.username_pw_set(username, password)

    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to the MQTT broker
    try:
        client.connect(broker_ip, broker_port, keepalive=60)
    except Exception:
        print(f"[HQ Dispatcher] Connection Error: Unable to connect to broker at {broker_ip}:{broker_port}.", file=sys.stderr)
        print(f"[HQ Dispatcher] Details:\n{traceback.format_exc()}", file=sys.stderr)
        sys.exit(1)

    # Use the background loop helper thread
    client.loop_start()

    # Wait for exactly one response with a timeout
    timeout = 15.0  # seconds
    start_time = time.time()
    print("[HQ Dispatcher] Waiting for CLI task response from Branch Daemon...", file=sys.stderr)

    try:
        while received_response is None and (time.time() - start_time) < timeout:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[HQ Dispatcher] Canceled by user.")
    
    # Stop background thread and disconnect cleanly
    client.loop_stop()
    client.disconnect()

    if received_response:
        status = received_response.get("status", "unknown")
        stdout = received_response.get("stdout", "")
        stderr = received_response.get("stderr", "")
        returncode = received_response.get("returncode")

        if stdout:
            print(stdout.rstrip())
        
        if stderr:
            print(stderr.rstrip(), file=sys.stderr)
        
        if status.lower() == "success" and returncode == 0:
            sys.exit(0)
        else:
            print(f"[HQ Dispatcher] Task failed with status={status}, returncode={returncode}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"\n[HQ Dispatcher] Error: CLI command timed out after {timeout} seconds without receiving response from Branch 1.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
