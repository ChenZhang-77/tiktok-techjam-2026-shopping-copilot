from __future__ import annotations

import math
import time
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Protocol

from starter.contracts import (
    Candidate,
    RetrievalDiagnostics,
    RetrievalRequest,
    RetrievalResult,
    validate_retrieval_request_object,
)
from starter.retrieval.dense import DenseConfig, DenseRetriever
from starter.retrieval.hybrid import HybridRetriever


ROUTE_ORDER = ("lexical", "structured", "dense")


@dataclass(frozen=True)
class FusionConfig:
    rrf_k: float = 60.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.rrf_k, bool)
            or not isinstance(self.rrf_k, (int, float))
            or not math.isfinite(self.rrf_k)
            or self.rrf_k <= 0
        ):
            raise ValueError("rrf_k must be a finite positive number")


@dataclass(frozen=True)
class RouteBatch:
    results: dict[str, RetrievalResult]
    failures: dict[str, str]


@dataclass
class _FusionEntry:
    score: float
    first_seen: int
    evidence_text: str | None
    route_ranks: dict[str, int]
    route_scores: dict[str, float]


class RouteProvider(Protocol):
    catalog_ids: frozenset[str]
    fallback_ids: tuple[str, ...]

    def retrieve_routes(
        self,
        request: RetrievalRequest,
        routes: tuple[str, ...],
    ) -> RouteBatch:
        ...


class LocalRouteProvider:
    """Run local Routes while sharing one catalog/index owner."""

    def __init__(
        self,
        catalog_path: str | Path = "data/catalog.jsonl",
        *,
        dense_config: DenseConfig | None = None,
    ) -> None:
        self._hybrid = HybridRetriever(catalog_path)
        self._dense = DenseRetriever(
            catalog_path,
            config=dense_config,
            lexical_fallback=self._hybrid,
        )
        self.catalog_ids = self._hybrid.catalog_ids
        self.fallback_ids = self._hybrid.fallback_ids

    def retrieve_routes(
        self,
        request: RetrievalRequest,
        routes: tuple[str, ...],
    ) -> RouteBatch:
        results: dict[str, RetrievalResult] = {}
        failures: dict[str, str] = {}
        hybrid_routes = tuple(route for route in routes if route in {"lexical", "structured"})
        if hybrid_routes:
            try:
                available = self._hybrid.retrieve_routes(request)
                results.update({route: available[route] for route in hybrid_routes})
            except Exception:
                failures.update({route: "hybrid_route_error" for route in hybrid_routes})
        if "dense" in routes:
            try:
                dense = self._dense.retrieve(request)
            except Exception:
                failures["dense"] = "dense_route_error"
            else:
                if dense.diagnostics.route == "dense" and not dense.diagnostics.fallback_used:
                    results["dense"] = dense
                else:
                    failures["dense"] = next(
                        (
                            note
                            for note in reversed(dense.diagnostics.notes)
                            if note.startswith("dense_")
                        ),
                        "dense_route_degraded",
                    )
        return RouteBatch(results=results, failures=failures)


class FusionRetriever:
    """Fuse independent Route rankings behind the shared retrieval seam."""

    def __init__(
        self,
        route_provider: RouteProvider,
        *,
        config: FusionConfig | None = None,
    ) -> None:
        self._route_provider = route_provider
        self.config = config if config is not None else FusionConfig()
        self.catalog_ids = route_provider.catalog_ids
        self.fallback_ids = route_provider.fallback_ids

    @classmethod
    def from_catalog(
        cls,
        catalog_path: str | Path = "data/catalog.jsonl",
        *,
        config: FusionConfig | None = None,
        dense_config: DenseConfig | None = None,
    ) -> FusionRetriever:
        return cls(
            LocalRouteProvider(catalog_path, dense_config=dense_config),
            config=config,
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        validate_retrieval_request_object(request)
        started = time.perf_counter()
        weights = {
            "lexical": request.strategy.lexical_weight,
            "structured": request.strategy.structured_weight,
            "dense": request.strategy.semantic_weight,
        }
        active_routes = tuple(route for route in ROUTE_ORDER if weights[route] > 0)
        batch = self._route_provider.retrieve_routes(request, active_routes)
        fusion_started = time.perf_counter()
        failures = dict(batch.failures)
        for route in active_routes:
            if route not in batch.results and route not in failures:
                failures[route] = "route_unavailable"

        fused: dict[str, _FusionEntry] = {}
        route_ids: dict[str, set[str]] = {}
        next_seen = 0
        for route in active_routes:
            result = batch.results.get(route)
            if result is None:
                continue
            seen_on_route: set[str] = set()
            for rank, candidate in enumerate(result.candidates, start=1):
                parent_asin = candidate.parent_asin
                if parent_asin not in self.catalog_ids or parent_asin in seen_on_route:
                    continue
                seen_on_route.add(parent_asin)
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
            route_ids[route] = seen_on_route

        overlap_counts = {
            f"{left}|{right}": len(route_ids[left] & route_ids[right])
            for left, right in combinations(route_ids, 2)
        }

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
                },
            )
            for rank, (parent_asin, entry) in enumerate(ordered, start=1)
        ]
        catalog_fallback_used = not candidates and bool(failures)
        if catalog_fallback_used:
            candidates = [
                Candidate(
                    parent_asin=parent_asin,
                    source="catalog_fallback",
                    diagnostics={"fusion_rank": rank},
                )
                for rank, parent_asin in enumerate(
                    self.fallback_ids[: request.strategy.retrieval_depth],
                    start=1,
                )
            ]
        completed = time.perf_counter()
        total_latency_ms = (completed - started) * 1000.0
        fusion_latency_ms = (completed - fusion_started) * 1000.0
        stage_latencies_ms = {
            f"{route}_route": result.diagnostics.latency_ms
            for route, result in batch.results.items()
            if route in active_routes
        }
        stage_latencies_ms["fusion"] = round(fusion_latency_ms, 6)
        return RetrievalResult(
            candidates=candidates,
            diagnostics=RetrievalDiagnostics(
                route="fusion",
                candidate_count=len(candidates),
                fallback_used=bool(failures),
                latency_ms=round(total_latency_ms, 6),
                notes=[
                    f"route_failed:{route}:{reason}"
                    for route, reason in failures.items()
                ] + (["all_routes_failed_catalog_fallback"] if catalog_fallback_used else []),
                stage_latencies_ms=stage_latencies_ms,
                route_candidate_counts={
                    route: len(ids) for route, ids in route_ids.items()
                },
                route_overlap_counts=overlap_counts,
                route_failures=failures,
            ),
        )
