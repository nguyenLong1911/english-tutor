from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Verdict = Literal["pass", "fail", "blocked", "error"]


@dataclass(frozen=True)
class EvalStep:
    id: str
    action: str
    user: str = "primary"
    message: str | None = None
    message_type: str = "PRACTICE"
    expect: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalCase:
    id: str
    title: str
    priority: str
    objective: str
    persona: dict[str, Any]
    steps: list[EvalStep]
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    case_id: str
    step_id: str
    action: str
    verdict: Verdict
    trace_id: str
    latency_ms: int
    feedback: str
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)
    checks: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "step_id": self.step_id,
            "action": self.action,
            "verdict": self.verdict,
            "trace_id": self.trace_id,
            "latency_ms": self.latency_ms,
            "feedback": self.feedback,
            "request": self.request,
            "response": self.response,
            "checks": self.checks,
        }

@dataclass
class CaseResult:
    case: EvalCase
    verdict: Verdict
    feedback: str
    steps: list[StepResult]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.case.id,
            "title": self.case.title,
            "priority": self.case.priority,
            "objective": self.case.objective,
            "verdict": self.verdict,
            "feedback": self.feedback,
            "steps": [step.as_dict() for step in self.steps],
            "evidence": self.case.evidence,
        }
