#!/usr/bin/env python3
"""
Branch Daemon (The Listener)
Phase 3b: Policy Enforcement and Git Synchronization.
"""

import os
import sys
import time
import json
import subprocess
import traceback
import re
from pathlib import Path
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

# The Regex Bouncer strict blocklist
BLOCKLIST_PATTERNS = [
    # System commands: rm, mv, chmod, chown, kill, sudo
    r"\brm\b",
    r"\bmv\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"\bkill\b",
    r"\bsudo\b",
    # Network calls: curl, wget, ssh
    r"\bcurl\b",
    r"\bwget\b",
    r"\bssh\b",
    # Package managers: npm install, pip install
    r"\bnpm\s+install\b",
    r"\bpip\s+install\b"
]

def check_bouncer_security(text):
    """
    Scans a string against the strict blocklist patterns to prevent dangerous command execution.
    Returns (True, pattern) if a blocked pattern is matched, otherwise (False, None).
    """
    if not text:
        return False, None
    for pattern in BLOCKLIST_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, pattern
    return False, None

# 1. Load credentials from the root .env file
script_dir = Path(__file__).resolve().parent
root_env = script_dir.parent / ".env"

if not root_env.exists():
    print(f"[Branch Daemon] Error: Root .env file not found at {root_env}", file=sys.stderr)
    print("[Branch Daemon] Please run scaffolding and ensure .env is created.", file=sys.stderr)
    sys.exit(1)

load_dotenv(dotenv_path=root_env)

# Retrieve configuration parameters
broker_ip = os.getenv("MQTT_BROKER_IP")
broker_port_str = os.getenv("MQTT_PORT", "1883")
username = os.getenv("MQTT_USER")
password = os.getenv("MQTT_PASSWORD")

# Hardcoded Directory Jail
WORKSPACE_DIR = Path("/ai-agency-workspace/sandbox")
DEFAULT_TIMEOUT_SECONDS = 300
MAX_TIMEOUT_SECONDS = 300
BRANCH_ID = os.getenv("BRANCH_ID", "branch_1")

# Basic validation
if not broker_ip:
    print("[Branch Daemon] Error: MQTT_BROKER_IP not set in environment.", file=sys.stderr)
    sys.exit(1)

try:
    broker_port = int(broker_port_str)
except ValueError:
    print(f"[Branch Daemon] Error: Invalid MQTT_PORT '{broker_port_str}'. Must be an integer.", file=sys.stderr)
    sys.exit(1)

# Callback signatures for MQTT v1 API
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[Branch Daemon] Successfully connected to MQTT Broker!")
        topic = f"agency/tasks/{BRANCH_ID}"
        client.subscribe(topic, qos=1)
        print(f"[Branch Daemon] Subscribed to topic: {topic}")
        print("[Branch Daemon] Standing by and listening for jailed tasks...")
    else:
        print(f"[Branch Daemon] Connection failed with code {rc}", file=sys.stderr)
        if rc == 1:
            print("[Branch Daemon] Error: Incorrect protocol version.", file=sys.stderr)
        elif rc == 2:
            print("[Branch Daemon] Error: Invalid client identifier.", file=sys.stderr)
        elif rc == 3:
            print("[Branch Daemon] Error: Server unavailable.", file=sys.stderr)
        elif rc == 4:
            print("[Branch Daemon] Error: Bad username or password.", file=sys.stderr)
        elif rc == 5:
            print("[Branch Daemon] Error: Not authorized.", file=sys.stderr)
        # Terminate script on authentication/connection setup failure
        os._exit(1)

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"[Branch Daemon] WARNING: Unexpected disconnection (code {rc}). Reconnecting...", file=sys.stderr)

def on_message(client, userdata, msg):
    response_topic = f"agency/status/{BRANCH_ID}"
    task_id = "unknown"

    try:
        payload = msg.payload.decode('utf-8')
    except Exception:
        payload = ""
        error = traceback.format_exc()
        publish_response(client, response_topic, {
            "task_id": task_id,
            "status": "error",
            "stdout": "",
            "stderr": error,
            "returncode": None
        })
        return

    print(f"\n[Branch Daemon] >>> Received payload on [{msg.topic}]: {payload}")
    
    # Check for backward-compatible heartbeat PING
    if payload.strip().upper() == "PING":
        response_payload = f"PONG: {BRANCH_ID} is alive"
        print(f"[Branch Daemon] <<< Publishing heartbeat response: '{response_payload}' to [{response_topic}]")
        client.publish(response_topic, response_payload, qos=1)
        return

    try:
        task = parse_task_payload(payload)
        task_id = task["task_id"]
    except ValueError as e:
        publish_response(client, response_topic, build_response(task_id, "rejected", stderr=str(e)))
        return

    command = task.get("command")
    if not command:
        publish_response(client, response_topic, build_response(task_id, "accepted"))
        return

    print(f"[Branch Daemon] Executing task [{task_id}] command in jail '{task['repo_path']}'")

    try:
        response_payload = execute_task_with_git(task)
    except subprocess.TimeoutExpired as e:
        print(f"[Branch Daemon] Command timed out after {task['timeout']} seconds", file=sys.stderr)
        reset_git_branch(task["repo_path"], task_id)
        response_payload = build_response(
            task_id,
            "timeout_error",
            stdout=e.stdout or "",
            stderr=(e.stderr or "") + f"\nCommand execution timed out after {task['timeout']} seconds.",
            repo_path=task["repo_path"]
        )
    except Exception:
        error = traceback.format_exc()
        print(f"[Branch Daemon] Exception while executing command:\n{error}", file=sys.stderr)
        response_payload = build_response(task_id, "error", stderr=error, repo_path=task["repo_path"])

    publish_response(client, response_topic, response_payload)

def execute_task_with_git(task):
    repo_path = task["repo_path"]
    task_id = task["task_id"]
    branch_name = build_task_branch_name(task_id)

    # Step 1: The Regex Bouncer Check
    prompt = task.get("prompt", "")
    command = task.get("command", "")
    is_blocked, pattern = check_bouncer_security(prompt)
    if not is_blocked and not prompt:
        is_blocked, pattern = check_bouncer_security(command)
        
    if is_blocked:
        print(f"[Branch Daemon] SECURITY VIOLATION: Task [{task_id}] contains forbidden pattern '{pattern}'. Aborting.", file=sys.stderr)
        return build_response(
            task_id,
            "security_error",
            stdout="",
            stderr=f"Security Error: Bouncer blocklist violation. Input prompt/command contains forbidden pattern: '{pattern}'",
            repo_path=repo_path,
            branch_name=branch_name
        )

    try:
        if git_has_changes(repo_path):
            raise GitCommandError(["status", "--porcelain"], "", "working tree is dirty before task start", 1)
        run_git(repo_path, ["fetch", "origin"])
        run_git(repo_path, ["checkout", "-b", branch_name])
    except GitCommandError as exc:
        abort_git_branch(repo_path, task_id)
        return build_git_error_response(task_id, exc, repo_path, branch_name)

    try:
        result = subprocess.run(
            task["command"],
            shell=True,
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=task["timeout"],
            stdin=subprocess.DEVNULL
        )
    except Exception:
        abort_git_branch(repo_path, task_id)
        raise

    if result.returncode != 0:
        abort_git_branch(repo_path, task_id)
        return build_response(
            task_id,
            "error",
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            repo_path=repo_path,
            branch_name=branch_name
        )

    try:
        run_git(repo_path, ["add", "."])
        run_git(repo_path, ["commit", "-m", f"Caveman auto-commit: Task {task_id}"])
        run_git(repo_path, ["push", "origin", branch_name])
    except GitCommandError as exc:
        abort_git_branch(repo_path, task_id)
        return build_git_error_response(task_id, exc, repo_path, branch_name)

    return build_response(
        task_id,
        "success",
        stdout="",
        stderr=result.stderr,
        returncode=result.returncode,
        repo_path=repo_path,
        branch_name=branch_name,
        file_changes=True
    )

def parse_task_payload(payload):
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Payload must be a JSON object.")

    legacy_keys = {"task_id", "command"}
    task_keys = {"task_id", "agent", "repo_path", "prompt", "timeout"}
    actual_keys = set(data.keys())
    if actual_keys == legacy_keys:
        command = data["command"]
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string.")
        if "../" in command:
            raise ValueError("command rejected: directory traversal marker '../' is forbidden.")
        return {
            "task_id": validate_non_empty_string(data["task_id"], "task_id"),
            "agent": "legacy",
            "repo_path": ensure_workspace_dir(WORKSPACE_DIR),
            "prompt": "",
            "timeout": DEFAULT_TIMEOUT_SECONDS,
            "command": command,
        }

    if actual_keys != task_keys:
        raise ValueError(f"Payload keys must be exactly {sorted(task_keys)}.")

    timeout = data["timeout"]
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        raise ValueError("timeout must be an integer number of seconds.")
    if timeout < 1 or timeout > MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout must be between 1 and {MAX_TIMEOUT_SECONDS} seconds.")

    task_id = validate_non_empty_string(data["task_id"], "task_id")
    agent = validate_non_empty_string(data["agent"], "agent")
    prompt = validate_non_empty_string(data["prompt"], "prompt")
    repo_path = resolve_jailed_path(validate_non_empty_string(data["repo_path"], "repo_path"))
    return {
        "task_id": task_id,
        "agent": agent,
        "repo_path": repo_path,
        "prompt": prompt,
        "timeout": timeout,
        "command": build_agent_command(agent, prompt),
    }

def validate_non_empty_string(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()

def ensure_workspace_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    return str(path.resolve())

def resolve_jailed_path(repo_path):
    workspace = WORKSPACE_DIR.resolve()
    candidate = Path(repo_path)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("repo_path rejected: path escapes WORKSPACE_DIR jail.") from exc
    resolved.mkdir(parents=True, exist_ok=True)
    return str(resolved)

def build_response(
    task_id,
    status,
    stdout="",
    stderr="",
    returncode=None,
    repo_path=None,
    branch_name=None,
    file_changes=False,
):
    response = {
        "task_id": task_id,
        "status": status,
        "branch_name": branch_name or get_branch_name(repo_path),
        "commit_hash": get_commit_hash(repo_path),
        "stdout": stdout,
        "stderr": stderr,
        "returncode": returncode,
    }
    if file_changes:
        response["file_changes"] = True
    return response

def get_branch_name(repo_path):
    if not repo_path:
        return os.getenv("BRANCH_NAME") or BRANCH_ID
    current_branch = get_current_branch(repo_path)
    return current_branch or os.getenv("BRANCH_NAME") or BRANCH_ID

def build_task_branch_name(task_id):
    safe_task_id = "".join(char if char.isalnum() or char in ("-", "_") else "-" for char in task_id)
    return f"feature/task_{safe_task_id}"

def build_agent_command(agent, prompt):
    lower_agent = agent.lower()
    quoted_prompt = json.dumps(prompt)
    
    # Step 2: Inject safety flags (cost limit and terminal command execution disable / restriction)
    safety_flags = "--max-cost 0.50 --permission-mode acceptEdits"
    
    if "pixel" in lower_agent or "gemini" in lower_agent:
        # Pixel uses Gemini CLI. 
        # Step 3: Append headless flag after safety flags
        headless_flag = "--yolo"
        return f"gemini --skip-trust {safety_flags} {headless_flag} -p {quoted_prompt}"
        
    if "ada" in lower_agent or "claude" in lower_agent:
        # Ada uses Claude Code CLI.
        # Step 3: Append headless flag after safety flags
        headless_flag = "--dangerously-skip-permissions"
        return f"claude {safety_flags} {headless_flag} -p {quoted_prompt}"
        
    # Linus / Codex: run Codex
    # Step 3: Append headless flag after safety flags
    headless_flag = "--dangerously-bypass-approvals-and-sandbox"
    return f"codex exec {safety_flags} {headless_flag} {quoted_prompt}"

class GitCommandError(Exception):
    def __init__(self, command, stdout, stderr, returncode):
        super().__init__(f"git {' '.join(command)} failed with return code {returncode}")
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

def run_git(repo_path, args, check=True):
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=repo_path,
        timeout=60,
        check=False,
    )
    if check and result.returncode != 0:
        raise GitCommandError(args, result.stdout, result.stderr, result.returncode)
    return result

def get_current_branch(repo_path):
    if not repo_path:
        return None
    try:
        result = run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None

def git_has_changes(repo_path):
    result = run_git(repo_path, ["status", "--porcelain"])
    return bool(result.stdout.strip())

def abort_git_branch(repo_path, task_id):
    branch_name = build_task_branch_name(task_id)
    try:
        checkout_main = run_git(repo_path, ["checkout", "main"], check=False)
        if checkout_main.returncode != 0:
            run_git(repo_path, ["reset", "--hard"], check=False)
            run_git(repo_path, ["clean", "-fd"], check=False)
            run_git(repo_path, ["checkout", "main"], check=False)
        run_git(repo_path, ["branch", "-D", branch_name], check=False)
    except Exception:
        print(f"[Branch Daemon] Failed to abort branch {branch_name}:\n{traceback.format_exc()}", file=sys.stderr)

def reset_git_branch(repo_path, task_id, original_branch=None):
    abort_git_branch(repo_path, task_id)

def build_git_error_response(task_id, error, repo_path, branch_name):
    stderr = error.stderr or str(error)
    if error.stdout:
        stderr = f"{stderr}\n{error.stdout}".strip()
    return build_response(
        task_id,
        "git_error",
        stdout="",
        stderr=stderr,
        returncode=error.returncode,
        repo_path=repo_path,
        branch_name=branch_name
    )

def get_commit_hash(repo_path):
    if not repo_path:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None

def publish_response(client, response_topic, response_payload):
    try:
        response_json = json.dumps(response_payload)
        print(f"[Branch Daemon] <<< Publishing JSON response to [{response_topic}]: {response_json}")
        result = client.publish(response_topic, response_json, qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[Branch Daemon] Publish failed with MQTT code {result.rc}", file=sys.stderr)
    except Exception:
        print(f"[Branch Daemon] Fatal publish exception:\n{traceback.format_exc()}", file=sys.stderr)

def main():
    print(f"[Branch Daemon] Initializing Node Client (CLI Bridge Phase)...")
    print(f"[Branch Daemon] Target Broker: {broker_ip}:{broker_port}")
    print(f"[Branch Daemon] Target User: {username}")

    # Initialize client supporting both paho-mqtt v1.x and v2.x
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION1)
    except ImportError:
        # Fallback for old paho-mqtt versions (< 2.0.0)
        client = mqtt.Client()

    # Assign credentials if specified
    if username or password:
        client.username_pw_set(username, password)

    # Assign callback hooks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Connect to the MQTT broker
    try:
        client.connect(broker_ip, broker_port, keepalive=60)
    except Exception as e:
        print(f"[Branch Daemon] Connection Error: Unable to connect to broker at {broker_ip}:{broker_port}.", file=sys.stderr)
        print(f"[Branch Daemon] Details: {e}", file=sys.stderr)
        sys.exit(1)

    # continuous loop listening for messages
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[Branch Daemon] Shutting down branch worker gracefully. Goodbye!")
        client.disconnect()
        sys.exit(0)

if __name__ == "__main__":
    main()
