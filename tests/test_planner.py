from __future__ import annotations

import unittest

from starter.core.context_engine import IntentAssessment
from starter.core.planner import StrategyConfig, plan_strategy
from starter.core.state import SessionState


class PlannerTest(unittest.TestCase):
    def test_buying_strategy_is_more_precise(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        state.apply_user_context(constraints=[
            {"attribute": "material", "normalized_value": "leather", "hard": True},
            {"attribute": "color", "normalized_value": "black", "hard": True},
        ])

        strategy = plan_strategy(state, turn=2, top_k=10)

        self.assertEqual(strategy.intent, "buying")
        self.assertEqual(strategy.retrieval_depth, 80)
        self.assertTrue(strategy.allow_hard_filter)
        self.assertGreater(strategy.lexical_weight, strategy.structured_weight)

    def test_browsing_strategy_is_broader(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "browsing"

        strategy = plan_strategy(state, turn=1, top_k=10)

        self.assertEqual(strategy.intent, "browsing")
        self.assertEqual(strategy.retrieval_depth, 120)
        self.assertFalse(strategy.allow_hard_filter)
        self.assertGreater(strategy.semantic_weight, 0.0)

    def test_strategy_config_overrides_defaults(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        config = StrategyConfig(
            buying_depth_sparse=30,
            buying_depth_constrained=40,
            buying_lexical_weight=0.8,
            buying_structured_weight=0.2,
        )

        strategy = plan_strategy(state, turn=1, top_k=10, config=config)

        self.assertEqual(strategy.retrieval_depth, 30)
        self.assertEqual(strategy.lexical_weight, 0.8)
        self.assertEqual(strategy.structured_weight, 0.2)

    def test_strategy_reason_exposes_persisted_intent_transition(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.set_intent_assessment(
            IntentAssessment(
                intent="buying",
                confidence=0.84,
                evidence=("active_concrete_attributes:color,material",),
                source_turn=2,
                transition_reason="accumulated",
            )
        )

        strategy = plan_strategy(state, turn=2, top_k=10)

        self.assertIn("accumulated", strategy.reason)
        self.assertNotIn("confidence", strategy.reason)

    def test_high_confidence_narrow_buying_uses_shallower_existing_floor(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.set_intent_assessment(
            IntentAssessment(
                intent="buying",
                confidence=0.90,
                evidence=("active_concrete_attributes:color,material",),
                source_turn=2,
                transition_reason="accumulated",
            )
        )
        state.apply_user_context(
            constraints=[
                {"attribute": "material", "normalized_value": "leather", "hard": True},
                {"attribute": "color", "normalized_value": "black", "hard": True},
            ]
        )

        strategy = plan_strategy(state, turn=2, top_k=10)

        self.assertEqual(strategy.retrieval_depth, 60)
        self.assertIn("depth policy=adaptive_narrow", strategy.reason)

        large_response = plan_strategy(state, turn=2, top_k=100)
        self.assertEqual(large_response.retrieval_depth, 100)

    def test_medium_confidence_and_missing_assessment_preserve_fixed_fallback(self) -> None:
        constrained = [
            {"attribute": "material", "normalized_value": "leather", "hard": True},
            {"attribute": "color", "normalized_value": "black", "hard": True},
        ]
        medium = SessionState(session_id="medium", user_profile={})
        medium.set_intent_assessment(
            IntentAssessment(
                intent="buying",
                confidence=0.72,
                evidence=(),
                source_turn=1,
                transition_reason="accumulated",
            )
        )
        medium.apply_user_context(constraints=constrained)
        legacy = SessionState(session_id="legacy", user_profile={})
        legacy.intent = "buying"
        legacy.apply_user_context(constraints=constrained)

        self.assertEqual(plan_strategy(medium, turn=1, top_k=10).retrieval_depth, 80)
        self.assertEqual(plan_strategy(legacy, turn=1, top_k=10).retrieval_depth, 80)

if __name__ == "__main__":
    unittest.main()
