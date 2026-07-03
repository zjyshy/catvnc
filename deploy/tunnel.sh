#!/bin/sh
# iPhone-side tunnel agent.
# Calls the backend heartbeat (server detects our public IP automatically),
# then holds the SSH reverse tunnel. Restarts automatically on disconnect.

SERVER="39.106.125.238"
BACKEND_URL="http://${SERVER}:18888"
DEVICE_SLUG="iphone8"
DEVICE_TOKEN="REPLACE_WITH_AGENT_TOKEN"
TUNNEL_PORT="15901"
CATVNC_PORT="5800"

while true; do
    curl -sf --max-time 10 -X POST "${BACKEND_URL}/agent/heartbeat" \
        -H "Content-Type: application/json" \
        -d "{\"slug\":\"${DEVICE_SLUG}\",\"token\":\"${DEVICE_TOKEN}\"}"
    echo "[tunnel] heartbeat done, connecting..."
    ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=no -R "127.0.0.1:${TUNNEL_PORT}:localhost:${CATVNC_PORT}" "root@${SERVER}"
    echo "[tunnel] disconnected, retrying in 5s..."
    sleep 5
done
