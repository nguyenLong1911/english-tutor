from __future__ import annotations

from app.models.processed_dataset_schemas import LearnerProfile
from app.services.personalization import personalize_learner_profile


def get_learner_profile(user_id: str | None = None) -> LearnerProfile:
    profile = LearnerProfile(
        user_id=user_id or "mock-user",
        cefr_level="A2",
        industry="business",
        learning_goals=["daily work communication"],
        weak_points=["articles", "verb forms"],
        preferred_language="vi",
    )
    if user_id is None:
        return profile
    return personalize_learner_profile(profile)
