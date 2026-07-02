"""HTTP reverse proxy for /d/{slug}/* to the device's CatVNC tunnel.

WebSocket upgrades on /d/{slug}/ws are handled by the signaling router.
Everything else — HTML, JS bundles, static assets — streams through here
unchanged. Body rewriting for ICE happens in the signaling layer, not here.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from catvnc.deps import get_device_by_slug
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


@router.api_route(
    "/d/{slug}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy_http(
    slug: str,
    path: str,
    request: Request,
    device: Device = Depends(get_device_by_slug),
) -> StreamingResponse:
    from catvnc.config import get_settings

    settings = get_settings()
    upstream_url = f"http://{settings.upstream_host}:{device.tunnel_port}/{path}"

    upstream_headers = _filter_headers(request.headers)
    # Force upstream to send uncompressed so future body rewrites work
    upstream_headers["accept-encoding"] = "identity"
    upstream_headers["host"] = f"{settings.upstream_host}:{device.tunnel_port}"

    req = _client.build_request(
        method=request.method,
        url=upstream_url,
        headers=upstream_headers,
        params=request.query_params,
        content=request.stream(),
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
    "/d/{slug}/",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy_http_root(
    slug: str,
    request: Request,
    device: Device = Depends(get_device_by_slug),
) -> StreamingResponse:
    return await proxy_http(slug=slug, path="", request=request, device=device)
