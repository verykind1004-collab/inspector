#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$SCRIPT_DIR/server.pid"

if [ ! -f "$PIDFILE" ]; then
  echo "[TS] PID 파일 없음. 이미 종료된 상태."
  exit 0
fi

WATCHDOG_PID=$(cat "$PIDFILE")
echo "[TS] watchdog PID $WATCHDOG_PID 종료..."
kill "$WATCHDOG_PID" 2>/dev/null || true

CHILD_PIDS=$(pgrep -P "$WATCHDOG_PID" 2>/dev/null || true)
if [ -n "$CHILD_PIDS" ]; then
  kill $CHILD_PIDS 2>/dev/null || true
fi

pkill -f "$SCRIPT_DIR/bin/tablespace_server.py" 2>/dev/null || true

rm -f "$PIDFILE"
echo "[TS] tablespace dashboard stopped."
