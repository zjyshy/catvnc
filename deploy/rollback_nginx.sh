#!/usr/bin/env bash
# Revert nginx to the pre-M1 sub_filter config that was known-working.
set -euo pipefail

NGINX_CONF="/etc/nginx/conf.d/catvnc.conf"
BACKUP="$NGINX_CONF.bak"

if [ ! -f "$BACKUP" ]; then
    echo "no backup at $BACKUP, cannot rollback automatically"
    exit 1
fi

echo ">>> restoring $BACKUP -> $NGINX_CONF"
cp "$BACKUP" "$NGINX_CONF"

echo ">>> nginx -t"
nginx -t

echo ">>> reload nginx"
systemctl reload nginx

echo ">>> rolled back. The Python backend is still running (harmless);"
echo ">>> stop it if you want:  systemctl stop catvnc-backend"
