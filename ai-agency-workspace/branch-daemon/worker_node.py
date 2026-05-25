#!/usr/bin/env python3
"""
Branch Daemon (The Listener)
V2: Policy enforcement, Git synchronization, and structured status reports.
"""

import os
import sys
import time
import json
import subprocess
import traceback
import re
import uuid
from datetime import datetime, timezone
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

DEFAULT_TIMEOUT_SECONDS = 300
MAX_TIMEOUT_SECONDS = 300
BRANCH_ID = os.getenv("BRANCH_ID", "branch_1")

# Per-persona workspace allowlist. Kent (QA) is locked to the sandbox folder
# so tests cannot accidentally run against a real project. Other personas
# remain unrestricted (any absolute path that passes existing checks).
KENT_SANDBOX_ROOTS = [Path.home() / "Development" / "Sandbox_TheOffice"]

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

    print(f"[Branch Daemon] Executing task [{task_id}] command in workspace '{task['workspace_path']}'")
    original_branch = get_current_branch(task["workspace_path"])

    try:
        response_payload = execute_task_with_git(task)
    except subprocess.TimeoutExpired as e:
        print(f"[Branch Daemon] Command timed out after {task['timeout']} seconds", file=sys.stderr)
        reset_git_branch(task["workspace_path"], task_id, original_branch=original_branch)
        response_payload = build_response(
            task_id,
            "timeout_error",
            stdout=e.stdout or "",
            stderr=(e.stderr or "") + f"\nCommand execution timed out after {task['timeout']} seconds.",
            repo_path=task["workspace_path"]
        )
    except Exception:
        error = traceback.format_exc()
        print(f"[Branch Daemon] Exception while executing command:\n{error}", file=sys.stderr)
        response_payload = build_response(task_id, "error", stderr=error, repo_path=task["workspace_path"])

    publish_response(client, response_topic, response_payload)

def execute_task_with_git(task):
    workspace_path = task.get("workspace_path")
    task_id = task["task_id"]
    branch_name = build_task_branch_name(task_id)
    base_branch = task.get("base_branch") or "main"
    original_branch = None

    # 1. Security Validation on workspace_path
    if not workspace_path:
        return build_response(
            task_id,
            "security_error",
            stdout="",
            stderr="Security Error: workspace_path is missing in task payload.",
            repo_path=None,
            branch_name=branch_name
        )

    workspace_path_obj = Path(workspace_path)
    if not workspace_path_obj.is_absolute():
        print(f"[Branch Daemon] SECURITY VIOLATION: Task [{task_id}] workspace_path is relative: '{workspace_path}'. Aborting.", file=sys.stderr)
        return build_response(
            task_id,
            "security_error",
            stdout="",
            stderr=f"Security Error: workspace_path must be an absolute path. Got: '{workspace_path}'",
            repo_path=workspace_path,
            branch_name=branch_name
        )

    if not workspace_path_obj.exists() or not workspace_path_obj.is_dir():
        print(f"[Branch Daemon] SECURITY VIOLATION: Task [{task_id}] workspace_path does not exist or is not a directory: '{workspace_path}'. Aborting.", file=sys.stderr)
        return build_response(
            task_id,
            "security_error",
            stdout="",
            stderr=f"Security Error: workspace_path directory does not exist. Got: '{workspace_path}'",
            repo_path=workspace_path,
            branch_name=branch_name
        )

    resolved_workspace = workspace_path_obj.resolve()
    workspace_path = str(resolved_workspace)

    # Kent (QA) is restricted to the sandbox roots. Other personas pass through.
    agent_name = (task.get("agent") or "").lower()
    if "kent" in agent_name and not is_under_allowed_root(workspace_path_obj, KENT_SANDBOX_ROOTS):
        roots_repr = ", ".join(str(r) for r in KENT_SANDBOX_ROOTS)
        print(f"[Branch Daemon] SECURITY VIOLATION: Task [{task_id}] Kent target outside sandbox: '{workspace_path}'. Aborting.", file=sys.stderr)
        return build_response(
            task_id,
            "security_error",
            stdout="",
            stderr=f"Security Error: Kent (QA) workspace_path must resolve under one of [{roots_repr}]. Got: '{workspace_path}'",
            repo_path=workspace_path,
            branch_name=branch_name,
        )

    # Step 2: The Regex Bouncer Check. Both prompt and command are user-controlled
    # inputs and must both be scanned. Previous logic only checked the command
    # when prompt was empty, leaving a hole where a benign prompt paired with a
    # malicious command (legacy payload path) slipped past the bouncer.
    prompt = task.get("prompt", "")
    command = task.get("command", "")
    is_blocked, pattern = check_bouncer_security(prompt)
    if not is_blocked:
        is_blocked, pattern = check_bouncer_security(command)

    if is_blocked:
        print(f"[Branch Daemon] SECURITY VIOLATION: Task [{task_id}] contains forbidden pattern '{pattern}'. Aborting.", file=sys.stderr)
        return build_response(
            task_id,
            "security_error",
            stdout="",
            stderr=f"Security Error: Bouncer blocklist violation. Input prompt/command contains forbidden pattern: '{pattern}'",
            repo_path=workspace_path,
            branch_name=branch_name
        )

    try:
        ensure_git_repository(workspace_path)
        original_branch = get_current_branch(workspace_path)
        if not original_branch:
            raise GitCommandError(["rev-parse", "--abbrev-ref", "HEAD"], "", "could not determine current branch", 1)
        validate_git_branch_name(base_branch)
        if git_has_changes(workspace_path):
            raise GitCommandError(["status", "--porcelain"], "", "working tree is dirty before task start", 1)
        if git_branch_exists(workspace_path, branch_name):
            raise GitCommandError(["branch", "--list", branch_name], branch_name, "task branch already exists", 1)
        if task.get("base_branch"):
            run_git(workspace_path, ["fetch", "origin"])
            checkout_git_branch(workspace_path, base_branch, "base_branch")
            run_git(workspace_path, ["pull", "origin", base_branch])
        else:
            checkout_git_branch(workspace_path, "main", "default base branch")
        checkout_git_branch(workspace_path, branch_name, "task branch", create=True)
    except GitCommandError as exc:
        abort_git_branch(workspace_path, task_id, original_branch=original_branch, branch_was_created=False)
        return build_git_error_response(task_id, exc, workspace_path, branch_name)

    try:
        result = subprocess.run(
            task["command"],
            shell=True,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            timeout=task["timeout"],
            stdin=subprocess.DEVNULL
        )
    except Exception:
        abort_git_branch(workspace_path, task_id, original_branch=original_branch)
        raise

    if result.returncode != 0:
        abort_git_branch(workspace_path, task_id, original_branch=original_branch)
        return build_response(
            task_id,
            "error",
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            repo_path=workspace_path,
            branch_name=branch_name
        )

    try:
        run_git(workspace_path, ["add", "."])
        run_git(workspace_path, ["commit", "-m", f"Caveman auto-commit: Task {task_id}"])
        run_git(workspace_path, ["push", "origin", branch_name])
    except GitCommandError as exc:
        abort_git_branch(workspace_path, task_id, original_branch=original_branch)
        return build_git_error_response(task_id, exc, workspace_path, branch_name)

    return build_response(
        task_id,
        "success",
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
        repo_path=workspace_path,
        branch_name=branch_name,
        file_changes=True,
        base_branch=base_branch
    )

def parse_task_payload(payload):
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Payload must be a JSON object.")

    workspace_path = data.get("workspace_path")
    if workspace_path is not None:
        workspace_path = validate_non_empty_string(workspace_path, "workspace_path")
    base_branch = data.get("base_branch")
    if base_branch is not None:
        base_branch = validate_non_empty_string(base_branch, "base_branch")

    if "command" in data:
        command = data["command"]
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string.")
        if "../" in command:
            raise ValueError("command rejected: directory traversal marker '../' is forbidden.")
        return {
            "task_id": validate_non_empty_string(data["task_id"], "task_id"),
            "agent": "legacy",
            "repo_path": workspace_path or "",
            "prompt": "",
            "timeout": DEFAULT_TIMEOUT_SECONDS,
            "command": command,
            "workspace_path": workspace_path or "",
            "base_branch": base_branch,
        }

    required_keys = {"task_id", "agent", "repo_path", "prompt", "timeout"}
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Payload is missing required key: {key}")

    timeout = data["timeout"]
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        raise ValueError("timeout must be an integer number of seconds.")
    if timeout < 1 or timeout > MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout must be between 1 and {MAX_TIMEOUT_SECONDS} seconds.")

    task_id = validate_non_empty_string(data["task_id"], "task_id")
    agent = validate_non_empty_string(data["agent"], "agent")
    prompt = validate_non_empty_string(data["prompt"], "prompt")
    repo_path = validate_non_empty_string(data["repo_path"], "repo_path")

    # BRANCH_PERSONA lets a pool member override the routed agent so an
    # assistant (e.g. branch_donald) loads its own persona invocation instead
    # of the senior's (Linus). Router still picks the topic by task_type;
    # daemon decides which persona file to prepend.
    persona_override = os.getenv("BRANCH_PERSONA")
    if persona_override and persona_override.strip():
        agent = persona_override.strip()

    return {
        "task_id": task_id,
        "agent": agent,
        "repo_path": repo_path,
        "prompt": prompt,
        "timeout": timeout,
        "command": build_agent_command(agent, prompt),
        "workspace_path": workspace_path or "",
        "base_branch": base_branch,
    }

def validate_non_empty_string(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()

def build_response(
    task_id,
    status,
    stdout="",
    stderr="",
    returncode=None,
    repo_path=None,
    branch_name=None,
    file_changes=False,
    base_branch=None,
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
    if base_branch:
        response["base_branch"] = base_branch
    return response

def get_branch_name(repo_path):
    if not repo_path:
        return os.getenv("BRANCH_NAME") or BRANCH_ID
    current_branch = get_current_branch(repo_path)
    return current_branch or os.getenv("BRANCH_NAME") or BRANCH_ID

def build_task_branch_name(task_id):
    safe_task_id = "".join(char if char.isalnum() or char in ("-", "_") else "-" for char in task_id)
    safe_task_id = safe_task_id.strip("-_") or "unknown"
    return f"feature/task_{safe_task_id}"

def build_agent_command(agent, prompt):
    # Only documented CLI flags. Cost caps belong at the orchestrator layer,
    # not in CLI args: claude/gemini/codex don't expose --max-cost.
    lower_agent = agent.lower()
    persona_invocation = load_persona_invocation(lower_agent)
    full_prompt = (
        f"{persona_invocation}\n{prompt}" if persona_invocation else prompt
    )
    quoted_prompt = json.dumps(full_prompt)

    if "pixel" in lower_agent or "gemini" in lower_agent:
        return f"gemini --yolo -p {quoted_prompt}"

    if "ada" in lower_agent or "claude" in lower_agent:
        return f"claude --permission-mode acceptEdits -p {quoted_prompt}"

    # Linus, Kent, or any codex-bound persona.
    return f"codex exec --dangerously-bypass-approvals-and-sandbox {quoted_prompt}"


PERSONAS_DIR = Path(__file__).resolve().parent.parent / "hq-backend" / "personas"


def load_persona_invocation(lower_agent):
    """Prepend the persona's invocation prompt if one exists on disk.

    Looks for `personas/{name}/codex_invocation.md` (today Kent ships one;
    other personas can drop their own and be auto-loaded). Returns the file
    contents stripped of trailing whitespace, or empty string if absent.
    """
    if not PERSONAS_DIR.is_dir():
        return ""
    for candidate in PERSONAS_DIR.iterdir():
        if not candidate.is_dir():
            continue
        if candidate.name.lower() not in lower_agent:
            continue
        invocation = candidate / "codex_invocation.md"
        if invocation.is_file():
            try:
                return invocation.read_text(encoding="utf-8").strip()
            except Exception:
                return ""
    return ""


def is_under_allowed_root(path, roots):
    try:
        resolved = Path(path).resolve()
    except Exception:
        return False
    for root in roots:
        try:
            root_resolved = root.resolve()
        except Exception:
            continue
        if resolved == root_resolved:
            return True
        if root_resolved in resolved.parents:
            return True
    return False

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

def checkout_git_branch(repo_path, branch_name, label, create=False):
    args = ["checkout", "-b", branch_name] if create else ["checkout", branch_name]
    result = run_git(repo_path, args, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip() or f"failed to checkout {label}: {branch_name}"
        raise GitCommandError(args, result.stdout, f"failed to checkout {label} '{branch_name}': {stderr}", result.returncode)
    return result

def validate_git_branch_name(branch_name):
    if not isinstance(branch_name, str) or not branch_name.strip():
        raise GitCommandError(["check-ref-format", "--branch", str(branch_name)], "", "base_branch must be a non-empty string", 1)

    branch_name = branch_name.strip()
    if branch_name.startswith("-") or branch_name.startswith("@{"):
        raise GitCommandError(["check-ref-format", "--branch", branch_name], "", f"invalid base_branch: {branch_name}", 1)

    result = subprocess.run(
        ["git", "check-ref-format", "--branch", branch_name],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or f"invalid base_branch: {branch_name}"
        raise GitCommandError(["check-ref-format", "--branch", branch_name], result.stdout, stderr, result.returncode)

def git_has_changes(repo_path):
    result = run_git(repo_path, ["status", "--porcelain"])
    return bool(result.stdout.strip())

def ensure_git_repository(repo_path):
    result = run_git(repo_path, ["rev-parse", "--is-inside-work-tree"], check=False)
    if result.returncode != 0 or result.stdout.strip() != "true":
        stderr = "workspace is not a Git repository"
        if result.stderr:
            stderr = f"{stderr}: {result.stderr.strip()}"
        raise GitCommandError(["rev-parse", "--is-inside-work-tree"], result.stdout, stderr, result.returncode or 1)

def git_branch_exists(repo_path, branch_name):
    result = run_git(repo_path, ["branch", "--list", branch_name], check=False)
    return bool(result.stdout.strip())

def abort_git_branch(repo_path, task_id, original_branch=None, branch_was_created=True):
    branch_name = build_task_branch_name(task_id)
    target_branch = original_branch or os.getenv("DEFAULT_BASE_BRANCH", "main")
    try:
        if branch_was_created:
            run_git(repo_path, ["reset", "--hard"], check=False)
            run_git(repo_path, ["clean", "-fd"], check=False)
        checkout_base = run_git(repo_path, ["checkout", target_branch], check=False)
        if checkout_base.returncode != 0 and target_branch != "main":
            run_git(repo_path, ["checkout", "main"], check=False)
        run_git(repo_path, ["branch", "-D", branch_name], check=False)
    except Exception:
        print(f"[Branch Daemon] Failed to abort branch {branch_name}:\n{traceback.format_exc()}", file=sys.stderr)

def reset_git_branch(repo_path, task_id, original_branch=None):
    abort_git_branch(repo_path, task_id, original_branch=original_branch)

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

_VALID_SEVERITIES = {"info", "question", "block"}
_VALID_REQUIRES = {"ceo", "cto"}


def publish_issue(client, project_id, agent, task_id, severity, subject, body, requires):
    """Library function for stage-task scripts and persona prompts.

    Publishes a structured issue to agency/issues/{project_id} at QoS 1.
    Does NOT touch on_message / execute_task_with_git.
    """
    if severity not in _VALID_SEVERITIES:
        raise ValueError(f"severity must be one of {_VALID_SEVERITIES}; got '{severity}'")
    if requires not in _VALID_REQUIRES:
        raise ValueError(f"requires must be one of {_VALID_REQUIRES}; got '{requires}'")

    issue_id = f"iss-{uuid.uuid4().hex[:8]}"
    payload = {
        "issue_id": issue_id,
        "project_id": project_id,
        "from_agent": agent,
        "task_id": task_id,
        "severity": severity,
        "subject": subject,
        "body": body,
        "requires": requires,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    topic = f"agency/issues/{project_id}"
    client.publish(topic, json.dumps(payload), qos=1)
    return issue_id


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
