from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catvnc.db import get_db
from catvnc.models import Device

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_active_device(request: Request, db: DbSession) -> Device:
    """Resolve which device this HTTP/WS request targets.

    M1: only one device provisioned, so we just return it.
    M3+: read `active_device` cookie set when the user enters a device page,
    fall back to the sole device if the cookie is missing and there's only one.
    """
    slug = request.cookies.get("active_device")
    if slug:
        result = await db.execute(select(Device).where(Device.slug == slug))
        device = result.scalar_one_or_none()
        if device is not None:
            return device
        # Cookie references a device that no longer exists — fall through to
        # the single-device path so the browser recovers instead of 404-ing.

    result = await db.execute(select(Device).order_by(Device.id).limit(2))
    devices = result.scalars().all()
    if not devices:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "no devices provisioned",
        )
    if len(devices) > 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "multiple devices exist but no active_device cookie is set",
        )
    return devices[0]


async def get_active_device_for_ws(websocket_scope_cookies: dict[str, str], db: AsyncSession) -> Device:
    """Same policy as get_active_device but for WebSocket handlers,
    which don't have a Request object.
    """
    slug = websocket_scope_cookies.get("active_device")
    if slug:
        result = await db.execute(select(Device).where(Device.slug == slug))
        device = result.scalar_one_or_none()
        if device is not None:
            return device

    result = await db.execute(select(Device).order_by(Device.id).limit(2))
    devices = result.scalars().all()
    if not devices:
        raise LookupError("no devices provisioned")
    if len(devices) > 1:
        raise LookupError("multiple devices but no active_device cookie set")
    return devices[0]
