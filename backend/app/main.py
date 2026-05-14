"""QuizRoyale Backend — FastAPI Application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.redis_client import close_redis, get_redis
from app.api.router import api_router
from app.ws.lobby import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # Startup
    print(f"🎮 {settings.APP_NAME} v{settings.APP_VERSION} starting...")

    # Verify Redis connection
    try:
        redis_client = await get_redis()
        await redis_client.ping()
        print("✅ Redis connected")
    except Exception as e:
        print(f"⚠️  Redis connection failed: {e}")

    # Verify DB connection
    try:
        async with engine.begin() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        print("✅ PostgreSQL connected")
    except Exception as e:
        print(f"⚠️  PostgreSQL connection failed: {e}")

    print(f"🚀 {settings.APP_NAME} ready!")

    yield

    # Shutdown
    print(f"👋 {settings.APP_NAME} shutting down...")
    await close_redis()
    await engine.dispose()
    print("✅ Connections closed")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Mobil Trivia Battle Royale — Backend API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow all in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")

# Include WebSocket routes
app.include_router(ws_router, prefix="/ws")


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    # Check DB
    db_ok = False
    try:
        async with engine.begin() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        db_ok = True
    except Exception:
        pass

    # Check Redis
    redis_ok = False
    try:
        redis_client = await get_redis()
        await redis_client.ping()
        redis_ok = True
    except Exception:
        pass

    status = "healthy" if (db_ok and redis_ok) else "degraded"

    return {
        "status": status,
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "services": {
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    }
