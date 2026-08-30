from __future__ import annotations

from dataclasses import dataclass
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

    def decide(
        self,
        *,
        state: SessionState,
        result: RetrievalResult | None,
        turn: int,
        top_k: int,
        response_fallback_used: bool = False,
    ) -> QuestionPolicyOutcome:
        fallback_reason: str | None = None
        try:
            decision_evidence = build_decision_evidence(
                result,
                state=state,
                turn=turn,
                top_k=top_k,
                response_fallback_used=response_fallback_used,
            )
            candidate_texts = [
                candidate.evidence_text or ""
                for candidate in (
                    result.candidates[:top_k] if result is not None else []
                )
            ]
        except Exception:
            decision_evidence = build_decision_evidence(
                None,
                state=state,
                turn=turn,
                top_k=top_k,
                response_fallback_used=True,
            )
            candidate_texts = []
            fallback_reason = "invalid_retrieval_evidence"
        eligible = available_attributes(state) if turn < 10 else ()
        attribute, question = choose_clarification(
            state,
            turn=turn,
            candidate_texts=candidate_texts,
            decision_evidence=decision_evidence,
        )
        action: Literal["ask", "stop"] = "ask" if attribute else "stop"
        reason_code = (
            "legacy_ask"
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
        return QuestionPolicyOutcome(
            decision=decision,
            decision_evidence=decision_evidence,
            diagnostics=diagnostics,
            usage={"prompt_tokens": 0, "completion_tokens": 0},
        )
