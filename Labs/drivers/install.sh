#!/usr/bin/env bash
# python-utils/drivers/install.sh
# Download python-build-standalone Python 3 + install DB drivers
#
# Usage:
#   cd python-utils/drivers
#   bash install.sh
#
# What this does:
#   1. Download self-contained Python 3.11 (no system install needed)
#   2. Install python-oracledb (Thin mode - no Oracle Instant Client needed)
#   3. Install psycopg2-binary (libpq bundled)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON3_DIR="$SCRIPT_DIR/python3"

# ── detect architecture ──────────────────────────────────────────────────────
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64)  PY_ARCH="x86_64-unknown-linux-gnu" ;;
    aarch64) PY_ARCH="aarch64-unknown-linux-gnu" ;;
    *)
        echo "[ERROR] Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

PY_VERSION="3.11.9"
PY_TAG="20240814"
PY_TARBALL="cpython-${PY_VERSION}+${PY_TAG}-${PY_ARCH}-install_only.tar.gz"
PY_URL="https://github.com/indygreg/python-build-standalone/releases/download/${PY_TAG}/${PY_TARBALL}"

echo "============================================================"
echo " python-utils driver installer"
echo "============================================================"
echo " Python : $PY_VERSION (standalone, no system install)"
echo " Arch   : $ARCH"
echo " Target : $PYTHON3_DIR"
echo "============================================================"
echo ""

# ── step 1: download & extract standalone Python 3 ──────────────────────────
if [ -f "$PYTHON3_DIR/bin/python3" ]; then
    echo "[1/3] Standalone Python 3 already installed. Skipping download."
else
    echo "[1/3] Downloading Python $PY_VERSION standalone..."
    mkdir -p "$PYTHON3_DIR"
    TMP_TAR="/tmp/${PY_TARBALL}"

    if command -v curl &>/dev/null; then
        curl -L --progress-bar "$PY_URL" -o "$TMP_TAR"
    elif command -v wget &>/dev/null; then
        wget --progress=bar:force "$PY_URL" -O "$TMP_TAR"
    else
        echo "[ERROR] curl or wget is required."
        exit 1
    fi

    echo "      Extracting..."
    tar -xzf "$TMP_TAR" -C "$PYTHON3_DIR" --strip-components=1
    rm -f "$TMP_TAR"
    echo "      Python $PY_VERSION installed at $PYTHON3_DIR"
fi

PYTHON3="$PYTHON3_DIR/bin/python3"
PIP3="$PYTHON3_DIR/bin/pip3"

echo ""

# ── step 2: install python-oracledb (Thin mode - no Instant Client needed) ──
echo "[2/3] Installing python-oracledb..."
if "$PIP3" install "oracledb" 2>&1; then
    VER="$($PYTHON3 -c 'import oracledb; print(oracledb.__version__)' 2>/dev/null || echo '?')"
    echo "      python-oracledb $VER installed."
    echo "      NOTE: Thin mode is used by default - Oracle Instant Client NOT required."
else
    echo "      [WARN] python-oracledb install failed."
fi

echo ""

# ── step 3: install psycopg2-binary (libpq bundled) ─────────────────────────
echo "[3/3] Installing psycopg2-binary..."
if "$PIP3" install "psycopg2-binary" --no-deps 2>&1; then
    VER="$($PYTHON3 -c 'import psycopg2; print(psycopg2.__version__)' 2>/dev/null || echo '?')"
    echo "      psycopg2-binary $VER installed."
else
    echo "      [WARN] psycopg2-binary install failed."
fi

echo ""
echo "============================================================"
echo " Installation complete."
echo " Restart python-utils: cd ../  &&  bash start.sh"
echo "============================================================"
