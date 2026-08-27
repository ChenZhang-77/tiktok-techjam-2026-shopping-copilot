from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from starter.agent import Agent
from starter.contracts import (
    Candidate,
    RetrievalDiagnostics,
    RetrievalRequest,
    RetrievalResult,
)
from starter.core.planner import Strategy
from starter.retrieval import DenseConfig, DenseRetriever, HybridRetriever
from starter.retrieval.dense import file_sha256
from starter.retrieval.conditional_dense import (
    ConditionalDenseConfig,
    ConditionalDenseRetriever,
)


def _request(
    *,
    intent: str = "browsing",
    active_constraints: list[dict] | None = None,
    semantic_weight: float = 0.18,
) -> RetrievalRequest:
    return RetrievalRequest(
        session_id="conditional-dense",
        turn=1,
        top_k=3,
        query="comfortable walking shoes",
        intent=intent,
        strategy=Strategy(
            intent=intent,
            lexical_weight=0.62 if intent == "browsing" else 0.72,
            structured_weight=0.20 if intent == "browsing" else 0.28,
            semantic_weight=semantic_weight,
            retrieval_depth=20,
            allow_hard_filter=intent == "buying",
            clarification_enabled=True,
            fallback_mode="broad_lexical" if intent == "browsing" else "lexical",
            reason="conditional dense fixture",
        ),
        active_constraints=active_constraints or [],
    )


def _result(
    route: str,
    ids: list[str],
    *,
    latency_ms: float = 5.0,
    fallback_used: bool = False,
) -> RetrievalResult:
    executed = ["dense"] if route == "dense" else ["lexical", "structured"]
    return RetrievalResult(
        candidates=[
            Candidate(
                parent_asin=parent_asin,
                score=round(1.0 / rank, 8),
                source=route,
                evidence_text=f"evidence {parent_asin}",
            )
            for rank, parent_asin in enumerate(ids, start=1)
        ],
        diagnostics=RetrievalDiagnostics(
            route=route,
            candidate_count=len(ids),
            fallback_used=fallback_used,
            latency_ms=latency_ms,
            requested_route_weights={
                "lexical": 0.62,
                "structured": 0.20,
                "dense": 0.18,
            },
            executed_routes=executed,
            fallback_route="structured" if fallback_used else None,
            route_failures={"dense": "dense_cache_missing"} if fallback_used else {},
        ),
    )


class FakeRetriever:
    catalog_ids = frozenset({"A", "B", "C", "D", "E"})
    fallback_ids = ("A", "B", "C", "D", "E")

    def __init__(self, result: RetrievalResult) -> None:
        self.result = result
        self.requests: list[RetrievalRequest] = []

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        self.requests.append(request)
        return self.result


class ConditionalDenseRetrieverTest(unittest.TestCase):
    def _retriever(
        self,
        *,
        dense_result: RetrievalResult | None = None,
        config: ConditionalDenseConfig | None = None,
    ) -> tuple[ConditionalDenseRetriever, FakeRetriever, FakeRetriever]:
        base = FakeRetriever(_result("structured", ["A", "B", "C", "D"]))
        dense = FakeRetriever(dense_result or _result("dense", ["D", "C", "E", "B"]))
        return (
            ConditionalDenseRetriever(
                base,
                dense,
                config=config or ConditionalDenseConfig(min_base_candidates=3),
            ),
            base,
            dense,
        )

    def test_broad_browsing_executes_dense_and_fuses_valid_unique_candidates(self) -> None:
        retriever, base, dense = self._retriever()

        first = retriever.retrieve(_request())
        second = retriever.retrieve(_request())

        self.assertEqual(len(base.requests), 2)
        self.assertEqual(len(dense.requests), 2)
        self.assertEqual(
            [item.parent_asin for item in first.candidates],
            [item.parent_asin for item in second.candidates],
        )
        self.assertEqual(len({item.parent_asin for item in first.candidates}), 5)
        self.assertTrue(
            all(item.parent_asin in retriever.catalog_ids for item in first.candidates)
        )
        self.assertEqual(first.diagnostics.route, "fusion")
        self.assertEqual(
            first.diagnostics.executed_routes,
            ["lexical", "structured", "dense", "fusion"],
        )
        self.assertFalse(first.diagnostics.fallback_used)
        self.assertIn("conditional_dense_gate:broad_browsing", first.diagnostics.notes)
        self.assertEqual(first.diagnostics.route_candidate_counts["dense"], 4)

    def test_buying_and_constrained_browsing_keep_the_exact_structured_order(self) -> None:
        cases = (
            _request(intent="buying", semantic_weight=0.0),
            _request(
                active_constraints=[
                    {"attribute": "color", "normalized_value": "black"},
                    {"attribute": "material", "normalized_value": "leather"},
                ]
            ),
        )
        for request in cases:
            with self.subTest(intent=request.intent):
                retriever, base, dense = self._retriever()

                result = retriever.retrieve(request)

                self.assertEqual(result.candidates, base.result.candidates)
                self.assertEqual(result.diagnostics.route, "structured")
                self.assertEqual(dense.requests, [])
                self.assertIn("conditional_dense_gate_skipped", result.diagnostics.notes[-1])

    def test_small_base_pool_does_not_pay_for_dense(self) -> None:
        base = FakeRetriever(_result("structured", ["A", "B"]))
        dense = FakeRetriever(_result("dense", ["C", "D"]))
        retriever = ConditionalDenseRetriever(
            base,
            dense,
            config=ConditionalDenseConfig(min_base_candidates=3),
        )

        result = retriever.retrieve(_request())

        self.assertEqual(result.candidates, base.result.candidates)
        self.assertEqual(dense.requests, [])
        self.assertIn("base_pool_too_small", result.diagnostics.notes[-1])

    def test_dense_failure_returns_the_exact_structured_candidates(self) -> None:
        dense_failure = _result(
            "structured",
            ["D", "C", "B", "A"],
            fallback_used=True,
        )
        retriever, base, _dense = self._retriever(dense_result=dense_failure)

        result = retriever.retrieve(_request())

        self.assertEqual(result.candidates, base.result.candidates)
        self.assertTrue(result.diagnostics.fallback_used)
        self.assertEqual(result.diagnostics.fallback_route, "structured")
        self.assertEqual(result.diagnostics.route_failures, {"dense": "dense_cache_missing"})
        self.assertEqual(result.diagnostics.executed_routes, ["lexical", "structured"])

    def test_slow_dense_result_is_discarded_but_execution_remains_observable(self) -> None:
        slow_dense = _result("dense", ["D", "C", "E"], latency_ms=51.0)
        retriever, base, _dense = self._retriever(
            dense_result=slow_dense,
            config=ConditionalDenseConfig(
                min_base_candidates=3,
                max_accepted_dense_latency_ms=50.0,
            ),
        )

        result = retriever.retrieve(_request())

        self.assertEqual(result.candidates, base.result.candidates)
        self.assertTrue(result.diagnostics.fallback_used)
        self.assertEqual(result.diagnostics.fallback_route, "structured")
        self.assertEqual(
            result.diagnostics.executed_routes,
            ["lexical", "structured", "dense"],
        )
        self.assertEqual(
            result.diagnostics.route_failures,
            {"dense": "dense_latency_budget_exceeded"},
        )

    def test_successful_fusion_preserves_an_upstream_structured_fallback(self) -> None:
        base = FakeRetriever(
            replace(
                _result("structured", ["A", "B", "C", "D"]),
                diagnostics=replace(
                    _result("structured", ["A", "B", "C", "D"]).diagnostics,
                    fallback_used=True,
                    fallback_route="structured",
                    route_failures={"structured": "guarded_filter_relaxed"},
                ),
            )
        )
        dense = FakeRetriever(_result("dense", ["D", "C", "E", "B"]))
        retriever = ConditionalDenseRetriever(
            base,
            dense,
            config=ConditionalDenseConfig(min_base_candidates=3),
        )

        result = retriever.retrieve(_request())

        self.assertEqual(result.diagnostics.route, "fusion")
        self.assertTrue(result.diagnostics.fallback_used)
        self.assertEqual(result.diagnostics.fallback_route, "structured")
        self.assertEqual(
            result.diagnostics.route_failures,
            {"structured": "guarded_filter_relaxed"},
        )

    def test_legacy_base_keeps_ab1_route_semantics_unreported(self) -> None:
        legacy = FakeRetriever(
            replace(
                _result("structured", ["A", "B", "C", "D"]),
                diagnostics=RetrievalDiagnostics("structured", 4),
            )
        )
        for dense_result in (
            _result("dense", ["D", "C", "E"]),
            _result("structured", ["D", "C", "B"], fallback_used=True),
        ):
            with self.subTest(dense_route=dense_result.diagnostics.route):
                retriever = ConditionalDenseRetriever(
                    legacy,
                    FakeRetriever(dense_result),
                    config=ConditionalDenseConfig(min_base_candidates=3),
                )

                result = retriever.retrieve(_request())

                self.assertEqual(result.diagnostics.requested_route_weights, {})
                self.assertEqual(result.diagnostics.executed_routes, [])
                self.assertIsNone(result.diagnostics.fallback_route)

    def test_config_bounds_are_enforced(self) -> None:
        invalid = (
            {"max_active_constraints": -1},
            {"min_base_candidates": 0},
            {"rrf_k": 0.0},
            {"max_accepted_dense_latency_ms": 0.0},
        )
        for fields in invalid:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                ConditionalDenseConfig(**fields)

    def test_catalog_backed_wrapper_preserves_agent_catalog_vocabulary(self) -> None:
        rows = [
            {
                "parent_asin": "A",
                "title": "trail shoe",
                "categories": ["Clothing", "Women's Trail Running Shoes"],
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            catalog.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            retriever = ConditionalDenseRetriever.from_catalog(
                catalog,
                dense_config=DenseConfig(cache_dir=root / "missing-cache"),
            )
            agent = Agent(catalog, retriever=retriever)

            self.assertEqual(retriever.catalog_path, catalog)
            self.assertIn(
                "women s trail running shoes",
                agent.context_vocabulary.category_terms,
            )

    def test_known_warmup_failure_skips_dense_without_repeating_base_work(self) -> None:
        base = FakeRetriever(_result("structured", ["A", "B", "C", "D"]))
        dense = FakeRetriever(_result("structured", ["D", "C", "B", "A"]))
        retriever = ConditionalDenseRetriever(
            base,
            dense,
            config=ConditionalDenseConfig(min_base_candidates=3),
            dense_warmup_status="dense_cache_missing",
        )

        result = retriever.retrieve(_request())

        self.assertEqual(len(base.requests), 1)
        self.assertEqual(dense.requests, [])
        self.assertEqual(result.candidates, base.result.candidates)
        self.assertEqual(
            result.diagnostics.route_failures,
            {"dense": "dense_cache_missing"},
        )

    def test_constructor_rejects_mismatched_catalog_order_or_path(self) -> None:
        base = FakeRetriever(_result("structured", ["A", "B", "C"]))
        dense = FakeRetriever(_result("dense", ["C", "B", "A"]))
        dense.fallback_ids = tuple(reversed(base.fallback_ids))
        with self.assertRaises(ValueError):
            ConditionalDenseRetriever(base, dense)

        base = FakeRetriever(_result("structured", ["A", "B", "C"]))
        dense = FakeRetriever(_result("dense", ["C", "B", "A"]))
        base.catalog_path = Path("catalog-a.jsonl")
        dense.catalog_path = Path("catalog-b.jsonl")
        with self.assertRaises(ValueError):
            ConditionalDenseRetriever(base, dense)

    def test_missing_or_nonfinite_dense_latency_uses_exact_base_fallback(self) -> None:
        for latency in (None, float("nan"), float("inf"), -1.0):
            with self.subTest(latency=latency):
                dense_result = replace(
                    _result("dense", ["D", "C", "E"]),
                    diagnostics=replace(
                        _result("dense", ["D", "C", "E"]).diagnostics,
                        latency_ms=latency,
                    ),
                )
                retriever, base, _dense = self._retriever(
                    dense_result=dense_result
                )

                result = retriever.retrieve(_request())

                self.assertEqual(result.candidates, base.result.candidates)
                self.assertTrue(result.diagnostics.fallback_used)
                self.assertEqual(
                    result.diagnostics.route_failures,
                    {"dense": "dense_latency_invalid"},
                )
                self.assertNotIn("dense", result.diagnostics.stage_latencies_ms)

    def test_close_releases_distinct_base_and_dense_retrievers(self) -> None:
        class ClosingFakeRetriever(FakeRetriever):
            def __init__(self, result: RetrievalResult) -> None:
                super().__init__(result)
                self.close_calls = 0

            def close(self) -> None:
                self.close_calls += 1

        base = ClosingFakeRetriever(_result("structured", ["A", "B", "C"]))
        dense = ClosingFakeRetriever(_result("dense", ["C", "B", "A"]))
        retriever = ConditionalDenseRetriever(base, dense)

        retriever.close()

        self.assertEqual(base.close_calls, 1)
        self.assertEqual(dense.close_calls, 1)

    def test_query_failure_never_repeats_shared_base_work(self) -> None:
        class CountingHybridRetriever(HybridRetriever):
            def __init__(self, catalog_path: Path) -> None:
                super().__init__(catalog_path)
                self.retrieve_calls = 0

            def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
                self.retrieve_calls += 1
                return super().retrieve(request)

        class QueryFailingBackend:
            def __init__(self) -> None:
                self.rank_calls = 0

            def rank(self, query: str, top_n: int) -> list[tuple[int, float]]:
                self.rank_calls += 1
                raise RuntimeError("query encoding failed")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            cache = root / "cache"
            cache.mkdir()
            rows = [
                {"parent_asin": value, "title": f"{value} walking shoes"}
                for value in ("A", "B", "C", "D", "E")
            ]
            catalog.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            ids_path = cache / "ids.json"
            vectors_path = cache / "vectors.npy"
            ids_path.write_text(
                json.dumps([row["parent_asin"] for row in rows]),
                encoding="utf-8",
            )
            vectors_path.write_bytes(b"fixture")
            (cache / "metadata.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "catalog_sha256": file_sha256(catalog),
                        "model_id": "sentence-transformers/all-MiniLM-L6-v2",
                        "model_revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                        "dimension": 384,
                        "dtype": "float32",
                        "normalized": True,
                        "product_count": len(rows),
                        "product_text_template": "product-fields-v1",
                        "query_text_template": "distilled-query-v1",
                        "ids_sha256": file_sha256(ids_path),
                        "vectors_sha256": file_sha256(vectors_path),
                    }
                ),
                encoding="utf-8",
            )
            base = CountingHybridRetriever(catalog)
            backend = QueryFailingBackend()
            dense = DenseRetriever(
                catalog,
                config=DenseConfig(cache_dir=cache),
                lexical_fallback=base,
                backend_factory=lambda _config, _ids: backend,
            )
            retriever = ConditionalDenseRetriever(
                base,
                dense,
                config=ConditionalDenseConfig(min_base_candidates=3),
            )

            first = retriever.retrieve(_request())
            second = retriever.retrieve(_request())

            self.assertEqual(base.retrieve_calls, 2)
            self.assertEqual(backend.rank_calls, 1)
            self.assertEqual(first.diagnostics.route_failures, {"dense": "dense_query_failed"})
            self.assertEqual(second.diagnostics.route_failures, {"dense": "dense_query_failed"})
            self.assertEqual(first.candidates, second.candidates)


if __name__ == "__main__":
    unittest.main()
