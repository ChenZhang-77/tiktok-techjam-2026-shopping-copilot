from __future__ import annotations

import unittest

from starter.core.state import SessionState
from starter.core.context_engine import IntentAssessment


class SessionStateTest(unittest.TestCase):
    def test_intent_assessment_persists_the_complete_cross_turn_decision(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        assessment = IntentAssessment(
            intent="buying",
            confidence=0.9,
            evidence=("current_hard_constraint",),
            source_turn=2,
            transition_reason="accumulated",
        )

        state.set_intent_assessment(assessment)

        self.assertIs(state.intent_assessment, assessment)
        self.assertEqual(state.intent, "buying")
    def test_history_accumulates_and_records_agent_response(self) -> None:
        state = SessionState(session_id="s1", user_profile={"summary": "test"})

        state.record_user_turn(1, "I need leather shoes")
        state.record_agent_response({
            "message": "Here are matches.",
            "ask_attribute": "material",
            "recommendations": [{"parent_asin": "A"}, {"parent_asin": "B"}],
        })
        state.record_user_turn(2, "Black would be better")

        self.assertEqual(state.current_turn, 2)
        self.assertEqual(len(state.raw_history), 2)
        self.assertEqual(state.raw_history[0].user_message, "I need leather shoes")
        self.assertEqual(state.raw_history[0].ask_attribute, "material")
        self.assertEqual(state.asked_attributes, {"material"})
        self.assertEqual(state.previous_candidate_ids, ["A", "B"])

    def test_sessions_are_independent_objects(self) -> None:
        first = SessionState(session_id="s1", user_profile={})
        second = SessionState(session_id="s2", user_profile={})

        first.record_user_turn(1, "one")
        second.record_user_turn(1, "two")
        first.mark_no_preference("color")

        self.assertEqual(first.raw_history[0].user_message, "one")
        self.assertEqual(second.raw_history[0].user_message, "two")
        self.assertEqual(first.no_preference_attributes, {"color"})
        self.assertEqual(second.no_preference_attributes, set())

    def test_override_deactivates_prior_same_attribute_constraints(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.record_user_turn(2, "Actually cotton instead")
        state.previous_candidate_ids = ["A", "B"]
        state.apply_user_context(constraints=[{
            "attribute": "material",
            "normalized_value": "leather",
            "active": True,
        }])
        state.apply_user_context(
            constraints=[{"attribute": "material", "normalized_value": "cotton", "active": True}],
            override=True,
        )

        self.assertEqual(state.active_constraint_values("material"), ["cotton"])
        self.assertEqual([item["normalized_value"] for item in state.overridden_constraints], ["leather"])
        self.assertTrue(state.override_seen)
        self.assertEqual(state.previous_candidate_ids, [])
        self.assertEqual(state.override_events[-1]["reason"], "attribute replacement")

    def test_category_override_deactivates_prior_product_context(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.apply_user_context(constraints=[
            {"attribute": "category", "normalized_value": "shoes", "active": True},
            {"attribute": "material", "normalized_value": "leather", "active": True},
            {"attribute": "color", "normalized_value": "black", "active": True},
        ])
        state.record_user_turn(2, "Actually I need a cotton shirt instead")
        state.apply_user_context(
            constraints=[
                {"attribute": "category", "normalized_value": "shirt", "active": True},
                {"attribute": "material", "normalized_value": "cotton", "active": True},
            ],
            override=True,
        )

        self.assertEqual(state.active_constraint_values("category"), ["shirt"])
        self.assertEqual(state.active_constraint_values("material"), ["cotton"])
        self.assertEqual(state.active_constraint_values("color"), [])
        self.assertEqual(
            sorted(item["normalized_value"] for item in state.overridden_constraints),
            ["black", "leather", "shoes"],
        )
        self.assertEqual(state.override_events[-1]["reason"], "category reset")

    def test_no_preference_deactivates_attribute_constraints(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.apply_user_context(constraints=[{
            "attribute": "color",
            "normalized_value": "black",
            "active": True,
        }])
        state.apply_user_context(constraints=[], no_preference_attributes=["color"])

        self.assertEqual(state.active_constraint_values("color"), [])
        self.assertEqual(state.no_preference_attributes, {"color"})
        self.assertEqual([item["normalized_value"] for item in state.rejected_constraints], ["black"])

    def test_low_confidence_feature_expires_without_becoming_rejected(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.record_user_turn(1, "Something premium and giftable")
        state.apply_user_context(
            constraints=[{
                "attribute": "feature",
                "normalized_value": "something premium and giftable",
                "source_turn": 1,
                "confidence": 0.35,
                "active": True,
            }]
        )

        state.record_user_turn(3, "Show me more")
        state.apply_user_context(constraints=[])

        self.assertEqual(state.active_constraint_values("feature"), [])
        self.assertEqual(
            [item["normalized_value"] for item in state.expired_constraints],
            ["something premium and giftable"],
        )
        self.assertEqual(state.rejected_constraints, [])

    def test_rejected_constraint_is_not_readded_as_active(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.apply_user_context(constraints=[{
            "attribute": "color",
            "normalized_value": "black",
            "active": True,
        }])
        state.apply_user_context(
            constraints=[{"attribute": "color", "normalized_value": "black", "active": True}],
            rejected_constraints=[{"attribute": "color", "normalized_value": "black", "active": False}],
        )

        self.assertEqual(state.active_constraint_values("color"), [])
        self.assertEqual([item["normalized_value"] for item in state.rejected_constraints], ["black"])


if __name__ == "__main__":
    unittest.main()
