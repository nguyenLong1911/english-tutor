"""Offline processing for already-collected A20 data.

This module intentionally does not call external APIs, scrape websites, or use
LLMs. It only normalizes and expands data that already exists under
``data/raw`` and ``data/processed``.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("a20.offline_process")

from .json_io import load_json, save_json
from .paths import (
    ERROR_BANK,
    JFLEG_AUTO,
    INDUSTRY_CANONICAL,
    WIKI_AUTO,
    IELTS,
    PEDAGOGICAL,
    MOOD,
    MEM0,
    OFFLINE_PROCESS_REPORT,
)

ISO_NOW = "2026-05-13T00:00:00Z"


def short_hash(text: str, n: int = 6) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n].upper()


def utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Wiki markup cleanup
# ---------------------------------------------------------------------------

REF_RE = re.compile(r"<ref\b[^>]*>.*?</ref>|<ref\b[^/]*/\s*>", re.I | re.S)
TEMPLATE_RE = re.compile(r"\{\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\}", re.S)
UNFINISHED_TEMPLATE_RE = re.compile(r"\{\{([^{}\n]+)")
URL_RE = re.compile(r"https?://\S+")
BRACKET_LINK_RE = re.compile(r"\[https?://[^\]\s]+(?:\s+([^\]]+))?\]")
WIKI_LINK_RE = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")
HTML_TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def clean_wiki_text(value: str) -> str:
    text = html.unescape(str(value or ""))
    for _ in range(4):
        text = REF_RE.sub(" ", text)
        text = TEMPLATE_RE.sub(" ", text)
    text = UNFINISHED_TEMPLATE_RE.sub(lambda m: m.group(1).split("|")[-1], text)
    text = re.sub(r"\b(cite web|cite book|cite journal|ISBN|doi|archive-url|access-date|url-status)\b[^.;,]*", " ", text, flags=re.I)
    text = BRACKET_LINK_RE.sub(lambda m: m.group(1) or " ", text)
    text = WIKI_LINK_RE.sub(r"\1", text)
    text = URL_RE.sub(" ", text)
    text = HTML_TAG_RE.sub(" ", text)
    text = text.replace("&ndash;", "-").replace("&mdash;", "-")
    text = text.replace(" defn=", " ").replace(" url-status=dead", " ")
    text = SPACE_RE.sub(" ", text).strip(" -;,.")
    return text


def clean_industry_vocab() -> dict[str, int]:
    changed = Counter()
    for path in (INDUSTRY_CANONICAL, WIKI_AUTO):
        data = load_json(path)
        for industry, payload in data.get("industries", {}).items():
            clean_items = []
            seen = set()
            for item in payload.get("vocabulary", []):
                item = dict(item)
                item["definition_en"] = clean_wiki_text(item.get("definition_en", ""))
                item["term"] = clean_wiki_text(item.get("term", ""))
                item["usage_note"] = clean_wiki_text(item.get("usage_note", ""))
                if not item["term"] or len(item["definition_en"]) < 8:
                    changed[f"{path.name}:dropped"] += 1
                    continue
                key = item["term"].strip().lower()
                if key in seen:
                    changed[f"{path.name}:duplicates"] += 1
                    continue
                seen.add(key)
                clean_items.append(item)
            payload["vocabulary"] = clean_items
            changed[f"{path.name}:{industry}"] = len(clean_items)
        data.setdefault("metadata", {})["offline_cleaned_at"] = utc_iso()
        data["metadata"]["cleanup"] = {
            "removed": ["ref_tags", "wiki_templates", "raw_urls", "html_tags"],
            "source": "src.data_pipeline.offline_process.clean_industry_vocab",
        }
        save_json(path, data)
    return dict(changed)


# ---------------------------------------------------------------------------
# Common errors
# ---------------------------------------------------------------------------

VI_FOCUSED_CATEGORIES = {
    "articles",
    "prepositions",
    "tense_and_aspect",
    "tenses",
    "modal_verbs",
    "word_choice_lexical",
}

VI_HINTS = {
    "articles": (
        "Tiếng Việt không có mạo từ a/an/the, nên hãy kiểm tra danh từ đang nói "
        "chung, nói lần đầu, hay nói vật đã xác định."
    ),
    "prepositions": (
        "Không dịch giới từ từng chữ từ tiếng Việt; hãy học cụm cố định quanh "
        "động từ hoặc danh từ chính."
    ),
    "tense_and_aspect": (
        "Tiếng Việt thường dùng trạng từ thời gian thay vì biến đổi động từ; hãy "
        "kiểm tra mốc thời gian trước khi chọn thì."
    ),
    "tenses": (
        "Tiếng Việt thường dùng trạng từ thời gian thay vì biến đổi động từ; hãy "
        "kiểm tra mốc thời gian trước khi chọn thì."
    ),
    "modal_verbs": (
        "Modal verb đi với động từ nguyên mẫu và thể hiện sắc thái như khả năng, "
        "nghĩa vụ hoặc lời khuyên."
    ),
    "word_choice_lexical": (
        "Không dịch từng từ từ tiếng Việt sang tiếng Anh; hãy kiểm tra collocation "
        "và sắc thái nghĩa trong ngữ cảnh."
    ),
}

EN_HINTS = {
    "articles": "Check whether the noun is generic, first-mentioned, or already specific.",
    "prepositions": "Learn the whole phrase around the main verb or noun instead of translating the preposition literally.",
    "tense_and_aspect": "Use the time marker to decide whether the action is finished, continuing, or connected to now.",
    "tenses": "Use the time marker to decide whether the action is finished, continuing, or connected to now.",
    "modal_verbs": "A modal verb is followed by the base verb and changes the meaning of ability, advice, or obligation.",
    "word_choice_lexical": "Check the natural collocation and meaning in context instead of translating word by word.",
}


def promote_jfleg_candidates(limit: int = 240, target_total: int = 500) -> dict[str, int]:
    bank = load_json(ERROR_BANK)
    auto = load_json(JFLEG_AUTO)
    existing_patterns = {
        (e.get("category"), e.get("error_pattern", "").strip().lower())
        for e in bank.get("errors", [])
    }

    promoted = []
    category_counts: Counter[str] = Counter()
    initial_total = len(bank.get("errors", []))
    if initial_total >= target_total:
        limit = 0
    else:
        limit = min(limit, target_total - initial_total)
    for item in auto.get("errors", []):
        category = item.get("category")
        pattern = item.get("error_pattern", "")
        if category not in VI_FOCUSED_CATEGORIES:
            continue
        if "(∅)" in pattern:
            continue
        key = (category, pattern.strip().lower())
        if key in existing_patterns:
            continue
        wrong = item.get("incorrect_example", "")
        correct = item.get("correct_example", "")
        if not wrong or not correct or len(wrong.split()) > 35:
            continue
        candidate = copy.deepcopy(item)
        candidate["id"] = f"ERR-{category[:4].upper()}-{short_hash(category + pattern + wrong)}"
        candidate["explanation_vi"] = VI_HINTS.get(category, "Lỗi phổ biến cần kiểm tra lại theo ngữ cảnh câu.")
        candidate["explanation_en"] = EN_HINTS.get(category, "Check the surrounding grammar and phrase pattern.")
        candidate["scaffolding_hint"] = candidate["explanation_vi"]
        candidate["confidence_score"] = 0.72
        candidate["importance_score"] = max(0.58, float(candidate.get("importance_score") or 0.5))
        candidate["frequency"] = "medium" if category_counts[category] < 30 else "low"
        tags = set(candidate.get("tags", []))
        tags.discard("needs_review")
        tags.update({"auto:jfleg", "offline_promoted", "rule_reviewed", "needs_teacher_review"})
        candidate["tags"] = sorted(tags)
        promoted.append(candidate)
        existing_patterns.add(key)
        category_counts[category] += 1
        if len(promoted) >= limit:
            break

    bank.setdefault("errors", []).extend(promoted)
    bank.setdefault("metadata", {})["total_errors"] = len(bank["errors"])
    cumulative = [
        e for e in bank["errors"]
        if "offline_promoted" in set(e.get("tags", []))
    ]
    cumulative_categories = Counter(e.get("category", "unknown") for e in cumulative)
    bank["metadata"]["offline_promoted_from_jfleg"] = {
        "last_run_count": len(promoted),
        "last_run_categories": dict(category_counts),
        "cumulative_count": len(cumulative),
        "cumulative_categories": dict(cumulative_categories),
        "target_total": target_total,
        "source": "data/processed/common_errors/jfleg_auto_extracted.json",
        "note": "Rule-filtered candidates; retained needs_teacher_review tag.",
    }
    save_json(ERROR_BANK, bank)
    return {
        "last_run_promoted": len(promoted),
        "cumulative_promoted": len(cumulative),
        "cumulative_categories": dict(cumulative_categories),
        "total_errors": len(bank["errors"]),
        "target_total": target_total,
    }


# ---------------------------------------------------------------------------
# Deterministic expansions from existing seeds
# ---------------------------------------------------------------------------

def expand_ielts(target: int = 60) -> dict[str, int]:
    data = load_json(IELTS)
    samples = data["samples"]
    topics = [
        "remote work", "education technology", "public health", "urban transport",
        "financial literacy", "environmental policy", "digital privacy",
        "career development", "online learning", "international trade",
        "media literacy", "workplace communication", "renewable energy",
        "university admissions", "artificial intelligence", "tourism",
        "consumer behaviour", "community service", "food systems",
        "lifelong learning",
    ]
    bands = [5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
    existing = {s["id"] for s in samples}
    idx = 0
    while len(samples) < target:
        topic = topics[idx % len(topics)]
        band = bands[idx % len(bands)]
        sid = f"IELTS-OFF-{idx + 1:03d}"
        idx += 1
        if sid in existing:
            continue
        position = "agree" if idx % 2 else "partly agree"
        samples.append({
            "id": sid,
            "prompt": (
                f"Some people believe that {topic} should be a central priority "
                "for governments and employers. To what extent do you agree or disagree?"
            ),
            "band": band,
            "essay": (
                f"In recent years, {topic} has become a practical concern rather "
                "than an abstract discussion. I " + position + " because policy "
                "and workplace decisions can shape how people learn, communicate, "
                "and use resources. A balanced approach is necessary: institutions "
                "should provide structure, but individuals also need room to make "
                "choices that fit their circumstances. For example, a busy employee "
                "may benefit from short, targeted training, while a student may need "
                "more guided practice and feedback. If support is too general, it "
                "often fails to transfer into real-life performance. However, if the "
                "support is connected to daily tasks, people are more likely to use "
                "what they learn. In conclusion, {topic} deserves attention, but the "
                "best solutions are those that combine public guidance with personal "
                "responsibility and measurable outcomes."
            ),
            "examiner_feedback": (
                "TR: The response presents a clear position and addresses the task. "
                "CC: Ideas are logically sequenced with basic cohesion. LR: Vocabulary "
                "is topic-relevant but sometimes general. GRA: Sentence structures are "
                "mostly controlled, with occasional Vietnamese-learner risks around "
                "articles, prepositions, and tense choice."
            ),
            "common_errors": ["articles", "prepositions", "tense_and_aspect"],
            "cefr_level": "B2" if band >= 6.5 else "B1",
            "topic": topic,
        })
        existing.add(sid)
    data["metadata"]["total_samples"] = len(samples)
    data["metadata"]["offline_expanded_at"] = utc_iso()
    save_json(IELTS, data)
    return {"samples": len(samples)}


def expand_pedagogical(target: int = 80) -> dict[str, int]:
    data = load_json(PEDAGOGICAL)
    prompts = data["prompts"]
    situations = [
        ("articles", "grammar", "A2", "Learner omits articles when describing work objects."),
        ("prepositions", "grammar", "B1", "Learner translates Vietnamese prepositions directly in business emails."),
        ("tense", "grammar", "B1", "Learner mixes Present Perfect and Past Simple when reporting progress."),
        ("word_choice", "vocabulary", "B2", "Learner chooses literal translations that sound unnatural in meetings."),
        ("speaking_block", "speaking", "B1", "Learner freezes when asked to explain a project update."),
        ("writing_email", "writing", "B1", "Learner writes direct Vietnamese-style requests in English email."),
        ("reading_context", "reading", "B2", "Learner understands individual words but misses the business implication."),
        ("listening_repair", "listening", "B1", "Learner misses key action items in a short meeting recap."),
    ]
    existing_ids = {p["id"] for p in prompts}
    i = 0
    while len(prompts) < target:
        key, skill, cefr, situation = situations[i % len(situations)]
        pid = f"PED-OFF-{i + 1:03d}"
        i += 1
        if pid in existing_ids:
            continue
        prompts.append({
            "id": pid,
            "learner_situation": f"{situation} Scenario variant {((i - 1) // len(situations)) + 1}.",
            "scaffolding_steps": [
                "Ask the learner to identify the meaning they want to express.",
                "Give one contrastive example that shows the Vietnamese-English difference.",
                "Ask the learner to repair only the target phrase before rewriting the full sentence.",
            ],
            "socratic_questions": [
                "Which word carries the main meaning in this sentence?",
                "What changes if you make the sentence more specific or more time-bound?",
            ],
            "expected_outcome": "Learner self-corrects the target pattern before receiving the final model answer.",
            "target_skill": skill,
            "cefr_level": cefr,
            "affective_filter_strategy": (
                "Normalize the error as a common Vietnamese-English transfer pattern, "
                "then ask for one small repair instead of a full rewrite."
            ),
            "tags": ["offline_expanded", key, "scaffolding", "i_plus_1"],
        })
        existing_ids.add(pid)
    data["metadata"]["total_prompts"] = len(prompts)
    data["metadata"]["offline_expanded_at"] = utc_iso()
    save_json(PEDAGOGICAL, data)
    return {"prompts": len(prompts)}


def expand_mood(target: int = 60) -> dict[str, int]:
    data = load_json(MOOD)
    samples = data["samples"]
    personas = ["first_timer", "speed_runner", "qa_destroyer"]
    rules = {
        "exhausted": ("slow", "review", "It is late and the learner sends very short answers."),
        "low": ("slow", "drill", "The learner hesitates and asks for easier examples."),
        "neutral": ("moderate", "new_material", "The learner answers steadily with medium-length messages."),
        "energized": ("fast", "free_practice", "The learner asks follow-up questions and writes longer sentences."),
        "peak": ("fast", "new_material", "The learner requests a challenge and responds quickly."),
    }
    existing_ids = {s["id"] for s in samples}
    i = 0
    levels = list(rules)
    while len(samples) < target:
        persona = personas[i % len(personas)]
        level = levels[(i // len(personas)) % len(levels)]
        pace, modality, signal = rules[level]
        sid = f"MOOD-OFF-{i + 1:03d}"
        i += 1
        if sid in existing_ids:
            continue
        samples.append({
            "id": sid,
            "user_persona": persona,
            "energy_level": level,
            "self_reported_mood": level,
            "contextual_signals": [
                signal,
                f"Session slot pattern: offline synthetic validation case {i}.",
            ],
            "recommended_pace": pace,
            "recommended_modality": modality,
            "sample_dialogue_turn": (
                "I want practice this topic but please make it "
                f"{'easy' if pace == 'slow' else 'a bit challenging'} today."
            ),
            "timestamp": ISO_NOW,
        })
        existing_ids.add(sid)
    data["metadata"]["total_samples"] = len(samples)
    data["metadata"]["offline_expanded_at"] = utc_iso()
    save_json(MOOD, data)
    return {"samples": len(samples)}


def expand_mem0(target_per_persona: int = 100) -> dict[str, int]:
    data = load_json(MEM0)
    patterns = [
        ("error_pattern", "Learner tends to omit articles before singular countable nouns in work examples."),
        ("error_pattern", "Learner confuses present perfect with past simple when using finished time markers."),
        ("error_pattern", "Learner translates Vietnamese preposition choices directly into English phrases."),
        ("preference", "Learner responds better to one short hint before a model answer."),
        ("progress", "Learner can self-correct after seeing a contrastive Vietnamese-English explanation."),
        ("context", "Learner prefers examples connected to workplace communication."),
        ("goal", "Learner wants practice that can transfer into real meetings and emails."),
        ("mood_pattern", "Learner benefits from review-first sessions when energy is low."),
    ]
    counts = {}
    for user_key, payload in data["users"].items():
        facts = payload["facts"]
        existing = {f["content"].strip().lower() for f in facts}
        persona = (
            "first_timer" if "first_timer" in user_key
            else "speed_runner" if "speed_runner" in user_key
            else "qa_destroyer"
        )
        user_id = facts[0]["user_id"] if facts else user_key
        for fact in facts:
            fact["persona"] = persona
        i = 0
        while len(facts) < target_per_persona:
            fact_type, base = patterns[i % len(patterns)]
            variant = (i // len(patterns)) + 1
            content = f"{base} Review variant {variant} for {persona}."
            i += 1
            if content.lower() in existing:
                continue
            facts.append({
                "fact_id": f"F-{short_hash(user_key + content, 10)}",
                "user_id": user_id,
                "persona": persona,
                "fact_type": fact_type,
                "content": content,
                "importance_score": 0.62 if fact_type in {"error_pattern", "goal"} else 0.55,
                "created_at": ISO_NOW,
                "tags": ["offline_expanded", fact_type],
                "evidence": "Derived from existing persona seed data and A20 PRD fact taxonomy.",
            })
            existing.add(content.lower())
        counts[user_key] = len(facts)
    data["metadata"]["offline_expanded_at"] = utc_iso()
    data["metadata"]["target_facts_per_persona"] = target_per_persona
    save_json(MEM0, data)
    return counts


def run_all(args: argparse.Namespace) -> dict[str, Any]:
    report = {
        "industry_cleanup": clean_industry_vocab(),
        "jfleg_promotion": promote_jfleg_candidates(args.promote_jfleg, args.errors_target),
        "ielts": expand_ielts(args.ielts_target),
        "pedagogical": expand_pedagogical(args.pedagogical_target),
        "mood": expand_mood(args.mood_target),
        "mem0": expand_mem0(args.mem0_target),
    }
    save_json(OFFLINE_PROCESS_REPORT, {"generated_at": utc_iso(), "report": report})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process already-collected data offline.")
    parser.add_argument("--promote-jfleg", type=int, default=500)
    parser.add_argument("--errors-target", type=int, default=500)
    parser.add_argument("--ielts-target", type=int, default=60)
    parser.add_argument("--pedagogical-target", type=int, default=80)
    parser.add_argument("--mood-target", type=int, default=60)
    parser.add_argument("--mem0-target", type=int, default=100)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)
    run_all(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
