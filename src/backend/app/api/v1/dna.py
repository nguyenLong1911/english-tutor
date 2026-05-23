"""Error DNA radar API (§9.3)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.auth_dep import get_current_user, require_admin
from ...core.database import get_db
from ...models.error_dna import ErrorDnaSnapshot
from ...models.user import User
from ...services.error_dna_aggregator import DIMENSIONS, aggregate_for_user, week_start_of

router = APIRouter(tags=["dna"])


def _avg_dimensions(db: Session) -> dict[str, float]:
    rows = db.scalars(select(ErrorDnaSnapshot)).all()
    if not rows:
        return {d: 0.0 for d in DIMENSIONS}
    totals = {d: 0.0 for d in DIMENSIONS}
    for r in rows:
        dims = r.dimensions or {}
        for d in DIMENSIONS:
            totals[d] += float(dims.get(d, 0) or 0)
    return {d: round(totals[d] / len(rows), 2) for d in DIMENSIONS}


@router.get("/dna/{user_id}")
def get_dna(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if str(current_user.user_id) != user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="forbidden")

    monday = week_start_of(date.today())
    snap = db.scalar(
        select(ErrorDnaSnapshot)
        .where(ErrorDnaSnapshot.user_id == user_id, ErrorDnaSnapshot.week_start == monday)
    )
    if not snap:
        # Lazy build for this week so the FE always has data.
        snap = aggregate_for_user(db, user_id)

    return {
        "user_id": user_id,
        "week_start": snap.week_start.isoformat(),
        "dimensions": {d: int((snap.dimensions or {}).get(d, 0) or 0) for d in DIMENSIONS},
        "average": _avg_dimensions(db),
    }


@router.get("/dna/all/list", dependencies=[Depends(require_admin)])
def list_dna(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ErrorDnaSnapshot).order_by(ErrorDnaSnapshot.week_start.desc()).limit(200)
    ).all()
    return [
        {
            "user_id": str(r.user_id),
            "week_start": r.week_start.isoformat(),
            "dimensions": r.dimensions,
        }
        for r in rows
    ]
