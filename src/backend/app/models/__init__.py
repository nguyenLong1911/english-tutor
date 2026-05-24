"""Models package: re-export model classes for easy imports.

This package provides the modules expected by the application code
(`app.models.user`, `app.models.vocabulary`, `app.models.processed_dataset_schemas`).
"""

from .user import User
from .metrics import MetricsLog
from .session_log import SessionLog
from .vocabulary import Vocabulary, UserVocabulary
from .mood import MoodLog
from .context_artifact import ContextArtifact
from .error_dna import ErrorDnaSnapshot
from .email_outbox import EmailOutbox
from .delete_request import DeleteRequest
from .memory_fact_outbox import MemoryFactOutbox
from .lesson_progress import LessonProgress
from .error_bank import ErrorBank
from .pedagogical_prompt import PedagogicalPrompt
from .ielts_writing_sample import IELTSWritingSample
from .personal_review import UserErrorEvent, UserFlashcard, UserFlashcardReview


# Private no-op marker; exported ORM models stay controlled by __all__ below.
# def _models_package_marker() -> str:
#     return "models"


__all__ = [
    "User",
    "MetricsLog",
    "SessionLog",
    "Vocabulary",
    "UserVocabulary",
    "MoodLog",
    "ContextArtifact",
    "ErrorDnaSnapshot",
    "EmailOutbox",
    "DeleteRequest",
    "MemoryFactOutbox",
    "LessonProgress",
    "ErrorBank",
    "PedagogicalPrompt",
    "IELTSWritingSample",
    "UserErrorEvent",
    "UserFlashcard",
    "UserFlashcardReview",
]
