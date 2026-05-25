#!/usr/bin/env bash
# stop_hq_daemons.sh - paired with start_hq_daemons.sh

set -uo pipefail

stop_one() {
    local label="$1"
    local pid_file="/tmp/the_office_${label}.pid"
    if [ ! -f "$pid_file" ]; then
        echo "[skip] $label not running (no pid file at $pid_file)."
        return 0
    fi
    local pid
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
        kill -TERM "$pid" 2>/dev/null || true
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
        echo "[OK] $label stopped (was pid $pid)."
    else
        echo "[clean] $label pid $pid not alive; removing stale pid file."
    fi
    rm -f "$pid_file"
}

stop_one issue_listener
stop_one status_listener
stop_one project_manager
stop_one epic_manager
stop_one router
