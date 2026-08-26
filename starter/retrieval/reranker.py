from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from typing import Protocol, cast

from starter.contracts import RetrievalRequest, RetrievalResult


MODEL_ID = "cross-encoder/ms-marco-MiniLM-L2-v2"
MODEL_REVISION = "1b5cd67b15209f24824c50370e0397743aa9b787"


@dataclass(frozen=True)
class RerankerConfig:
    candidate_limit: int = 30
    model_id: str = MODEL_ID
    model_revision: str = MODEL_REVISION
    model_cache_dir: Path = Path("models/huggingface/hub")
    batch_size: int = 16
    max_length: int = 256
    timeout_ms: float = 5000.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.candidate_limit, bool)
            or not isinstance(self.candidate_limit, int)
            or not 1 <= self.candidate_limit <= 100
        ):
            raise ValueError("candidate_limit must be an integer from 1 to 100")
        for field_name, value in (
            ("batch_size", self.batch_size),
            ("max_length", self.max_length),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")
        if (
            isinstance(self.timeout_ms, bool)
            or not isinstance(self.timeout_ms, (int, float))
            or not math.isfinite(self.timeout_ms)
            or self.timeout_ms <= 0
        ):
            raise ValueError("timeout_ms must be a finite positive number")


class RerankerBackend(Protocol):
    def score(self, query: str, evidence_texts: list[str]) -> list[float]:
        ...


class LocalCrossEncoderBackend:
    """Lazy, network-free CrossEncoder scorer pinned to an exact revision."""

    def __init__(self, config: RerankerConfig) -> None:
        self._config = config
        self._model: object | None = None

    def _load_model(self) -> object:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(
                self._config.model_id,
                revision=self._config.model_revision,
                cache_folder=str(self._config.model_cache_dir),
                local_files_only=True,
                max_length=self._config.max_length,
            )
        return self._model

    def score(self, query: str, evidence_texts: list[str]) -> list[float]:
        model = self._load_model()
        scores = model.predict(
            [(query, evidence_text) for evidence_text in evidence_texts],
            batch_size=self._config.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [float(score) for score in scores]


class RerankingRetriever:
    """Bounded semantic reranker with exact pre-rerank Candidate fallback."""

    def __init__(
        self,
        base_retriever: object,
        *,
        config: RerankerConfig | None = None,
        backend: RerankerBackend | None = None,
    ) -> None:
        self._base = base_retriever
        self.config = config if config is not None else RerankerConfig()
        self._backend = backend if backend is not None else LocalCrossEncoderBackend(self.config)
        self._disabled_reason: str | None = None
        self.catalog_ids = base_retriever.catalog_ids
        self.fallback_ids = base_retriever.fallback_ids

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        base = self._base.retrieve(request)
        pool_size = min(self.config.candidate_limit, len(base.candidates))
        if pool_size < 2:
            return base

        started = time.perf_counter()
        if self._disabled_reason is not None:
            return self._fallback(base, started, pool_size, self._disabled_reason)
        try:
            scores = self._score_with_timeout(
                request.query,
                [candidate.evidence_text or "" for candidate in base.candidates[:pool_size]],
            )
            if len(scores) != pool_size or any(not math.isfinite(score) for score in scores):
                raise ValueError("invalid_reranker_scores")
        except Exception as error:
            if isinstance(error, TimeoutError):
                reason = "reranker_timeout"
                self._disabled_reason = reason
            elif isinstance(error, ValueError) and str(error) == "invalid_reranker_scores":
                reason = "invalid_reranker_scores"
            else:
                reason = "reranker_error"
            return self._fallback(base, started, pool_size, reason)

        indexed = list(enumerate(zip(base.candidates[:pool_size], scores), start=1))
        indexed.sort(key=lambda item: (-item[1][1], item[0]))
        reranked = [
            replace(
                candidate,
                source="semantic_rerank",
                score=round(score, 8),
                diagnostics={
                    **candidate.diagnostics,
                    "pre_rerank_rank": previous_rank,
                    "semantic_rerank_rank": rank,
                    "semantic_rerank_score": round(score, 8),
                },
            )
            for rank, (previous_rank, (candidate, score)) in enumerate(indexed, start=1)
        ]
        latency_ms = (time.perf_counter() - started) * 1000.0
        stage_latencies = dict(base.diagnostics.stage_latencies_ms)
        stage_latencies["semantic_rerank"] = round(latency_ms, 6)
        base_latency = base.diagnostics.latency_ms or 0.0
        diagnostics = replace(
            base.diagnostics,
            route="semantic_rerank",
            latency_ms=round(base_latency + latency_ms, 6),
            notes=[*base.diagnostics.notes, "semantic_rerank_applied"],
            stage_latencies_ms=stage_latencies,
            rerank_pool_size=pool_size,
            cache_state={
                **base.diagnostics.cache_state,
                "semantic_reranker": "local_only_ready",
            },
            ranking_pool_sizes={
                **base.diagnostics.ranking_pool_sizes,
                "semantic_rerank": pool_size,
            },
        )
        return RetrievalResult(
            candidates=[*reranked, *base.candidates[pool_size:]],
            diagnostics=diagnostics,
        )

    def _score_with_timeout(self, query: str, evidence_texts: list[str]) -> list[float]:
        completed: Queue[tuple[bool, object]] = Queue(maxsize=1)

        def score() -> None:
            try:
                completed.put((True, self._backend.score(query, evidence_texts)))
            except Exception as error:
                completed.put((False, error))

        worker = Thread(target=score, name="semantic-reranker", daemon=True)
        worker.start()
        worker.join(self.config.timeout_ms / 1000.0)
        if worker.is_alive():
            raise TimeoutError("semantic reranker exceeded its time budget")
        try:
            succeeded, payload = completed.get_nowait()
        except Empty as error:
            raise RuntimeError("semantic reranker completed without a result") from error
        if not succeeded:
            raise cast(Exception, payload)
        return list(cast(list[float], payload))

    def _fallback(
        self,
        base: RetrievalResult,
        started: float,
        pool_size: int,
        reason: str,
    ) -> RetrievalResult:
        latency_ms = (time.perf_counter() - started) * 1000.0
        stage_latencies = dict(base.diagnostics.stage_latencies_ms)
        stage_latencies["semantic_rerank"] = round(latency_ms, 6)
        failures = dict(base.diagnostics.route_failures)
        failures["semantic_rerank"] = reason
        base_latency = base.diagnostics.latency_ms or 0.0
        diagnostics = replace(
            base.diagnostics,
            fallback_used=True,
            latency_ms=round(base_latency + latency_ms, 6),
            notes=[*base.diagnostics.notes, f"semantic_rerank_failed:{reason}"],
            stage_latencies_ms=stage_latencies,
            route_failures=failures,
            rerank_pool_size=pool_size,
            cache_state={
                **base.diagnostics.cache_state,
                "semantic_reranker": "failed",
            },
            ranking_pool_sizes={
                **base.diagnostics.ranking_pool_sizes,
                "semantic_rerank": pool_size,
            },
        )
        return RetrievalResult(candidates=base.candidates, diagnostics=diagnostics)

    def configuration_snapshot(self) -> dict:
        return {
            "candidate_limit": self.config.candidate_limit,
            "model_id": self.config.model_id,
            "model_revision": self.config.model_revision,
            "model_cache_dir": str(self.config.model_cache_dir),
            "batch_size": self.config.batch_size,
            "max_length": self.config.max_length,
            "timeout_ms": self.config.timeout_ms,
            "runtime_network_access": False,
            "failure_fallback": "exact_pre_rerank_candidate_order",
        }
