#!/usr/bin/env bash
# Cut nginx over from the sub_filter version to the plain reverse-proxy version.
# Only run AFTER install_on_server.sh has confirmed the backend is healthy.
#
# Rollback: deploy/rollback_nginx.sh

set -euo pipefail

INSTALL_DIR="/opt/catvnc"
NGINX_CONF="/etc/nginx/conf.d/catvnc.conf"
BACKUP="$NGINX_CONF.bak"

BACKEND_PORT="${BACKEND_PORT:-8001}"

echo ">>> pre-flight: backend must be healthy on :$BACKEND_PORT"
curl -sf "http://127.0.0.1:$BACKEND_PORT/healthz" >/dev/null || { echo "backend not responding on :$BACKEND_PORT, aborting"; exit 1; }

if [ ! -f "$BACKUP" ]; then
    echo ">>> backing up current nginx config -> $BACKUP"
    cp "$NGINX_CONF" "$BACKUP"
else
    echo ">>> $BACKUP already exists, leaving it as the pristine pre-M1 copy"
fi

echo ">>> installing new nginx config"
cp "$INSTALL_DIR/deploy/nginx-catvnc.conf" "$NGINX_CONF"

echo ">>> nginx -t"
nginx -t

echo ">>> reload nginx"
systemctl reload nginx

echo ">>> smoke test through nginx"
sleep 1
curl -sfI http://127.0.0.1:18888/d/myphone/ | head -1 || true

echo
echo ">>> nginx now proxies 18888 -> 127.0.0.1:$BACKEND_PORT (Python backend)"
echo ">>> Test in a browser:  http://39.106.125.238:18888/d/myphone/"
echo ">>> Rollback if screen breaks:  bash deploy/rollback_nginx.sh"
