"""Device agent heartbeat endpoint.

Called by the iPhone tunnel script on each connection. The server detects the
caller's public IP from the X-Real-IP header set by nginx, so the iPhone does
not need to know or report its own IP.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catvnc.db import get_db
from catvnc.models import Device

router = APIRouter(prefix="/agent")


class HeartbeatRequest(BaseModel):
    slug: str
    token: str


@router.post("/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
async def heartbeat(
    body: HeartbeatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Device).where(Device.slug == body.slug))
    device = result.scalar_one_or_none()

    if device is None or device.agent_token is None or device.agent_token != body.token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid slug or token")

    # nginx sets X-Real-IP to the real client IP; uvicorn --proxy-headers
    # makes request.client.host the forwarded IP. Fall back to direct connection.
    detected_ip = (
        request.headers.get("x-real-ip")
        or (request.client.host if request.client else None)
    )
    if detected_ip:
        device.public_egress_ip = detected_ip
    device.last_seen_at = datetime.utcnow()
    await db.commit()
