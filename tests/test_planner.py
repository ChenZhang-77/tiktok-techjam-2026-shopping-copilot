from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
