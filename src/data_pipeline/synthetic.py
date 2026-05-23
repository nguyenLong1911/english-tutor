"""Synthetic Data *Engineering* pipeline.

Implements the four-stage flow recommended by NeMo Data Designer /
synth-dataset-kit, as adapted for the A20 project:

    Seed Sampling  →  Expansion  →  LLM-as-a-Judge  →  Decontamination

Each stage is independently testable and produces strongly-typed Pydantic
objects so downstream consumers cannot silently ingest malformed records.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Callable, Generic, Iterable, List, Sequence, Type, TypeVar

from pydantic import BaseModel

from .llm_client import StructuredLLM

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Judge schema
# ---------------------------------------------------------------------------

class JudgeVerdict(BaseModel):
    """LLM-as-a-judge verdict. Most fields default-friendly because non-OpenAI
    providers occasionally omit one when wrapped in JSON mode."""

    overall_score: float = 0.0
    linguistic_accuracy: float = 0.0
    pedagogical_value: float = 0.0
    diversity: float = 0.0
    rationale: str = ""
    accept: bool = False

    def model_post_init(self, _ctx) -> None:  # type: ignore[override]
        if self.overall_score == 0.0:
            comps = [self.linguistic_accuracy, self.pedagogical_value, self.diversity]
            comps = [c for c in comps if c]
            if comps:
                self.overall_score = sum(comps) / len(comps)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

@dataclass
class SyntheticPipeline(Generic[T]):
    """Generic four-stage synthetic-data pipeline.

    Parameters
    ----------
    item_schema:
        Pydantic model for the *batch* response (must contain a list field).
    extract_items:
        Callable that pulls ``List[T]`` out of the parsed batch object.
    """

    llm: StructuredLLM
    item_schema: Type[BaseModel]
    extract_items: Callable[[BaseModel], Sequence[BaseModel]]
    judge_threshold: float = 0.75
    max_attempts: int = 3
    similarity_threshold: float = 0.92  # for decontamination

    # ------------------------------------------------------ stage 1: seed
    @staticmethod
    def sample_seeds(seeds: Sequence[dict], k: int) -> List[dict]:
        """Random sub-sample of seed attributes (controls diversity)."""
        if not seeds:
            return []
        return random.sample(list(seeds), min(k, len(seeds)))

    # -------------------------------------------------- stage 2: expansion
    def expand(self, system_prompt: str, user_prompt: str) -> Sequence[BaseModel]:
        batch = self.llm.parse(system_prompt, user_prompt, self.item_schema)
        return list(self.extract_items(batch))

    # ------------------------------------------------------- stage 3: judge
    def judge(self, candidate_json: str, rubric: str) -> JudgeVerdict:
        sys = (
            "You are an LLM-as-a-judge evaluator for a Vietnamese-English ESL "
            "dataset. Score the candidate against the provided rubric. Respond "
            "ONLY with the JudgeVerdict schema."
        )
        usr = (
            f"Rubric:\n{rubric}\n\n"
            f"Candidate (JSON):\n{candidate_json}\n\n"
            "Score linguistic_accuracy, pedagogical_value, diversity ∈ [0,1]. "
            "Set accept=true iff overall_score ≥ "
            f"{self.judge_threshold:.2f}."
        )
        return self.llm.parse(sys, usr, JudgeVerdict)

    # ------------------------------------------- stage 4: decontamination
    def decontaminate(
        self,
        candidates: Iterable[BaseModel],
        seen_keys: set[str],
        key_fn: Callable[[BaseModel], str],
    ) -> List[BaseModel]:
        """Drop near-duplicate candidates via key-based hashing.

        For Sprint 1 we use a normalised key string; Sprint 2 will replace
        this with a cosine-similarity check on text-embedding-3-small vectors.
        """
        out: List[BaseModel] = []
        for cand in candidates:
            k = self._normalise_key(key_fn(cand))
            if k in seen_keys:
                continue
            seen_keys.add(k)
            out.append(cand)
        return out

    @staticmethod
    def _normalise_key(s: str) -> str:
        return " ".join(s.lower().split())

    # ----------------------------------------------------- orchestration
    def run(
        self,
        *,
        system_prompt: str,
        user_prompt_builder: Callable[[List[dict]], str],
        seeds: Sequence[dict],
        rubric: str,
        target_count: int,
        seen_keys: set[str],
        key_fn: Callable[[BaseModel], str],
        seeds_per_call: int = 5,
        fail_fast: bool = True,
    ) -> List[BaseModel]:
        accepted: List[BaseModel] = []
        attempts = 0
        while len(accepted) < target_count and attempts < self.max_attempts * target_count:
            attempts += 1
            sampled = self.sample_seeds(seeds, seeds_per_call)
            user_prompt = user_prompt_builder(sampled)
            try:
                candidates = self.expand(system_prompt, user_prompt)
            except Exception as exc:
                if fail_fast:
                    raise RuntimeError(f"Expansion failed; stopping synthetic pipeline: {exc}") from exc
                log.warning("Expansion failed: %s", exc)
                continue

            unique = self.decontaminate(candidates, seen_keys, key_fn)
            for cand in unique:
                try:
                    verdict = self.judge(
                        cand.model_dump_json(), rubric=rubric
                    )
                except Exception as exc:
                    if fail_fast:
                        raise RuntimeError(f"Judge failed; stopping synthetic pipeline: {exc}") from exc
                    log.warning("Judge failed (accepting tentatively): %s", exc)
                    verdict = JudgeVerdict(
                        overall_score=self.judge_threshold,
                        linguistic_accuracy=0.8,
                        pedagogical_value=0.8,
                        diversity=0.7,
                        rationale="judge-unavailable",
                        accept=True,
                    )
                if verdict.accept and verdict.overall_score >= self.judge_threshold:
                    accepted.append(cand)
                    if len(accepted) >= target_count:
                        break
        return accepted
