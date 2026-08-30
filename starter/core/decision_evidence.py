from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal

from starter.contracts import RetrievalResult
from starter.core.clarification import candidate_attribute_scores
from starter.core.state import SessionState


STABILITY_STATUSES = (
    "available",
    "no_previous_candidates",
    "no_comparable_candidates",
    "current_retrieval_degraded",
    "previous_response_degraded",
    "retrieval_unavailable",
)
SCORE_MARGIN_STATUSES = (
    "route_local_uncalibrated",
    "insufficient_candidates",
    "missing_scores",
    "invalid_scores",
    "non_monotonic_scores",
    "retrieval_unavailable",
)
CONSTRAINT_COVERAGE_STATUSES = (
    "available",
    "no_active_constraints",
    "no_candidates",
    "structured_matches_unavailable",
    "retrieval_unavailable",
)

StabilityStatus = Literal[
    "available",
    "no_previous_candidates",
    "no_comparable_candidates",
    "current_retrieval_degraded",
    "previous_response_degraded",
    "retrieval_unavailable",
]
ScoreMarginStatus = Literal[
    "route_local_uncalibrated",
    "insufficient_candidates",
    "missing_scores",
    "invalid_scores",
    "non_monotonic_scores",
    "retrieval_unavailable",
]
ConstraintCoverageStatus = Literal[
    "available",
    "no_active_constraints",
    "no_candidates",
    "structured_matches_unavailable",
    "retrieval_unavailable",
]


@dataclass(frozen=True)
class DecisionEvidence:
    """A-side, label-free evidence available to a later dialogue policy."""

    source_status: str
    turn: int
    top_k: int
    pool_size: int
    reported_pool_size: int
    pool_size_consistent: bool
    current_candidate_depth: int
    previous_candidate_depth: int
    candidate_stability: float | None
    stability_metric: str
    stability_status: StabilityStatus
    top_score_margin: float | None
    score_margin_status: ScoreMarginStatus
    score_margin_usable: bool
    constraint_coverage: float | None
    constraint_coverage_status: ConstraintCoverageStatus
    attribute_partition_scores: dict[str, float]
    evidence_candidate_count: int
    relaxation_used: bool
    degraded: bool
    route_failure_count: int
    exhausted_attributes: tuple[str, ...]

    def to_diagnostics(self) -> dict:
        return asdict(self)


def _ordered_unique(values: list[str], depth: int) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= depth:
            break
    return tuple(result)


def _candidate_stability(
    current_ids: tuple[str, ...],
    previous_ids: tuple[str, ...],
) -> tuple[float | None, StabilityStatus]:
    if not previous_ids:
        return None, "no_previous_candidates"
    union = set(current_ids) | set(previous_ids)
    if not union:
        return None, "no_comparable_candidates"
    overlap = len(set(current_ids) & set(previous_ids)) / len(union)
    return round(overlap, 6), "available"


def _score_margin(result: RetrievalResult) -> tuple[float | None, ScoreMarginStatus, bool]:
    if len(result.candidates) < 2:
        return None, "insufficient_candidates", False
    first = result.candidates[0].score
    second = result.candidates[1].score
    if first is None or second is None:
        return None, "missing_scores", False
    if (
        isinstance(first, bool)
        or isinstance(second, bool)
        or not isinstance(first, (int, float))
        or not isinstance(second, (int, float))
        or not math.isfinite(first)
        or not math.isfinite(second)
    ):
        return None, "invalid_scores", False
    if first < second:
        return None, "non_monotonic_scores", False
    # Candidate.score is route-local today. The value is observable for source
    # auditing but remains unusable by A9 until a shared calibration exists.
    return round(float(first - second), 8), "route_local_uncalibrated", False


def _constraint_coverage(
    result: RetrievalResult,
    active_constraints: list[dict],
) -> tuple[float | None, ConstraintCoverageStatus]:
    active_keys = {
        (
            str(item.get("attribute") or ""),
            str(item.get("normalized_value") or item.get("raw_value") or ""),
        )
        for item in active_constraints
        if item.get("active", True)
        and str(item.get("attribute") or "")
        and str(item.get("normalized_value") or item.get("raw_value") or "")
    }
    if not active_keys:
        return None, "no_active_constraints"
    if not result.candidates:
        return None, "no_candidates"

    total = 0.0
    for candidate in result.candidates:
        matches = candidate.diagnostics.get("structured_matches")
        if not isinstance(matches, list) or not all(isinstance(item, dict) for item in matches):
            return None, "structured_matches_unavailable"
        matched_keys = {
            (
                str(item.get("attribute") or ""),
                str(item.get("value") or item.get("normalized_value") or ""),
            )
            for item in matches
        }
        total += len(active_keys & matched_keys) / len(active_keys)
    return round(total / len(result.candidates), 6), "available"


def build_decision_evidence(
    result: RetrievalResult | None,
    *,
    state: SessionState,
    turn: int,
    top_k: int,
    response_fallback_used: bool = False,
    attribute_partition_scores: dict[str, float] | None = None,
) -> DecisionEvidence:
    """Summarize full retrieval evidence without exposing Candidate IDs/text."""

    exhausted = tuple(sorted(state.asked_attributes | state.no_preference_attributes))
    if result is None:
        return DecisionEvidence(
            source_status="retrieval_unavailable",
            turn=turn,
            top_k=top_k,
            pool_size=0,
            reported_pool_size=0,
            pool_size_consistent=True,
            current_candidate_depth=0,
            previous_candidate_depth=min(top_k, len(state.previous_candidate_ids)),
            candidate_stability=None,
            stability_metric="top_k_jaccard",
            stability_status="retrieval_unavailable",
            top_score_margin=None,
            score_margin_status="retrieval_unavailable",
            score_margin_usable=False,
            constraint_coverage=None,
            constraint_coverage_status="retrieval_unavailable",
            attribute_partition_scores={},
            evidence_candidate_count=0,
            relaxation_used=False,
            degraded=True,
            route_failure_count=0,
            exhausted_attributes=exhausted,
        )

    current_ids = _ordered_unique(
        [candidate.parent_asin for candidate in result.candidates],
        top_k,
    )
    previous_ids = _ordered_unique(state.previous_candidate_ids, top_k)
    diagnostics = result.diagnostics
    pool_size_consistent = len(result.candidates) == diagnostics.candidate_count
    current_degraded = bool(
        diagnostics.fallback_used
        or diagnostics.route_failures
        or not pool_size_consistent
        or len(current_ids) < top_k
        or response_fallback_used
    )
    previous_diagnostics = state.previous_diagnostics or {}
    previous_decision_evidence = previous_diagnostics.get("decision_evidence")
    previous_retrieval = previous_diagnostics.get("retrieval")
    previous_degraded = bool(
        previous_diagnostics.get("fallback_used")
        or (
            isinstance(previous_decision_evidence, dict)
            and previous_decision_evidence.get("degraded") is True
        )
        or (
            isinstance(previous_retrieval, dict)
            and (
                previous_retrieval.get("fallback_used")
                or previous_retrieval.get("route_failures")
            )
        )
    )
    if current_degraded:
        stability, stability_status = None, "current_retrieval_degraded"
    elif previous_degraded:
        stability, stability_status = None, "previous_response_degraded"
    else:
        stability, stability_status = _candidate_stability(current_ids, previous_ids)
    score_margin, score_status, score_usable = _score_margin(result)
    coverage, coverage_status = _constraint_coverage(result, state.active_constraints)
    candidate_texts = [candidate.evidence_text or "" for candidate in result.candidates]
    evidence_count = sum(bool(text.strip()) for text in candidate_texts)
    return DecisionEvidence(
        source_status="available",
        turn=turn,
        top_k=top_k,
        pool_size=len(result.candidates),
        reported_pool_size=diagnostics.candidate_count,
        pool_size_consistent=pool_size_consistent,
        current_candidate_depth=len(current_ids),
        previous_candidate_depth=len(previous_ids),
        candidate_stability=stability,
        stability_metric="top_k_jaccard",
        stability_status=stability_status,
        top_score_margin=score_margin,
        score_margin_status=score_status,
        score_margin_usable=score_usable,
        constraint_coverage=coverage,
        constraint_coverage_status=coverage_status,
        attribute_partition_scores=(
            dict(attribute_partition_scores)
            if attribute_partition_scores is not None
            else candidate_attribute_scores(candidate_texts)
        ),
        evidence_candidate_count=evidence_count,
        relaxation_used=bool(
            diagnostics.relaxed_constraints
            or "structured_filter_relaxed" in diagnostics.notes
        ),
        degraded=current_degraded,
        route_failure_count=len(diagnostics.route_failures),
        exhausted_attributes=exhausted,
    )
