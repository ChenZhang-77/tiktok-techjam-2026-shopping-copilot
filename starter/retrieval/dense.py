from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from starter.contracts import Candidate, RetrievalDiagnostics, RetrievalRequest, RetrievalResult
from starter.retrieval.hybrid import HybridRetriever
from starter.retrieval.structured import EVIDENCE_FIELDS, evidence_text


MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
CACHE_SCHEMA_VERSION = 1
EMBEDDING_DIMENSION = 384
EMBEDDING_DTYPE = "float32"
PRODUCT_TEXT_TEMPLATE = "product-fields-v1"
QUERY_TEXT_TEMPLATE = "distilled-query-v1"


def product_text(product: Mapping[str, object]) -> str:
    return "\n".join(
        f"{field}: {evidence_text(product.get(field))}" for field in EVIDENCE_FIELDS
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class DenseConfig:
    cache_dir: Path = Path("embeddings/minilm-l6-v2-v1")
    model_id: str = MODEL_ID
    model_revision: str = MODEL_REVISION
    dimension: int = EMBEDDING_DIMENSION
    dtype: str = EMBEDDING_DTYPE
    normalized: bool = True
    model_cache_dir: Path = Path("models/huggingface/hub")


class DenseBackend(Protocol):
    def rank(self, query: str, top_n: int) -> list[tuple[int, float]]:
        ...


class NumpySentenceBackend:
    def __init__(self, config: DenseConfig, ids: Sequence[str]) -> None:
        import numpy as np

        self._np = np
        self._config = config
        self._vectors = np.load(config.cache_dir / "vectors.npy", mmap_mode="r")
        if self._vectors.shape != (len(ids), config.dimension):
            raise ValueError("dense vector shape is incompatible")
        if str(self._vectors.dtype) != config.dtype:
            raise ValueError("dense vector dtype is incompatible")
        self._model = None

    def _load_model(self) -> object:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self._config.model_id,
                revision=self._config.model_revision,
                cache_folder=str(self._config.model_cache_dir),
                local_files_only=True,
            )
        return self._model

    def rank(self, query: str, top_n: int) -> list[tuple[int, float]]:
        model = self._load_model()
        query_vector = model.encode(
            [query],
            normalize_embeddings=self._config.normalized,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0].astype(self._config.dtype, copy=False)
        scores = self._vectors @ query_vector
        limit = min(top_n, len(scores))
        if limit == 0:
            return []
        selected = self._np.argpartition(-scores, limit - 1)[:limit]
        ordered = sorted(selected.tolist(), key=lambda index: (-float(scores[index]), index))
        return [(index, float(scores[index])) for index in ordered]


class DenseRetriever:
    """Optional local dense route with deterministic BM25 degradation."""

    def __init__(
        self,
        catalog_path: str | Path = "data/catalog.jsonl",
        *,
        config: DenseConfig | None = None,
        lexical_fallback: HybridRetriever | None = None,
        backend_factory: Callable[[DenseConfig, Sequence[str]], DenseBackend] | None = None,
    ) -> None:
        self.catalog_path = Path(catalog_path)
        self.config = config if config is not None else DenseConfig()
        self._lexical = (
            lexical_fallback
            if lexical_fallback is not None
            else HybridRetriever(self.catalog_path)
        )
        self.catalog_ids = self._lexical.catalog_ids
        self.fallback_ids = self._lexical.fallback_ids
        self._unavailable_reason = self._validate_cache_metadata()
        self._ids: list[str] = []
        self._backend: DenseBackend | None = None
        if self._unavailable_reason is None:
            try:
                payload = json.loads(
                    (self.config.cache_dir / "ids.json").read_text(encoding="utf-8")
                )
                if (
                    not isinstance(payload, list)
                    or len(payload) != len(self.catalog_ids)
                    or len(set(payload)) != len(payload)
                    or set(payload) != set(self.catalog_ids)
                ):
                    raise ValueError("dense ids are incompatible")
                self._ids = [str(item) for item in payload]
                factory = backend_factory or NumpySentenceBackend
                self._backend = factory(self.config, self._ids)
            except (ImportError, OSError, UnicodeError, ValueError, json.JSONDecodeError):
                self._unavailable_reason = "dense_cache_corrupt"

    def _validate_cache_metadata(self) -> str | None:
        metadata_path = self.config.cache_dir / "metadata.json"
        if not metadata_path.is_file():
            return "dense_cache_missing"
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return "dense_cache_corrupt"
        if not isinstance(payload, Mapping):
            return "dense_cache_corrupt"
        expected: dict[str, Any] = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "catalog_sha256": file_sha256(self.catalog_path),
            "model_id": self.config.model_id,
            "model_revision": self.config.model_revision,
            "dimension": self.config.dimension,
            "dtype": self.config.dtype,
            "normalized": self.config.normalized,
            "product_count": len(self.catalog_ids),
            "product_text_template": PRODUCT_TEXT_TEMPLATE,
            "query_text_template": QUERY_TEXT_TEMPLATE,
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            return "dense_cache_incompatible"
        if not (self.config.cache_dir / "ids.json").is_file():
            return "dense_cache_corrupt"
        if not (self.config.cache_dir / "vectors.npy").is_file():
            return "dense_cache_corrupt"
        return None

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        if self._backend is not None:
            started = time.perf_counter()
            ranked = self._backend.rank(request.query, request.strategy.retrieval_depth)
            latency_ms = (time.perf_counter() - started) * 1000.0
            candidates = [
                Candidate(
                    parent_asin=self._ids[index],
                    score=round(score, 8),
                    source="dense",
                    evidence_text=self._lexical.evidence_text(self._ids[index]),
                    diagnostics={"dense_rank": rank, "dense_score": round(score, 8)},
                )
                for rank, (index, score) in enumerate(ranked, start=1)
            ]
            return RetrievalResult(
                candidates=candidates,
                diagnostics=RetrievalDiagnostics(
                    route="dense",
                    candidate_count=len(candidates),
                    fallback_used=False,
                    latency_ms=round(latency_ms, 6),
                    notes=["dense_cache_hit"],
                    stage_latencies_ms={"dense": round(latency_ms, 6)},
                ),
            )
        result = self._lexical.retrieve(request)
        reason = self._unavailable_reason or "dense_route_unavailable"
        diagnostics = replace(
            result.diagnostics,
            fallback_used=True,
            notes=[*result.diagnostics.notes, reason],
        )
        return RetrievalResult(candidates=result.candidates, diagnostics=diagnostics)
