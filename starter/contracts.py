from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from starter.core.planner import Strategy


FORBIDDEN_RETRIEVAL_REQUEST_KEYS = {
    "ground_truth",
    "target",
    "target_asin",
    "target_parent_asin",
    "scenario_type",
    "difficulty_bucket",
    "intent_card",
    "behavior",
}


@dataclass(frozen=True)
class RetrievalRequest:
    session_id: str
    turn: int
    top_k: int
    query: str
    intent: str
    strategy: Strategy
    active_constraints: list[dict] = field(default_factory=list)
    no_preference_attributes: list[str] = field(default_factory=list)
    rejected_constraints: list[dict] = field(default_factory=list)
    asked_attributes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "turn": self.turn,
            "top_k": self.top_k,
            "query": self.query,
            "intent": self.intent,
            "strategy": self.strategy.to_dict(),
            "active_constraints": [dict(item) for item in self.active_constraints],
            "no_preference_attributes": list(self.no_preference_attributes),
            "rejected_constraints": [dict(item) for item in self.rejected_constraints],
            "asked_attributes": list(self.asked_attributes),
        }


@dataclass(frozen=True)
class Candidate:
    parent_asin: str
    score: float | None = None
    source: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_recommendation(self) -> dict:
        payload = {"parent_asin": self.parent_asin}
        if self.score is not None:
            payload["score"] = self.score
        return payload


@dataclass(frozen=True)
class RetrievalDiagnostics:
    route: str
    candidate_count: int
    fallback_used: bool = False
    latency_ms: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalResult:
    candidates: list[Candidate]
    diagnostics: RetrievalDiagnostics

    def recommendations(self, top_k: int) -> list[dict]:
        return [candidate.to_recommendation() for candidate in self.candidates[:top_k]]


def validate_retrieval_request(payload: dict) -> None:
    leaked = FORBIDDEN_RETRIEVAL_REQUEST_KEYS & set(payload)
    if leaked:
        raise ValueError(f"RetrievalRequest contains evaluator-only fields: {sorted(leaked)}")
