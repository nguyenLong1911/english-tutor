"""Analytics endpoints for user progress dashboard (Sprint 3)."""

import logging
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.redis_client import get_redis
from ...models.user import User
from ...services.progress_analytics import build_user_progress_summary, build_user_vocabulary_summary

router = APIRouter(tags=["analytics"])
logger = logging.getLogger(__name__)

# Cache TTL: 1 hour
ANALYTICS_CACHE_TTL = 3600


async def _get_cached_or_compute(redis, cache_key: str, compute_fn):
    """Helper: check cache, return cached value or compute and cache it."""
    try:
        cached = await redis.get(cache_key)
        if cached:
            logger.info(f"Cache hit: {cache_key}")
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
    
    result = compute_fn()
    
    # Save to cache
    try:
        await redis.setex(cache_key, ANALYTICS_CACHE_TTL, json.dumps(result, default=str))
    except Exception as e:
        logger.warning(f"Cache write error: {e}")
    
    return result


@router.get("/analytics/{user_id}/summary")
async def get_user_summary(
    user_id: str, 
    db: Session = Depends(get_db),
    redis = Depends(get_redis)
):
    """
    Get user progress summary: accuracy trend (30d), top errors, vocabulary stats.
    Results cached for 1 hour.
    
    Returns:
    - accuracy_trend: list of {date, accuracy} for past 30 days
    - top_errors: list of [error_type, count] sorted by frequency
    - vocabulary: {total_learned, mastered, total_reviews}
    """
    cache_key = f"analytics:summary:{user_id}"
    
    def compute_summary():
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return build_user_progress_summary(db, user)
    
    return await _get_cached_or_compute(redis, cache_key, compute_summary)


@router.get("/analytics/{user_id}/vocabulary")
async def get_user_vocabulary(
    user_id: str, 
    db: Session = Depends(get_db),
    redis = Depends(get_redis)
):
    """
    Get detailed vocabulary statistics.
    Results cached for 1 hour.
    
    Returns:
    - total_learned: number of words user has seen
    - mastered: number of words with mastered=true
    - by_cefr: breakdown by CEFR level
    - by_industry: breakdown by industry tag
    """
    cache_key = f"analytics:vocabulary:{user_id}"
    
    def compute_vocabulary():
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return build_user_vocabulary_summary(db, user)
    
    return await _get_cached_or_compute(redis, cache_key, compute_vocabulary)
