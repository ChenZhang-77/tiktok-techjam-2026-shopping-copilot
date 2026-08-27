from __future__ import annotations

import unittest

from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalResult
from starter.core.clarification import (
    candidate_attribute_scores,
    choose_clarification,
    select_clarification,
)
from starter.core.decision_evidence import build_decision_evidence
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

    def test_black_shoes_next_asks_material_before_unrelated_feature(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        state.apply_user_context(constraints=[
            {"attribute": "category", "normalized_value": "shoes"},
            {"attribute": "color", "normalized_value": "black"},
        ])

        ask_attribute, _ = choose_clarification(state, turn=1)

        self.assertEqual(ask_attribute, "material")

    def test_full_pool_question_value_ranks_attributes_after_feature_is_exhausted(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        state.asked_attributes.add("feature")
        state.apply_user_context(
            constraints=[{"attribute": "category", "normalized_value": "shoes"}]
        )
        evidence = build_decision_evidence(
            RetrievalResult(
                candidates=[
                    Candidate("A", evidence_text="black leather running shoes"),
                    Candidate("B", evidence_text="white cotton walking shoes"),
                    Candidate("C", evidence_text="black wool hiking boots"),
                ],
                diagnostics=RetrievalDiagnostics(route="fixture", candidate_count=3),
            ),
            state=state,
            turn=1,
            top_k=3,
        )

        selection = select_clarification(
            state,
            turn=1,
            decision_evidence=evidence,
        )

        self.assertEqual(selection.ask_attribute, "material")
        self.assertEqual(selection.reason, "candidate_question_value")
        self.assertEqual(selection.score_source, "decision_evidence_full_pool")
        self.assertGreater(selection.question_value or 0.0, 0.0)

    def test_no_partition_evidence_preserves_existing_should_ask_behavior(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        state.previous_candidate_ids = ["A", "B"]
        evidence = build_decision_evidence(
            RetrievalResult(
                candidates=[Candidate("A"), Candidate("B")],
                diagnostics=RetrievalDiagnostics(route="fixture", candidate_count=2),
            ),
            state=state,
            turn=2,
            top_k=2,
        )

        selection = select_clarification(
            state,
            turn=2,
            decision_evidence=evidence,
        )

        self.assertEqual(selection.ask_attribute, "feature")
        self.assertEqual(selection.reason, "legacy_feature_fallback")


if __name__ == "__main__":
    unittest.main()
