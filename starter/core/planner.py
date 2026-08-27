from __future__ import annotations

from dataclasses import dataclass

from starter.core.state import SessionState


@dataclass(frozen=True)
class StrategyConfig:
    buying_depth_sparse: int = 60
    buying_depth_constrained: int = 80
    browsing_depth_sparse: int = 120
    browsing_depth_constrained: int = 100
    buying_lexical_weight: float = 0.72
    buying_structured_weight: float = 0.28
    browsing_lexical_weight: float = 0.62
    browsing_structured_weight: float = 0.20
    browsing_semantic_weight: float = 0.18


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


def plan_strategy(state: SessionState, *, turn: int, top_k: int, config: StrategyConfig | None = None) -> Strategy:
    config = config or StrategyConfig()
    intent = state.intent or "browsing"
    active_count = sum(1 for item in state.active_constraints if item.get("active", True))
    has_hard = any(bool(item.get("hard")) for item in state.active_constraints if item.get("active", True))
    assessment = state.intent_assessment
    assessment_reason = (
        f"{assessment.transition_reason}, confidence={assessment.confidence:.2f}"
        if assessment is not None
        else "legacy intent"
    )

    if intent == "buying":
        depth = max(top_k, config.buying_depth_constrained if active_count >= 2 else config.buying_depth_sparse)
        return Strategy(
            intent="buying",
            lexical_weight=config.buying_lexical_weight,
            structured_weight=config.buying_structured_weight,
            semantic_weight=0.0,
            retrieval_depth=depth,
            allow_hard_filter=has_hard and active_count >= 2,
            clarification_enabled=turn < 10,
            fallback_mode="lexical",
            reason=(
                f"buying intent ({assessment_reason}) with {active_count} active constraints"
            ),
        )

    depth = max(top_k, config.browsing_depth_sparse if active_count <= 1 else config.browsing_depth_constrained)
    return Strategy(
        intent="browsing",
        lexical_weight=config.browsing_lexical_weight,
        structured_weight=config.browsing_structured_weight,
        semantic_weight=config.browsing_semantic_weight,
        retrieval_depth=depth,
        allow_hard_filter=False,
        clarification_enabled=turn < 10,
        fallback_mode="broad_lexical",
        reason=(
            f"browsing intent ({assessment_reason}) with {active_count} active constraints"
        ),
    )
