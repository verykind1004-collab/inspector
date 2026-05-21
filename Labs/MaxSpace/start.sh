#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# MaxSpace 는 Labs/ 바로 아래. drivers 는 Labs/drivers (공용).
LABS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$LABS_DIR/drivers/python3/bin/python3"
SCRIPT="$SCRIPT_DIR/bin/tablespace_server.py"
PIDFILE="$SCRIPT_DIR/server.pid"

cd "$SCRIPT_DIR"

if [ -f "$PIDFILE" ]; then
  OLD_PID=$(cat "$PIDFILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "[TS] 이미 실행 중 (PID $OLD_PID)"
    exit 0
  fi
fi

watchdog() {
  while true; do
    $PYTHON $SCRIPT > /dev/null 2>&1
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 143 ]; then
      echo "[TS] 정상 종료 (exit $EXIT_CODE)"
      rm -f "$PIDFILE"
      exit 0
    fi
    echo "[TS] 비정상 종료 (exit $EXIT_CODE). 5초 후 재시작..."
    sleep 5
  done
}

watchdog &
echo $! > "$PIDFILE"
echo "[TS] tablespace dashboard started (PID $(cat $PIDFILE))"
