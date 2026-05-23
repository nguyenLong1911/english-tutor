"""Rate limiting and other middleware for FastAPI app."""

import logging
from datetime import datetime, timedelta
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from redis.asyncio import Redis

from .config import get_settings

logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW_SECONDS = 86400  # 1 day


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limit middleware using Redis.
    Tracks requests per user_id (from query param or header).
    Limit is configured by RATE_LIMIT_PER_DAY.
    """
    
    def __init__(self, app, redis: Redis):
        super().__init__(app)
        self.redis = redis
        self.limit = get_settings().RATE_LIMIT_PER_DAY
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limit for health check and docs
        if request.url.path in ["/health", "/docs", "/openapi.json", "/api/hello", "/api/tools"]:
            return await call_next(request)
        
        # Extract user_id from query param or header
        user_id = request.query_params.get("user_id") or request.headers.get("X-User-ID")
        
        if user_id:
            # Check rate limit
            is_rate_limited = await self._check_rate_limit(user_id)
            if is_rate_limited:
                logger.warning(f"Rate limit exceeded for user: {user_id}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too many requests",
                        "detail": f"Rate limit exceeded: {self.limit} requests per day",
                    }
                )
        
        # Continue to next middleware/route
        response = await call_next(request)
        return response
    
    async def _check_rate_limit(self, user_id: str) -> bool:
        """
        Check if user has exceeded rate limit.
        Returns True if rate limited (request should be rejected).
        Returns False if under limit (request is allowed).
        """
        key = f"rate_limit:{user_id}"
        try:
            current_count = await self.redis.incr(key)
            
            # Set TTL on first request of the day
            if current_count == 1:
                await self.redis.expire(key, RATE_LIMIT_WINDOW_SECONDS)
            
            # Check if exceeded limit
            return current_count > self.limit
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # On error, allow the request (fail open)
            return False
