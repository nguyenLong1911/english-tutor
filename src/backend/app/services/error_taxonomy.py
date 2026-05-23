from __future__ import annotations

import re
from typing import Any

DNA_DIMENSIONS = ("grammar", "vocab", "preposition", "writing", "collocations", "pronunciation")

SUBTYPE_TO_DIMENSION = {
    "article": "grammar",
    "tense": "grammar",
    "subject_verb_agreement": "grammar",
    "pluralization": "grammar",
    "word_form": "grammar",
    "spelling": "writing",
    "sentence_naturalness": "writing",
    "word_choice": "vocab",
    "preposition_choice": "preposition",
    "collocation_mismatch": "collocations",
    "pronunciation": "pronunciation",
}

_PREPOSITIONS = {"in", "on", "at", "for", "to", "with", "from", "about", "of", "by", "into", "over", "under"}
_ARTICLES = {"a", "an", "the"}

_TYPE_ALIASES = {
    "article": ("grammar", "article"),
    "articles": ("grammar", "article"),
    "tense": ("grammar", "tense"),
    "subject_verb": ("grammar", "subject_verb_agreement"),
    "subject_verb_agreement": ("grammar", "subject_verb_agreement"),
    "agreement": ("grammar", "subject_verb_agreement"),
    "plural": ("grammar", "pluralization"),
    "pluralization": ("grammar", "pluralization"),
    "word_form": ("grammar", "word_form"),
    "grammar": ("grammar", None),
    "vocab": ("vocab", "word_choice"),
    "vocabulary": ("vocab", "word_choice"),
    "word_choice": ("vocab", "word_choice"),
    "preposition": ("preposition", "preposition_choice"),
    "collocation": ("collocations", "collocation_mismatch"),
    "collocations": ("collocations", "collocation_mismatch"),
    "writing": ("writing", "sentence_naturalness"),
    "sentence_naturalness": ("writing", "sentence_naturalness"),
    "spelling": ("writing", "spelling"),
    "pronunciation": ("pronunciation", "pronunciation"),
}


def _clean(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_subtype(value: str) -> str | None:
    cleaned = re.sub(r"[^a-z_]+", "_", _clean(value)).strip("_")
    return cleaned or None


def _pattern_tokens(pattern: str) -> tuple[str, str]:
    if "->" not in pattern:
        return "", ""
    left, right = pattern.split("->", 1)
    return _clean(left), _clean(right)


def _infer_from_pattern(pattern: str) -> tuple[str | None, str | None]:
    left, right = _pattern_tokens(pattern)
    joined = f"{left} {right}".strip()
    if not joined:
        return None, None
    if left in _PREPOSITIONS or right in _PREPOSITIONS:
        return "preposition", "preposition_choice"
    if left in _ARTICLES or right in _ARTICLES:
        return "grammar", "article"
    if any(token in joined for token in ("more then", "rather then", "different then", "then", "than")):
        return "vocab", "word_choice"
    if len(left.split()) > 1 or len(right.split()) > 1:
        return "collocations", "collocation_mismatch"
    if left.endswith("s") != right.endswith("s"):
        return "grammar", "pluralization"
    return None, None


def _infer_from_explanation(explanation: str) -> tuple[str | None, str | None]:
    text = _clean(explanation)
    if not text:
        return None, None
    if "preposition" in text:
        return "preposition", "preposition_choice"
    if "article" in text:
        return "grammar", "article"
    if "tense" in text:
        return "grammar", "tense"
    if "subject-verb" in text or "subject verb" in text or "agreement" in text:
        return "grammar", "subject_verb_agreement"
    if "plural" in text:
        return "grammar", "pluralization"
    if "collocation" in text or "phrase" in text:
        return "collocations", "collocation_mismatch"
    if "spelling" in text:
        return "writing", "spelling"
    if "natural" in text or "tu nhien" in text or "sentence" in text:
        return "writing", "sentence_naturalness"
    if "pronunciation" in text or "stress" in text:
        return "pronunciation", "pronunciation"
    if "vocab" in text or "word choice" in text:
        return "vocab", "word_choice"
    return None, None


def normalize_error_taxonomy(
    *,
    error_type: Any = None,
    error_dimension: Any = None,
    error_subtype: Any = None,
    error_pattern: Any = None,
    explanation_vi: Any = None,
) -> dict[str, str]:
    dimension = _clean(error_dimension)
    subtype = _normalize_subtype(str(error_subtype or ""))
    error_type_clean = _clean(error_type)
    pattern = str(error_pattern or "")
    explanation = str(explanation_vi or "")

    if subtype in SUBTYPE_TO_DIMENSION:
        dimension = SUBTYPE_TO_DIMENSION[subtype]

    if dimension not in DNA_DIMENSIONS:
        dimension = ""

    if error_type_clean in _TYPE_ALIASES:
        alias_dimension, alias_subtype = _TYPE_ALIASES[error_type_clean]
        if not dimension:
            dimension = alias_dimension
        if subtype is None and alias_subtype:
            subtype = alias_subtype

    if not dimension or subtype is None:
        inferred_dimension, inferred_subtype = _infer_from_pattern(pattern)
        if not dimension and inferred_dimension:
            dimension = inferred_dimension
        if subtype is None and inferred_subtype:
            subtype = inferred_subtype

    if not dimension or subtype is None:
        inferred_dimension, inferred_subtype = _infer_from_explanation(explanation)
        if not dimension and inferred_dimension:
            dimension = inferred_dimension
        if subtype is None and inferred_subtype:
            subtype = inferred_subtype

    if subtype in SUBTYPE_TO_DIMENSION and not dimension:
        dimension = SUBTYPE_TO_DIMENSION[subtype]

    if not dimension:
        dimension = "grammar"

    if subtype is None:
        subtype = {
            "grammar": "grammar",
            "vocab": "word_choice",
            "preposition": "preposition_choice",
            "writing": "sentence_naturalness",
            "collocations": "collocation_mismatch",
            "pronunciation": "pronunciation",
        }[dimension]

    return {
        "error_type": error_type_clean or dimension,
        "error_dimension": dimension,
        "error_subtype": subtype,
    }
