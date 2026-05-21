#!/usr/bin/env bash
# python-utils/start.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PID_FILE="$SCRIPT_DIR/log/python_utils.pid"
LOG_FILE="$SCRIPT_DIR/log/python_utils.log"

mkdir -p "$SCRIPT_DIR/log"

# Prefer bundled standalone Python 3 (Labs/drivers, 공용), then system
STANDALONE_PY="$LABS_DIR/drivers/python3/bin/python3"
if [ -f "$STANDALONE_PY" ]; then
    PYTHON_BIN="$STANDALONE_PY"
else
    PYTHON_BIN="$(command -v python3 || command -v python2 || command -v python || true)"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "[python-utils] Python not found."
    exit 1
fi

# Read port from config.yaml via config_loader
PORT="$("$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
import config_loader
cfg = config_loader.load()
print(config_loader.get_utils_port(cfg))
" 2>/dev/null || echo "8083")"

# 1. Check if already running by PID file
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[python-utils] already running. (PID: $(cat "$PID_FILE"))"
    exit 0
fi

# 2. Check if port is already in use
if lsof -Pi :"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "[python-utils] port $PORT is already in use. Run stop.sh first."
    exit 1
fi

echo "[python-utils] Starting... (Using: $PYTHON_BIN, port: $PORT)"
cd "$SCRIPT_DIR"
export PYTHONIOENCODING=utf-8
nohup "$PYTHON_BIN" Inspector.py > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

sleep 1
if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[python-utils] Started. (PID: $(cat "$PID_FILE") | log: $LOG_FILE)"
else
    echo "[python-utils] Failed to start. Check log: $LOG_FILE"
    exit 1
fi
