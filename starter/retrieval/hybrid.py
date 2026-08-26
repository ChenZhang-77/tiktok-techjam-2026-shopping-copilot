from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from pathlib import Path

from starter.contracts import (
    Candidate,
    RetrievalDiagnostics,
    RetrievalRequest,
    RetrievalResult,
    validate_retrieval_request,
)
from starter.core.planner import Strategy
from starter.core.ranking import rerank_candidates
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
MAX_RETRIEVAL_DEPTH = 500


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
        self._validate_request(request)
        started = time.perf_counter()
        unique_terms = list(dict.fromkeys(_terms(request.query)))[:40]
        expression = " OR ".join(f'"{term}"' for term in unique_terms)
        if not expression:
            return self._result(
                [],
                [],
                request,
                started,
                StructuredOutcome([]),
                constraint_reranked=False,
                lexical_latency_ms=0.0,
                constraint_rerank_latency_ms=0.0,
                structured_filter_latency_ms=0.0,
            )

        lexical_started = time.perf_counter()
        rows = self._connection.execute(
            "SELECT parent_asin FROM products WHERE products MATCH ? "
            f"ORDER BY {BM25_EXPRESSION}, rowid ASC LIMIT ?",
            (expression, request.strategy.retrieval_depth),
        ).fetchall()
        lexical_latency_ms = (time.perf_counter() - lexical_started) * 1000.0
        lexical_ids = [str(row[0]) for row in rows]
        rerank_started = time.perf_counter()
        if self.constraint_rerank_enabled:
            ranked_ids = rerank_candidates(
                lexical_ids,
                product_texts=self._product_texts,
                active_constraints=request.active_constraints,
                lexical_weight=request.strategy.lexical_weight,
                structured_weight=request.strategy.structured_weight,
            )
        else:
            ranked_ids = list(lexical_ids)
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
        return self._result(
            lexical_ids,
            structured_outcome.ordered_ids,
            request,
            started,
            structured_outcome,
            constraint_reranked=constraint_reranked,
            lexical_latency_ms=lexical_latency_ms,
            constraint_rerank_latency_ms=constraint_rerank_latency_ms,
            structured_filter_latency_ms=structured_filter_latency_ms,
        )

    def _result(
        self,
        lexical_ids: list[str],
        ranked_ids: list[str],
        request: RetrievalRequest,
        started: float,
        structured_outcome: StructuredOutcome,
        *,
        constraint_reranked: bool,
        lexical_latency_ms: float,
        constraint_rerank_latency_ms: float,
        structured_filter_latency_ms: float,
    ) -> RetrievalResult:
        lexical_ranks = {parent_asin: rank for rank, parent_asin in enumerate(lexical_ids, start=1)}
        candidates = [
            Candidate(
                parent_asin=parent_asin,
                source="bm25",
                evidence_text=self._product_texts[parent_asin],
                diagnostics={
                    "lexical_rank": lexical_ranks[parent_asin],
                    "final_rank": rank,
                    "constraint_reranked": constraint_reranked,
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
                route="bm25",
                candidate_count=len(candidates),
                fallback_used=False,
                latency_ms=round((time.perf_counter() - started) * 1000.0, 6),
                lexical_latency_ms=round(lexical_latency_ms, 6),
                constraint_rerank_latency_ms=round(constraint_rerank_latency_ms, 6),
                structured_filter_latency_ms=round(structured_filter_latency_ms, 6),
                notes=notes,
                structured_filter_applied=structured_outcome.filter_applied,
                relaxed_constraints=structured_outcome.relaxed_constraints,
                filtered_pool_sizes=structured_outcome.pool_sizes,
            ),
        )

    @staticmethod
    def _validate_request(request: RetrievalRequest) -> None:
        if not isinstance(request, RetrievalRequest):
            raise TypeError("request must be a RetrievalRequest")
        if not isinstance(request.session_id, str) or not request.session_id:
            raise ValueError("session_id must be a non-empty string")
        if isinstance(request.turn, bool) or not isinstance(request.turn, int) or not 1 <= request.turn <= 10:
            raise ValueError("turn must be an integer from 1 to 10")
        if isinstance(request.top_k, bool) or not isinstance(request.top_k, int) or not 1 <= request.top_k <= 100:
            raise ValueError("top_k must be an integer from 1 to 100")
        if not isinstance(request.query, str):
            raise ValueError("query must be a string")
        if request.intent not in {"buying", "browsing"}:
            raise ValueError("intent must be buying or browsing")
        if not isinstance(request.strategy, Strategy):
            raise ValueError("strategy must be a Strategy")
        if request.strategy.intent != request.intent:
            raise ValueError("strategy intent must match request intent")
        if (
            isinstance(request.strategy.retrieval_depth, bool)
            or not isinstance(request.strategy.retrieval_depth, int)
            or not 1 <= request.strategy.retrieval_depth <= MAX_RETRIEVAL_DEPTH
        ):
            raise ValueError(
                f"strategy retrieval_depth must be an integer from 1 to {MAX_RETRIEVAL_DEPTH}"
            )
        for value in (
            request.strategy.lexical_weight,
            request.strategy.structured_weight,
            request.strategy.semantic_weight,
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError("strategy weights must be finite non-negative numbers")
        if not isinstance(request.active_constraints, list) or not all(
            isinstance(item, dict) for item in request.active_constraints
        ):
            raise ValueError("active_constraints must be a list of objects")
        for field_name, values in (
            ("no_preference_attributes", request.no_preference_attributes),
            ("asked_attributes", request.asked_attributes),
        ):
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise ValueError(f"{field_name} must be a list of strings")
        if not isinstance(request.rejected_constraints, list) or not all(
            isinstance(item, dict) for item in request.rejected_constraints
        ):
            raise ValueError("rejected_constraints must be a list of objects")
        validate_retrieval_request(request.to_dict())
