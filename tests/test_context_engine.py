from __future__ import annotations

import unittest

from starter.core.context_engine import (
    IntentAssessment,
    assess_intent,
    detect_no_preference_attributes,
    detect_override,
    detect_rejected_constraints,
    extract_constraints,
    infer_intent,
)
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

    def test_detects_rejected_constraints(self) -> None:
        rejected = detect_rejected_constraints("Any color is fine except black, and avoid leather.", 3)
        by_attribute = {item["attribute"]: item["normalized_value"] for item in rejected}

        self.assertEqual(by_attribute["color"], "black")
        self.assertEqual(by_attribute["material"], "leather")

    def test_intent_infers_buying_from_hard_constraints(self) -> None:
        self.assertEqual(
            infer_intent("I need black leather shoes", [{"attribute": "material", "hard": True}]),
            "buying",
        )
        self.assertEqual(infer_intent("I'm just browsing ideas", []), "browsing")

    def test_buying_assessment_is_retained_after_soft_clarification_reply(self) -> None:
        previous = IntentAssessment(
            intent="buying",
            confidence=0.9,
            evidence=("current_hard_constraint",),
            source_turn=1,
            transition_reason="accumulated",
        )

        assessment = assess_intent(
            "Black would be better",
            extract_constraints("Black would be better", 2),
            active_constraints=[
                {"attribute": "category", "normalized_value": "shoes", "active": True},
                {"attribute": "color", "normalized_value": "black", "active": True},
            ],
            turn=2,
            previous=previous,
            override=False,
            no_preference_attributes=(),
        )

        self.assertEqual(assessment.intent, "buying")
        self.assertEqual(assessment.source_turn, 1)
        self.assertEqual(assessment.transition_reason, "retained")
        self.assertIn("previous_intent:buying", assessment.evidence)

    def test_browsing_becomes_buying_after_specific_evidence_accumulates(self) -> None:
        previous = IntentAssessment(
            intent="browsing",
            confidence=0.9,
            evidence=("explicit_exploration",),
            source_turn=1,
            transition_reason="relaxed",
        )
        current = extract_constraints("Black leather would work", 2)

        assessment = assess_intent(
            "Black leather would work",
            current,
            active_constraints=[
                {"attribute": "category", "normalized_value": "shoes", "active": True},
                *current,
            ],
            turn=2,
            previous=previous,
            override=False,
            no_preference_attributes=(),
        )

        self.assertEqual(assessment.intent, "buying")
        self.assertEqual(assessment.source_turn, 2)
        self.assertEqual(assessment.transition_reason, "accumulated")
        self.assertGreaterEqual(assessment.confidence, 0.8)

    def test_explicit_exploration_can_restore_browsing(self) -> None:
        previous = IntentAssessment(
            intent="buying",
            confidence=0.9,
            evidence=("current_hard_constraint",),
            source_turn=1,
            transition_reason="accumulated",
        )

        assessment = assess_intent(
            "Actually, I'm just browsing ideas now",
            [],
            active_constraints=[],
            turn=2,
            previous=previous,
            override=True,
            no_preference_attributes=(),
        )

        self.assertEqual(assessment.intent, "browsing")
        self.assertEqual(assessment.source_turn, 2)
        self.assertEqual(assessment.transition_reason, "explicit_override")
        self.assertIn("explicit_exploration", assessment.evidence)

    def test_repeated_explicit_no_preference_can_relax_buying(self) -> None:
        previous = IntentAssessment(
            intent="buying",
            confidence=0.9,
            evidence=("current_hard_constraint",),
            source_turn=1,
            transition_reason="accumulated",
        )

        assessment = assess_intent(
            "I don't have an additional preference for color.",
            [],
            active_constraints=[
                {"attribute": "category", "normalized_value": "shoes", "active": True}
            ],
            turn=3,
            previous=previous,
            override=False,
            no_preference_attributes=("color", "material"),
        )

        self.assertEqual(assessment.intent, "browsing")
        self.assertEqual(assessment.transition_reason, "relaxed")
        self.assertIn("no_preference_attributes:color,material", assessment.evidence)

    def test_override_assessment_yields_on_next_explicit_relaxation(self) -> None:
        previous = IntentAssessment(
            intent="buying",
            confidence=0.9,
            evidence=("override_seen", "current_hard_constraint"),
            source_turn=3,
            transition_reason="explicit_override",
        )

        assessment = assess_intent(
            "I don't have an additional preference for style.",
            [],
            active_constraints=[
                {"attribute": "material", "normalized_value": "polyester", "active": True}
            ],
            turn=4,
            previous=previous,
            override=False,
        )

        self.assertEqual(assessment.intent, "browsing")
        self.assertEqual(assessment.transition_reason, "relaxed")

    def test_intent_assessment_rejects_invalid_domain_values(self) -> None:
        with self.assertRaises(ValueError):
            IntentAssessment(
                intent="buying",
                confidence=1.1,
                evidence=(),
                source_turn=1,
                transition_reason="accumulated",
            )


if __name__ == "__main__":
    unittest.main()
