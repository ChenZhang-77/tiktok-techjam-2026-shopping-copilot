from __future__ import annotations

from dataclasses import dataclass

from starter.core.state import SessionState


@dataclass(frozen=True)
class Strategy:
    intent: str
    lexical_weight: float
    structured_weight: float
    semantic_weight: float
    retrieval_depth: int
    allow_hard_filter: bool
    clarification_enabled: bool
    fallback_mode: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "lexical_weight": self.lexical_weight,
            "structured_weight": self.structured_weight,
            "semantic_weight": self.semantic_weight,
            "retrieval_depth": self.retrieval_depth,
            "allow_hard_filter": self.allow_hard_filter,
            "clarification_enabled": self.clarification_enabled,
            "fallback_mode": self.fallback_mode,
            "reason": self.reason,
        }


def plan_strategy(state: SessionState, *, turn: int, top_k: int) -> Strategy:
    intent = state.intent or "browsing"
    active_count = sum(1 for item in state.active_constraints if item.get("active", True))
    has_hard = any(bool(item.get("hard")) for item in state.active_constraints if item.get("active", True))

    if intent == "buying":
        depth = max(top_k, 80 if active_count >= 2 else 60)
        return Strategy(
            intent="buying",
            lexical_weight=0.72,
            structured_weight=0.28,
            semantic_weight=0.0,
            retrieval_depth=depth,
            allow_hard_filter=has_hard and active_count >= 2,
            clarification_enabled=turn < 10,
            fallback_mode="lexical",
            reason=f"buying intent with {active_count} active constraints",
        )

    depth = max(top_k, 120 if active_count <= 1 else 100)
    return Strategy(
        intent="browsing",
        lexical_weight=0.62,
        structured_weight=0.20,
        semantic_weight=0.18,
        retrieval_depth=depth,
        allow_hard_filter=False,
        clarification_enabled=turn < 10,
        fallback_mode="broad_lexical",
        reason=f"browsing intent with {active_count} active constraints",
    )
