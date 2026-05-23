"""SM-2 spaced repetition algorithm.

Reference: https://www.supermemo.com/en/blog/application-of-a-computer-to-improve-the-results-obtained-in-working-with-the-supermemo-method

`quality` is on the SuperMemo 0–5 scale:
    5 = perfect recall
    4 = correct after hesitation
    3 = correct with serious difficulty
    2 = incorrect; correct one seemed easy
    1 = incorrect; correct one remembered
    0 = total blackout
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


MASTERED_THRESHOLD_DAYS = 60


@dataclass
class SM2State:
    ease_factor: float = 2.5
    interval_days: int = 1
    repetitions: int = 0
    next_review: date | None = None
    mastered: bool = False
    total_reviews: int = 0


def update_sm2(state: SM2State, quality: int, today: date | None = None) -> SM2State:
    if not 0 <= quality <= 5:
        raise ValueError("quality must be 0..5")
    today = today or date.today()

    if quality < 3:
        # Failure: reset repetition count, schedule for tomorrow
        state.repetitions = 0
        state.interval_days = 1
    else:
        if state.repetitions == 0:
            state.interval_days = 1
        elif state.repetitions == 1:
            state.interval_days = 6
        else:
            state.interval_days = max(1, round(state.interval_days * state.ease_factor))
        state.repetitions += 1

    # Standard SM-2 ease-factor update, floored at 1.3
    delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    state.ease_factor = max(1.3, state.ease_factor + delta)

    state.next_review = today + timedelta(days=state.interval_days)
    state.mastered = state.interval_days > MASTERED_THRESHOLD_DAYS
    state.total_reviews += 1
    return state
