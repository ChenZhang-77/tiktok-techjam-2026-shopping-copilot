from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from starter.contracts import RetrievalRequest
from starter.core.planner import Strategy
from starter.retrieval.dense import DenseConfig, DenseRetriever


def _write_catalog(path: Path) -> None:
    rows = [
        {"parent_asin": "A", "title": "walking shoes"},
        {"parent_asin": "B", "title": "running shoes"},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _request() -> RetrievalRequest:
    return RetrievalRequest(
        session_id="dense-fallback",
        turn=1,
        top_k=2,
        query="shoes",
        intent="buying",
        strategy=Strategy(
            intent="buying",
            lexical_weight=0.72,
            structured_weight=0.28,
            semantic_weight=0.0,
            retrieval_depth=20,
            allow_hard_filter=True,
            clarification_enabled=True,
            fallback_mode="lexical",
            reason="dense fallback fixture",
        ),
    )


class DenseFallbackTest(unittest.TestCase):
    def test_missing_cache_reaches_deterministic_lexical_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            _write_catalog(catalog)
            retriever = DenseRetriever(
                catalog,
                config=DenseConfig(cache_dir=root / "missing-cache"),
            )

            first = retriever.retrieve(_request())
            second = retriever.retrieve(_request())

            self.assertEqual(
                [candidate.parent_asin for candidate in first.candidates],
                [candidate.parent_asin for candidate in second.candidates],
            )
            self.assertTrue(first.diagnostics.fallback_used)
            self.assertIn("dense_cache_missing", first.diagnostics.notes)
            self.assertEqual(first.diagnostics.route, "bm25")

    def test_incompatible_metadata_reaches_lexical_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            cache = root / "cache"
            cache.mkdir()
            _write_catalog(catalog)
            (cache / "metadata.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "catalog_sha256": "wrong",
                        "model_id": "sentence-transformers/all-MiniLM-L6-v2",
                        "model_revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                        "dimension": 384,
                        "dtype": "float32",
                        "normalized": True,
                        "product_count": 2,
                    }
                ),
                encoding="utf-8",
            )

            result = DenseRetriever(catalog, config=DenseConfig(cache_dir=cache)).retrieve(
                _request()
            )

            self.assertTrue(result.diagnostics.fallback_used)
            self.assertIn("dense_cache_incompatible", result.diagnostics.notes)


if __name__ == "__main__":
    unittest.main()
