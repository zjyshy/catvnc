"""Insert or update a device row for local/dev testing.

Usage:
    uv run python scripts/seed_device.py \\
        --slug myphone --name "My iPhone" \\
        --tunnel-port 15901 --token some-secret-token
"""

from __future__ import annotations

import argparse
import asyncio
from sqlalchemy import select

from catvnc.db import Base, SessionLocal, engine
from catvnc.models import Device


async def upsert_device(slug: str, name: str, tunnel_port: int, token: str) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        result = await db.execute(select(Device).where(Device.slug == slug))
        device = result.scalar_one_or_none()

        if device is None:
            device = Device(
                slug=slug,
                name=name,
                tunnel_port=tunnel_port,
                agent_token=token,
            )
            db.add(device)
            print(f"inserted device slug={slug}")
        else:
            device.name = name
            device.tunnel_port = tunnel_port
            device.agent_token = token
            print(f"updated device slug={slug}")

        await db.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--tunnel-port", type=int, required=True)
    parser.add_argument("--token", required=True, help="agent_token for device heartbeat auth")
    args = parser.parse_args()

    asyncio.run(
        upsert_device(
            slug=args.slug,
            name=args.name,
            tunnel_port=args.tunnel_port,
            token=args.token,
        )
    )


if __name__ == "__main__":
    main()
