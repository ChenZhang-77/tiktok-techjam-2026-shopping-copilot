from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from starter.contracts import (
    Candidate,
    RetrievalRequest,
    RetrievalResult,
    validate_retrieval_request_object,
)

if TYPE_CHECKING:
    from starter.retrieval.dense import DenseConfig


class Retriever(Protocol):
    catalog_ids: frozenset[str]
    fallback_ids: tuple[str, ...]

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        ...


@dataclass(frozen=True)
class ConditionalDenseConfig:
    max_active_constraints: int = 1
    min_base_candidates: int = 30
    rrf_k: float = 60.0
    max_accepted_dense_latency_ms: float = 250.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_active_constraints, bool)
            or not isinstance(self.max_active_constraints, int)
            or self.max_active_constraints < 0
        ):
            raise ValueError("max_active_constraints must be a non-negative integer")
        if (
            isinstance(self.min_base_candidates, bool)
            or not isinstance(self.min_base_candidates, int)
            or self.min_base_candidates < 1
        ):
            raise ValueError("min_base_candidates must be a positive integer")
        for name, value in (
            ("rrf_k", self.rrf_k),
            (
                "max_accepted_dense_latency_ms",
                self.max_accepted_dense_latency_ms,
            ),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a finite positive number")


@dataclass
class _FusionEntry:
    score: float
    first_seen: int
    evidence_text: str | None
    route_ranks: dict[str, int]
    route_scores: dict[str, float]


class ConditionalDenseRetriever:
    """Execute dense only for broad Browsing and preserve exact base fallback."""

    def __init__(
        self,
        base_retriever: Retriever,
        dense_retriever: Retriever,
        *,
        config: ConditionalDenseConfig | None = None,
    ) -> None:
        if base_retriever.catalog_ids != dense_retriever.catalog_ids:
            raise ValueError("base and dense retrievers must share one catalog")
        self._base = base_retriever
        self._dense = dense_retriever
        self.config = config if config is not None else ConditionalDenseConfig()
        self.catalog_ids = base_retriever.catalog_ids
        self.fallback_ids = base_retriever.fallback_ids

    @classmethod
    def from_catalog(
        cls,
        catalog_path: str | Path = "data/catalog.jsonl",
        *,
        config: ConditionalDenseConfig | None = None,
        dense_config: DenseConfig | None = None,
    ) -> ConditionalDenseRetriever:
        from starter.retrieval.dense import DenseConfig, DenseRetriever
        from starter.retrieval.hybrid import HybridRetriever

        if dense_config is not None and not isinstance(dense_config, DenseConfig):
            raise TypeError("dense_config must be a DenseConfig")
        base = HybridRetriever(catalog_path)
        dense = DenseRetriever(
            catalog_path,
            config=dense_config,
            lexical_fallback=base,
        )
        return cls(base, dense, config=config)

    def _gate_reason(
        self,
        request: RetrievalRequest,
        base: RetrievalResult,
    ) -> str | None:
        if request.intent != "browsing":
            return "intent_not_browsing"
        if request.strategy.semantic_weight <= 0:
            return "dense_not_requested"
        active_count = sum(
            1
            for constraint in request.active_constraints
            if constraint.get("active", True)
            and str(constraint.get("attribute") or "")
            not in request.no_preference_attributes
        )
        if active_count > self.config.max_active_constraints:
            return "too_many_active_constraints"
        if len(base.candidates) < max(
            request.top_k,
            self.config.min_base_candidates,
        ):
            return "base_pool_too_small"
        return None

    @staticmethod
    def _unique_routes(routes: list[str]) -> list[str]:
        return list(dict.fromkeys(routes))

    def _base_fallback(
        self,
        base: RetrievalResult,
        *,
        reason: str,
        dense: RetrievalResult | None = None,
    ) -> RetrievalResult:
        route_semantics_reported = bool(
            base.diagnostics.requested_route_weights
            and base.diagnostics.executed_routes
        )
        dense_executed = bool(
            dense is not None and "dense" in dense.diagnostics.executed_routes
        )
        dense_latency = (
            float(dense.diagnostics.latency_ms or 0.0) if dense is not None else 0.0
        )
        route_failures = dict(base.diagnostics.route_failures)
        if dense is not None:
            route_failures.update(dense.diagnostics.route_failures)
        route_failures["dense"] = reason
        diagnostics = replace(
            base.diagnostics,
            fallback_used=True,
            fallback_route=(
                base.diagnostics.route if route_semantics_reported else None
            ),
            latency_ms=round(float(base.diagnostics.latency_ms or 0.0) + dense_latency, 6),
            notes=[
                *base.diagnostics.notes,
                "conditional_dense_gate:broad_browsing",
                f"conditional_dense_fallback:{reason}",
            ],
            stage_latencies_ms={
                **base.diagnostics.stage_latencies_ms,
                **(
                    {"dense": round(dense_latency, 6)}
                    if dense is not None
                    else {}
                ),
            },
            route_failures=route_failures,
            cache_state={
                **base.diagnostics.cache_state,
                **(dense.diagnostics.cache_state if dense is not None else {}),
            },
            executed_routes=(
                self._unique_routes(
                    [
                        *base.diagnostics.executed_routes,
                        *(["dense"] if dense_executed else []),
                    ]
                )
                if route_semantics_reported
                else []
            ),
        )
        return RetrievalResult(candidates=base.candidates, diagnostics=diagnostics)

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        validate_retrieval_request_object(request)
        base = self._base.retrieve(request)
        gate_reason = self._gate_reason(request, base)
        if gate_reason is not None:
            return RetrievalResult(
                candidates=base.candidates,
                diagnostics=replace(
                    base.diagnostics,
                    notes=[
                        *base.diagnostics.notes,
                        f"conditional_dense_gate_skipped:{gate_reason}",
                    ],
                ),
            )

        try:
            dense = self._dense.retrieve(request)
        except Exception:
            return self._base_fallback(base, reason="dense_route_error")
        if dense.diagnostics.fallback_used or dense.diagnostics.route != "dense":
            reason = dense.diagnostics.route_failures.get(
                "dense",
                "dense_route_degraded",
            )
            return self._base_fallback(base, reason=reason, dense=dense)
        if (
            float(dense.diagnostics.latency_ms or 0.0)
            > self.config.max_accepted_dense_latency_ms
        ):
            return self._base_fallback(
                base,
                reason="dense_latency_budget_exceeded",
                dense=dense,
            )
        return self._fuse(request, base, dense)

    def _fuse(
        self,
        request: RetrievalRequest,
        base: RetrievalResult,
        dense: RetrievalResult,
    ) -> RetrievalResult:
        started = time.perf_counter()
        route_semantics_reported = bool(
            base.diagnostics.requested_route_weights
            and base.diagnostics.executed_routes
        )
        weights = {
            "structured": (
                request.strategy.lexical_weight
                + request.strategy.structured_weight
            ),
            "dense": request.strategy.semantic_weight,
        }
        route_results = {"structured": base, "dense": dense}
        fused: dict[str, _FusionEntry] = {}
        route_ids: dict[str, set[str]] = {}
        next_seen = 0
        for route in ("structured", "dense"):
            seen: set[str] = set()
            for rank, candidate in enumerate(route_results[route].candidates, start=1):
                parent_asin = candidate.parent_asin
                if parent_asin not in self.catalog_ids or parent_asin in seen:
                    continue
                seen.add(parent_asin)
                if parent_asin not in fused:
                    fused[parent_asin] = _FusionEntry(
                        score=0.0,
                        first_seen=next_seen,
                        evidence_text=candidate.evidence_text,
                        route_ranks={},
                        route_scores={},
                    )
                    next_seen += 1
                entry = fused[parent_asin]
                entry.score += weights[route] / (self.config.rrf_k + rank)
                entry.route_ranks[route] = rank
                if candidate.score is not None:
                    entry.route_scores[route] = candidate.score
                if not entry.evidence_text and candidate.evidence_text:
                    entry.evidence_text = candidate.evidence_text
            route_ids[route] = seen
        overlap_counts = dict(base.diagnostics.route_overlap_counts)
        overlap_counts.update(
            {
                f"{left}|{right}": len(route_ids[left] & route_ids[right])
                for left, right in combinations(route_ids, 2)
            }
        )
        ordered = sorted(
            fused.items(),
            key=lambda item: (-item[1].score, item[1].first_seen, item[0]),
        )
        candidates = [
            Candidate(
                parent_asin=parent_asin,
                score=round(entry.score, 8),
                source="fusion",
                evidence_text=entry.evidence_text,
                diagnostics={
                    "route_ranks": dict(entry.route_ranks),
                    "route_scores": dict(entry.route_scores),
                    "fusion_rank": rank,
                    "fusion_score": round(entry.score, 8),
                    "conditional_dense_gate": "broad_browsing",
                },
            )
            for rank, (parent_asin, entry) in enumerate(ordered, start=1)
        ]
        fusion_latency = (time.perf_counter() - started) * 1000.0
        diagnostics = replace(
            base.diagnostics,
            route="fusion",
            candidate_count=len(candidates),
            fallback_used=False,
            fallback_route=None,
            latency_ms=round(
                float(base.diagnostics.latency_ms or 0.0)
                + float(dense.diagnostics.latency_ms or 0.0)
                + fusion_latency,
                6,
            ),
            notes=[
                *base.diagnostics.notes,
                "conditional_dense_gate:broad_browsing",
                "conditional_dense_fusion_applied",
            ],
            stage_latencies_ms={
                **base.diagnostics.stage_latencies_ms,
                "dense": round(float(dense.diagnostics.latency_ms or 0.0), 6),
                "fusion": round(fusion_latency, 6),
            },
            route_candidate_counts={
                **base.diagnostics.route_candidate_counts,
                "dense": len(route_ids["dense"]),
                "fusion": len(candidates),
            },
            route_overlap_counts=overlap_counts,
            route_failures={
                **base.diagnostics.route_failures,
                **dense.diagnostics.route_failures,
            },
            cache_state={
                **base.diagnostics.cache_state,
                **dense.diagnostics.cache_state,
            },
            ranking_pool_sizes={
                **base.diagnostics.ranking_pool_sizes,
                "dense": len(route_ids["dense"]),
                "conditional_dense_fusion": len(candidates),
            },
            executed_routes=(
                self._unique_routes(
                    [*base.diagnostics.executed_routes, "dense", "fusion"]
                )
                if route_semantics_reported
                else []
            ),
        )
        return RetrievalResult(candidates=candidates, diagnostics=diagnostics)

    def configuration_snapshot(self) -> dict[str, object]:
        return {
            "gate": "browsing_with_sparse_active_constraints",
            "max_active_constraints": self.config.max_active_constraints,
            "min_base_candidates": self.config.min_base_candidates,
            "rrf_k": self.config.rrf_k,
            "max_accepted_dense_latency_ms": (
                self.config.max_accepted_dense_latency_ms
            ),
            "latency_budget_kind": "post_execution_acceptance_budget",
        }

    def dense_configuration(self) -> dict[str, object]:
        snapshot = getattr(self._dense, "configuration_snapshot", None)
        if not callable(snapshot):
            raise RuntimeError("dense retriever does not expose its configuration")
        return dict(snapshot())

    def close(self) -> None:
        close_base = getattr(self._base, "close", None)
        if callable(close_base):
            close_base()
