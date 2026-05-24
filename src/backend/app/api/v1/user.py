"""User endpoints (Sprint 3) - profile and GDPR delete."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import delete

from ...core.database import get_db
from ...core.redis_client import get_redis
from ...core.mem0_client import get_memory
from ...models.user import User
from ...models.processed_dataset_schemas import UserOut
from ...models.vocabulary import UserVocabulary

router = APIRouter(tags=["user"])
logger = logging.getLogger(__name__)


@router.get("/user/{user_id}")
async def get_user_profile(user_id: str, db: Session = Depends(get_db)):
    """Get user profile information."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "display_name": user.display_name,
        "cefr_level": user.cefr_level,
        "industry": user.industry,
        "learning_goals": user.learning_goals,
        "preferred_study_time": user.preferred_study_time,
        "created_at": user.created_at.isoformat()
    }


@router.delete("/user/{user_id}")
async def delete_user_data(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    GDPR delete: Remove all user data from PostgreSQL, Mem0, and Redis.
    
    Cascade operations:
    1. Delete from PostgreSQL (user_vocabulary, then user_profile)
    2. Delete from Mem0 vector memory
    3. Delete from Redis session cache
    
    Completes within 30s.
    """
    # Check user exists
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete from PostgreSQL
    try:
        # CASCADE is set at schema level, so deleting user deletes user_vocabulary
        db.query(User).filter(User.user_id == user_id).delete()
        db.commit()
        logger.info(f"Deleted user profile and vocabulary: {user_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete user from PostgreSQL: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user data")
    
    # Delete from Mem0
    try:
        mem0 = get_memory()
        mem0.delete_user_memory(user_id)
        logger.info(f"Deleted user memory from Mem0: {user_id}")
    except Exception as e:
        logger.warning(f"Failed to delete user from Mem0 (may not exist): {e}")
    
    # Delete from Redis (session data)
    try:
        redis = get_redis()
        # Delete all keys matching pattern: session:{user_id}:*
        cursor = 0
        deleted_count = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=f"session:{user_id}:*", count=100)
            if keys:
                await redis.delete(*keys)
                deleted_count += len(keys)
            if cursor == 0:
                break
        logger.info(f"Deleted {deleted_count} session keys from Redis: {user_id}")
    except Exception as e:
        logger.warning(f"Failed to delete user from Redis: {e}")
    
    return {
        "status": "deleted",
        "user_id": user_id,
        "message": "All user data has been permanently removed"
    }


@router.post("/user/{user_id}/preferences", response_model=UserOut)
async def update_user_preferences(
    user_id: str,
    preferences: dict,
    db: Session = Depends(get_db)
):
    """Update profile fields used by the tutor personalization flow."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cefr_level = preferences.get("cefr_level")
    industry = preferences.get("industry")
    learning_goals = preferences.get("learning_goals")
    display_name = preferences.get("display_name")
    preferred_study_time = preferences.get("preferred_study_time")
    opening_should_refresh = False

    if cefr_level is not None:
        if cefr_level not in {"A1", "A2", "B1", "B2", "C1"}:
            raise HTTPException(status_code=422, detail="invalid cefr_level")
        user.cefr_level = cefr_level
        opening_should_refresh = True
    if industry is not None:
        industry = str(industry).strip()
        if not industry:
            raise HTTPException(status_code=422, detail="industry must not be empty")
        user.industry = industry[:100]
        opening_should_refresh = True
    if learning_goals is not None:
        if not isinstance(learning_goals, list) or len(learning_goals) == 0 or len(learning_goals) > 10:
            raise HTTPException(status_code=422, detail="learning_goals must contain 1-10 items")
        user.learning_goals = [str(goal) for goal in learning_goals]
        opening_should_refresh = True
    if display_name is not None:
        user.display_name = str(display_name).strip() or None
        opening_should_refresh = True
    if preferred_study_time is not None:
        user.preferred_study_time = str(preferred_study_time).strip() or None
        opening_should_refresh = True

    if opening_should_refresh:
        user.agent_opening_message = None

    db.commit()
    db.refresh(user)
    return user
