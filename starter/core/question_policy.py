from __future__ import annotations

from dataclasses import asdict, dataclass
import time
from typing import Literal

from starter.contracts import RetrievalResult
from starter.core.clarification import (
    CANDIDATE_PHRASE_PATTERNS,
    CANDIDATE_SINGLE_TERMS,
    WORD_RE,
    available_attributes,
    choose_clarification,
)
from starter.core.decision_evidence import DecisionEvidence, build_decision_evidence
from starter.core.state import SessionState


@dataclass(frozen=True)
class QuestionDecision:
    action: Literal["ask", "stop"]
    attribute: str | None
    question: str
    reason_code: str
    evidence_status: str


@dataclass(frozen=True)
class QuestionPolicyOutcome:
    decision: QuestionDecision
    decision_evidence: DecisionEvidence
    diagnostics: dict[str, object]
    usage: dict[str, int]


ATTRIBUTE_ORDER = (
    "category",
    "material",
    "color",
    "size",
    "style",
    "brand",
    "budget",
    "feature",
    "use_case",
    "other",
)
ATTRIBUTE_EVIDENCE_STATUSES = (
    "available",
    "partial",
    "unavailable",
    "uncalibrated",
    "degraded",
    "not_applicable",
)
BOUNDED_PARTITION_ATTRIBUTES = frozenset(CANDIDATE_SINGLE_TERMS)
UNTAGGED_CANDIDATE_ATTRIBUTES = frozenset({"size", "brand", "budget"})


@dataclass(frozen=True)
class AttributeQuestionEvidence:
    attribute: str
    status: Literal[
        "available",
        "partial",
        "unavailable",
        "uncalibrated",
        "degraded",
        "not_applicable",
    ]
    source: str
    lifecycle: str
    value_range: str
    candidate_coverage: float | None
    value_count: int | None
    rank_weighted_split: float | None
    answerability_status: str
    actionability_status: str
    comparability_family: str | None
    eligible: bool
    eligibility_status: str
    missing_data_behavior: str

    def to_diagnostics(self) -> dict[str, object]:
        return asdict(self)


def _candidate_partition(
    candidate_texts: list[str],
    attribute: str,
) -> tuple[float, int, float, int]:
    single_terms = CANDIDATE_SINGLE_TERMS[attribute]
    phrase_patterns = CANDIDATE_PHRASE_PATTERNS[attribute]
    covered = 0
    value_weights: dict[str, float] = {}
    for rank, text in enumerate(candidate_texts):
        tokens = set(WORD_RE.findall(text.lower()))
        hits = single_terms & tokens
        hits.update(
            term for term, pattern in phrase_patterns.items() if pattern.search(text)
        )
        if not hits:
            continue
        covered += 1
        candidate_weight = 1.0 / (rank + 1)
        per_value_weight = candidate_weight / len(hits)
        for value in hits:
            value_weights[value] = value_weights.get(value, 0.0) + per_value_weight
    coverage = covered / max(len(candidate_texts), 1)
    total_weight = sum(value_weights.values())
    split = (
        1.0 - max(value_weights.values()) / total_weight
        if value_weights and total_weight > 0
        else 0.0
    )
    return round(coverage, 6), len(value_weights), round(split, 6), covered


def _candidate_partitions(
    candidate_texts: list[str],
) -> dict[str, tuple[float, int, float, int]]:
    return {
        attribute: _candidate_partition(candidate_texts, attribute)
        for attribute in BOUNDED_PARTITION_ATTRIBUTES
    }


def _legacy_partition_scores(
    partitions: dict[str, tuple[float, int, float, int]],
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for attribute, (coverage, value_count, _split, covered) in partitions.items():
        if value_count < 2 or covered < 2:
            continue
        diversity = min(value_count, 6) / 6.0
        scores[attribute] = round(0.65 * diversity + 0.35 * coverage, 6)
    return scores


def _eligibility_status(
    *,
    state: SessionState | None,
    attribute: str,
    eligible: set[str],
    turn: int,
) -> str:
    if turn >= 10:
        return "final_turn"
    if state is None:
        return "policy_state_invalid"
    if attribute in state.asked_attributes:
        return "asked"
    if attribute in state.no_preference_attributes:
        return "no_preference"
    active = {
        str(item.get("attribute"))
        for item in state.active_constraints
        if isinstance(item, dict) and item.get("active", True)
    }
    if attribute in active and attribute != "other":
        return "satisfied"
    if attribute in eligible:
        return "eligible"
    return "not_in_legacy_priority"


def build_attribute_question_evidence(
    *,
    state: SessionState | None,
    decision_evidence: DecisionEvidence,
    candidate_texts: list[str],
    candidate_partitions: dict[str, tuple[float, int, float, int]],
    eligible_attributes: tuple[str, ...],
    turn: int,
) -> tuple[AttributeQuestionEvidence, ...]:
    """Compile explicit A14-1 evidence without changing the legacy action."""

    eligible = set(eligible_attributes)
    has_candidate_text = any(text.strip() for text in candidate_texts)
    records: list[AttributeQuestionEvidence] = []
    for attribute in ATTRIBUTE_ORDER:
        coverage: float | None = None
        value_count: int | None = None
        rank_weighted_split: float | None = None
        comparability_family: str | None = None
        if attribute in BOUNDED_PARTITION_ATTRIBUTES:
            source = "candidate_evidence_text_bounded_vocabulary"
            if decision_evidence.source_status != "available":
                status = "unavailable"
            elif decision_evidence.degraded:
                status = "degraded"
            else:
                coverage, value_count, rank_weighted_split, covered = (
                    candidate_partitions.get(attribute, (0.0, 0, 0.0, 0))
                )
                comparability_family = "bounded_candidate_vocabulary_v1"
                status = (
                    "available"
                    if value_count >= 2 and covered >= 2
                    else "partial"
                    if value_count > 0
                    else "unavailable"
                )
        elif attribute == "feature":
            source = "candidate_evidence_text_unstructured"
            status = (
                "unavailable"
                if decision_evidence.source_status != "available"
                or not has_candidate_text
                else "degraded"
                if decision_evidence.degraded
                else "uncalibrated"
            )
        elif attribute in UNTAGGED_CANDIDATE_ATTRIBUTES:
            source = "candidate_field_tags_absent"
            status = (
                "degraded"
                if decision_evidence.source_status == "available"
                and decision_evidence.degraded
                else "unavailable"
            )
        else:
            source = "controlled_legacy_fallback"
            status = "not_applicable"

        eligibility_status = _eligibility_status(
            state=state,
            attribute=attribute,
            eligible=eligible,
            turn=turn,
        )
        records.append(
            AttributeQuestionEvidence(
                attribute=attribute,
                status=status,
                source=source,
                lifecycle="current_turn_full_pool",
                value_range=(
                    "coverage_and_split_float_0_1;value_count_int_gte_0;null_when_not_comparable"
                ),
                candidate_coverage=coverage,
                value_count=value_count,
                rank_weighted_split=rank_weighted_split,
                answerability_status=(
                    "open_text_fallback"
                    if attribute == "other"
                    else "canonical_question"
                ),
                actionability_status=(
                    "residual_extractor"
                    if attribute == "other"
                    else "bounded_or_residual_extractor"
                    if attribute == "feature"
                    else "bounded_extractor"
                ),
                comparability_family=comparability_family,
                eligible=attribute in eligible,
                eligibility_status=eligibility_status,
                missing_data_behavior=(
                    "comparable_within_family"
                    if status == "available"
                    else "controlled_legacy_fallback"
                    if status == "not_applicable"
                    else "preserve_legacy_action"
                ),
            )
        )
    return tuple(records)


class QuestionPolicy:
    """One read-only A-side seam for clarification decisions."""

    policy_version = "a14-1-attribute-evidence-v1"

    def __init__(self) -> None:
        self.last_latency_ms: float | None = None

    def decide(
        self,
        *,
        state: SessionState,
        result: RetrievalResult | None,
        turn: int,
        top_k: int,
        response_fallback_used: bool = False,
    ) -> QuestionPolicyOutcome:
        started = time.perf_counter()
        fallback_reason: str | None = None
        evidence_state: SessionState | None = state
        try:
            full_candidate_texts = [
                candidate.evidence_text or "" for candidate in result.candidates
            ] if result is not None else []
            if not all(isinstance(text, str) for text in full_candidate_texts):
                raise ValueError("candidate evidence text must be strings")
            candidate_partitions = _candidate_partitions(full_candidate_texts)
            decision_evidence = build_decision_evidence(
                result,
                state=state,
                turn=turn,
                top_k=top_k,
                response_fallback_used=response_fallback_used,
                attribute_partition_scores=_legacy_partition_scores(
                    candidate_partitions
                ),
            )
            candidates = result.candidates[:top_k] if result is not None else []
            evidence_by_id = {
                candidate.parent_asin: candidate.evidence_text or ""
                for candidate in candidates
            }
            candidate_texts = [
                evidence_by_id.get(candidate.parent_asin, "")
                for candidate in candidates
            ]
        except Exception:
            safe_state = SessionState(
                session_id=str(getattr(state, "session_id", "question-policy-fallback")),
                user_profile={},
            )
            asked_attributes = getattr(state, "asked_attributes", set())
            no_preference_attributes = getattr(
                state,
                "no_preference_attributes",
                set(),
            )
            if isinstance(asked_attributes, set):
                safe_state.asked_attributes = {
                    str(attribute) for attribute in asked_attributes
                }
            if isinstance(no_preference_attributes, set):
                safe_state.no_preference_attributes = {
                    str(attribute) for attribute in no_preference_attributes
                }
            decision_evidence = build_decision_evidence(
                None,
                state=safe_state,
                turn=turn,
                top_k=top_k,
                response_fallback_used=True,
            )
            candidate_texts = []
            full_candidate_texts = []
            candidate_partitions = {}
            evidence_state = safe_state
            fallback_reason = "invalid_retrieval_evidence"
        try:
            eligible = available_attributes(state) if turn < 10 else ()
            attribute, question = choose_clarification(
                state,
                turn=turn,
                candidate_texts=candidate_texts,
                decision_evidence=decision_evidence,
            )
            if attribute is not None and (
                attribute not in eligible or not question or turn >= 10
            ):
                raise ValueError("legacy clarification returned an invalid action")
            evidence_state = state
        except Exception:
            eligible = ()
            attribute, question = None, ""
            evidence_state = None
            fallback_reason = "legacy_policy_error"
        try:
            attribute_evidence = build_attribute_question_evidence(
                state=evidence_state,
                decision_evidence=decision_evidence,
                candidate_texts=full_candidate_texts,
                candidate_partitions=candidate_partitions,
                eligible_attributes=eligible,
                turn=turn,
            )
        except Exception:
            attribute_evidence = build_attribute_question_evidence(
                state=None,
                decision_evidence=build_decision_evidence(
                    None,
                    state=SessionState(
                        session_id="question-policy-evidence-fallback",
                        user_profile={},
                    ),
                    turn=turn,
                    top_k=top_k,
                    response_fallback_used=True,
                ),
                candidate_texts=[],
                candidate_partitions={},
                eligible_attributes=(),
                turn=turn,
            )
            fallback_reason = fallback_reason or "attribute_evidence_error"
        action: Literal["ask", "stop"] = "ask" if attribute else "stop"
        reason_code = (
            "policy_error_fallback"
            if fallback_reason == "legacy_policy_error"
            else "legacy_ask"
            if attribute
            else "final_turn"
            if turn >= 10
            else "no_eligible_attribute"
        )
        evidence_status = (
            "unavailable"
            if decision_evidence.source_status != "available"
            else "degraded"
            if decision_evidence.degraded
            else "available"
        )
        decision = QuestionDecision(
            action=action,
            attribute=attribute,
            question=question,
            reason_code=reason_code,
            evidence_status=evidence_status,
        )
        diagnostics: dict[str, object] = {
            "policy_version": self.policy_version,
            "mode": "legacy_action_attribute_evidence",
            "eligible_attributes": list(eligible),
            "baseline_action": action,
            "baseline_attribute": attribute,
            "reason_code": reason_code,
            "evidence_status": evidence_status,
            "attribute_evidence": {
                item.attribute: item.to_diagnostics() for item in attribute_evidence
            },
        }
        if fallback_reason is not None:
            diagnostics["fallback_used"] = True
            diagnostics["fallback_reason"] = fallback_reason
        self.last_latency_ms = round((time.perf_counter() - started) * 1000.0, 6)
        return QuestionPolicyOutcome(
            decision=decision,
            decision_evidence=decision_evidence,
            diagnostics=diagnostics,
            usage={"prompt_tokens": 0, "completion_tokens": 0},
        )
