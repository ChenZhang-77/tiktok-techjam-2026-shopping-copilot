from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalRequest, RetrievalResult
from starter.core.planner import Strategy
from starter.retrieval.dense import DenseConfig
from starter.retrieval.fusion import FusionConfig, FusionRetriever, RouteBatch


def _request(
    *,
    lexical_weight: float = 1.0,
    structured_weight: float = 1.0,
    semantic_weight: float = 0.0,
) -> RetrievalRequest:
    return RetrievalRequest(
        session_id="fusion-session",
        turn=1,
        top_k=3,
        query="walking shoes",
        intent="browsing",
        strategy=Strategy(
            intent="browsing",
            lexical_weight=lexical_weight,
            structured_weight=structured_weight,
            semantic_weight=semantic_weight,
            retrieval_depth=20,
            allow_hard_filter=False,
            clarification_enabled=True,
            fallback_mode="broad_lexical",
            reason="fusion fixture",
        ),
    )


def _result(route: str, ids: list[str], *, latency_ms: float = 1.25) -> RetrievalResult:
    return RetrievalResult(
        candidates=[
            Candidate(parent_asin=parent_asin, source=route, evidence_text=f"evidence-{parent_asin}")
            for parent_asin in ids
        ],
        diagnostics=RetrievalDiagnostics(
            route=route,
            candidate_count=len(ids),
            latency_ms=latency_ms,
        ),
    )


class _RouteProvider:
    catalog_ids = frozenset({"A", "B", "C"})
    fallback_ids = ("A", "B", "C")

    def retrieve_routes(self, request: RetrievalRequest, routes: tuple[str, ...]) -> RouteBatch:
        available = {
            "lexical": _result("lexical", ["A", "B"]),
            "structured": _result("structured", ["B", "C"]),
        }
        return RouteBatch(
            results={route: available[route] for route in routes if route in available},
            failures={},
        )


class _FailedRouteProvider:
    catalog_ids = frozenset({"A", "B", "C"})
    fallback_ids = ("A", "B", "C")

    def retrieve_routes(self, request: RetrievalRequest, routes: tuple[str, ...]) -> RouteBatch:
        return RouteBatch(
            results={},
            failures={route: "route_error" for route in routes},
        )


class FusionRetrieverTest(unittest.TestCase):
    def test_zero_route_weights_use_deterministic_catalog_fallback(self) -> None:
        retriever = FusionRetriever(_RouteProvider())

        result = retriever.retrieve(
            _request(lexical_weight=0.0, structured_weight=0.0, semantic_weight=0.0)
        )

        self.assertEqual([candidate.parent_asin for candidate in result.candidates], ["A", "B", "C"])
        self.assertTrue(result.diagnostics.fallback_used)
        self.assertEqual(result.diagnostics.route_failures, {"fusion": "no_active_routes"})

    def test_complete_route_failure_fills_a_valid_candidate_pool(self) -> None:
        retriever = FusionRetriever(_FailedRouteProvider())

        result = retriever.retrieve(_request())

        self.assertEqual([candidate.parent_asin for candidate in result.candidates], ["A", "B", "C"])
        self.assertTrue(all(candidate.source == "catalog_fallback" for candidate in result.candidates))
        self.assertTrue(result.diagnostics.fallback_used)
        self.assertIn("all_routes_failed_catalog_fallback", result.diagnostics.notes)
        self.assertEqual(result.diagnostics.executed_routes, ["catalog_fallback"])
        self.assertEqual(result.diagnostics.fallback_route, "catalog_fallback")

    def test_invalid_request_is_rejected_before_route_failures_can_degrade_it(self) -> None:
        retriever = FusionRetriever(_RouteProvider())

        with self.assertRaisesRegex(ValueError, "top_k"):
            retriever.retrieve(replace(_request(), top_k=-1))

    def test_local_routes_share_catalog_and_degrade_when_dense_cache_is_missing(self) -> None:
        rows = [
            {"parent_asin": "A", "title": "cotton walking shoes"},
            {"parent_asin": "B", "title": "leather walking shoes"},
            {"parent_asin": "C", "title": "rubber walking shoes"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            catalog.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            retriever = FusionRetriever.from_catalog(
                catalog,
                dense_config=DenseConfig(cache_dir=root / "missing-cache"),
            )

            result = retriever.retrieve(
                _request(lexical_weight=0.6, structured_weight=0.2, semantic_weight=0.2)
            )

        self.assertEqual(set(candidate.parent_asin for candidate in result.candidates), {"A", "B", "C"})
        self.assertEqual(result.diagnostics.route_candidate_counts, {"lexical": 3, "structured": 3})
        self.assertEqual(result.diagnostics.route_failures, {"dense": "dense_cache_missing"})
        self.assertEqual(result.diagnostics.cache_state["dense"], "dense_cache_missing")
        self.assertTrue(result.diagnostics.fallback_used)

    def test_rrf_deduplicates_candidates_and_preserves_every_route_rank(self) -> None:
        retriever = FusionRetriever(_RouteProvider(), config=FusionConfig(rrf_k=10.0))

        result = retriever.retrieve(_request())

        self.assertEqual([candidate.parent_asin for candidate in result.candidates], ["B", "A", "C"])
        self.assertEqual(result.candidates[0].source, "fusion")
        self.assertEqual(
            result.candidates[0].diagnostics["route_ranks"],
            {"lexical": 2, "structured": 1},
        )
        self.assertEqual(
            result.candidates[0].score,
            round(1.0 / 12.0 + 1.0 / 11.0, 8),
        )
        self.assertEqual(len({candidate.parent_asin for candidate in result.candidates}), 3)
        self.assertEqual(result.diagnostics.route, "fusion")
        self.assertEqual(
            result.diagnostics.route_candidate_counts,
            {"lexical": 2, "structured": 2},
        )
        self.assertEqual(
            result.diagnostics.route_overlap_counts,
            {"lexical|structured": 1},
        )
        self.assertEqual(result.diagnostics.stage_latencies_ms["lexical_route"], 1.25)
        self.assertEqual(result.diagnostics.stage_latencies_ms["structured_route"], 1.25)
        self.assertIn("fusion", result.diagnostics.stage_latencies_ms)
        self.assertLessEqual(
            result.diagnostics.stage_latencies_ms["fusion"],
            result.diagnostics.latency_ms,
        )
        self.assertEqual(result.diagnostics.route_failures, {})
        self.assertEqual(
            result.diagnostics.requested_route_weights,
            {"lexical": 1.0, "structured": 1.0, "dense": 0.0},
        )
        self.assertEqual(
            result.diagnostics.executed_routes,
            ["lexical", "structured", "fusion"],
        )
        self.assertIsNone(result.diagnostics.fallback_route)

    def test_missing_requested_route_returns_valid_degraded_result_with_reason(self) -> None:
        retriever = FusionRetriever(_RouteProvider())

        result = retriever.retrieve(
            _request(lexical_weight=1.0, structured_weight=0.0, semantic_weight=1.0)
        )

        self.assertEqual([candidate.parent_asin for candidate in result.candidates], ["A", "B"])
        self.assertTrue(result.diagnostics.fallback_used)
        self.assertIn("route_failed:dense:route_unavailable", result.diagnostics.notes)
        self.assertEqual(result.diagnostics.route_failures, {"dense": "route_unavailable"})
        self.assertEqual(
            result.diagnostics.requested_route_weights,
            {"lexical": 1.0, "structured": 0.0, "dense": 1.0},
        )
        self.assertEqual(result.diagnostics.executed_routes, ["lexical", "fusion"])
        self.assertEqual(result.diagnostics.fallback_route, "fusion")
        self.assertTrue(
            all("dense" not in candidate.diagnostics["route_ranks"] for candidate in result.candidates)
        )


if __name__ == "__main__":
    unittest.main()
