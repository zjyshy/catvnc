from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from catvnc.db import Base, engine
from catvnc.routers import agent, proxy, signaling


@asynccontextmanager
async def lifespan(_: FastAPI):
    # M1: auto-create tables. M3 will switch to alembic-managed migrations.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="CatVNC Gateway", lifespan=lifespan)


# Route registration order matters: FastAPI matches in declaration order and
# the proxy is a `/{path:path}` catch-all that would swallow anything below it.

@app.get("/healthz", response_class=PlainTextResponse)
async def healthz() -> str:
    return "ok"


# Device agent heartbeat — must be before the proxy catch-all.
app.include_router(agent.router)

# WebSocket route (/ws) — WS and HTTP scopes are separate, but keep it above
# the catch-all for clarity.
app.include_router(signaling.router)


# Catch-all HTTP reverse proxy to the active device. MUST BE LAST.
app.include_router(proxy.router)
