from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from app.models.processed_dataset_schemas import LessonContent, LessonSummary

try:  # pragma: no cover - exercised only in environments without PyYAML
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def _find_repo_root() -> Path:
    env_root = os.getenv("REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()

    env_curriculum_root = os.getenv("CURRICULUM_ROOT")
    if env_curriculum_root:
        curriculum_root = Path(env_curriculum_root).resolve()
        if curriculum_root.name == "curriculum_skeleton" and curriculum_root.parent.name == "data":
            return curriculum_root.parent.parent
        return curriculum_root.parent

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "data" / "curriculum_skeleton").exists():
            return parent

    for parent in current.parents:
        if (parent / "alembic.ini").exists():
            return parent

    return current.parents[min(2, len(current.parents) - 1)]


REPO_ROOT = _find_repo_root()
CURRICULUM_ROOT = Path(os.getenv("CURRICULUM_ROOT", REPO_ROOT / "data" / "curriculum_skeleton")).resolve()
CEFR_ORDER = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
LESSON_FILE_RE = re.compile(r"^(?P<order>\d+)_?(?P<slug>.+)$")
FRONTMATTER_RE = re.compile(r"\A---\s*\r?\n(?P<body>.*?)\r?\n---\s*\r?\n?", re.DOTALL)


def list_lessons(cefr_level: str | None = None) -> list[LessonSummary]:
    level_filter = cefr_level.upper() if cefr_level else None
    lessons = [
        _build_summary(path)
        for path in CURRICULUM_ROOT.glob("*/*.md")
        if level_filter is None or path.parent.name.upper() == level_filter
    ]
    return sorted(lessons, key=_summary_sort_key)


def get_lesson(lesson_id: str) -> LessonContent:
    for summary in list_lessons():
        if summary.lesson_id == lesson_id:
            lesson_path = REPO_ROOT / summary.lesson_path
            markdown = _strip_frontmatter(lesson_path.read_text(encoding="utf-8")).strip()
            return LessonContent(**summary.model_dump(), markdown=markdown)
    raise KeyError(f"Lesson not found: {lesson_id}")


def get_next_lesson(user_id: str, cefr_level: str) -> LessonSummary:
    _ = user_id
    lessons = list_lessons(cefr_level)
    if not lessons:
        raise KeyError(f"No lessons found for CEFR level: {cefr_level}")
    return lessons[0]


def _build_summary(markdown_path: Path) -> LessonSummary:
    metadata_path = markdown_path.with_suffix(".yaml")
    metadata = _load_yaml_metadata(metadata_path)
    if not metadata:
        metadata = _load_markdown_frontmatter(markdown_path)

    order_index = _numeric_prefix(markdown_path)
    lesson_id = str(metadata.get("topic_id") or metadata.get("lesson_id") or _lesson_id_from_stem(markdown_path.stem))
    cefr_level = str(metadata.get("cefr_level") or markdown_path.parent.name).upper()
    title = str(metadata.get("title") or _title_from_markdown(markdown_path) or lesson_id.replace("_", " "))

    return LessonSummary(
        lesson_id=lesson_id,
        title=title,
        cefr_level=cefr_level,
        lesson_path=_relative_path(markdown_path),
        metadata_path=_relative_path(metadata_path) if metadata_path.exists() else None,
        order_index=order_index,
        skill_type=metadata.get("skill_type"),
        metadata=metadata,
    )


def _summary_sort_key(summary: LessonSummary) -> tuple[int, int, str]:
    cefr_rank = CEFR_ORDER.get(summary.cefr_level.upper(), 999)
    return (cefr_rank, summary.order_index, summary.lesson_id)


def _numeric_prefix(path: Path) -> int:
    match = LESSON_FILE_RE.match(path.stem)
    if match:
        return int(match.group("order"))
    return 9999


def _lesson_id_from_stem(stem: str) -> str:
    match = LESSON_FILE_RE.match(stem)
    return match.group("slug") if match else stem


def _load_yaml_metadata(path: Path) -> dict[str, Any]:
    if not path.exists() or yaml is None:
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _load_markdown_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match or yaml is None:
        return {}
    loaded = yaml.safe_load(match.group("body"))
    return loaded if isinstance(loaded, dict) else {}


def _strip_frontmatter(markdown: str) -> str:
    return FRONTMATTER_RE.sub("", markdown, count=1)


def _title_from_markdown(path: Path) -> str | None:
    for line in _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _relative_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()
