#!/usr/bin/env bash
# start_hq_daemons.sh
# Boots the HQ-side daemons that drive the project lifecycle:
#   hq_router            task_queue/*.json -> agency/tasks/{branch}
#   hq_epic_manager      epic_queue/*.json -> task_queue/*.json (DAG dripper)
#   hq_project_manager   project_queue/*.intake.json -> projects/{id}/manifest.json -> task_queue
#   hq_status_listener   agency/status/# -> status_log/*.json
#   hq_issue_listener    agency/issues/# -> projects/{id}/issues/*.json
#
# Run:   bash hq-backend/start_hq_daemons.sh
# Stop:  bash hq-backend/stop_hq_daemons.sh
# Tail:  tail -f /tmp/the_office_*.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$WORKSPACE/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "[ERROR] venv python not found at $PYTHON. Run python -m venv .venv && .venv/bin/pip install -r branch-daemon/requirements.txt in $WORKSPACE."
    exit 1
fi

is_running() {
    local pid_file="$1"
    [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

launch() {
    local label="$1"
    local script="$2"
    local pid_file="/tmp/the_office_${label}.pid"
    local log_file="/tmp/the_office_${label}.log"

    if is_running "$pid_file"; then
        echo "[skip] $label already running (pid $(cat "$pid_file"))."
        return 0
    fi
    cd "$WORKSPACE"
    nohup env PYTHONUNBUFFERED=1 "$PYTHON" "$script" > "$log_file" 2>&1 &
    local pid=$!
    echo "$pid" > "$pid_file"
    sleep 2
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "[FAIL] $label crashed on startup. Last log lines:"
        tail -20 "$log_file"
        rm -f "$pid_file"
        return 1
    fi
    echo "[OK] $label pid=$pid log=$log_file"
}

launch router          hq-backend/hq_router.py
launch epic_manager    hq-backend/hq_epic_manager.py
launch project_manager hq-backend/hq_project_manager.py
launch status_listener hq-backend/hq_status_listener.py
launch issue_listener  hq-backend/hq_issue_listener.py

echo ""
echo "All HQ daemons online."
echo "Drop intakes into:      $WORKSPACE/hq-backend/project_queue/"
echo "Drop ad-hoc tasks into: $WORKSPACE/hq-backend/task_queue/"
echo "Drop epics into:        $WORKSPACE/hq-backend/epic_queue/"
