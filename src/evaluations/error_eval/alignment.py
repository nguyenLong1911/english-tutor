from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Any


TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:[.,]\d+)?|[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class GoldEdit:
    op: str
    wrong: str
    correct: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(str(text or ""))


def normalize_text(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = lowered.replace("’", "'").replace("`", "'")
    lowered = re.sub(r"[^a-z0-9']+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def normalized_tokens(text: str) -> set[str]:
    normalized = normalize_text(text)
    if not normalized:
        return set()
    return set(normalized.split())


def build_gold_edits(original: str, correction: str) -> list[GoldEdit]:
    original_tokens = tokenize(original)
    corrected_tokens = tokenize(correction)
    matcher = SequenceMatcher(a=original_tokens, b=corrected_tokens, autojunk=False)

    edits: list[GoldEdit] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        wrong = " ".join(original_tokens[i1:i2]).strip()
        correct = " ".join(corrected_tokens[j1:j2]).strip()
        if not wrong and not correct:
            continue
        edits.append(GoldEdit(op=tag, wrong=wrong, correct=correct))
    return edits


def parse_system_edit(event: dict[str, Any]) -> tuple[str, str]:
    pattern = str(event.get("error_pattern") or "").strip()
    corrected_text = str(event.get("corrected_text") or "").strip()
    if "->" in pattern:
        wrong, correct = pattern.split("->", 1)
        return wrong.strip(), correct.strip() or corrected_text
    if "→" in pattern:
        wrong, correct = pattern.split("→", 1)
        return wrong.strip(), correct.strip() or corrected_text
    return pattern, corrected_text


def _overlaps(expected: str, observed: str) -> bool:
    expected_norm = normalize_text(expected)
    observed_norm = normalize_text(observed)
    if not expected_norm:
        return True
    if not observed_norm:
        return False
    if expected_norm in observed_norm or observed_norm in expected_norm:
        return True

    expected_tokens = normalized_tokens(expected_norm)
    observed_tokens = normalized_tokens(observed_norm)
    if not expected_tokens:
        return True
    if not observed_tokens:
        return False
    return bool(expected_tokens & observed_tokens)


def system_event_matches_gold(event: dict[str, Any], gold: GoldEdit) -> bool:
    wrong, correct = parse_system_edit(event)
    return _overlaps(gold.wrong, wrong) and _overlaps(gold.correct, correct)


def score_events(gold_edits: list[GoldEdit], events: list[dict[str, Any]]) -> dict[str, Any]:
    matched_gold: set[int] = set()
    matched_events: set[int] = set()
    for gold_index, gold in enumerate(gold_edits):
        for event_index, event in enumerate(events):
            if event_index in matched_events:
                continue
            if system_event_matches_gold(event, gold):
                matched_gold.add(gold_index)
                matched_events.add(event_index)
                break

    total = len(gold_edits)
    matched = len(matched_gold)
    return {
        "gold_edits": total,
        "matched_edits": matched,
        "edit_recall": matched / total if total else 1.0,
        "sentence_full_match": bool(total and matched == total),
        "false_positive_events": max(0, len(events) - len(matched_events)),
        "missed_edits": [
            gold.as_dict()
            for index, gold in enumerate(gold_edits)
            if index not in matched_gold
        ],
    }
