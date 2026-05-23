import json
from typing import Optional

from redis.asyncio import Redis

from .config import get_settings


_settings = get_settings()
_redis: Optional[Redis] = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(_settings.REDIS_URL, decode_responses=True)
    return _redis


class SessionStore:
    """Thin wrapper for chat session state with TTL."""

    def __init__(self, redis: Redis, ttl_seconds: int = 86400):
        self.redis = redis
        self.ttl = ttl_seconds

    def _key(self, user_id: str) -> str:
        return f"session:{user_id}:latest"

    async def save(self, user_id: str, state: dict) -> None:
        await self.redis.setex(self._key(user_id), self.ttl, json.dumps(state))

    async def restore(self, user_id: str) -> Optional[dict]:
        data = await self.redis.get(self._key(user_id))
        return json.loads(data) if data else None

    async def delete(self, user_id: str) -> None:
        await self.redis.delete(self._key(user_id))


def get_session_store() -> SessionStore:
    return SessionStore(get_redis(), ttl_seconds=_settings.SESSION_TTL_SECONDS)
