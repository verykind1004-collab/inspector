#!/usr/bin/env bash
# Inspector unified stop: python-utils + gateway (robust)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[insp] stopping python-utils..."
"$SCRIPT_DIR/python-utils/stop.sh" 2>&1 || true

echo "[insp] stopping gateway..."
NGINX_BIN="$SCRIPT_DIR/gateway/bin/nginx"
NGINX_CONF="$SCRIPT_DIR/gateway/nginx.conf"
NGINX_PID="$SCRIPT_DIR/gateway/log/nginx.pid"
NGINX_LIB="$SCRIPT_DIR/gateway/bin/lib"

if [ -f "$NGINX_BIN" ]; then
    export LD_LIBRARY_PATH="$NGINX_LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

# Try graceful shutdown first via pid file
if [ -f "$NGINX_PID" ] && [ -f "$NGINX_BIN" ] && [ -f "$NGINX_CONF" ]; then
    "$NGINX_BIN" -c "$NGINX_CONF" -s quit 2>/dev/null || true
    sleep 1
fi

# Find ALL nginx processes belonging to THIS Inspector instance
# (matches by binary path so other Inspectors are not affected)
NGINX_PIDS="$(pgrep -f "$SCRIPT_DIR/gateway/bin/nginx" 2>/dev/null || true)"

if [ -n "$NGINX_PIDS" ]; then
    echo "[insp] graceful term for nginx pids: $NGINX_PIDS"
    kill $NGINX_PIDS 2>/dev/null || true
    sleep 1
    # Force-kill any survivors
    SURVIVORS=""
    for p in $NGINX_PIDS; do
        if kill -0 "$p" 2>/dev/null; then
            SURVIVORS="$SURVIVORS $p"
        fi
    done
    if [ -n "$SURVIVORS" ]; then
        echo "[insp] force killing nginx pids:$SURVIVORS"
        kill -9 $SURVIVORS 2>/dev/null || true
    fi
fi

rm -f "$NGINX_PID"

echo "[insp] stopping MaxSpace..."
"$SCRIPT_DIR/../MaxSpace/stop.sh" 2>&1 || true

echo "[insp] all stopped."
