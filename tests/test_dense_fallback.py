from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from starter.contracts import RetrievalRequest
from starter.core.planner import Strategy
from starter.retrieval.dense import DenseConfig, DenseRetriever, product_text


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
    def test_product_text_template_is_exact_and_cross_field(self) -> None:
        text = product_text(
            {
                "title": "Trail Shoe",
                "categories": ["Footwear", "Outdoor"],
                "features": ["waterproof"],
                "details": {"material": "mesh"},
                "store": "Example",
                "description": ["lightweight"],
            }
        )

        self.assertEqual(
            text,
            "title: Trail Shoe\ncategories: Footwear Outdoor\nfeatures: waterproof\n"
            "details: material mesh\nstore: Example\ndescription: lightweight",
        )

    def test_compatible_cache_returns_dense_rank_provenance(self) -> None:
        class FakeBackend:
            def rank(self, query: str, top_n: int) -> list[tuple[int, float]]:
                self.query = query
                return [(1, 0.9), (0, 0.8)][:top_n]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            cache = root / "cache"
            cache.mkdir()
            _write_catalog(catalog)
            catalog_sha = hashlib.sha256(catalog.read_bytes()).hexdigest()
            (cache / "metadata.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "catalog_sha256": catalog_sha,
                        "model_id": "sentence-transformers/all-MiniLM-L6-v2",
                        "model_revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                        "dimension": 384,
                        "dtype": "float32",
                        "normalized": True,
                        "product_count": 2,
                        "product_text_template": "product-fields-v1",
                        "query_text_template": "distilled-query-v1",
                    }
                ),
                encoding="utf-8",
            )
            (cache / "ids.json").write_text(json.dumps(["A", "B"]), encoding="utf-8")
            (cache / "vectors.npy").write_bytes(b"fixture")
            backend = FakeBackend()

            result = DenseRetriever(
                catalog,
                config=DenseConfig(cache_dir=cache),
                backend_factory=lambda _config, _ids: backend,
            ).retrieve(_request())

            self.assertEqual([item.parent_asin for item in result.candidates], ["B", "A"])
            self.assertEqual(result.candidates[0].source, "dense")
            self.assertEqual(result.candidates[0].score, 0.9)
            self.assertEqual(result.candidates[0].diagnostics["dense_rank"], 1)
            self.assertFalse(result.diagnostics.fallback_used)
            self.assertEqual(result.diagnostics.route, "dense")

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
