from __future__ import annotations

import unittest

from starter.core.context_engine import detect_no_preference_attributes, detect_override, extract_constraints
from starter.core.state import SessionState


class ContextEngineTest(unittest.TestCase):
    def test_extracts_common_shopping_constraints(self) -> None:
        constraints = extract_constraints(
            "I need black leather running shoes under $80 for hiking.",
            2,
        )
        by_attribute = {item["attribute"]: item for item in constraints}

        self.assertEqual(by_attribute["material"]["normalized_value"], "leather")
        self.assertEqual(by_attribute["color"]["normalized_value"], "black")
        self.assertEqual(by_attribute["category"]["normalized_value"], "shoes")
        self.assertEqual(by_attribute["budget"]["normalized_value"], "$80")
        self.assertEqual(by_attribute["use_case"]["normalized_value"], "hiking")
        self.assertEqual(by_attribute["material"]["source_turn"], 2)
        self.assertTrue(by_attribute["material"]["hard"])

    def test_uncertain_message_is_preserved_as_soft_feature(self) -> None:
        constraints = extract_constraints("Something that feels premium and giftable", 1)

        self.assertEqual(len(constraints), 1)
        self.assertEqual(constraints[0]["attribute"], "feature")
        self.assertFalse(constraints[0]["hard"])

    def test_session_state_accumulates_constraints_without_duplicates(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.add_constraints(extract_constraints("I need black leather shoes", 1))
        state.add_constraints(extract_constraints("Black leather would be ideal", 2))

        self.assertEqual(state.active_constraint_values("color"), ["black"])
        self.assertEqual(state.active_constraint_values("material"), ["leather"])
        self.assertEqual(state.active_constraint_values("category"), ["shoes"])

    def test_detects_override_and_no_preference_attributes(self) -> None:
        self.assertTrue(detect_override("Actually, ignore that. I need cotton instead."))
        self.assertEqual(detect_no_preference_attributes("I don't care about material."), ["material"])
        self.assertEqual(detect_no_preference_attributes("Color does not matter."), ["color"])


if __name__ == "__main__":
    unittest.main()
