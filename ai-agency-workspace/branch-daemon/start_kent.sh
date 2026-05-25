#!/usr/bin/env bash
# start_kent.sh
# Launches Kent's persistent QA daemon (and the HQ router if it is not
# already running). Kent then sits idle in the background, subscribed to
# MQTT topic agency/tasks/branch_kent, and only wakes when a `qa` task
# is dropped into ai-agency-workspace/hq-backend/task_queue/.
#
# Run once:   bash start_kent.sh
# Take down:  bash stop_kent.sh
# Tail logs:  tail -f /tmp/kent_daemon.log /tmp/the_office_router.log

set -euo pipefail

# Script-relative so the daemon survives anyone cloning the repo under a different prefix.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$WORKSPACE/.venv/bin/python"

ROUTER_PID_FILE="/tmp/the_office_router.pid"
ROUTER_LOG_FILE="/tmp/the_office_router.log"
KENT_PID_FILE="/tmp/kent_daemon.pid"
KENT_LOG_FILE="/tmp/kent_daemon.log"

if [ ! -x "$PYTHON" ]; then
    echo "[ERROR] venv python not found at $PYTHON. Did you run 'python -m venv .venv && .venv/bin/pip install -r branch-daemon/requirements.txt' in $WORKSPACE?"
    exit 1
fi

is_running() {
    local pid_file="$1"
    [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

start_router() {
    if is_running "$ROUTER_PID_FILE"; then
        echo "[skip] HQ router already running (pid $(cat "$ROUTER_PID_FILE"))."
        return 0
    fi
    cd "$WORKSPACE"
    nohup env PYTHONUNBUFFERED=1 "$PYTHON" hq-backend/hq_router.py > "$ROUTER_LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$ROUTER_PID_FILE"
    sleep 2
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "[FAIL] HQ router crashed on startup. Last log lines:"
        tail -20 "$ROUTER_LOG_FILE"
        rm -f "$ROUTER_PID_FILE"
        return 1
    fi
    echo "[OK] HQ router online. pid=$pid log=$ROUTER_LOG_FILE"
}

start_kent() {
    if is_running "$KENT_PID_FILE"; then
        echo "[skip] Kent already running (pid $(cat "$KENT_PID_FILE")). Tail $KENT_LOG_FILE."
        return 0
    fi
    cd "$WORKSPACE"
    nohup env BRANCH_ID=branch_kent PYTHONUNBUFFERED=1 "$PYTHON" branch-daemon/worker_node.py > "$KENT_LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$KENT_PID_FILE"
    sleep 2
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "[FAIL] Kent crashed on startup. Last log lines:"
        tail -20 "$KENT_LOG_FILE"
        rm -f "$KENT_PID_FILE"
        return 1
    fi
    echo "[OK] Kent online. pid=$pid branch=branch_kent log=$KENT_LOG_FILE"
}

start_router
start_kent

echo ""
echo "Ready. Drop QA tasks into:"
echo "  $WORKSPACE/hq-backend/task_queue/"
echo "Example task is at:"
echo "  /Users/tijmenbaas/Development/TheOffice/docs/example_tasks/first_kent_qa_test.json"
