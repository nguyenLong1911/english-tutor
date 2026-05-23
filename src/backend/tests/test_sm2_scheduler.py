"""Unit tests for SM-2 spaced repetition (Sprint 1 — Task 1.5).

Reference: SuperMemo SM-2 paper. Verifies the canonical interval schedule
(1d, 6d, then prior * EF), ease-factor adjustment formula, failure reset,
and the mastered-threshold flag.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from app.services.sm2_scheduler import MASTERED_THRESHOLD_DAYS, SM2State, update_sm2

REFERENCE_DAY = date(2026, 4, 28)


def _ef_after(quality: int, start: float = 2.5) -> float:
    """Reference EF formula from the SM-2 paper, floored at 1.3."""
    delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    return max(1.3, start + delta)


def test_first_successful_review_schedules_one_day():
    state = update_sm2(SM2State(), quality=5, today=REFERENCE_DAY)
    assert state.repetitions == 1
    assert state.interval_days == 1
    assert state.next_review == REFERENCE_DAY + timedelta(days=1)
    assert state.total_reviews == 1
    assert state.mastered is False


def test_second_successful_review_schedules_six_days():
    state = SM2State(repetitions=1, interval_days=1, ease_factor=2.5)
    update_sm2(state, quality=5, today=REFERENCE_DAY)
    assert state.repetitions == 2
    assert state.interval_days == 6
    assert state.next_review == REFERENCE_DAY + timedelta(days=6)


def test_third_review_uses_previous_interval_times_ease_factor():
    state = SM2State(repetitions=2, interval_days=6, ease_factor=2.5)
    update_sm2(state, quality=5, today=REFERENCE_DAY)
    assert state.repetitions == 3
    # 6 * 2.5 = 15
    assert state.interval_days == 15
    # EF after q=5: 2.5 + 0.1 = 2.6
    assert state.ease_factor == pytest.approx(_ef_after(5))


def test_failure_resets_repetitions_and_interval():
    state = SM2State(repetitions=4, interval_days=30, ease_factor=2.6)
    update_sm2(state, quality=2, today=REFERENCE_DAY)
    assert state.repetitions == 0
    assert state.interval_days == 1
    assert state.next_review == REFERENCE_DAY + timedelta(days=1)
    # EF still gets adjusted on failure
    assert state.ease_factor == pytest.approx(_ef_after(2, start=2.6))


def test_ease_factor_floored_at_1_3():
    # Hammer with q=0 a few times — EF should clamp at 1.3
    state = SM2State(ease_factor=1.4)
    for _ in range(5):
        update_sm2(state, quality=0, today=REFERENCE_DAY)
    assert state.ease_factor == 1.3


def test_quality_5_increases_ease_factor_by_zero_point_one():
    state = SM2State(ease_factor=2.5)
    update_sm2(state, quality=5, today=REFERENCE_DAY)
    assert state.ease_factor == pytest.approx(2.6)


def test_quality_3_keeps_ease_factor_steady_below_initial():
    # Per SM-2: q=3 yields delta = 0.1 - 2*(0.08 + 2*0.02) = 0.1 - 0.24 = -0.14
    state = SM2State(ease_factor=2.5)
    update_sm2(state, quality=3, today=REFERENCE_DAY)
    assert state.ease_factor == pytest.approx(2.36)


def test_invalid_quality_raises():
    with pytest.raises(ValueError):
        update_sm2(SM2State(), quality=6)
    with pytest.raises(ValueError):
        update_sm2(SM2State(), quality=-1)


def test_mastered_flag_set_when_interval_exceeds_threshold():
    # Big interval × big EF pushes past the threshold in one update
    state = SM2State(
        repetitions=5,
        interval_days=MASTERED_THRESHOLD_DAYS,
        ease_factor=2.5,
    )
    update_sm2(state, quality=5, today=REFERENCE_DAY)
    assert state.interval_days > MASTERED_THRESHOLD_DAYS
    assert state.mastered is True


def test_total_reviews_increments_on_every_call():
    state = SM2State()
    for q in [5, 4, 3, 2, 5]:
        update_sm2(state, quality=q, today=REFERENCE_DAY)
    assert state.total_reviews == 5


def test_canonical_three_review_sequence_matches_paper():
    """A->1d, then 6d, then 6*2.6=15.6 → rounded to 16."""
    state = SM2State()
    update_sm2(state, quality=5, today=REFERENCE_DAY)
    assert state.interval_days == 1
    update_sm2(state, quality=5, today=REFERENCE_DAY)
    assert state.interval_days == 6
    update_sm2(state, quality=5, today=REFERENCE_DAY)
    # After three q=5s, EF = 2.5 + 0.1 + 0.1 + 0.1 = 2.8 → 6 * 2.7 = 16.2 → round = 16
    assert state.interval_days == 16
    assert state.ease_factor == pytest.approx(2.8)
