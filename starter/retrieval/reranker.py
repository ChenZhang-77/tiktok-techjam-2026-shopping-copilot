from __future__ import annotations

import math
import multiprocessing
import time
from dataclasses import dataclass, replace
from pathlib import Path
from queue import Empty
from typing import Any, Callable, Protocol

from starter.contracts import RetrievalRequest, RetrievalResult


MODEL_ID = "cross-encoder/ms-marco-MiniLM-L2-v2"
MODEL_REVISION = "1b5cd67b15209f24824c50370e0397743aa9b787"


@dataclass(frozen=True)
class RerankerConfig:
    candidate_limit: int = 30
    anchor_count: int = 0
    base_score_weight: float = 0.0
    minimum_constraint_confidence: float = 0.75
    constraint_guard_enabled: bool = False
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
        if (
            isinstance(self.anchor_count, bool)
            or not isinstance(self.anchor_count, int)
            or not 0 <= self.anchor_count < self.candidate_limit
        ):
            raise ValueError(
                "anchor_count must be a non-negative integer below candidate_limit"
            )
        for field_name, value in (
            ("base_score_weight", self.base_score_weight),
            ("minimum_constraint_confidence", self.minimum_constraint_confidence),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                raise ValueError(f"{field_name} must be a finite number from 0 to 1")
        if not isinstance(self.constraint_guard_enabled, bool):
            raise ValueError("constraint_guard_enabled must be a boolean")
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
    def score(
        self,
        query: str,
        evidence_texts: list[str],
        timeout_ms: float,
    ) -> list[float]:
        ...


class RerankerTimeoutError(TimeoutError):
    pass


def _cross_encoder_worker(
    config: RerankerConfig,
    requests: Any,
    responses: Any,
) -> None:
    from sentence_transformers import CrossEncoder

    model = CrossEncoder(
        config.model_id,
        revision=config.model_revision,
        cache_folder=str(config.model_cache_dir),
        local_files_only=True,
        max_length=config.max_length,
    )
    while True:
        payload = requests.get()
        if payload is None:
            return
        request_id, query, evidence_texts = payload
        try:
            scores = model.predict(
                [(query, evidence_text) for evidence_text in evidence_texts],
                batch_size=config.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            responses.put((request_id, True, [float(score) for score in scores]))
        except Exception as error:
            responses.put((request_id, False, type(error).__name__))


class LocalCrossEncoderBackend:
    """Pinned local CrossEncoder isolated in a terminate-on-timeout process."""

    def __init__(
        self,
        config: RerankerConfig,
        *,
        worker_target: Callable[[RerankerConfig, Any, Any], None] = _cross_encoder_worker,
    ) -> None:
        self._config = config
        self._worker_target = worker_target
        self._context = multiprocessing.get_context("spawn")
        self._process: multiprocessing.Process | None = None
        self._requests: Any = None
        self._responses: Any = None
        self._next_request_id = 1

    @property
    def worker_alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def _start(self) -> None:
        if self.worker_alive:
            return
        self._requests = self._context.Queue()
        self._responses = self._context.Queue()
        self._process = self._context.Process(
            target=self._worker_target,
            args=(self._config, self._requests, self._responses),
            name="semantic-reranker",
            daemon=True,
        )
        self._process.start()

    def score(
        self,
        query: str,
        evidence_texts: list[str],
        timeout_ms: float,
    ) -> list[float]:
        self._start()
        request_id = self._next_request_id
        self._next_request_id += 1
        self._requests.put((request_id, query, evidence_texts))
        try:
            response_id, succeeded, payload = self._responses.get(
                timeout=timeout_ms / 1000.0
            )
        except Empty as error:
            self._stop(force=True)
            raise RerankerTimeoutError(
                "semantic reranker exceeded its time budget and was terminated"
            ) from error
        if response_id != request_id:
            self._stop(force=True)
            raise RuntimeError("semantic reranker response order is invalid")
        if not succeeded:
            raise RuntimeError(f"semantic reranker worker failed: {payload}")
        return [float(score) for score in payload]

    def _stop(self, *, force: bool) -> None:
        process = self._process
        if process is None:
            return
        if process.is_alive() and not force and self._requests is not None:
            self._requests.put(None)
            process.join(timeout=0.5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=1.0)
        self._process = None
        for queue in (self._requests, self._responses):
            if queue is not None:
                queue.close()
                queue.join_thread()
        self._requests = None
        self._responses = None

    def close(self) -> None:
        self._stop(force=False)

    def __del__(self) -> None:
        try:
            self._stop(force=True)
        except Exception:
            pass


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
        pool_end = min(self.config.candidate_limit, len(base.candidates))
        pool_start = min(self.config.anchor_count, pool_end)
        pool_size = pool_end - pool_start
        if pool_size < 2:
            return base

        started = time.perf_counter()
        if self._disabled_reason is not None:
            return self._fallback(base, started, pool_size, self._disabled_reason)
        try:
            scores = self._backend.score(
                request.query,
                [
                    candidate.evidence_text or ""
                    for candidate in base.candidates[pool_start:pool_end]
                ],
                self.config.timeout_ms,
            )
            if len(scores) != pool_size or any(not math.isfinite(score) for score in scores):
                raise ValueError("invalid_reranker_scores")
        except Exception as error:
            if isinstance(error, RerankerTimeoutError):
                reason = "reranker_timeout"
                self._disabled_reason = reason
            elif isinstance(error, ValueError) and str(error) == "invalid_reranker_scores":
                reason = "invalid_reranker_scores"
            else:
                reason = "reranker_error"
            return self._fallback(base, started, pool_size, reason)

        semantic_order = sorted(
            range(pool_size),
            key=lambda index: (-scores[index], index),
        )
        semantic_ranks = {
            index: rank for rank, index in enumerate(semantic_order, start=1)
        }
        denominator = max(1, pool_size - 1)
        pool_candidates = base.candidates[pool_start:pool_end]
        raw_base_scores = [
            self._candidate_base_score(candidate, previous_rank=pool_start + index + 1)
            for index, candidate in enumerate(pool_candidates)
        ]
        base_values = [value for value, _source in raw_base_scores]
        base_min = min(base_values)
        base_max = max(base_values)
        indexed = []
        for tail_index, (candidate, score) in enumerate(
            zip(pool_candidates, scores)
        ):
            previous_rank = pool_start + tail_index + 1
            raw_base_score, base_score_source = raw_base_scores[tail_index]
            base_score_signal = (
                (raw_base_score - base_min) / (base_max - base_min)
                if base_max > base_min
                else 1.0 - tail_index / denominator
            )
            semantic_rank = semantic_ranks[tail_index]
            semantic_rank_signal = 1.0 - (semantic_rank - 1) / denominator
            blended_score = (
                self.config.base_score_weight * base_score_signal
                + (1.0 - self.config.base_score_weight) * semantic_rank_signal
            )
            guard_status = self._constraint_guard_status(candidate, request)
            guard_rank = 1 if guard_status == "contradicted" else 0
            indexed.append(
                (
                    guard_rank,
                    -blended_score,
                    previous_rank,
                    candidate,
                    score,
                    semantic_rank,
                    raw_base_score,
                    base_score_source,
                    base_score_signal,
                    semantic_rank_signal,
                    blended_score,
                    guard_status,
                )
            )
        indexed.sort(key=lambda item: item[:3])
        reranked = [
            replace(
                candidate,
                source="semantic_rerank",
                score=round(blended_score, 8),
                diagnostics={
                    **candidate.diagnostics,
                    "pre_rerank_rank": previous_rank,
                    "semantic_rerank_rank": semantic_rank,
                    "semantic_rerank_score": round(score, 8),
                    "pre_rerank_base_score": round(raw_base_score, 8),
                    "pre_rerank_base_score_source": base_score_source,
                    "base_score_signal": round(base_score_signal, 8),
                    "semantic_rank_signal": round(semantic_rank_signal, 8),
                    "blended_rerank_score": round(blended_score, 8),
                    "constraint_guard_status": guard_status,
                    "rerank_anchor_count": self.config.anchor_count,
                },
            )
            for (
                _guard_rank,
                _negative_blended_score,
                previous_rank,
                candidate,
                score,
                semantic_rank,
                raw_base_score,
                base_score_source,
                base_score_signal,
                semantic_rank_signal,
                blended_score,
                guard_status,
            ) in indexed
        ]
        latency_ms = (time.perf_counter() - started) * 1000.0
        stage_latencies = dict(base.diagnostics.stage_latencies_ms)
        stage_latencies["semantic_rerank"] = round(latency_ms, 6)
        base_latency = base.diagnostics.latency_ms or 0.0
        route_semantics_reported = bool(
            base.diagnostics.requested_route_weights
            and base.diagnostics.executed_routes
        )

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
            executed_routes=(
                [*base.diagnostics.executed_routes, "semantic_rerank"]
                if route_semantics_reported
                else []
            ),
            fallback_route=(
                base.diagnostics.fallback_route
                if route_semantics_reported
                else None
            ),
        )
        return RetrievalResult(
            candidates=[
                *base.candidates[:pool_start],
                *reranked,
                *base.candidates[pool_end:],
            ],
            diagnostics=diagnostics,
        )

    @staticmethod
    def _candidate_base_score(
        candidate: object,
        *,
        previous_rank: int,
    ) -> tuple[float, str]:
        diagnostics = getattr(candidate, "diagnostics", {})
        if isinstance(diagnostics, dict):
            for field_name in ("fusion_score", "ranking_score"):
                value = diagnostics.get(field_name)
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                ):
                    return float(value), field_name
        value = getattr(candidate, "score", None)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        ):
            return float(value), "candidate_score"
        return 1.0 / previous_rank, "reciprocal_pre_rerank_rank"

    @staticmethod
    def _constraint_keys(items: object) -> set[tuple[str, str]]:
        if not isinstance(items, list):
            return set()
        keys = {
            (
                str(item.get("attribute") or "").strip().lower(),
                str(item.get("value") or item.get("normalized_value") or "")
                .strip()
                .lower(),
            )
            for item in items
            if isinstance(item, dict)
        }
        return {key for key in keys if key[0] and key[1]}

    def _constraint_guard_status(
        self,
        candidate: object,
        request: RetrievalRequest,
    ) -> str:
        if not self.config.constraint_guard_enabled:
            return "neutral"
        active_keys = {
            (
                str(item.get("attribute") or "").strip().lower(),
                str(item.get("normalized_value") or item.get("raw_value") or "")
                .strip()
                .lower(),
            )
            for item in request.active_constraints
            if item.get("active", True)
            and item.get("hard")
            and float(item.get("confidence") or 0.0)
            >= self.config.minimum_constraint_confidence
        }
        rejected_keys = {
            (
                str(item.get("attribute") or "").strip().lower(),
                str(item.get("normalized_value") or item.get("raw_value") or "")
                .strip()
                .lower(),
            )
            for item in request.rejected_constraints
            if item.get("active", True)
            and float(item.get("confidence") or 0.0)
            >= self.config.minimum_constraint_confidence
        }
        diagnostics = getattr(candidate, "diagnostics", {})
        if not isinstance(diagnostics, dict):
            return "neutral"
        rejected_matches = self._constraint_keys(
            diagnostics.get("rejected_constraint_matches")
        )
        if rejected_keys & rejected_matches:
            return "contradicted"
        structured_matches = self._constraint_keys(diagnostics.get("structured_matches"))
        if active_keys & structured_matches:
            return "matched"
        return "neutral"

    def close(self) -> None:
        close_backend = getattr(self._backend, "close", None)
        if callable(close_backend):
            close_backend()
        close_base = getattr(self._base, "close", None)
        if callable(close_base):
            close_base()

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
        route_semantics_reported = bool(
            base.diagnostics.requested_route_weights
            and base.diagnostics.executed_routes
        )
        fallback_route = None
        if route_semantics_reported:
            fallback_route = base.diagnostics.fallback_route
            if fallback_route is None:
                fallback_route = (
                    base.diagnostics.route
                    if base.diagnostics.route in base.diagnostics.executed_routes
                    else base.diagnostics.executed_routes[-1]
                )
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
            fallback_route=fallback_route,
        )
        return RetrievalResult(candidates=base.candidates, diagnostics=diagnostics)

    def configuration_snapshot(self) -> dict:
        return {
            "candidate_limit": self.config.candidate_limit,
            "anchor_count": self.config.anchor_count,
            "tail_start_rank": self.config.anchor_count + 1,
            "base_score_weight": self.config.base_score_weight,
            "semantic_rank_weight": 1.0 - self.config.base_score_weight,
            "constraint_guard_enabled": self.config.constraint_guard_enabled,
            "minimum_constraint_confidence": (
                self.config.minimum_constraint_confidence
            ),
            "model_id": self.config.model_id,
            "model_revision": self.config.model_revision,
            "model_cache_dir": str(self.config.model_cache_dir),
            "batch_size": self.config.batch_size,
            "max_length": self.config.max_length,
            "timeout_ms": self.config.timeout_ms,
            "runtime_network_access": False,
            "failure_fallback": "exact_pre_rerank_candidate_order",
        }
