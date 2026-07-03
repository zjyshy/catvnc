#!/bin/sh
# iPhone-side tunnel agent.
# Detects current public IP, reports it to the backend, then holds the SSH
# reverse tunnel. Restarts automatically on disconnect.

SERVER="39.106.125.238"
BACKEND_URL="http://${SERVER}:18888"
DEVICE_SLUG="iphone8"
DEVICE_TOKEN="REPLACE_WITH_AGENT_TOKEN"
TUNNEL_PORT="15901"
CATVNC_PORT="5800"

report_ip() {
    PUBLIC_IP=$(curl -sf --max-time 10 https://api.ipify.org) || \
    PUBLIC_IP=$(curl -sf --max-time 10 https://ifconfig.me)

    if [ -z "$PUBLIC_IP" ]; then
        echo "[tunnel] WARNING: could not detect public IP, skipping heartbeat"
        return 1
    fi

    echo "[tunnel] public IP: $PUBLIC_IP"

    curl -sf --max-time 10 -X POST "${BACKEND_URL}/agent/heartbeat" \
        -H "Content-Type: application/json" \
        -d "{\"slug\":\"${DEVICE_SLUG}\",\"token\":\"${DEVICE_TOKEN}\",\"public_egress_ip\":\"${PUBLIC_IP}\"}" \
        && echo "[tunnel] heartbeat OK" \
        || echo "[tunnel] WARNING: heartbeat failed"
}

while true; do
    report_ip

    echo "[tunnel] connecting..."
    ssh -N \
        -o ExitOnForwardFailure=yes \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -o StrictHostKeyChecking=no \
        -R "127.0.0.1:${TUNNEL_PORT}:0.0.0.0:${CATVNC_PORT}" \
        "root@${SERVER}"

    echo "[tunnel] disconnected, retrying in 5s..."
    sleep 5
done
