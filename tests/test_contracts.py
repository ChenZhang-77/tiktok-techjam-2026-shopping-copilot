from __future__ import annotations

import unittest

from starter.contracts import (
    Candidate,
    RetrievalDiagnostics,
    RetrievalRequest,
    RetrievalResult,
    validate_retrieval_request,
)
from starter.core.planner import Strategy


def _strategy() -> Strategy:
    return Strategy(
        intent="buying",
        lexical_weight=0.7,
        structured_weight=0.3,
        semantic_weight=0.0,
        retrieval_depth=80,
        allow_hard_filter=True,
        clarification_enabled=True,
        fallback_mode="lexical",
        reason="test",
    )


class ContractsTest(unittest.TestCase):
    def test_retrieval_request_serializes_without_evaluator_only_fields(self) -> None:
        request = RetrievalRequest(
            session_id="s1",
            turn=1,
            top_k=10,
            query="black shoes",
            intent="buying",
            strategy=_strategy(),
            active_constraints=[{"attribute": "color", "normalized_value": "black"}],
            no_preference_attributes=["brand"],
            rejected_constraints=[{"attribute": "material", "normalized_value": "leather"}],
            asked_attributes=["material"],
        )

        payload = request.to_dict()

        validate_retrieval_request(payload)
        self.assertEqual(payload["query"], "black shoes")
        self.assertEqual(payload["strategy"]["intent"], "buying")
        self.assertNotIn("ground_truth", payload)
        self.assertNotIn("scenario_type", payload)
        self.assertNotIn("target_asin", payload)

    def test_validate_retrieval_request_rejects_label_leakage(self) -> None:
        with self.assertRaises(ValueError):
            validate_retrieval_request({"query": "shoes", "target_asin": "B000"})

    def test_retrieval_result_exports_recommendations(self) -> None:
        result = RetrievalResult(
            candidates=[
                Candidate(parent_asin="A", score=0.9, source="bm25"),
                Candidate(parent_asin="B", score=0.8, source="dense"),
            ],
            diagnostics=RetrievalDiagnostics(route="hybrid", candidate_count=2),
        )

        self.assertEqual(result.recommendations(1), [{"parent_asin": "A", "score": 0.9}])
        self.assertEqual(result.diagnostics.to_dict()["route"], "hybrid")


if __name__ == "__main__":
    unittest.main()
