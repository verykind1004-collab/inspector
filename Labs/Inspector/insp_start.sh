#!/usr/bin/env bash
# Inspector unified start: gateway + python-utils
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[insp] starting gateway..."
"$SCRIPT_DIR/gateway/start.sh"

echo "[insp] starting python-utils..."
"$SCRIPT_DIR/python-utils/start.sh"

echo "[insp] starting MaxSpace..."
"$SCRIPT_DIR/../MaxSpace/start.sh"

echo "[insp] all started."
