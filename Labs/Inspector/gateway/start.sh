#!/usr/bin/env bash
# gateway/start.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
LABS_DIR="$(dirname "$ROOT_DIR")"
NGINX_PID="$SCRIPT_DIR/log/nginx.pid"
NGINX_CONF="$SCRIPT_DIR/nginx.conf"
NGINX_ERR="$SCRIPT_DIR/log/nginx_error.log"

mkdir -p "$SCRIPT_DIR/log"
mkdir -p "$SCRIPT_DIR/tmp"

# Resolve nginx: prefer bundled binary, fall back to system nginx
NGINX_BIN="$SCRIPT_DIR/bin/nginx"
NGINX_LIB="$SCRIPT_DIR/bin/lib"
if [ -f "$NGINX_BIN" ]; then
    export LD_LIBRARY_PATH="$NGINX_LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
else
    NGINX_BIN="$(command -v nginx 2>/dev/null || true)"
    if [ -z "$NGINX_BIN" ]; then
        echo "[gateway] nginx not found."
        echo "          Run build-package.sh to bundle nginx, or install nginx."
        exit 1
    fi
fi

# Resolve Python: prefer bundled python3 (Labs/drivers, 공용), fall back to system
PYTHON="$LABS_DIR/drivers/python3/bin/python3"
if [ ! -f "$PYTHON" ]; then
    PYTHON="$(command -v python3 2>/dev/null || command -v python2 2>/dev/null || command -v python 2>/dev/null || true)"
fi
if [ -z "$PYTHON" ]; then
    echo "[gateway] python not found."
    exit 1
fi

# Check already running
if [ -f "$NGINX_PID" ] && kill -0 "$(cat "$NGINX_PID")" 2>/dev/null; then
    echo "[gateway] already running. (PID: $(cat "$NGINX_PID"))"
    echo "          Use reload.sh to apply config changes."
    exit 0
fi

echo "[gateway] generating nginx.conf..."
"$PYTHON" "$SCRIPT_DIR/generate_conf.py"

echo "[gateway] validating config..."
"$NGINX_BIN" -e "$NGINX_ERR" -t -c "$NGINX_CONF" 2>&1

echo "[gateway] starting nginx..."
"$NGINX_BIN" -e "$NGINX_ERR" -c "$NGINX_CONF"
echo "[gateway] started. (nginx: $NGINX_BIN)"
