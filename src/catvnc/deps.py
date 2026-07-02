from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catvnc.db import get_db
from catvnc.models import Device

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_device_by_slug(slug: str, db: DbSession) -> Device:
    result = await db.execute(select(Device).where(Device.slug == slug))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"device '{slug}' not found")
    return device
