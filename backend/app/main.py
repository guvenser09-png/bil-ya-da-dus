"""QuizRoyale Backend — FastAPI Application."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.middleware.rate_limit import RateLimitMiddleware
from app.redis_client import close_redis, get_redis
from app.api.router import api_router
from app.api.legal import router as legal_router
from app.api.admin_metrics import router as admin_metrics_router
from app.ws.lobby import router as ws_lobby_router
from app.ws.game import router as ws_game_router
from app.ws.room import router as ws_room_router

logger = logging.getLogger("app.main")

# Ranked sezon settlement'in periyodik kontrol aralığı (saniye). Backend bir ay
# restart olmasa bile bitmiş sezonun ödülleri dağıtılsın. settle_due_seasons
# idempotenttir → sık çalışması güvenli (zaten dağıtılmışsa no-op).
_SEASON_SETTLEMENT_INTERVAL = 6 * 3600  # 6 saat

# Yetim turnuva bileti süpürücü aralığı (saniye). Kullanıcı /enter yapıp lobiye
# hiç bağlanmazsa bilet pending kalır; >10 dk pending biletler iade edilir.
# sweep_orphan_tickets idempotenttir (yalnızca pending iade edilir) → sık çalışsa
# da çift iade olmaz. 3 dk makul: TTL (1 saat) dolup iadesiz silinmeden çok önce.
_TICKET_SWEEP_INTERVAL = 180  # 3 dakika


async def _ticket_sweeper_loop() -> None:
    """Periyodik olarak yetim (hiç bağlanılmamış) turnuva biletlerini iade eder.

    Startup'ta başlatılır. Hata loglanır ama döngüyü öldürmez. Çekirdek iptal
    yolları (lobby_cancelled / run_game abort) zaten iade ediyor; bu loop yalnızca
    "kullanıcı /enter yapıp lobiye hiç bağlanmadı" durumundaki para sızıntısını
    kapatır (TTL dolup iadesiz silinmeden iade et).
    """
    from app.services.tournament_service import TournamentService

    while True:
        try:
            await asyncio.sleep(_TICKET_SWEEP_INTERVAL)
            await TournamentService.sweep_orphan_tickets()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover
            logger.warning("Yetim bilet süpürücü hatası: %s", exc)


async def _season_settlement_loop() -> None:
    """Periyodik olarak bitmiş ranked sezonları settle eder (idempotent).

    Startup'ta başlatılır, harici cron'a gerek bırakmaz. Hata loglanır ama
    döngüyü öldürmez. İlk çalışma startup settlement'ten hemen sonra olmasın
    diye bir aralık bekleyerek başlar.
    """
    from app.services.tournament_service import TournamentService

    while True:
        try:
            await asyncio.sleep(_SEASON_SETTLEMENT_INTERVAL)
            await TournamentService.settle_due_seasons()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover
            logger.warning("Periyodik sezon settlement hatası: %s", exc)


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

    # Ranked sezon settlement (lazy): bir önceki ay bitmiş ama ödül dağıtılmamışsa
    # şimdi dağıt (idempotent). Üretimde gün-içi kesin tetik için ayrıca cron
    # önerilir (bkz. settle_due_seasons docstring + rapor notu).
    try:
        from app.services.tournament_service import TournamentService
        await TournamentService.settle_due_seasons()
    except Exception as e:
        print(f"⚠️  Ranked sezon settlement atlandı: {e}")

    # Periyodik sezon settlement görevi (harici cron gerekmez; idempotent).
    settlement_task = asyncio.create_task(
        _season_settlement_loop(), name="season-settlement-loop"
    )

    # Periyodik yetim turnuva bileti süpürücü (money-safe; idempotent).
    ticket_sweeper_task = asyncio.create_task(
        _ticket_sweeper_loop(), name="tournament-ticket-sweeper"
    )

    print(f"🚀 {settings.APP_NAME} ready!")

    yield

    # Shutdown
    print(f"👋 {settings.APP_NAME} shutting down...")
    settlement_task.cancel()
    ticket_sweeper_task.cancel()
    for _task in (settlement_task, ticket_sweeper_task):
        try:
            await _task
        except asyncio.CancelledError:
            pass
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

# Rate limiting (Redis-based sliding window)
app.add_middleware(RateLimitMiddleware)

# Include API routes
app.include_router(api_router, prefix="/api")

# Admin analitik ucu (paylaşılan-anahtar korumalı; JWT değil). Tam yol:
# /api/admin/metrics?key=<ADMIN_METRICS_KEY>. Hafif, SDK'sız DAU/retention.
app.include_router(admin_metrics_router, prefix="/api/admin", tags=["Admin"])

# Herkese açık (auth'suz) yasal sayfalar. App Store Connect "Privacy Policy URL"
# zorunlu + abonelik (3.1.2) için EULA gerekir. /api altında DEĞİL: deploy edilince
# https://<domain>/legal/privacy ve https://<domain>/legal/terms ile erişilir.
app.include_router(legal_router, prefix="/legal", tags=["Legal"])

# Include WebSocket routes
app.include_router(ws_lobby_router, prefix="/ws")
app.include_router(ws_game_router, prefix="/ws")
app.include_router(ws_room_router, prefix="/ws")


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
