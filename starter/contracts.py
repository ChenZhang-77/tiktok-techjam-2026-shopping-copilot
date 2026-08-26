from __future__ import annotations

import json
import math
from collections.abc import Collection
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
MAX_RETRIEVAL_DEPTH = 500


def _find_forbidden_runtime_keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_RETRIEVAL_REQUEST_KEYS:
                found.add(key)
            found.update(_find_forbidden_runtime_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_find_forbidden_runtime_keys(item))
    return found


def _normalize_json(value: object, subject: str) -> object:
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{subject} must be JSON-serializable") from error


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
    evidence_text: str | None = None

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
    structured_filter_applied: bool = False
    relaxed_constraints: list[dict[str, Any]] = field(default_factory=list)
    filtered_pool_sizes: list[dict[str, Any]] = field(default_factory=list)
    stage_latencies_ms: dict[str, float] = field(default_factory=dict)
    route_candidate_counts: dict[str, int] = field(default_factory=dict)
    route_overlap_counts: dict[str, int] = field(default_factory=dict)
    route_failures: dict[str, str] = field(default_factory=dict)
    rerank_pool_size: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalResult:
    candidates: list[Candidate]
    diagnostics: RetrievalDiagnostics

    def recommendations(self, top_k: int) -> list[dict]:
        return [candidate.to_recommendation() for candidate in self.candidates[:top_k]]


def validate_retrieval_request(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("RetrievalRequest payload must be an object")
    leaked = _find_forbidden_runtime_keys(_normalize_json(payload, "RetrievalRequest payload"))
    if leaked:
        raise ValueError(f"RetrievalRequest contains evaluator-only fields: {sorted(leaked)}")


def validate_retrieval_request_object(request: RetrievalRequest) -> None:
    if not isinstance(request, RetrievalRequest):
        raise TypeError("request must be a RetrievalRequest")
    if not isinstance(request.session_id, str) or not request.session_id:
        raise ValueError("session_id must be a non-empty string")
    if isinstance(request.turn, bool) or not isinstance(request.turn, int) or not 1 <= request.turn <= 10:
        raise ValueError("turn must be an integer from 1 to 10")
    if isinstance(request.top_k, bool) or not isinstance(request.top_k, int) or not 1 <= request.top_k <= 100:
        raise ValueError("top_k must be an integer from 1 to 100")
    if not isinstance(request.query, str):
        raise ValueError("query must be a string")
    if request.intent not in {"buying", "browsing"}:
        raise ValueError("intent must be buying or browsing")
    if not isinstance(request.strategy, Strategy):
        raise ValueError("strategy must be a Strategy")
    if request.strategy.intent != request.intent:
        raise ValueError("strategy intent must match request intent")
    if (
        isinstance(request.strategy.retrieval_depth, bool)
        or not isinstance(request.strategy.retrieval_depth, int)
        or not 1 <= request.strategy.retrieval_depth <= MAX_RETRIEVAL_DEPTH
    ):
        raise ValueError(
            f"strategy retrieval_depth must be an integer from 1 to {MAX_RETRIEVAL_DEPTH}"
        )
    for value in (
        request.strategy.lexical_weight,
        request.strategy.structured_weight,
        request.strategy.semantic_weight,
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError("strategy weights must be finite non-negative numbers")
    if not isinstance(request.active_constraints, list) or not all(
        isinstance(item, dict) for item in request.active_constraints
    ):
        raise ValueError("active_constraints must be a list of objects")
    for field_name, values in (
        ("no_preference_attributes", request.no_preference_attributes),
        ("asked_attributes", request.asked_attributes),
    ):
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise ValueError(f"{field_name} must be a list of strings")
    if not isinstance(request.rejected_constraints, list) or not all(
        isinstance(item, dict) for item in request.rejected_constraints
    ):
        raise ValueError("rejected_constraints must be a list of objects")
    validate_retrieval_request(request.to_dict())


def validate_agent_response(
    payload: object,
    *,
    catalog_ids: Collection[str],
    top_k: int,
    allowed_ask_attributes: Collection[str],
) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Agent response must be an object")
    required_fields = {"message", "ask_attribute", "recommendations"}
    allowed_fields = required_fields | {"usage", "diagnostics"}
    if not required_fields <= set(payload) or not set(payload) <= allowed_fields:
        raise ValueError("Agent response fields do not match the public contract")
    if not isinstance(payload["message"], str):
        raise ValueError("Agent response message must be a string")

    ask_attribute = payload["ask_attribute"]
    if ask_attribute is not None and ask_attribute not in allowed_ask_attributes:
        raise ValueError("Agent response ask_attribute is not allowed")

    recommendations = payload["recommendations"]
    if not isinstance(recommendations, list) or not 0 <= len(recommendations) <= min(top_k, 100):
        raise ValueError("Agent response recommendations exceed the allowed count")
    seen: set[str] = set()
    for item in recommendations:
        if not isinstance(item, dict) or not {"parent_asin"} <= set(item) <= {"parent_asin", "score"}:
            raise ValueError("Agent recommendation fields do not match the public contract")
        parent_asin = item["parent_asin"]
        if not isinstance(parent_asin, str) or not parent_asin or parent_asin not in catalog_ids or parent_asin in seen:
            raise ValueError("Agent recommendation ASIN is invalid or duplicated")
        if "score" in item:
            score = item["score"]
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
                raise ValueError("Agent recommendation score must be a finite number")
        seen.add(parent_asin)

    usage = payload.get("usage")
    if usage is not None:
        if not isinstance(usage, dict) or set(usage) != {"prompt_tokens", "completion_tokens"}:
            raise ValueError("Agent response usage fields do not match the public contract")
        for value in usage.values():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("Agent response token counts must be non-negative integers")

    diagnostics = payload.get("diagnostics")
    if diagnostics is not None and not isinstance(diagnostics, dict):
        raise ValueError("Agent response diagnostics must be an object")
    normalized_diagnostics = _normalize_json(diagnostics, "Agent response diagnostics")
    leaked = _find_forbidden_runtime_keys(normalized_diagnostics)
    if leaked:
        raise ValueError(f"Agent response diagnostics contain evaluator-only fields: {sorted(leaked)}")
