from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes import auth
from app.core.config import settings
from app.db.postgres import Base, engine
from app.db.redis import close_redis, get_redis_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = get_redis_pool()
    await redis.ping()
    if settings.is_dev:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(title="MMO Backend", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.APP_ENV}