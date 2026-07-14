"""Security utilities — password hashing, JWT tokens (access + refresh), token blacklist."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings
from app.redis_client import get_redis

# Bearer token scheme
bearer_scheme = HTTPBearer()


# --- Password Hashing ---

def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    if not hashed_password:
        return False
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# --- JWT Token Creation ---

def create_access_token(user_id: str) -> str:
    """Create a short-lived JWT access token (30 min default)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_EXPIRATION_MINUTES)
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),  # unique token ID for blacklist
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived JWT refresh token (30 days default)."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_EXPIRATION_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_password_reset_token(user_id: str) -> str:
    """Create a short-lived token for password reset (15 min)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    payload = {
        "sub": user_id,
        "type": "password_reset",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# --- JWT Token Decoding ---

def decode_token(token: str, expected_type: str = "access") -> dict:
    """Decode and validate a JWT token of the expected type."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş token.",
        ) from e

    token_type = payload.get("type", "access")
    if token_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Beklenen token tipi '{expected_type}', alınan '{token_type}'.",
        )
    return payload


# --- Token Blacklist (Redis) ---

async def blacklist_token(jti: str, expires_in_seconds: int) -> None:
    """Add a token's JTI to the Redis blacklist until it naturally expires."""
    redis_client = await get_redis()
    await redis_client.set(f"blacklist:{jti}", "1", ex=expires_in_seconds)


async def is_token_blacklisted(jti: str) -> bool:
    """Check if a token's JTI is in the blacklist."""
    redis_client = await get_redis()
    return await redis_client.exists(f"blacklist:{jti}") > 0


# --- Refresh Token Store (Redis) ---

async def store_refresh_token(user_id: str, jti: str, expires_in_seconds: int) -> None:
    """Store a refresh token's JTI in Redis, mapped to user_id."""
    redis_client = await get_redis()
    # Store user's active refresh tokens in a set
    key = f"refresh_tokens:{user_id}"
    await redis_client.sadd(key, jti)
    await redis_client.expire(key, expires_in_seconds)
    # Also store JTI -> user_id mapping for validation
    await redis_client.set(f"refresh:{jti}", user_id, ex=expires_in_seconds)


async def revoke_refresh_token(jti: str) -> None:
    """Revoke a single refresh token."""
    redis_client = await get_redis()
    user_id = await redis_client.get(f"refresh:{jti}")
    if user_id:
        await redis_client.srem(f"refresh_tokens:{user_id}", jti)
    await redis_client.delete(f"refresh:{jti}")


async def revoke_all_refresh_tokens(user_id: str) -> None:
    """Revoke all refresh tokens for a user (e.g. password change)."""
    redis_client = await get_redis()
    key = f"refresh_tokens:{user_id}"
    jtis = await redis_client.smembers(key)
    if jtis:
        pipe = redis_client.pipeline()
        for jti in jtis:
            pipe.delete(f"refresh:{jti}")
        pipe.delete(key)
        await pipe.execute()


async def is_refresh_token_valid(jti: str) -> bool:
    """Check if a refresh token JTI is still valid (stored in Redis)."""
    redis_client = await get_redis()
    return await redis_client.exists(f"refresh:{jti}") > 0


# --- FastAPI Dependencies ---

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """FastAPI dependency: extract user_id from JWT bearer token.
    Also checks token blacklist.
    """
    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = payload.get("sub")
    jti = payload.get("jti")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token geçersiz.",
        )

    # Check if token is blacklisted
    if jti and await is_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token iptal edilmiş.",
        )

    # Hafif analitik: kullanıcıyı bugünün DAU setine işaretle. Best-effort —
    # Redis hatası tamamen yutulur, auth akışını ASLA bozmaz. (SADD çok ucuz.)
    from app.services import analytics_service
    await analytics_service.mark_daily_active(user_id)

    return user_id
