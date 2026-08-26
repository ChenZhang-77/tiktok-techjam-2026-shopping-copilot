from __future__ import annotations

import math
import unittest

from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalRequest, RetrievalResult
from starter.core.planner import Strategy
from starter.retrieval.reranker import RerankerConfig, RerankingRetriever


def _request() -> RetrievalRequest:
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
            ),
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        return self.result


class RecordingBackend:
    def __init__(self, scores: list[float] | Exception) -> None:
        self.scores = scores
        self.calls: list[tuple[str, list[str]]] = []

    def score(self, query: str, evidence_texts: list[str]) -> list[float]:
        self.calls.append((query, list(evidence_texts)))
        if isinstance(self.scores, Exception):
            raise self.scores
        return list(self.scores)


class RerankingRetrieverTest(unittest.TestCase):
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
        self.assertEqual(result.diagnostics.rerank_pool_size, 2)
        self.assertEqual(result.candidates[0].diagnostics["pre_rerank_rank"], 2)
        self.assertEqual(result.candidates[0].diagnostics["semantic_rerank_rank"], 1)
        self.assertEqual(result.candidates[0].diagnostics["semantic_rerank_score"], 0.9)
        self.assertEqual(result.candidates[2].diagnostics, {"final_rank": 3})

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


if __name__ == "__main__":
    unittest.main()
