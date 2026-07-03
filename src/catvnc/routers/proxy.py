"""Root-level HTTP reverse proxy to the active device's CatVNC tunnel.

CatVNC's frontend bundle references assets via absolute paths (/assets/*,
/detector.js, ...). Rather than rewriting HTML/JS on the fly, we proxy
everything at root and pick the active device from a cookie (or the sole
device in M1). WebSocket upgrades on /ws are handled by the signaling router.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from catvnc.config import get_settings
from catvnc.deps import get_active_device
from catvnc.models import Device

router = APIRouter()

_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-encoding",
    "content-length",
}

_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=None))


def _filter_headers(headers) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


async def _do_proxy(path: str, request: Request, device: Device) -> StreamingResponse:
    settings = get_settings()
    upstream_url = f"http://{settings.upstream_host}:{device.tunnel_port}/{path}"

    upstream_headers = _filter_headers(request.headers)
    upstream_headers["accept-encoding"] = "identity"
    upstream_headers["host"] = f"{settings.upstream_host}:{device.tunnel_port}"

    req = _client.build_request(
        method=request.method,
        url=upstream_url,
        headers=upstream_headers,
        params=request.query_params,
        content=request.stream() if request.method not in ("GET", "HEAD") else None,
    )
    upstream = await _client.send(req, stream=True)

    async def stream():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()

    response_headers = _filter_headers(upstream.headers)
    return StreamingResponse(
        stream(),
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy_http(
    path: str,
    request: Request,
    device: Device = Depends(get_active_device),
) -> StreamingResponse:
    return await _do_proxy(path, request, device)
