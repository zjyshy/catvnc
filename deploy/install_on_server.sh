#!/usr/bin/env bash
# One-time bootstrap for the catvnc gateway backend on 39.106.125.238.
# Run as root. Idempotent enough to re-run for updates.
#
# Prerequisites already assumed on the server:
#   - nginx installed and serving 18888 via /etc/nginx/conf.d/catvnc.conf (the sub_filter version)
#   - coturn installed and running (unchanged in M1)
#   - SSH reverse tunnel from iPhone landing on 127.0.0.1:15901 (unchanged)

set -euo pipefail

REPO_URL="https://github.com/zjyshy/catvnc.git"   # public HTTPS clone works even without a deploy key
INSTALL_DIR="/opt/catvnc"
SERVICE_USER="catvnc"

echo ">>> ensure service user"
id -u "$SERVICE_USER" >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d "$INSTALL_DIR" "$SERVICE_USER"

echo ">>> ensure install dir"
mkdir -p "$INSTALL_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

echo ">>> clone or pull code"
if [ -d "$INSTALL_DIR/.git" ]; then
    sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" fetch --all --prune
    sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" reset --hard origin/main
else
    sudo -u "$SERVICE_USER" git clone "$REPO_URL" "$INSTALL_DIR"
fi

echo ">>> install uv (per-user) if missing"
if [ ! -x "$INSTALL_DIR/.local/bin/uv" ]; then
    sudo -u "$SERVICE_USER" bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi

UV="$INSTALL_DIR/.local/bin/uv"

echo ">>> sync python deps"
sudo -u "$SERVICE_USER" bash -c "cd $INSTALL_DIR && $UV sync"

echo ">>> ensure .env (edit afterwards if needed)"
if [ ! -f "$INSTALL_DIR/.env" ]; then
    sudo -u "$SERVICE_USER" cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo "    wrote fresh $INSTALL_DIR/.env — review the values"
fi

echo ">>> seed the device row (idempotent upsert)"
sudo -u "$SERVICE_USER" bash -c "cd $INSTALL_DIR && $UV run python scripts/seed_device.py \
    --slug myphone --name 'iPhone 8' \
    --tunnel-port 15901 --public-ip 123.124.217.250"

echo ">>> install systemd unit"
cp "$INSTALL_DIR/deploy/catvnc-backend.service" /etc/systemd/system/catvnc-backend.service
# The unit hard-codes /opt/catvnc/.venv/bin/uvicorn; that's what `uv sync` creates.
systemctl daemon-reload
systemctl enable catvnc-backend

echo ">>> restart backend"
systemctl restart catvnc-backend
sleep 1
systemctl status catvnc-backend --no-pager | head -20

echo ">>> health check"
curl -sf http://127.0.0.1:8000/healthz && echo "  backend OK" || { echo "  backend NOT OK"; exit 1; }

echo
echo ">>> backend is up. nginx is NOT yet switched over."
echo ">>> Next, review /etc/nginx/conf.d/catvnc.conf, back it up, then cut over:"
echo "      cp /etc/nginx/conf.d/catvnc.conf /etc/nginx/conf.d/catvnc.conf.bak"
echo "      cp $INSTALL_DIR/deploy/nginx-catvnc.conf /etc/nginx/conf.d/catvnc.conf"
echo "      nginx -t && systemctl reload nginx"
echo ">>> Then test:  http://39.106.125.238:18888/d/myphone/"
echo ">>> Rollback if broken:"
echo "      cp /etc/nginx/conf.d/catvnc.conf.bak /etc/nginx/conf.d/catvnc.conf"
echo "      nginx -t && systemctl reload nginx"
