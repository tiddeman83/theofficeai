#!/usr/bin/env bash
# stop_kent.sh
# Cleanly stops Kent's daemon and the HQ router started by start_kent.sh.

set -uo pipefail

ROUTER_PID_FILE="/tmp/the_office_router.pid"
KENT_PID_FILE="/tmp/kent_daemon.pid"

stop_one() {
    local label="$1"
    local pid_file="$2"
    if [ ! -f "$pid_file" ]; then
        echo "[skip] $label not running (no pid file at $pid_file)."
        return 0
    fi
    local pid
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
        kill -TERM "$pid" 2>/dev/null || true
        # Give it a moment to flush stdout and disconnect from MQTT.
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

stop_one "Kent" "$KENT_PID_FILE"
stop_one "HQ router" "$ROUTER_PID_FILE"
