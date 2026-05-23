"""Context Injection (§9.2): paste-box → mini lesson."""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ...core.auth_dep import get_current_user
from ...core.database import get_db
from ...models.context_artifact import ContextArtifact
from ...models.user import User
from ...services.memory_outbox import enqueue_memory_facts
from ...utils.llm import get_llm_client

router = APIRouter(tags=["context"])
logger = logging.getLogger(__name__)


class ContextIn(BaseModel):
    text: str
    language: str = "en"

    @field_validator("text")
    @classmethod
    def _v(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("text required")
        if len(v) > 4096:
            raise ValueError("text exceeds 4KB")
        return v


def _heuristic_terms(text: str) -> list[str]:
    # Pull "interesting" tokens: capitalized, hyphenated, or longer than 6 chars.
    tokens = re.findall(r"[A-Za-z][A-Za-z\-']{3,}", text)
    seen, out = set(), []
    for t in tokens:
        low = t.lower()
        if low in seen:
            continue
        seen.add(low)
        if t[0].isupper() or "-" in t or len(t) >= 7:
            out.append(t)
        if len(out) >= 12:
            break
    return out


@router.post("/context/analyze")
async def analyze_context(payload: ContextIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    digest = hashlib.sha256(payload.text.encode("utf-8")).hexdigest()
    terms = _heuristic_terms(payload.text)

    llm = get_llm_client()
    prompt = (
        "Người học Việt Nam dán đoạn văn công việc dưới đây. Hãy:\n"
        "1) Liệt kê tối đa 8 từ/cụm tiếng Anh khó hoặc đáng học (ưu tiên ngành nghề).\n"
        "2) Soạn 1 mini-lesson tiếng Việt ngắn gọn (≤120 từ) gợi ý cách dùng, tránh nhầm lẫn.\n"
        "Trả về JSON với keys: terms (list các từ), mini_lesson (string)."
    )
    try:
        raw = await llm.generate_chat_completion(
            [{"role": "system", "content": prompt}, {"role": "user", "content": payload.text}],
            temperature=0.3,
            max_tokens=400,
        )
    except Exception:  # pragma: no cover - defensive
        raw = ""

    mini = ""
    if raw and getattr(llm, "last_provider", "mock") != "mock":
        # crude JSON harvest
        import json
        try:
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end > start:
                obj = json.loads(raw[start : end + 1])
                if isinstance(obj.get("terms"), list):
                    terms = [str(t) for t in obj["terms"]][:12] or terms
                mini = str(obj.get("mini_lesson") or "").strip()
        except Exception:
            mini = raw.strip()[:600]

    if not mini:
        mini = (
            "Mini-lesson: Hãy chú ý các từ trên — kiểm tra collocation, giới từ và ngữ cảnh "
            "ngành nghề trước khi dùng trong email/báo cáo."
        )

    artifact = ContextArtifact(user_id=user.user_id, text_hash=digest, extracted_terms=terms)
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    facts = [
        {
            "content": f"Learner pasted workplace context for study; extracted terms: {', '.join(terms[:8])}.",
            "metadata": {"fact_type": "context", "source": "context_injection", "importance_score": 0.72},
        }
    ]
    for term in terms[:8]:
        facts.append(
            {
                "content": f"Learner encountered industry/workplace vocabulary: {term}.",
                "metadata": {"fact_type": "industry_vocab", "source": "context_injection", "importance_score": 0.68},
            }
        )
    try:
        enqueue_memory_facts(db, user_id=user.user_id, facts=facts, source="context_injection", commit=True)
    except Exception:
        logger.exception("context: failed to enqueue Mem0 facts")

    return {
        "lesson_id": str(artifact.id),
        "terms": terms,
        "mini_lesson": mini,
    }
