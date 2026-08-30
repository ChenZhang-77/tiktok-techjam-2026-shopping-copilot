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

        outcome = QuestionPolicy().decide(
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


if __name__ == "__main__":
    unittest.main()
