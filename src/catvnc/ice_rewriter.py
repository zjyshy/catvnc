"""Rewrite private-network IPs in WebRTC SDP and ICE candidate strings.

CatVNC sits behind an SSH reverse tunnel. When it advertises ICE candidates it
uses the iPhone's private-network IPs (e.g. 10.x.x.x, 192.168.x.x). The browser
cannot reach those addresses. This module rewrites them to the iPhone's real
public egress IP, so ICE can complete via the TURN relay.

We match the RFC1918 space plus CGNAT/link-local ranges. IPv6 is not handled
because CatVNC does not emit IPv6 candidates in the current setup.
"""

from __future__ import annotations

import re

_PRIVATE_IPV4_PATTERNS = [
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}",
    r"192\.168\.\d{1,3}\.\d{1,3}",
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}",
    r"169\.254\.\d{1,3}\.\d{1,3}",
    r"100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}",
]

_PRIVATE_IPV4_RE = re.compile("|".join(f"(?:{p})" for p in _PRIVATE_IPV4_PATTERNS))


def rewrite_ips_in_text(text: str, public_ip: str) -> str:
    """Replace every private-range IPv4 literal in *text* with *public_ip*.

    Safe to call on full SDP blobs or on a single a=candidate line. The regex
    only matches strict IPv4 dotted-quads inside the private ranges, so it
    won't touch ports, fingerprints, or hex fields.
    """
    return _PRIVATE_IPV4_RE.sub(public_ip, text)


def rewrite_sdp(sdp: str, public_ip: str) -> str:
    """Rewrite private IPs in an SDP blob."""
    return rewrite_ips_in_text(sdp, public_ip)


def rewrite_candidate(candidate: str, public_ip: str) -> str:
    """Rewrite private IPs in a single 'candidate:...' line."""
    return rewrite_ips_in_text(candidate, public_ip)
