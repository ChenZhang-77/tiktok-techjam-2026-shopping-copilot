from __future__ import annotations

import unittest

from starter.contracts import (
    Candidate,
    RetrievalDiagnostics,
    RetrievalRequest,
    RetrievalResult,
    validate_agent_response,
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
    def test_retrieval_diagnostics_preserves_the_original_positional_signature(self) -> None:
        diagnostics = RetrievalDiagnostics("bm25", 10, False, 1.5, ["legacy-note"])

        self.assertEqual(diagnostics.notes, ["legacy-note"])
        self.assertEqual(diagnostics.requested_route_weights, {})
        self.assertEqual(diagnostics.executed_routes, [])
        self.assertIsNone(diagnostics.fallback_route)

    def test_retrieval_diagnostics_exposes_requested_and_executed_routes(self) -> None:
        diagnostics = RetrievalDiagnostics(
            route="structured",
            candidate_count=10,
            requested_route_weights={
                "lexical": 0.62,
                "structured": 0.20,
                "dense": 0.18,
            },
            executed_routes=["lexical", "structured"],
            fallback_route=None,
        )

        payload = diagnostics.to_dict()

        self.assertEqual(
            payload["requested_route_weights"],
            {"lexical": 0.62, "structured": 0.20, "dense": 0.18},
        )
        self.assertEqual(payload["executed_routes"], ["lexical", "structured"])
        self.assertIsNone(payload["fallback_route"])

    def test_retrieval_diagnostics_rejects_invalid_route_execution_semantics(self) -> None:
        invalid_fields = (
            {"requested_route_weights": {"dense": -0.1}},
            {"requested_route_weights": {"dense": float("nan")}},
            {"requested_route_weights": {"": 0.2}},
            {"executed_routes": ["lexical", "lexical"]},
            {"executed_routes": [""]},
            {"fallback_route": ""},
        )

        for fields in invalid_fields:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                RetrievalDiagnostics(
                    route="structured",
                    candidate_count=10,
                    **fields,
                )

    def test_agent_response_validator_rejects_schema_drift(self) -> None:
        with self.assertRaises(ValueError):
            validate_agent_response(
                {
                    "message": "ok",
                    "ask_attribute": None,
                    "recommendations": [{"parent_asin": "VALID", "score": "high"}],
                    "usage": {"prompt_tokens": True, "completion_tokens": 0},
                    "unexpected": True,
                },
                catalog_ids={"VALID"},
                top_k=10,
                allowed_ask_attributes={"color"},
            )

    def test_agent_response_validator_rejects_nested_evaluator_labels(self) -> None:
        with self.assertRaisesRegex(ValueError, "evaluator-only"):
            validate_agent_response(
                {
                    "message": "ok",
                    "ask_attribute": None,
                    "recommendations": [{"parent_asin": "VALID"}],
                    "diagnostics": {"retrieval": {"target_asin": "VALID"}},
                },
                catalog_ids={"VALID"},
                top_k=10,
                allowed_ask_attributes={"color"},
            )

    def test_agent_response_validator_scans_json_serializable_tuples(self) -> None:
        with self.assertRaisesRegex(ValueError, "evaluator-only"):
            validate_agent_response(
                {
                    "message": "ok",
                    "ask_attribute": None,
                    "recommendations": [{"parent_asin": "VALID"}],
                    "diagnostics": {"retrieval": ({"target_asin": "VALID"},)},
                },
                catalog_ids={"VALID"},
                top_k=10,
                allowed_ask_attributes={"color"},
            )

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

    def test_validate_retrieval_request_rejects_nested_label_leakage(self) -> None:
        with self.assertRaisesRegex(ValueError, "evaluator-only"):
            validate_retrieval_request(
                {"query": "shoes", "active_constraints": [{"target_asin": "B000"}]}
            )

    def test_validate_retrieval_request_scans_json_serializable_tuples(self) -> None:
        with self.assertRaisesRegex(ValueError, "evaluator-only"):
            validate_retrieval_request(
                {"query": "shoes", "active_constraints": ({"target_asin": "B000"},)}
            )

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
