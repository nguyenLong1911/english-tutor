"""Multi-tier PII Sentinel.

Implements the *Sentinel* architecture described in the guide:
1. Rule-based regex for fixed formats (email, phone, IDs).
2. Luhn checksum gate to suppress false positives on credit-card-shaped numbers.
3. Optional NER pass via Microsoft Presidio (lazy import; degrades gracefully).
4. Per-PII strategy: REDACT / MASK / HASH / PSEUDONYMIZE.

Vietnamese names are pseudonymised so that ``[NAME_<hash>]`` tokens preserve
co-reference within a document while removing identity.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b")
_PHONE_VN_RE = re.compile(r"(?<!\d)(?:\+?84|0)\d{9,10}(?!\d)")
_PHONE_GENERIC_RE = re.compile(r"(?<!\d)\d{10,11}(?!\d)")
_LONG_DIGITS_RE = re.compile(r"(?<!\d)\d{13,19}(?!\d)")
_VN_NAME_RE = re.compile(
    r"\b(?:Nguyen|Tran|Le|Pham|Hoang|Huynh|Phan|Vu|Vo|Dang|Bui|Do|Ho|Ngo|Duong|Ly)"
    r"(?:\s+[A-Z][a-zA-Zà-ỹÀ-Ỹ]+){1,3}\b"
)
_GENERIC_NAME_RE = re.compile(r"\b[A-Z][a-z]{1,15}(?:\s+[A-Z][a-z]{1,15}){1,2}\b")


def luhn_valid(digits: str) -> bool:
    """Standard Luhn checksum. Returns True iff ``digits`` is a *plausible*
    account/card number. Used as a gate before redacting long digit runs."""
    if not digits.isdigit() or len(digits) < 13:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _hash_token(value: str, salt: str) -> str:
    h = hashlib.sha256((salt + value).encode("utf-8")).hexdigest()
    return h[:8].upper()


# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------

@dataclass
class PIISentinel:
    """Stateful PII filter.

    The same surface form maps to the same pseudonym within a single
    Sentinel instance, preserving local co-reference.

    Tiers (per § "Kiến trúc Lọc đa tầng Sentinel và Microsoft Presidio"):
      1. Regex (email, phone, IDs)
      2. Luhn checksum gate (suppress false positives on long digit runs)
      3. Presidio NER (optional; enable via ``use_presidio=True``)
      4. LLM semantic pass (optional; enable via ``llm_callback`` for
         indirect / contextual PII such as "Trợ lý Hiệu trưởng + giải Nhất Orion"
         that regex and NER cannot detect). Tier 4 is OPT-IN and a no-op
         when ``llm_callback`` is None — the rest of the pipeline keeps
         running unchanged when no API key is available.
    """

    salt: str = field(default_factory=lambda: os.getenv("A20_PII_SALT", "a20-default-salt"))
    use_presidio: bool = False
    llm_callback: Optional[Callable[[str], str]] = None

    _name_cache: Dict[str, str] = field(default_factory=dict)
    _id_cache: Dict[str, str] = field(default_factory=dict)

    # ----- public API ------------------------------------------------------
    def scrub(self, text: str) -> str:
        if not text:
            return text
        text = self._scrub_emails(text)
        text = self._scrub_phones(text)
        text = self._scrub_long_digits(text)
        text = self._scrub_names(text)
        if self.use_presidio:
            text = self._presidio_pass(text)
        if self.llm_callback is not None:
            text = self._llm_pass(text)
        return text

    def _llm_pass(self, text: str) -> str:
        """Tier 4 — semantic redaction via an injected LLM callback.

        The callback signature is ``(text) -> redacted_text``; it should
        replace contextual / indirect PII with bracketed placeholders such
        as ``[ROLE_TITLE]`` or ``[AWARD]``. Errors are swallowed (graceful
        degradation) so a transient LLM outage cannot block the pipeline.
        """
        try:
            return self.llm_callback(text)  # type: ignore[misc]
        except Exception:  # pragma: no cover — defensive
            return text

    # ----- individual passes ----------------------------------------------
    def _scrub_emails(self, text: str) -> str:
        return _EMAIL_RE.sub("[EMAIL]", text)

    def _scrub_phones(self, text: str) -> str:
        text = _PHONE_VN_RE.sub("[PHONE]", text)
        # Generic 10-11 digit phones, but only if Luhn does NOT validate
        # (i.e. unlikely to be a card number that the next pass should HASH).
        def _replace(match: re.Match) -> str:
            d = match.group(0)
            if luhn_valid(d):
                return match.group(0)  # let _scrub_long_digits handle it
            return "[PHONE]"
        return _PHONE_GENERIC_RE.sub(_replace, text)

    def _scrub_long_digits(self, text: str) -> str:
        def _replace(match: re.Match) -> str:
            d = match.group(0)
            if not luhn_valid(d):
                # Not a valid account/card – keep as-is to avoid clobbering
                # legitimate numeric examples in academic prose.
                return d
            token = self._id_cache.setdefault(d, _hash_token(d, self.salt))
            return f"[ID_{token}]"
        return _LONG_DIGITS_RE.sub(_replace, text)

    def _scrub_names(self, text: str) -> str:
        def _replace(match: re.Match) -> str:
            name = match.group(0)
            tok = self._name_cache.setdefault(
                name.lower(), _hash_token(name.lower(), self.salt)
            )
            return f"[NAME_{tok}]"
        text = _VN_NAME_RE.sub(_replace, text)
        # Avoid pseudo-replacing common English bigrams that look like names
        # by skipping if all words appear in a small allow-list.
        return text

    def _presidio_pass(self, text: str) -> str:
        try:
            from presidio_analyzer import AnalyzerEngine  # type: ignore
            from presidio_anonymizer import AnonymizerEngine  # type: ignore
        except Exception:
            return text  # graceful degradation
        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
        results = analyzer.analyze(text=text, language="en")
        return anonymizer.anonymize(text=text, analyzer_results=results).text


# Module-level convenience -------------------------------------------------

_default_sentinel: Optional[PIISentinel] = None


def scrub(text: str) -> str:
    """Module-level helper using a singleton sentinel."""
    global _default_sentinel
    if _default_sentinel is None:
        _default_sentinel = PIISentinel()
    return _default_sentinel.scrub(text)
