from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from starter.contracts import RetrievalRequest, RetrievalResult
from starter.retrieval.hybrid import HybridRetriever


MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
CACHE_SCHEMA_VERSION = 1
EMBEDDING_DIMENSION = 384
EMBEDDING_DTYPE = "float32"


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


class DenseRetriever:
    """Optional local dense route with deterministic BM25 degradation."""

    def __init__(
        self,
        catalog_path: str | Path = "data/catalog.jsonl",
        *,
        config: DenseConfig | None = None,
        lexical_fallback: HybridRetriever | None = None,
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
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            return "dense_cache_incompatible"
        if not (self.config.cache_dir / "ids.json").is_file():
            return "dense_cache_corrupt"
        if not (self.config.cache_dir / "vectors.npy").is_file():
            return "dense_cache_corrupt"
        return "dense_backend_not_loaded"

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        result = self._lexical.retrieve(request)
        reason = self._unavailable_reason or "dense_route_unavailable"
        diagnostics = replace(
            result.diagnostics,
            fallback_used=True,
            notes=[*result.diagnostics.notes, reason],
        )
        return RetrievalResult(candidates=result.candidates, diagnostics=diagnostics)
