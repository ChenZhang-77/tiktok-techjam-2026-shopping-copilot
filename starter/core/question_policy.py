from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Literal

from starter.contracts import RetrievalResult
from starter.core.clarification import available_attributes, choose_clarification
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


class QuestionPolicy:
    """One read-only A-side seam for clarification decisions."""

    policy_version = "a14-0-legacy-parity-v1"

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
        try:
            decision_evidence = build_decision_evidence(
                result,
                state=state,
                turn=turn,
                top_k=top_k,
                response_fallback_used=response_fallback_used,
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
        except Exception:
            eligible = ()
            attribute, question = None, ""
            fallback_reason = "legacy_policy_error"
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
            "mode": "legacy_parity",
            "eligible_attributes": list(eligible),
            "baseline_action": action,
            "baseline_attribute": attribute,
            "reason_code": reason_code,
            "evidence_status": evidence_status,
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
