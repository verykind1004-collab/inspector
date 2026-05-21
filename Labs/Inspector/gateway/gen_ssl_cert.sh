#!/usr/bin/env bash
# Generate self-signed SSL certificate for Inspector gateway
# Usage: ./gen_ssl_cert.sh [days] [CN]

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSL_DIR="$SCRIPT_DIR/ssl"
DAYS="${1:-3650}"
CN="${2:-MaxGauge Inspector}"

mkdir -p "$SSL_DIR"

if [ -f "$SSL_DIR/server.crt" ] && [ -f "$SSL_DIR/server.key" ]; then
    echo "[ssl] Certificate already exists:"
    openssl x509 -in "$SSL_DIR/server.crt" -noout -subject -dates 2>/dev/null
    read -p "Regenerate? (y/N): " ans
    [ "$ans" != "y" ] && [ "$ans" != "Y" ] && exit 0
    # Backup existing
    mv "$SSL_DIR/server.crt" "$SSL_DIR/server.crt.bak_$(date +%Y%m%d_%H%M%S)"
    mv "$SSL_DIR/server.key" "$SSL_DIR/server.key.bak_$(date +%Y%m%d_%H%M%S)"
fi

echo "[ssl] Generating self-signed certificate..."
echo "      Validity: ${DAYS} days"
echo "      CN: ${CN}"

openssl req -x509 -nodes -days "$DAYS" -newkey rsa:2048 \
    -keyout "$SSL_DIR/server.key" \
    -out "$SSL_DIR/server.crt" \
    -subj "/C=KR/ST=Seoul/O=EXEM/OU=MaxGauge/CN=${CN}"

chmod 600 "$SSL_DIR/server.key"
chmod 644 "$SSL_DIR/server.crt"

echo ""
echo "[ssl] Certificate generated successfully:"
echo "      Cert: $SSL_DIR/server.crt"
echo "      Key:  $SSL_DIR/server.key"
openssl x509 -in "$SSL_DIR/server.crt" -noout -subject -dates -fingerprint
echo ""
echo "[ssl] To enable HTTPS, update config.yaml:"
echo "      gateway:"
echo "        ssl_enabled: true"
echo "        ssl_port: 8443"
echo "        ssl_cert: ssl/server.crt"
echo "        ssl_key: ssl/server.key"
echo ""
echo "[ssl] Then restart: ./insp_stop.sh && ./insp_start.sh"
