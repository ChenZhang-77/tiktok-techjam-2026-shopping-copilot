from __future__ import annotations

import unittest

from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalResult
from starter.core.decision_evidence import build_decision_evidence
from starter.core.state import SessionState


class DecisionEvidenceTest(unittest.TestCase):
    def test_builds_bounded_summary_from_the_full_candidate_pool(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.previous_candidate_ids = ["A", "C"]
        state.asked_attributes.add("feature")
        state.no_preference_attributes.add("color")
        state.active_constraints = [
            {"attribute": "category", "normalized_value": "shoes", "active": True},
            {"attribute": "material", "normalized_value": "leather", "active": True},
        ]
        result = RetrievalResult(
            candidates=[
                Candidate(
                    "A",
                    score=1.0,
                    evidence_text="leather walking shoes",
                    diagnostics={
                        "structured_matches": [
                            {"attribute": "category", "value": "shoes"},
                            {"attribute": "material", "value": "leather"},
                        ]
                    },
                ),
                Candidate(
                    "B",
                    score=0.75,
                    evidence_text="leather hiking shoes",
                    diagnostics={
                        "structured_matches": [
                            {"attribute": "category", "value": "shoes"}
                        ]
                    },
                ),
                Candidate(
                    "C",
                    score=0.5,
                    evidence_text="cotton casual shoes",
                    diagnostics={"structured_matches": []},
                ),
            ],
            diagnostics=RetrievalDiagnostics(
                route="fixture",
                candidate_count=3,
                structured_filter_applied=True,
                relaxed_constraints=[{"attribute": "material", "value": "leather"}],
            ),
        )

        evidence = build_decision_evidence(result, state=state, turn=2, top_k=2)

        self.assertEqual(evidence.pool_size, 3)
        self.assertEqual(evidence.reported_pool_size, 3)
        self.assertTrue(evidence.pool_size_consistent)
        self.assertEqual(evidence.current_candidate_depth, 2)
        self.assertEqual(evidence.previous_candidate_depth, 2)
        self.assertAlmostEqual(evidence.candidate_stability, 1 / 3, places=6)
        self.assertEqual(evidence.stability_metric, "top_k_jaccard")
        self.assertAlmostEqual(evidence.constraint_coverage, 0.5)
        self.assertEqual(evidence.constraint_coverage_status, "available")
        self.assertIn("material", evidence.attribute_partition_scores)
        self.assertEqual(evidence.evidence_candidate_count, 3)
        self.assertEqual(evidence.top_score_margin, 0.25)
        self.assertEqual(evidence.score_margin_status, "route_local_uncalibrated")
        self.assertFalse(evidence.score_margin_usable)
        self.assertTrue(evidence.relaxation_used)
        self.assertFalse(evidence.degraded)
        self.assertEqual(evidence.exhausted_attributes, ("color", "feature"))

    def test_missing_or_invalid_inputs_have_deterministic_fallbacks(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        result = RetrievalResult(
            candidates=[Candidate("A", score=None, diagnostics={})],
            diagnostics=RetrievalDiagnostics(
                route="fallback",
                candidate_count=2,
                fallback_used=True,
                route_failures={"dense": "missing cache"},
            ),
        )

        evidence = build_decision_evidence(result, state=state, turn=1, top_k=10)

        self.assertEqual(evidence.pool_size, 1)
        self.assertFalse(evidence.pool_size_consistent)
        self.assertIsNone(evidence.candidate_stability)
        self.assertEqual(evidence.stability_status, "current_retrieval_degraded")
        self.assertIsNone(evidence.constraint_coverage)
        self.assertEqual(evidence.constraint_coverage_status, "no_active_constraints")
        self.assertIsNone(evidence.top_score_margin)
        self.assertEqual(evidence.score_margin_status, "insufficient_candidates")
        self.assertTrue(evidence.degraded)
        self.assertEqual(evidence.route_failure_count, 1)

    def test_unavailable_retrieval_has_a_complete_non_label_fallback(self) -> None:
        state = SessionState(session_id="s1", user_profile={})

        evidence = build_decision_evidence(None, state=state, turn=3, top_k=5)
        diagnostics = evidence.to_diagnostics()

        self.assertEqual(diagnostics["pool_size"], 0)
        self.assertTrue(diagnostics["degraded"])
        self.assertEqual(diagnostics["source_status"], "retrieval_unavailable")
        self.assertNotIn("candidate_ids", diagnostics)
        self.assertNotIn("candidate_texts", diagnostics)
        self.assertNotIn("target", str(diagnostics).lower())

    def test_stability_is_unavailable_after_a_degraded_previous_response(self) -> None:
        state = SessionState(session_id="s1", user_profile={})
        state.previous_candidate_ids = ["A", "B"]
        state.previous_diagnostics = {"fallback_used": True}
        result = RetrievalResult(
            candidates=[Candidate("A"), Candidate("B")],
            diagnostics=RetrievalDiagnostics(route="fixture", candidate_count=2),
        )

        evidence = build_decision_evidence(result, state=state, turn=2, top_k=2)

        self.assertIsNone(evidence.candidate_stability)
        self.assertEqual(evidence.stability_status, "previous_response_degraded")


if __name__ == "__main__":
    unittest.main()
