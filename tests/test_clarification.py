from __future__ import annotations

import unittest

from starter.core.clarification import candidate_attribute_scores, choose_clarification
from starter.core.state import SessionState


class ClarificationTest(unittest.TestCase):
    def test_asks_missing_high_value_attribute(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        state.apply_user_context(constraints=[{"attribute": "category", "normalized_value": "shoes"}])

        ask_attribute, question = choose_clarification(state, turn=1)

        self.assertEqual(ask_attribute, "feature")
        self.assertIn("feature", question)

    def test_does_not_repeat_asked_or_no_preference_attributes(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        state.asked_attributes.add("feature")
        state.no_preference_attributes.add("material")

        ask_attribute, _ = choose_clarification(state, turn=2)

        self.assertEqual(ask_attribute, "color")

    def test_does_not_ask_on_final_turn(self) -> None:
        state = SessionState(session_id="s1", user_profile={})

        self.assertEqual(choose_clarification(state, turn=10), (None, ""))

    def test_candidate_scores_detect_attribute_diversity(self) -> None:
        scores = candidate_attribute_scores([
            "black leather running shoes",
            "white cotton walking shoes",
            "blue wool winter boots",
        ])

        self.assertGreater(scores["material"], 0)
        self.assertGreater(scores["color"], 0)

    def test_candidate_aware_choice_runs_after_feature_is_unavailable(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        state.asked_attributes.add("feature")
        state.asked_attributes.add("material")

        ask_attribute, _ = choose_clarification(
            state,
            turn=2,
            candidate_texts=[
                "black leather running shoes",
                "white cotton walking shoes",
                "blue wool winter boots",
            ],
        )

        self.assertEqual(ask_attribute, "color")


if __name__ == "__main__":
    unittest.main()
