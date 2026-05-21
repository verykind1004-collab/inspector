#!/usr/bin/env bash
# python-utils/stop.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PID_FILE="$SCRIPT_DIR/log/python_utils.pid"

# Resolve Python (Labs/drivers, 공용)
STANDALONE_PY="$LABS_DIR/drivers/python3/bin/python3"
if [ -f "$STANDALONE_PY" ]; then
    PYTHON_BIN="$STANDALONE_PY"
else
    PYTHON_BIN="$(command -v python3 || command -v python2 || command -v python || true)"
fi

# Read port from config.yaml
PORT="$("$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
import config_loader
cfg = config_loader.load()
print(config_loader.get_utils_port(cfg))
" 2>/dev/null || echo "8083")"

if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE")"
    if kill -0 "$PID" 2>/dev/null; then
        echo "[python-utils] stopping... (PID: $PID)"
        kill "$PID"
        sleep 2
        kill -9 "$PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
fi

# Force-kill anything still holding the port
P_PID="$(lsof -t -i:"$PORT" 2>/dev/null || true)"
if [ -n "$P_PID" ]; then
    echo "[python-utils] force-killing process on port $PORT (PID: $P_PID)"
    kill -9 "$P_PID" 2>/dev/null || true
fi

echo "[python-utils] stopped."
