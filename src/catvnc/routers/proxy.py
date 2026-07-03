"""Root-level HTTP reverse proxy to the active device's CatVNC tunnel.

For JavaScript assets we intercept the body and inject TURN servers into the
hard-coded `iceServers` literal. Everything else streams through untouched.
WebSocket upgrades on /ws are handled by the signaling router.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, StreamingResponse

from catvnc.config import get_settings
from catvnc.deps import get_active_device
from catvnc.ice_injector import inject_turn
from catvnc.models import Device

log = logging.getLogger("catvnc.proxy")

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


def _is_js(path: str, content_type: str) -> bool:
    ct = content_type.lower()
    if "javascript" in ct or ct.startswith("application/x-javascript"):
        return True
    # Fallback: path-based (CatVNC serves JS with correct content-type in practice)
    return path.endswith(".js")


async def _do_proxy(path: str, request: Request, device: Device) -> Response | StreamingResponse:
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

    content_type = upstream.headers.get("content-type", "")
    if request.method in ("GET",) and _is_js(path, content_type):
        # Buffer the JS body so we can inject TURN into iceServers.
        try:
            body = await upstream.aread()
        finally:
            await upstream.aclose()

        try:
            source = body.decode("utf-8")
        except UnicodeDecodeError:
            log.warning("cannot decode JS %s as utf-8, serving raw", path)
            source = None

        if source is not None:
            patched, did_replace = inject_turn(source, settings)
            if did_replace:
                log.info("injected TURN into %s (delta %+d bytes)", path, len(patched) - len(source))
            body = patched.encode("utf-8")

        return Response(
            content=body,
            status_code=upstream.status_code,
            headers=_filter_headers(upstream.headers),
            media_type=content_type or "application/javascript",
        )

    async def stream():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()

    return StreamingResponse(
        stream(),
        status_code=upstream.status_code,
        headers=_filter_headers(upstream.headers),
        media_type=content_type or None,
    )


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    response_model=None,
)
async def proxy_http(
    path: str,
    request: Request,
    device: Device = Depends(get_active_device),
) -> Response | StreamingResponse:
    return await _do_proxy(path, request, device)
