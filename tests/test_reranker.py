from __future__ import annotations

import math
import unittest
from dataclasses import replace

from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalRequest, RetrievalResult
from starter.core.planner import Strategy
from starter.core.state import SessionState
from starter.retrieval.reranker import (
    LocalCrossEncoderBackend,
    RerankerConfig,
    RerankingRetriever,
)


def _request(
    *,
    active_constraints: list[dict] | None = None,
    rejected_constraints: list[dict] | None = None,
) -> RetrievalRequest:
    strategy = Strategy(
        intent="buying",
        lexical_weight=0.72,
        structured_weight=0.28,
        semantic_weight=0.0,
        retrieval_depth=4,
        allow_hard_filter=True,
        clarification_enabled=True,
        fallback_mode="lexical",
        reason="reranker fixture",
    )
    return RetrievalRequest(
        session_id="reranker-session",
        turn=1,
        top_k=3,
        query="comfortable trail shoes",
        intent="buying",
        strategy=strategy,
        active_constraints=active_constraints or [],
        rejected_constraints=rejected_constraints or [],
    )


class FakeRetriever:
    catalog_ids = frozenset({"A", "B", "C", "D"})
    fallback_ids = ("A", "B", "C", "D")

    def __init__(self) -> None:
        self.result = RetrievalResult(
            candidates=[
                Candidate(
                    parent_asin=parent_asin,
                    source="structured",
                    evidence_text=f"evidence {parent_asin}",
                    diagnostics={"final_rank": rank},
                )
                for rank, parent_asin in enumerate(self.fallback_ids, start=1)
            ],
            diagnostics=RetrievalDiagnostics(
                route="structured",
                candidate_count=4,
                latency_ms=2.0,
                notes=["base_ready"],
                stage_latencies_ms={"lexical": 1.0, "structured_filter": 1.0},
                requested_route_weights={
                    "lexical": 0.72,
                    "structured": 0.28,
                    "dense": 0.0,
                },
                executed_routes=["lexical", "structured"],
            ),
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        return self.result


class LegacyFakeRetriever(FakeRetriever):
    def __init__(self, *, fallback_used: bool = False) -> None:
        super().__init__()
        self.result = replace(
            self.result,
            diagnostics=RetrievalDiagnostics(
                route="structured",
                candidate_count=4,
                fallback_used=fallback_used,
                notes=["legacy_base"],
            ),
        )


class RecordingBackend:
    def __init__(self, scores: list[float] | Exception) -> None:
        self.scores = scores
        self.calls: list[tuple[str, list[str]]] = []

    def score(
        self,
        query: str,
        evidence_texts: list[str],
        timeout_ms: float,
    ) -> list[float]:
        self.calls.append((query, list(evidence_texts)))
        if isinstance(self.scores, Exception):
            raise self.scores
        return list(self.scores)


class RerankingRetrieverTest(unittest.TestCase):
    def test_guard_consumes_the_persisted_rejection_shape_from_session_state(self) -> None:
        state = SessionState(session_id="persisted-rejection", user_profile={})
        state.apply_user_context(
            constraints=[],
            rejected_constraints=[
                {
                    "attribute": "material",
                    "normalized_value": "leather",
                    "confidence": 0.95,
                }
            ],
        )
        self.assertEqual(state.rejected_constraints[0]["active"], False)
        base = FakeRetriever()
        base.result = replace(
            base.result,
            candidates=[
                replace(
                    candidate,
                    diagnostics={
                        "structured_matches": [],
                        "rejected_constraint_matches": (
                            [{"attribute": "material", "value": "leather"}]
                            if candidate.parent_asin == "C"
                            else []
                        ),
                    },
                )
                for candidate in base.result.candidates
            ],
        )
        result = RerankingRetriever(
            base,
            config=RerankerConfig(
                candidate_limit=4,
                constraint_guard_enabled=True,
            ),
            backend=RecordingBackend([0.1, 0.2, 1.0, 0.9]),
        ).retrieve(
            _request(rejected_constraints=list(state.rejected_constraints))
        )

        self.assertEqual(
            [candidate.parent_asin for candidate in result.candidates],
            ["D", "B", "A", "C"],
        )
        self.assertEqual(
            result.candidates[-1].diagnostics["constraint_guard_status"],
            "contradicted",
        )

    def test_constraint_preserving_mode_anchors_top_three_and_scores_only_ranks_four_to_thirty(self) -> None:
        base = FakeRetriever()
        base.catalog_ids = frozenset(chr(code) for code in range(ord("A"), ord("Z") + 1))
        base.fallback_ids = tuple(sorted(base.catalog_ids))
        base.result = replace(
            base.result,
            candidates=[
                Candidate(
                    parent_asin=parent_asin,
                    source="structured",
                    evidence_text=f"evidence {parent_asin}",
                    diagnostics={"final_rank": rank},
                )
                for rank, parent_asin in enumerate(base.fallback_ids, start=1)
            ],
            diagnostics=replace(base.result.diagnostics, candidate_count=26),
        )
        backend = RecordingBackend([float(index) for index in range(23)])
        retriever = RerankingRetriever(
            base,
            config=RerankerConfig(
                candidate_limit=30,
                anchor_count=3,
                base_score_weight=0.35,
            ),
            backend=backend,
        )

        result = retriever.retrieve(_request())

        self.assertEqual(
            backend.calls,
            [
                (
                    "comfortable trail shoes",
                    [f"evidence {parent_asin}" for parent_asin in base.fallback_ids[3:]],
                )
            ],
        )
        self.assertEqual(result.candidates[:3], base.result.candidates[:3])
        self.assertNotEqual(result.candidates[3:], base.result.candidates[3:])
        self.assertEqual(result.diagnostics.rerank_pool_size, 23)
        self.assertEqual(result.candidates[3].diagnostics["pre_rerank_rank"], 26)
        self.assertEqual(result.candidates[3].diagnostics["semantic_rerank_rank"], 1)
        self.assertEqual(result.candidates[3].diagnostics["rerank_anchor_count"], 3)

    def test_constraint_guard_keeps_matches_then_unknown_then_explicit_contradictions(self) -> None:
        base = FakeRetriever()
        base.result = replace(
            base.result,
            candidates=[
                replace(
                    base.result.candidates[0],
                    diagnostics={
                        "structured_matches": [
                            {"attribute": "color", "value": "black", "confidence": 0.95}
                        ],
                        "rejected_constraint_matches": [],
                    },
                ),
                replace(
                    base.result.candidates[1],
                    diagnostics={
                        "structured_matches": [],
                        "rejected_constraint_matches": [],
                    },
                ),
                replace(
                    base.result.candidates[2],
                    diagnostics={
                        "structured_matches": [],
                        "rejected_constraint_matches": [
                            {"attribute": "material", "value": "leather", "confidence": 0.95}
                        ],
                    },
                ),
                base.result.candidates[3],
            ],
        )
        retriever = RerankingRetriever(
            base,
            config=RerankerConfig(
                candidate_limit=4,
                anchor_count=0,
                base_score_weight=0.0,
                minimum_constraint_confidence=0.75,
                constraint_guard_enabled=True,
            ),
            backend=RecordingBackend([0.1, 0.2, 1.0, 0.9]),
        )

        result = retriever.retrieve(
            _request(
                active_constraints=[
                    {
                        "attribute": "color",
                        "normalized_value": "black",
                        "confidence": 0.95,
                        "hard": True,
                        "active": True,
                    }
                ],
                rejected_constraints=[
                    {
                        "attribute": "material",
                        "normalized_value": "leather",
                        "confidence": 0.95,
                        "active": False,
                    }
                ],
            )
        )

        self.assertEqual(
            [candidate.parent_asin for candidate in result.candidates],
            ["A", "D", "B", "C"],
        )
        self.assertEqual(
            [candidate.diagnostics["constraint_guard_status"] for candidate in result.candidates],
            ["matched", "neutral", "neutral", "contradicted"],
        )

    def test_rejected_guard_honors_no_preference_and_current_positive_suppression(self) -> None:
        base = FakeRetriever()
        base.result = replace(
            base.result,
            candidates=[
                replace(
                    candidate,
                    diagnostics={
                        "structured_matches": (
                            [{"attribute": "material", "value": "leather"}]
                            if candidate.parent_asin == "C"
                            else []
                        ),
                        "rejected_constraint_matches": (
                            [{"attribute": "material", "value": "leather"}]
                            if candidate.parent_asin == "C"
                            else []
                        ),
                    },
                )
                for candidate in base.result.candidates
            ],
        )
        rejected = [
            {
                "attribute": "material",
                "normalized_value": "leather",
                "confidence": 0.95,
                "active": False,
            }
        ]

        no_preference = RerankingRetriever(
            base,
            config=RerankerConfig(
                candidate_limit=4,
                constraint_guard_enabled=True,
            ),
            backend=RecordingBackend([0.1, 0.2, 1.0, 0.9]),
        ).retrieve(
            replace(
                _request(rejected_constraints=rejected),
                no_preference_attributes=["material"],
            )
        )
        current_positive = RerankingRetriever(
            base,
            config=RerankerConfig(
                candidate_limit=4,
                constraint_guard_enabled=True,
            ),
            backend=RecordingBackend([0.1, 0.2, 1.0, 0.9]),
        ).retrieve(
            _request(
                active_constraints=[
                    {
                        "attribute": "material",
                        "normalized_value": "leather",
                        "confidence": 0.95,
                        "hard": True,
                        "active": True,
                    }
                ],
                rejected_constraints=rejected,
            )
        )

        no_preference_c = next(
            candidate
            for candidate in no_preference.candidates
            if candidate.parent_asin == "C"
        )
        positive_c = next(
            candidate
            for candidate in current_positive.candidates
            if candidate.parent_asin == "C"
        )
        self.assertEqual(
            no_preference_c.diagnostics["constraint_guard_status"],
            "neutral",
        )
        self.assertEqual(
            positive_c.diagnostics["constraint_guard_status"],
            "matched",
        )

    def test_constraint_preserving_failure_returns_the_exact_full_base_order(self) -> None:
        base = FakeRetriever()
        retriever = RerankingRetriever(
            base,
            config=RerankerConfig(candidate_limit=4, anchor_count=2),
            backend=RecordingBackend(RuntimeError("model unavailable")),
        )

        result = retriever.retrieve(_request())

        self.assertEqual(result.candidates, base.result.candidates)
        self.assertEqual(result.diagnostics.rerank_pool_size, 2)
        self.assertEqual(
            result.diagnostics.route_failures,
            {"semantic_rerank": "reranker_error"},
        )

    def test_timeout_returns_prompt_fallback_and_disables_the_expensive_stage(self) -> None:
        config = RerankerConfig(candidate_limit=2, timeout_ms=1.0)
        backend = LocalCrossEncoderBackend(config)
        retriever = RerankingRetriever(
            FakeRetriever(),
            config=config,
            backend=backend,
        )

        first = retriever.retrieve(_request())
        second = retriever.retrieve(_request())

        self.assertEqual(first.diagnostics.route_failures, {"semantic_rerank": "reranker_timeout"})
        self.assertEqual(second.diagnostics.route_failures, {"semantic_rerank": "reranker_timeout"})
        self.assertFalse(backend.worker_alive)

    def test_reranks_only_the_bounded_prefix_and_preserves_the_tail(self) -> None:
        backend = RecordingBackend([0.1, 0.9])
        retriever = RerankingRetriever(
            FakeRetriever(),
            config=RerankerConfig(candidate_limit=2),
            backend=backend,
        )

        result = retriever.retrieve(_request())

        self.assertEqual(backend.calls, [("comfortable trail shoes", ["evidence A", "evidence B"])])
        self.assertEqual([item.parent_asin for item in result.candidates], ["B", "A", "C", "D"])
        self.assertEqual(result.diagnostics.route, "semantic_rerank")
        self.assertEqual(
            result.diagnostics.executed_routes,
            ["lexical", "structured", "semantic_rerank"],
        )
        self.assertIsNone(result.diagnostics.fallback_route)
        self.assertEqual(result.diagnostics.rerank_pool_size, 2)
        self.assertEqual(result.candidates[0].diagnostics["pre_rerank_rank"], 2)
        self.assertEqual(result.candidates[0].diagnostics["semantic_rerank_rank"], 1)
        self.assertEqual(result.candidates[0].diagnostics["semantic_rerank_score"], 0.9)
        self.assertEqual(result.candidates[2].diagnostics, {"final_rank": 3})

    def test_successful_rerank_preserves_an_upstream_fallback_route(self) -> None:
        base = FakeRetriever()
        base.result = replace(
            base.result,
            diagnostics=replace(
                base.result.diagnostics,
                fallback_used=True,
                route_failures={"dense": "dense_cache_missing"},
                fallback_route="structured",
            ),
        )
        retriever = RerankingRetriever(
            base,
            config=RerankerConfig(candidate_limit=2),
            backend=RecordingBackend([0.1, 0.9]),
        )

        result = retriever.retrieve(_request())

        self.assertEqual(result.diagnostics.route, "semantic_rerank")
        self.assertTrue(result.diagnostics.fallback_used)
        self.assertEqual(
            result.diagnostics.route_failures,
            {"dense": "dense_cache_missing"},
        )
        self.assertEqual(result.diagnostics.fallback_route, "structured")
        self.assertEqual(
            result.diagnostics.executed_routes,
            ["lexical", "structured", "semantic_rerank"],
        )

    def test_successful_rerank_keeps_legacy_route_semantics_unreported(self) -> None:
        for fallback_used in (False, True):
            with self.subTest(fallback_used=fallback_used):
                retriever = RerankingRetriever(
                    LegacyFakeRetriever(fallback_used=fallback_used),
                    config=RerankerConfig(candidate_limit=2),
                    backend=RecordingBackend([0.1, 0.9]),
                )

                result = retriever.retrieve(_request())

                self.assertEqual(result.diagnostics.requested_route_weights, {})
                self.assertEqual(result.diagnostics.executed_routes, [])
                self.assertIsNone(result.diagnostics.fallback_route)
                self.assertEqual(result.diagnostics.fallback_used, fallback_used)

    def test_reranker_failure_keeps_legacy_route_semantics_unreported(self) -> None:
        retriever = RerankingRetriever(
            LegacyFakeRetriever(),
            config=RerankerConfig(candidate_limit=2),
            backend=RecordingBackend(RuntimeError("model unavailable")),
        )

        result = retriever.retrieve(_request())

        self.assertTrue(result.diagnostics.fallback_used)
        self.assertEqual(result.diagnostics.requested_route_weights, {})
        self.assertEqual(result.diagnostics.executed_routes, [])
        self.assertIsNone(result.diagnostics.fallback_route)
        self.assertIn("semantic_rerank_failed:reranker_error", result.diagnostics.notes)

    def test_backend_failure_preserves_exact_pre_rerank_candidates(self) -> None:
        base = FakeRetriever()
        retriever = RerankingRetriever(
            base,
            config=RerankerConfig(candidate_limit=3),
            backend=RecordingBackend(RuntimeError("model unavailable")),
        )

        result = retriever.retrieve(_request())

        self.assertEqual(result.candidates, base.result.candidates)
        self.assertEqual(result.diagnostics.route, "structured")
        self.assertTrue(result.diagnostics.fallback_used)
        self.assertEqual(result.diagnostics.route_failures, {"semantic_rerank": "reranker_error"})
        self.assertEqual(
            result.diagnostics.executed_routes,
            ["lexical", "structured"],
        )
        self.assertEqual(result.diagnostics.fallback_route, "structured")
        self.assertIn("semantic_rerank_failed:reranker_error", result.diagnostics.notes)

    def test_invalid_scores_use_the_same_deterministic_fallback(self) -> None:
        for scores in ([0.5], [0.5, math.nan]):
            with self.subTest(scores=scores):
                base = FakeRetriever()
                retriever = RerankingRetriever(
                    base,
                    config=RerankerConfig(candidate_limit=2),
                    backend=RecordingBackend(scores),
                )

                result = retriever.retrieve(_request())

                self.assertEqual(result.candidates, base.result.candidates)
                self.assertEqual(
                    result.diagnostics.route_failures,
                    {"semantic_rerank": "invalid_reranker_scores"},
                )

    def test_candidate_limit_is_strictly_bounded(self) -> None:
        for value in (0, 101, True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "candidate_limit"):
                    RerankerConfig(candidate_limit=value)

    def test_constraint_preserving_configuration_is_validated(self) -> None:
        invalid = (
            {"anchor_count": -1},
            {"anchor_count": 30, "candidate_limit": 30},
            {"base_score_weight": -0.1},
            {"base_score_weight": 1.1},
            {"minimum_constraint_confidence": math.nan},
        )
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    RerankerConfig(**values)


if __name__ == "__main__":
    unittest.main()
