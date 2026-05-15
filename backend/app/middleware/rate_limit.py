"""Redis-based rate limiting middleware for FastAPI.

Uses a sliding window counter per IP address stored in Redis.
Auth endpoints have stricter limits than general API endpoints.
"""

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.config import settings
from app.redis_client import get_redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis sliding window counter."""

    # Paths that get stricter rate limits
    AUTH_PATHS = {"/api/auth/login", "/api/auth/register", "/api/auth/password-reset"}

    # Paths excluded from rate limiting
    EXCLUDED_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Check rate limit before processing request."""
        import os
        # Skip rate limiting in test environment
        if os.environ.get("TESTING") == "1":
            return await call_next(request)

        path = request.url.path

        # Skip rate limiting for excluded paths
        if path in self.EXCLUDED_PATHS or path.startswith("/ws"):
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Determine rate limit
        if path in self.AUTH_PATHS:
            max_requests = settings.RATE_LIMIT_AUTH_PER_MINUTE
            window_key = f"rate_limit:auth:{client_ip}"
        else:
            max_requests = settings.RATE_LIMIT_PER_MINUTE
            window_key = f"rate_limit:api:{client_ip}"

        try:
            redis_client = await get_redis()
            current_time = int(time.time())
            window_start = current_time - 60  # 1-minute window

            # Use Redis pipeline for atomic operations
            pipe = redis_client.pipeline()
            # Remove expired entries
            pipe.zremrangebyscore(window_key, 0, window_start)
            # Count current requests in window
            pipe.zcard(window_key)
            # Add current request
            pipe.zadd(window_key, {str(current_time) + ":" + str(id(request)): current_time})
            # Set expiry on the key
            pipe.expire(window_key, 120)
            results = await pipe.execute()

            request_count = results[1]

            if request_count >= max_requests:
                # Calculate retry-after
                oldest = await redis_client.zrange(window_key, 0, 0, withscores=True)
                retry_after = 60
                if oldest:
                    retry_after = max(1, int(oldest[0][1]) + 60 - current_time)

                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Çok fazla istek. Lütfen biraz bekleyin.",
                        "retry_after": retry_after,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = str(
                max(0, max_requests - request_count - 1)
            )
            return response

        except Exception:
            # If Redis is down, allow the request (fail-open)
            return await call_next(request)
