"""Pytest configuration and shared fixtures."""

import asyncio
import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db

# Disable rate limiting in tests
os.environ["TESTING"] = "1"
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["RATE_LIMIT_AUTH_PER_MINUTE"] = "10000"

from app.main import app


# Use SQLite for tests (no PostgreSQL needed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override database dependency for tests."""
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Override the database dependency
app.dependency_overrides[get_db] = override_get_db


# Mock Redis for tests (auth uses Redis for token management)
_mock_redis_store: dict = {}


class MockRedis:
    """In-memory Redis mock for testing."""

    async def ping(self):
        return True

    async def get(self, key):
        return _mock_redis_store.get(key)

    async def set(self, key, value, ex=None, nx=False):
        # Gerçek Redis SET NX semantiği: anahtar zaten varsa yazma ve None dön
        # (idempotency testleri — ör. match:rewarded:{game_id} — buna dayanır).
        if nx and key in _mock_redis_store:
            return None
        _mock_redis_store[key] = value
        return True

    async def delete(self, *keys):
        for key in keys:
            _mock_redis_store.pop(key, None)

    async def exists(self, key):
        return 1 if key in _mock_redis_store else 0

    async def incr(self, key):
        # Gerçek Redis INCR: değeri int'e çevirip 1 artır, string olarak sakla
        # (decode_responses=True → GET string döner). Analitik maç sayacı buna dayanır.
        current = int(_mock_redis_store.get(key, 0) or 0)
        current += 1
        _mock_redis_store[key] = str(current)
        return current

    async def scard(self, key):
        val = _mock_redis_store.get(key)
        return len(val) if isinstance(val, set) else 0

    async def sadd(self, key, *values):
        if key not in _mock_redis_store:
            _mock_redis_store[key] = set()
        _mock_redis_store[key].update(values)

    async def srem(self, key, *values):
        if key in _mock_redis_store and isinstance(_mock_redis_store[key], set):
            _mock_redis_store[key] -= set(values)

    async def smembers(self, key):
        val = _mock_redis_store.get(key, set())
        return val if isinstance(val, set) else set()

    async def expire(self, key, seconds):
        pass

    async def zremrangebyscore(self, key, min_score, max_score):
        pass

    async def zcard(self, key):
        z = _mock_redis_store.get(key)
        return len(z) if isinstance(z, dict) else 0

    async def zadd(self, key, mapping):
        z = _mock_redis_store.get(key)
        if not isinstance(z, dict):
            z = {}
            _mock_redis_store[key] = z
        z.update(mapping)

    async def zrem(self, key, *members):
        z = _mock_redis_store.get(key)
        if isinstance(z, dict):
            for m in members:
                z.pop(m, None)

    async def zrangebyscore(self, key, min_score, max_score, start=0, num=None):
        z = _mock_redis_store.get(key)
        if not isinstance(z, dict):
            return []
        items = sorted(
            (m for m, s in z.items() if min_score <= s <= max_score),
            key=lambda m: z[m],
        )
        if num is not None:
            items = items[start:start + num]
        return items

    async def zrange(self, key, start, stop, withscores=False):
        return []

    async def zrevrange(self, key, start, stop, withscores=False):
        return []

    def pipeline(self):
        return MockRedisPipeline()


class MockRedisPipeline:
    """Mock Redis pipeline."""
    _ops = []

    def zremrangebyscore(self, key, min_val, max_val):
        self._ops.append(None)
        return self

    def zcard(self, key):
        self._ops.append(0)
        return self

    def zadd(self, key, mapping):
        self._ops.append(None)
        return self

    def expire(self, key, seconds):
        self._ops.append(None)
        return self

    def delete(self, key):
        _mock_redis_store.pop(key, None)
        self._ops.append(None)
        return self

    async def execute(self):
        results = [None, 0, None, None]  # zremrangebyscore, zcard=0, zadd, expire
        self._ops = []
        return results


_mock_redis = MockRedis()


@pytest_asyncio.fixture(autouse=True)
async def mock_redis():
    """Mock Redis for all tests."""
    _mock_redis_store.clear()
    with patch("app.redis_client.get_redis", return_value=_mock_redis):
        with patch("app.utils.security.get_redis", return_value=_mock_redis):
            yield _mock_redis


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Direct database session for tests."""
    async with test_session_factory() as session:
        yield session
