"""Inject TURN servers into CatVNC's frontend JS bundle.

CatVNC's built JS has a hard-coded `iceServers` array containing only STUN
entries. Without a TURN relay the browser cannot receive the WebRTC video
stream through most NAT topologies (especially mobile carriers). Rather than
running a live sub_filter in nginx (the pre-M1 hack), we rewrite the JS body
in the HTTP proxy layer so the source of truth stays in Python code + config.

The original literal is copied verbatim from what nginx's sub_filter was
matching, so it stays in sync with the deployed bundle. If CatVNC's build
changes the format, matching fails silently and the JS is served untouched —
the caller can spot this by watching for the log warning below.
"""

from __future__ import annotations

import logging

from catvnc.config import Settings

log = logging.getLogger("catvnc.ice_injector")


ORIGINAL_STUN_ONLY = (
    'iceServers:['
    '{urls:"stun:stun.chat.bilibili.com:3478"},'
    '{urls:"stun:stun.l.google.com:19302"}'
    ']'
)


def build_ice_servers_literal(settings: Settings) -> str:
    """Produce a minified JS literal for iceServers with TURN entries."""
    stun_urls = [u.strip() for u in settings.stun_urls.split(",") if u.strip()]
    servers: list[str] = [f'{{urls:"{u}"}}' for u in stun_urls]

    turn_udp = f'turn:{settings.turn_host}:{settings.turn_port}?transport=udp'
    turn_tcp = f'turn:{settings.turn_host}:{settings.turn_port}?transport=tcp'
    creds = f'username:"{settings.turn_username}",credential:"{settings.turn_credential}"'
    servers.append(f'{{urls:"{turn_udp}",{creds}}}')
    servers.append(f'{{urls:"{turn_tcp}",{creds}}}')

    return "iceServers:[" + ",".join(servers) + "]"


def inject_turn(js_source: str, settings: Settings) -> tuple[str, bool]:
    """Return (patched_js, did_replace)."""
    replacement = build_ice_servers_literal(settings)
    if ORIGINAL_STUN_ONLY not in js_source:
        return js_source, False
    return js_source.replace(ORIGINAL_STUN_ONLY, replacement), True
