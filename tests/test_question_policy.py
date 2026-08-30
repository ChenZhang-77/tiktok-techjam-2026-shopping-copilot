from __future__ import annotations

import copy
import unittest

from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalResult
from starter.core.question_policy import QuestionPolicy
from starter.core.state import SessionState


class QuestionPolicyTest(unittest.TestCase):
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
