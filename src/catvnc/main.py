from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from catvnc.db import Base, engine
from catvnc.routers import proxy, signaling


@asynccontextmanager
async def lifespan(_: FastAPI):
    # M1: auto-create tables. M3 will switch to alembic-managed migrations.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="CatVNC Gateway", lifespan=lifespan)

# WebSocket route must be registered before the HTTP catch-all router,
# but FastAPI matches WS routes independently of the api_route ones.
app.include_router(signaling.router)
app.include_router(proxy.router)


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz() -> str:
    return "ok"
