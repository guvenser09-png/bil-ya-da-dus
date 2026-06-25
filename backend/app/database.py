"""SQLAlchemy async database engine and session management."""

import ssl as _ssl
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def asyncpg_connect_args(url: str) -> dict:
    """asyncpg bağlantı argümanları.

    Yerel geliştirmede (localhost) Postgres TLS sunmaz → SSL kapalı.
    Uzak/yönetilen Postgres'te (Railway/Render/Heroku) bağlantı TLS ile
    şifrelenir. Railway genel proxy'si TLS ister; sertifika ana-makine adı
    uyuşmayabildiğinden doğrulama gevşetilir (trafik yine şifreli kalır).
    """
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1", ""):
        return {}
    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    return {"ssl": ctx}


# Bağlantı argümanları (alembic env.py de import eder).
DB_CONNECT_ARGS = asyncpg_connect_args(settings.DATABASE_URL)

# Async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # SQL echo KAPALI — açıkken her sorgu loglanıp diski dolduruyordu
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args=DB_CONNECT_ARGS,
)

# Async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
