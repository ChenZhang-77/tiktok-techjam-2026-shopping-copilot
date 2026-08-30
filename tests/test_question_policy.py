from __future__ import annotations

import copy
import unittest

from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalResult
from starter.core.clarification import candidate_attribute_scores
from starter.core.question_policy import QuestionPolicy
from starter.core.state import SessionState


class QuestionPolicyTest(unittest.TestCase):
    def test_attribute_evidence_covers_all_ten_attributes_with_explicit_statuses(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        state.apply_user_context(
            constraints=[
                {"attribute": "category", "normalized_value": "shoes"}
            ]
        )
        result = RetrievalResult(
            candidates=[
                Candidate("A", evidence_text="black leather modern hiking shoes"),
                Candidate("B", evidence_text="white cotton vintage running shoes"),
                Candidate("C", evidence_text="red wool casual work shoes"),
            ],
            diagnostics=RetrievalDiagnostics(route="fixture", candidate_count=3),
        )

        outcome = QuestionPolicy().decide(
            state=state,
            result=result,
            turn=1,
            top_k=3,
        )

        evidence = outcome.diagnostics["attribute_evidence"]
        self.assertEqual(
            set(evidence),
            {
                "category",
                "material",
                "color",
                "size",
                "style",
                "brand",
                "budget",
                "feature",
                "use_case",
                "other",
            },
        )
        self.assertEqual(evidence["material"]["status"], "available")
        self.assertEqual(evidence["material"]["candidate_coverage"], 1.0)
        self.assertEqual(evidence["material"]["value_count"], 3)
        self.assertGreater(evidence["material"]["rank_weighted_split"], 0.0)
        self.assertEqual(
            evidence["material"]["comparability_family"],
            "bounded_candidate_vocabulary_v1",
        )
        self.assertEqual(evidence["feature"]["status"], "uncalibrated")
        self.assertEqual(evidence["size"]["status"], "unavailable")
        self.assertEqual(evidence["brand"]["status"], "unavailable")
        self.assertEqual(evidence["budget"]["status"], "unavailable")
        self.assertEqual(evidence["other"]["status"], "not_applicable")
        self.assertEqual(evidence["category"]["eligibility_status"], "satisfied")
        self.assertFalse(evidence["category"]["eligible"])
        self.assertEqual(
            outcome.decision_evidence.attribute_partition_scores,
            candidate_attribute_scores(
                [candidate.evidence_text or "" for candidate in result.candidates]
            ),
        )
        for record in evidence.values():
            self.assertIn("source", record)
            self.assertEqual(record["lifecycle"], "current_turn_full_pool")
            self.assertIn("value_range", record)
            self.assertIn("missing_data_behavior", record)

    def test_attribute_evidence_marks_partial_degraded_and_exhausted_states(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "browsing"
        state.asked_attributes.add("feature")
        state.no_preference_attributes.add("color")
        result = RetrievalResult(
            candidates=[Candidate("A", evidence_text="leather product")],
            diagnostics=RetrievalDiagnostics(
                route="fixture",
                candidate_count=2,
                fallback_used=True,
            ),
        )

        outcome = QuestionPolicy().decide(
            state=state,
            result=result,
            turn=2,
            top_k=2,
            response_fallback_used=True,
        )

        evidence = outcome.diagnostics["attribute_evidence"]
        self.assertEqual(evidence["material"]["status"], "degraded")
        self.assertEqual(evidence["size"]["status"], "unavailable")
        self.assertEqual(evidence["brand"]["status"], "unavailable")
        self.assertEqual(evidence["budget"]["status"], "unavailable")
        self.assertEqual(evidence["feature"]["eligibility_status"], "asked")
        self.assertEqual(evidence["color"]["eligibility_status"], "no_preference")
        self.assertFalse(evidence["feature"]["eligible"])
        self.assertFalse(evidence["color"]["eligible"])

    def test_sparse_bounded_partition_is_partial_and_preserves_legacy_action(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "browsing"
        state.asked_attributes.add("feature")
        result = RetrievalResult(
            candidates=[Candidate("A", evidence_text="leather product")],
            diagnostics=RetrievalDiagnostics(route="fixture", candidate_count=1),
        )

        outcome = QuestionPolicy().decide(
            state=state,
            result=result,
            turn=2,
            top_k=1,
        )

        material = outcome.diagnostics["attribute_evidence"]["material"]
        self.assertEqual(material["status"], "partial")
        self.assertEqual(material["candidate_coverage"], 1.0)
        self.assertEqual(material["value_count"], 1)
        self.assertEqual(material["missing_data_behavior"], "preserve_legacy_action")
        self.assertEqual(outcome.decision.attribute, "use_case")

    def test_attribute_evidence_is_complete_when_retrieval_is_unavailable(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"

        outcome = QuestionPolicy().decide(
            state=state,
            result=None,
            turn=10,
            top_k=10,
        )

        evidence = outcome.diagnostics["attribute_evidence"]
        self.assertEqual(len(evidence), 10)
        self.assertTrue(all(not item["eligible"] for item in evidence.values()))
        self.assertEqual(
            {item["eligibility_status"] for item in evidence.values()},
            {"final_turn"},
        )
        self.assertEqual(evidence["material"]["status"], "unavailable")
        self.assertEqual(evidence["other"]["status"], "not_applicable")

    def test_decide_preserves_the_legacy_question_from_one_read_only_seam(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        state.apply_user_context(
            constraints=[
                {
                    "attribute": "category",
                    "normalized_value": "shoes",
                    "source_turn": 1,
                }
            ]
        )
        result = RetrievalResult(
            candidates=[
                Candidate("A", evidence_text="black leather running shoes"),
                Candidate("B", evidence_text="white cotton walking shoes"),
            ],
            diagnostics=RetrievalDiagnostics(route="fixture", candidate_count=2),
        )
        state_before = copy.deepcopy(state)
        result_before = copy.deepcopy(result)

        policy = QuestionPolicy()
        outcome = policy.decide(
            state=state,
            result=result,
            turn=1,
            top_k=2,
        )

        self.assertEqual(outcome.decision.action, "ask")
        self.assertEqual(outcome.decision.attribute, "feature")
        self.assertEqual(
            outcome.decision.question,
            "Which specific feature matters most to you?",
        )
        self.assertEqual(outcome.decision.reason_code, "legacy_ask")
        self.assertEqual(outcome.decision.evidence_status, "available")
        self.assertEqual(outcome.decision_evidence.pool_size, 2)
        self.assertEqual(outcome.diagnostics["baseline_attribute"], "feature")
        self.assertIn("feature", outcome.diagnostics["eligible_attributes"])
        self.assertIsNotNone(policy.last_latency_ms)
        self.assertGreaterEqual(policy.last_latency_ms, 0.0)
        self.assertNotIn("candidate_ids", outcome.diagnostics)
        self.assertNotIn("candidate_texts", outcome.diagnostics)
        self.assertNotIn("target", str(outcome.diagnostics).lower())
        self.assertEqual(outcome.usage, {"prompt_tokens": 0, "completion_tokens": 0})
        self.assertEqual(state, state_before)
        self.assertEqual(result, result_before)

    def test_invalid_retrieval_evidence_uses_the_legacy_fallback(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        state.apply_user_context(
            constraints=[
                {"attribute": "category", "normalized_value": "shoes"}
            ]
        )
        result = RetrievalResult(
            candidates=[Candidate("A", evidence_text=object())],
            diagnostics=RetrievalDiagnostics(route="fixture", candidate_count=1),
        )

        outcome = QuestionPolicy().decide(
            state=state,
            result=result,
            turn=1,
            top_k=1,
        )

        self.assertEqual(outcome.decision.action, "ask")
        self.assertEqual(outcome.decision.attribute, "feature")
        self.assertEqual(outcome.decision.evidence_status, "unavailable")
        self.assertTrue(outcome.diagnostics["fallback_used"])
        self.assertEqual(
            outcome.diagnostics["fallback_reason"],
            "invalid_retrieval_evidence",
        )

    def test_duplicate_candidate_ids_preserve_the_legacy_text_projection(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "browsing"
        state.asked_attributes.add("feature")
        result = RetrievalResult(
            candidates=[
                Candidate("A", evidence_text="leather product"),
                Candidate("A", evidence_text="cotton product"),
            ],
            diagnostics=RetrievalDiagnostics(route="fixture", candidate_count=2),
        )

        outcome = QuestionPolicy().decide(
            state=state,
            result=result,
            turn=2,
            top_k=2,
            response_fallback_used=True,
        )

        self.assertEqual(outcome.decision.attribute, "use_case")

    def test_invalid_policy_state_returns_a_total_guarded_stop(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.intent = "buying"
        state.active_constraints = [None]

        outcome = QuestionPolicy().decide(
            state=state,
            result=None,
            turn=1,
            top_k=2,
        )

        self.assertEqual(outcome.decision.action, "stop")
        self.assertIsNone(outcome.decision.attribute)
        self.assertEqual(outcome.decision.question, "")
        self.assertTrue(outcome.diagnostics["fallback_used"])
        self.assertEqual(outcome.diagnostics["fallback_reason"], "legacy_policy_error")


if __name__ == "__main__":
    unittest.main()
