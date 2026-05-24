"""Wikipedia glossary collector – no API key required.

Uses the public MediaWiki Action API (``action=parse``) which is free and
respects standard rate limits (1 req/sec via the user-agent header).

For each industry we fetch a *Glossary of …* article, parse the wikitext for
``;term : definition`` patterns, and emit raw JSON suitable for downstream
LLM-based enrichment.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Dict, List

import requests

from ...shared_pipeline_support.json_dataset_file_io import save_json
from ...shared_pipeline_support.data_file_paths import RAW_WIKIPEDIA_GLOSSARIES
from ...shared_pipeline_support.retry_and_circuit_breaker import RetryConfig, retry_transient

log = logging.getLogger(__name__)

API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "A20-DataPipeline/0.1 (research; contact: a20@local)"

# Mapping: A20 industry → Wikipedia glossary article title(s) (ordered fallback)
GLOSSARY_PAGES: Dict[str, List[str]] = {
    "IT": [
        "Glossary of computer science",
        "Glossary of artificial intelligence",
    ],
    "Finance": [
        "Glossary of economics",
        "Outline of finance",
    ],
    "Marketing": [
        "Outline of marketing",
        "List of marketing terms",
        "Marketing communications",
        "Marketing strategy",
        "Brand management",
        "Digital marketing",
    ],
    "Sales": [
        "Outline of business management",
        "Index of business ethics, political economy, and philosophy of business articles",
        "Glossary of project management",
        "Sales",
    ],
    "Education": [
        "Glossary of education terms (A–C)",
        "Glossary of education terms (D–F)",
        "Glossary of education terms (G–L)",
        "Glossary of education terms (M–O)",
        "Glossary of education terms (P–R)",
        "Glossary of education terms (S)",
        "Glossary of education terms (T–Z)",
        "Glossary of education",
    ],
    "Healthcare": [
        "Glossary of medicine",
        "Outline of health sciences",
        "Index of health articles",
        "List of medical abbreviations",
    ],
}

# ``;term : definition`` is the canonical wikitext glossary syntax.
_GLOSS_RE = re.compile(r"^;\s*([^:\n]{2,80})\s*\n?:\s*(.+?)(?=\n;|\n\n|\Z)", re.DOTALL | re.MULTILINE)
# Glossary template syntax (MOS:GLOSSARIES). Term and defn often span lines:
#   {{term|1=Foo}}
#   {{defn|1=Bar baz.}}
_TPL_RE = re.compile(
    r"\{\{\s*term\s*\|\s*(?:1\s*=\s*)?([^}|\n]+?)\s*\}\}\s*\{\{\s*defn\s*\|\s*(?:1\s*=\s*)?(.+?)\s*\}\}",
    re.IGNORECASE | re.DOTALL,
)
# Outline / Index articles: ``* [[Term]] – description`` or ``* [[Term]] - description``
_OUTLINE_RE = re.compile(
    r"^\*+\s*\[\[\s*([^\]\|\n]{2,80}?)\s*(?:\|[^\]]+)?\]\]\s*[\u2013\u2014\-:]\s+(.{8,400}?)$",
    re.MULTILINE,
)
# Bold-link list (medical / PM glossaries): ``*'''[[Term]]''' – def`` and the
# common variant where the dash is omitted: ``*'''[[Term]]''' def``.
_BOLD_LINK_RE = re.compile(
    r"^\*+\s*'''\s*\[\[\s*([^\]\|\n]{2,80}?)\s*(?:\|[^\]]+)?\]\]\s*'''"  # term
    r"\s*(?:\([^)]{0,40}\))?\s*(?:[\u2013\u2014\-:,]\s*)?(.{8,400}?)$",   # defn
    re.MULTILINE,
)
# Bold-only list: ``*'''Term''' – def`` (no link)
_BOLD_ONLY_RE = re.compile(
    r"^\*+\s*'''\s*([^']{2,80}?)\s*'''"
    r"\s*(?:\([^)]{0,40}\))?\s*(?:[\u2013\u2014\-:,]\s*)?(.{8,400}?)$",
    re.MULTILINE,
)
# Wiki-table abbreviation format: ``| AB || meaning`` (used by abbreviation lists)
_ABBR_TABLE_RE = re.compile(
    r"^\|\s*([A-Za-z][A-Za-z./\-+&]{1,15})\s*(?:\|\|)\s*([^\|\n]{8,200})$",
    re.MULTILINE,
)


_RETRY = RetryConfig(max_retries=4, base_delay=2.0, max_delay=30.0, jitter=2.0)


@retry_transient(_RETRY)
def _http_get(session: requests.Session, params: dict, timeout: float) -> requests.Response:
    r = session.get(API_URL, params=params, timeout=timeout)
    r.raise_for_status()
    return r


def _fetch_wikitext(title: str, *, session: requests.Session, timeout: float = 20.0) -> str | None:
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "format": "json",
        "redirects": 1,
        "formatversion": 2,
    }
    try:
        r = _http_get(session, params, timeout)
    except Exception as exc:
        log.warning("wikipedia fetch failed (%s): %s", title, exc)
        return None
    payload = r.json()
    if "error" in payload:
        log.warning("wikipedia error for %s: %s", title, payload["error"].get("info"))
        return None
    return payload.get("parse", {}).get("wikitext")


def _strip_wikitext(text: str) -> str:
    """Light-weight wikitext cleaner (good enough for definitions)."""
    text = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", text)  # links
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"\{\{[^{}]+\}\}", "", text)  # remaining templates
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_terms(wikitext: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for regex in (_GLOSS_RE, _TPL_RE, _BOLD_LINK_RE, _BOLD_ONLY_RE, _OUTLINE_RE, _ABBR_TABLE_RE):
        for m in regex.finditer(wikitext):
            term = _strip_wikitext(m.group(1))
            defn = _strip_wikitext(m.group(2))
            if term and defn and 1 < len(term) < 80 and len(defn) > 8:
                # Filter out section markers and pure navigation entries.
                if term.lower().startswith(("see also", "external links", "references")):
                    continue
                out.append({"term": term, "definition_en": defn})
    # de-dup (preserve order)
    seen = set()
    deduped: List[Dict[str, str]] = []
    for it in out:
        k = it["term"].lower()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(it)
    return deduped


def collect(
    *,
    industries: List[str] | None = None,
    out_dir: Path = RAW_WIKIPEDIA_GLOSSARIES,
    rate_limit_sec: float = 2.0,
) -> Dict[str, dict]:
    """Fetch wikipedia glossary entries for each industry.

    Returns a summary dict: ``{industry: {"page": str, "count": int, "path": str}}``.
    """
    industries = industries or list(GLOSSARY_PAGES.keys())
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

    summary: Dict[str, dict] = {}
    for ind in industries:
        candidates = GLOSSARY_PAGES.get(ind, [])
        # Walk *all* candidates and merge terms (de-duped). Stop early only if
        # we already have a healthy harvest (≥ 50 terms).
        merged: List[Dict[str, str]] = []
        seen_terms: set[str] = set()
        pages_used: List[str] = []
        for title in candidates:
            wikitext = _fetch_wikitext(title, session=session)
            time.sleep(rate_limit_sec)
            if not wikitext:
                continue
            local = _extract_terms(wikitext)
            new_count = 0
            for t in local:
                k = t["term"].lower()
                if k in seen_terms:
                    continue
                seen_terms.add(k)
                merged.append(t)
                new_count += 1
            if new_count:
                pages_used.append(title)
                log.debug("wikipedia[%s] +%d terms from %s", ind, new_count, title)
            if len(merged) >= 50:
                break

        out_file = out_dir / f"{ind.lower()}.json"
        payload = {
            "industry": ind,
            "source_pages": pages_used,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "license": "CC BY-SA 4.0 (Wikipedia)",
            "terms": merged,
        }
        save_json(out_file, payload)
        summary[ind] = {"pages": pages_used, "count": len(merged), "path": str(out_file)}
        log.info("wikipedia[%s] terms=%d (pages=%d) → %s",
                 ind, len(merged), len(pages_used), out_file)

    return summary
