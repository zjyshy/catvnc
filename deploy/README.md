# Deploy notes for CatVNC gateway (M1)

Target: `39.106.125.238` (Ubuntu, root).

## Files

- `nginx-catvnc.conf` — replaces `/etc/nginx/conf.d/catvnc.conf`. Removes all `sub_filter` patching; just forwards HTTP + WS to the Python backend.
- `catvnc-backend.service` — systemd unit for the FastAPI backend, running under a `catvnc` user, listening on `127.0.0.1:8000`.

## First-time server setup

```bash
# 1. system user + install target
sudo useradd -r -s /usr/sbin/nologin -d /opt/catvnc catvnc
sudo mkdir -p /opt/catvnc
sudo chown catvnc:catvnc /opt/catvnc

# 2. install uv (once)
curl -LsSf https://astral.sh/uv/install.sh | sudo -u catvnc sh
```

## Deploy / update

From dev machine:

```bash
# copy source (excluding venv/db/env)
rsync -av --delete \
    --exclude '.venv' --exclude '__pycache__' --exclude '*.db' \
    --exclude '.env' --exclude '.git' \
    ./ root@39.106.125.238:/opt/catvnc/
```

On the server:

```bash
cd /opt/catvnc
sudo -u catvnc /opt/catvnc/.local/bin/uv sync

# first time only: write /opt/catvnc/.env from .env.example
sudo cp .env.example /opt/catvnc/.env
sudo chown catvnc:catvnc /opt/catvnc/.env
sudo -e /opt/catvnc/.env   # fill in real secrets

# seed the first device
sudo -u catvnc /opt/catvnc/.local/bin/uv run python scripts/seed_device.py \
    --slug myphone --name "iPhone 8" \
    --tunnel-port 15901 --public-ip 123.124.217.250

# install systemd + start
sudo cp deploy/catvnc-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now catvnc-backend
sudo systemctl status catvnc-backend --no-pager
```

## Cut over nginx

```bash
# backup current sub_filter version
sudo cp /etc/nginx/conf.d/catvnc.conf /etc/nginx/conf.d/catvnc.conf.bak

# install new
sudo cp deploy/nginx-catvnc.conf /etc/nginx/conf.d/catvnc.conf
sudo nginx -t && sudo systemctl reload nginx
```

## Rollback

```bash
sudo cp /etc/nginx/conf.d/catvnc.conf.bak /etc/nginx/conf.d/catvnc.conf
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl stop catvnc-backend
```

## Verify M1

After cut-over, on the server:

```bash
# backend health
curl -sf http://127.0.0.1:8000/healthz

# via nginx
curl -sfI http://127.0.0.1:18888/d/myphone/

# from browser (mobile data recommended, that's the failure scenario):
#   http://39.106.125.238:18888/d/myphone/
# — screen should render and controls should work
```

If the public egress IP of the iPhone changes, update the device row:

```bash
sudo -u catvnc /opt/catvnc/.local/bin/uv run python scripts/seed_device.py \
    --slug myphone --name "iPhone 8" \
    --tunnel-port 15901 --public-ip <new-ip>
sudo systemctl restart catvnc-backend
```
