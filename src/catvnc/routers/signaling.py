"""WebSocket signaling proxy for /d/{slug}/ws.

Two-way pipe between the browser and CatVNC's local WS endpoint. On downstream
messages (CatVNC -> browser) we rewrite any private-network IPv4 literal to
the device's public egress IP. This handles ICE candidates and SDP c= lines
regardless of the CatVNC envelope format, because the private-IPv4 regex only
matches strict RFC1918/CGNAT/link-local ranges.

Upstream messages (browser -> CatVNC) are forwarded untouched.
"""

from __future__ import annotations

import asyncio
import logging

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from starlette.websockets import WebSocketState

from catvnc.config import get_settings
from catvnc.db import SessionLocal
from catvnc.ice_rewriter import rewrite_ips_in_text
from catvnc.models import Device

log = logging.getLogger("catvnc.signaling")

router = APIRouter()


@router.websocket("/d/{slug}/ws")
async def proxy_ws(websocket: WebSocket, slug: str) -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(Device).where(Device.slug == slug))
        device = result.scalar_one_or_none()

    if device is None:
        await websocket.close(code=4404, reason=f"device '{slug}' not found")
        return

    if not device.public_egress_ip:
        await websocket.close(code=4400, reason="device has no public_egress_ip configured")
        return

    settings = get_settings()
    upstream_url = f"ws://{settings.upstream_host}:{device.tunnel_port}/ws"
    public_ip = device.public_egress_ip

    await websocket.accept()

    try:
        async with websockets.connect(upstream_url, max_size=None) as upstream:
            await asyncio.gather(
                _pipe_downstream(upstream, websocket, public_ip, slug),
                _pipe_upstream(websocket, upstream, slug),
            )
    except (websockets.WebSocketException, ConnectionError, OSError) as exc:
        log.warning("upstream ws error for %s: %s", slug, exc)
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


async def _pipe_downstream(
    upstream: websockets.ClientConnection,
    browser: WebSocket,
    public_ip: str,
    slug: str,
) -> None:
    """CatVNC -> browser, rewriting private IPs on the way."""
    try:
        async for msg in upstream:
            if isinstance(msg, str):
                rewritten = rewrite_ips_in_text(msg, public_ip)
                if rewritten != msg:
                    log.debug("%s: rewrote private IPs in downstream text msg", slug)
                await browser.send_text(rewritten)
            else:
                # Binary frames — currently CatVNC signaling is text, but pass through safely
                await browser.send_bytes(msg)
    except (WebSocketDisconnect, websockets.WebSocketException):
        pass


async def _pipe_upstream(
    browser: WebSocket,
    upstream: websockets.ClientConnection,
    slug: str,
) -> None:
    """Browser -> CatVNC, forwarded verbatim."""
    try:
        while True:
            msg = await browser.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if "text" in msg and msg["text"] is not None:
                await upstream.send(msg["text"])
            elif "bytes" in msg and msg["bytes"] is not None:
                await upstream.send(msg["bytes"])
    except (WebSocketDisconnect, websockets.WebSocketException):
        pass
    finally:
        await upstream.close()
