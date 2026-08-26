from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Mapping
from pathlib import Path

from starter.contracts import (
    Candidate,
    RetrievalDiagnostics,
    RetrievalRequest,
    RetrievalResult,
    validate_retrieval_request_object,
)
from starter.core.ranking import RankingScore, rank_candidates
from starter.retrieval.structured import (
    EVIDENCE_FIELDS,
    ProductEvidence,
    StructuredConfig,
    StructuredOutcome,
    apply_guarded_filters,
    structured_matches,
)


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "i", "in", "is", "it", "me", "my", "of", "on", "or", "please", "some",
    "that", "the", "this", "to", "want", "with", "would", "you", "looking",
}
BM25_FIELD_WEIGHTS = (0.0, 6.0, 4.0, 2.5, 2.5, 1.5, 1.0)
BM25_EXPRESSION = f"bm25(products, {', '.join(str(weight) for weight in BM25_FIELD_WEIGHTS)})"


def _terms(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(text)
        if len(token) > 1 and token.lower() not in STOPWORDS
    ]


class HybridRetriever:
    """Deterministic lexical retrieval seam that preserves the A-side ordering."""

    def __init__(
        self,
        catalog_path: str | Path = "data/catalog.jsonl",
        structured_config: StructuredConfig | None = None,
        constraint_rerank_enabled: bool = True,
    ) -> None:
        started = time.perf_counter()
        self.catalog_path = Path(catalog_path)
        self._connection = sqlite3.connect(":memory:")
        self._catalog_ids: set[str] = set()
        self._fallback_ids: list[str] = []
        self._product_texts: dict[str, str] = {}
        self._structured_evidence: dict[str, ProductEvidence] = {}
        self.structured_config = (
            structured_config if structured_config is not None else StructuredConfig()
        )
        self.constraint_rerank_enabled = constraint_rerank_enabled
        try:
            self._build_index()
        except Exception:
            self._connection.close()
            raise
        self._frozen_catalog_ids = frozenset(self._catalog_ids)
        self.initialization_ms = round((time.perf_counter() - started) * 1000.0, 6)

    @property
    def catalog_ids(self) -> frozenset[str]:
        return self._frozen_catalog_ids

    @property
    def catalog_size(self) -> int:
        return len(self._catalog_ids)

    @property
    def fallback_ids(self) -> tuple[str, ...]:
        return tuple(self._fallback_ids)

    def evidence_text(self, parent_asin: str) -> str:
        return self._product_texts.get(parent_asin, "")

    def close(self) -> None:
        self._connection.close()

    def _build_index(self) -> None:
        cursor = self._connection.cursor()
        cursor.execute(
            "CREATE VIRTUAL TABLE products USING fts5("
            "parent_asin UNINDEXED, title, categories, features, details, store, description, "
            "tokenize='unicode61 remove_diacritics 2')"
        )
        batch: list[tuple[str, str, str, str, str, str, str]] = []
        with self.catalog_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                product = json.loads(line)
                parent_asin = str(product.get("parent_asin") or "").strip()
                if not parent_asin:
                    raise ValueError(f"Missing parent_asin at catalog line {line_number}")
                if parent_asin in self._catalog_ids:
                    raise ValueError(f"Duplicate parent_asin in catalog: {parent_asin}")

                self._catalog_ids.add(parent_asin)
                self._fallback_ids.append(parent_asin)
                product_evidence = ProductEvidence.from_product(product)
                self._structured_evidence[parent_asin] = product_evidence
                field_values = tuple(product_evidence.fields[field] for field in EVIDENCE_FIELDS)
                self._product_texts[parent_asin] = product_evidence.combined_text
                batch.append((parent_asin, *field_values))
                if len(batch) >= 1000:
                    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
                    batch.clear()
        if batch:
            cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
        self._connection.commit()

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        return self.retrieve_routes(request)["structured"]

    def retrieve_routes(self, request: RetrievalRequest) -> dict[str, RetrievalResult]:
        validate_retrieval_request_object(request)
        started = time.perf_counter()
        unique_terms = list(dict.fromkeys(_terms(request.query)))[:40]
        expression = " OR ".join(f'"{term}"' for term in unique_terms)
        if not expression:
            empty_timings = {
                "lexical": 0.0,
                "constraint_rerank": 0.0,
                "structured_filter": 0.0,
            }
            return {
                "lexical": self._result(
                    [],
                    [],
                    request,
                    started,
                    StructuredOutcome([]),
                    source="lexical",
                    route="lexical",
                    constraint_reranked=False,
                    stage_latencies_ms=empty_timings,
                ),
                "structured": self._result(
                    [],
                    [],
                    request,
                    started,
                    StructuredOutcome([]),
                    source="structured",
                    route="structured",
                    constraint_reranked=False,
                    stage_latencies_ms=empty_timings,
                ),
            }

        lexical_started = time.perf_counter()
        rows = self._connection.execute(
            "SELECT parent_asin FROM products WHERE products MATCH ? "
            f"ORDER BY {BM25_EXPRESSION}, rowid ASC LIMIT ?",
            (expression, request.strategy.retrieval_depth),
        ).fetchall()
        lexical_latency_ms = (time.perf_counter() - lexical_started) * 1000.0
        lexical_ids = [str(row[0]) for row in rows]
        lexical_result = self._result(
            lexical_ids,
            lexical_ids,
            request,
            started,
            StructuredOutcome(lexical_ids),
            source="lexical",
            route="lexical",
            constraint_reranked=False,
            stage_latencies_ms={
                "lexical": lexical_latency_ms,
                "constraint_rerank": 0.0,
                "structured_filter": 0.0,
            },
        )
        rerank_started = time.perf_counter()
        if self.constraint_rerank_enabled:
            ranking_scores = rank_candidates(
                lexical_ids,
                product_texts=self._product_texts,
                active_constraints=request.active_constraints,
                lexical_weight=request.strategy.lexical_weight,
                structured_weight=request.strategy.structured_weight,
            )
            ranked_ids = [item.parent_asin for item in ranking_scores]
        else:
            ranked_ids = list(lexical_ids)
            ranking_scores = rank_candidates(
                lexical_ids,
                product_texts=self._product_texts,
                active_constraints=[],
                lexical_weight=1.0,
                structured_weight=0.0,
            )
        constraint_rerank_latency_ms = (time.perf_counter() - rerank_started) * 1000.0
        constraint_reranked = ranked_ids != lexical_ids
        structured_outcome = StructuredOutcome(ranked_ids)
        structured_filter_started = time.perf_counter()
        if request.strategy.allow_hard_filter:
            structured_outcome = apply_guarded_filters(
                ranked_ids,
                evidence_by_id=self._structured_evidence,
                constraints=request.active_constraints,
                top_k=request.top_k,
                config=self.structured_config,
            )
        structured_filter_latency_ms = (
            time.perf_counter() - structured_filter_started
        ) * 1000.0
        return {
            "lexical": lexical_result,
            "structured": self._result(
                lexical_ids,
                structured_outcome.ordered_ids,
                request,
                started,
                structured_outcome,
                source="structured",
                route="structured",
                constraint_reranked=constraint_reranked,
                ranking_scores={item.parent_asin: item for item in ranking_scores},
                stage_latencies_ms={
                    "lexical": lexical_latency_ms,
                    "constraint_rerank": constraint_rerank_latency_ms,
                    "structured_filter": structured_filter_latency_ms,
                },
            ),
        }

    def _result(
        self,
        lexical_ids: list[str],
        ranked_ids: list[str],
        request: RetrievalRequest,
        started: float,
        structured_outcome: StructuredOutcome,
        *,
        source: str,
        route: str,
        constraint_reranked: bool,
        ranking_scores: Mapping[str, RankingScore] | None = None,
        stage_latencies_ms: dict[str, float],
    ) -> RetrievalResult:
        lexical_ranks = {parent_asin: rank for rank, parent_asin in enumerate(lexical_ids, start=1)}
        route_candidate_counts = {"lexical": len(lexical_ids)}
        route_overlap_counts: dict[str, int] = {}
        if route == "structured":
            route_candidate_counts["structured"] = len(ranked_ids)
            route_overlap_counts["lexical|structured"] = len(
                set(lexical_ids) & set(ranked_ids)
            )
        filtered_pool_size = len(ranked_ids)
        if structured_outcome.filter_applied:
            filtered_pool_size = next(
                (
                    int(step["after"])
                    for step in reversed(structured_outcome.pool_sizes)
                    if isinstance(step.get("after"), int)
                ),
                len(ranked_ids),
            )
        ranking_scores = ranking_scores or {}
        score_by_id = {
            parent_asin: ranking_scores.get(parent_asin)
            or RankingScore(
                parent_asin=parent_asin,
                lexical_rank=lexical_ranks[parent_asin],
                lexical_score=1.0 / lexical_ranks[parent_asin],
                constraint_score=0.0,
                ranking_score=1.0 / lexical_ranks[parent_asin],
            )
            for parent_asin in ranked_ids
        }
        candidates = [
            Candidate(
                parent_asin=parent_asin,
                source=source,
                evidence_text=self._product_texts[parent_asin],
                diagnostics={
                    "lexical_rank": lexical_ranks[parent_asin],
                    "final_rank": rank,
                    "constraint_reranked": constraint_reranked,
                    "lexical_score": round(score_by_id[parent_asin].lexical_score, 8),
                    "constraint_score": round(score_by_id[parent_asin].constraint_score, 8),
                    "ranking_score": round(score_by_id[parent_asin].ranking_score, 8),
                    "structured_matches": structured_matches(
                        self._structured_evidence[parent_asin],
                        request.active_constraints,
                    ),
                },
            )
            for rank, parent_asin in enumerate(ranked_ids, start=1)
        ]
        notes = ["constraint_rerank_applied"] if constraint_reranked else []
        if structured_outcome.filter_applied:
            notes.append("guarded_structured_filter_applied")
        if structured_outcome.relaxed_constraints:
            notes.append("structured_filter_relaxed")
        return RetrievalResult(
            candidates=candidates,
            diagnostics=RetrievalDiagnostics(
                route=route,
                candidate_count=len(candidates),
                fallback_used=False,
                latency_ms=round((time.perf_counter() - started) * 1000.0, 6),
                notes=notes,
                structured_filter_applied=structured_outcome.filter_applied,
                relaxed_constraints=structured_outcome.relaxed_constraints,
                filtered_pool_sizes=structured_outcome.pool_sizes,
                stage_latencies_ms={
                    name: round(value, 6) for name, value in stage_latencies_ms.items()
                },
                route_candidate_counts=route_candidate_counts,
                route_overlap_counts=route_overlap_counts,
                cache_state={
                    "lexical_index": "memory_ready",
                    "structured_evidence": "memory_ready",
                },
                ranking_pool_sizes={
                    "pre_constraint_rerank": len(lexical_ids),
                    "post_constraint_rerank": len(lexical_ids),
                    "post_structured_filter": filtered_pool_size,
                },
            ),
        )
