"""Device agent heartbeat endpoint.

Called by the iPhone tunnel script on each connection to report the current
public egress IP. Authenticated by the device's agent_token.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catvnc.db import get_db
from catvnc.models import Device

router = APIRouter(prefix="/agent")


class HeartbeatRequest(BaseModel):
    slug: str
    token: str
    public_egress_ip: str


@router.post("/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
async def heartbeat(body: HeartbeatRequest, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(Device).where(Device.slug == body.slug))
    device = result.scalar_one_or_none()

    if device is None or device.agent_token is None or device.agent_token != body.token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid slug or token")

    device.public_egress_ip = body.public_egress_ip
    device.last_seen_at = datetime.utcnow()
    await db.commit()
