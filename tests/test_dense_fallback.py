from __future__ import annotations

import json
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from starter.contracts import RetrievalRequest
from starter.core.planner import Strategy
from starter.retrieval.dense import DenseConfig, DenseRetriever, file_sha256, product_text


def _write_catalog(path: Path) -> None:
    rows = [
        {"parent_asin": "A", "title": "walking shoes"},
        {"parent_asin": "B", "title": "running shoes"},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _write_compatible_cache(cache: Path, catalog: Path) -> None:
    ids_path = cache / "ids.json"
    vectors_path = cache / "vectors.npy"
    ids_path.write_text(json.dumps(["A", "B"]), encoding="utf-8")
    vectors_path.write_bytes(b"fixture")
    (cache / "metadata.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "catalog_sha256": file_sha256(catalog),
                "model_id": "sentence-transformers/all-MiniLM-L6-v2",
                "model_revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                "dimension": 384,
                "dtype": "float32",
                "normalized": True,
                "product_count": 2,
                "product_text_template": "product-fields-v1",
                "query_text_template": "distilled-query-v1",
                "ids_sha256": file_sha256(ids_path),
                "vectors_sha256": file_sha256(vectors_path),
            }
        ),
        encoding="utf-8",
    )


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
    def test_prepare_warms_a_compatible_backend_without_querying_products(self) -> None:
        class PreparedBackend:
            def __init__(self) -> None:
                self.prepare_calls = 0

            def prepare(self) -> None:
                self.prepare_calls += 1

            def rank(self, query: str, top_n: int) -> list[tuple[int, float]]:
                return [(0, 1.0)]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            cache = root / "cache"
            cache.mkdir()
            _write_catalog(catalog)
            _write_compatible_cache(cache, catalog)
            backend = PreparedBackend()
            retriever = DenseRetriever(
                catalog,
                config=DenseConfig(cache_dir=cache),
                backend_factory=lambda _config, _ids: backend,
            )

            status = retriever.prepare()

            self.assertIsNone(status)
            self.assertEqual(backend.prepare_calls, 1)
            self.assertEqual(retriever.configuration_snapshot()["cache_status"], "compatible")

    def test_prepare_failure_disables_dense_and_preserves_structured_fallback(self) -> None:
        class FailingPrepareBackend:
            def prepare(self) -> None:
                raise OSError("model unavailable")

            def rank(self, query: str, top_n: int) -> list[tuple[int, float]]:
                raise AssertionError("disabled backend must not be queried")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            cache = root / "cache"
            cache.mkdir()
            _write_catalog(catalog)
            _write_compatible_cache(cache, catalog)
            retriever = DenseRetriever(
                catalog,
                config=DenseConfig(cache_dir=cache),
                backend_factory=lambda _config, _ids: FailingPrepareBackend(),
            )

            status = retriever.prepare()
            result = retriever.retrieve(_request())

            self.assertEqual(status, "dense_warmup_failed")
            self.assertTrue(result.diagnostics.fallback_used)
            self.assertIn("dense_warmup_failed", result.diagnostics.notes)

    def test_compatible_cache_rejects_invalid_request_before_backend_query(self) -> None:
        class FakeBackend:
            called = False

            def rank(self, query: str, top_n: int) -> list[tuple[int, float]]:
                self.called = True
                return []

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            cache = root / "cache"
            cache.mkdir()
            _write_catalog(catalog)
            _write_compatible_cache(cache, catalog)
            backend = FakeBackend()
            retriever = DenseRetriever(
                catalog,
                config=DenseConfig(cache_dir=cache),
                backend_factory=lambda _config, _ids: backend,
            )
            invalid = replace(
                _request(),
                strategy=replace(_request().strategy, retrieval_depth=50_000),
            )

            with self.assertRaisesRegex(ValueError, "retrieval_depth"):
                retriever.retrieve(invalid)

            self.assertFalse(backend.called)

    def test_query_time_dense_failure_reaches_lexical_fallback(self) -> None:
        class FailingBackend:
            def rank(self, query: str, top_n: int) -> list[tuple[int, float]]:
                time.sleep(0.005)
                raise OSError("model unavailable")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            cache = root / "cache"
            cache.mkdir()
            _write_catalog(catalog)
            _write_compatible_cache(cache, catalog)
            retriever = DenseRetriever(
                catalog,
                config=DenseConfig(cache_dir=cache),
                backend_factory=lambda _config, _ids: FailingBackend(),
            )

            result = retriever.retrieve(_request())

            self.assertEqual([item.parent_asin for item in result.candidates], ["A", "B"])
            self.assertTrue(result.diagnostics.fallback_used)
            self.assertIn("dense_query_failed", result.diagnostics.notes)
            self.assertGreaterEqual(result.diagnostics.stage_latencies_ms["dense"], 4.0)
            self.assertGreaterEqual(result.diagnostics.latency_ms, 4.0)

    def test_hash_mismatched_cache_reaches_lexical_fallback(self) -> None:
        class FakeBackend:
            def rank(self, query: str, top_n: int) -> list[tuple[int, float]]:
                return [(0, 0.9), (1, 0.8)][:top_n]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            cache = root / "cache"
            cache.mkdir()
            _write_catalog(catalog)
            _write_compatible_cache(cache, catalog)
            ids_path = cache / "ids.json"
            ids_path.write_text(json.dumps(["B", "A"]), encoding="utf-8")

            result = DenseRetriever(
                catalog,
                config=DenseConfig(cache_dir=cache),
                backend_factory=lambda _config, _ids: FakeBackend(),
            ).retrieve(_request())

            self.assertTrue(result.diagnostics.fallback_used)
            self.assertIn("dense_cache_corrupt", result.diagnostics.notes)

    def test_eof_while_loading_vectors_reaches_lexical_fallback(self) -> None:
        def raise_eof(_config: DenseConfig, _ids: object) -> object:
            raise EOFError("truncated vectors")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            cache = root / "cache"
            cache.mkdir()
            _write_catalog(catalog)
            _write_compatible_cache(cache, catalog)

            result = DenseRetriever(
                catalog,
                config=DenseConfig(cache_dir=cache),
                backend_factory=raise_eof,
            ).retrieve(_request())

            self.assertTrue(result.diagnostics.fallback_used)
            self.assertIn("dense_cache_corrupt", result.diagnostics.notes)

    def test_corrupt_metadata_reaches_lexical_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.jsonl"
            cache = root / "cache"
            cache.mkdir()
            _write_catalog(catalog)
            (cache / "metadata.json").write_text("{not-json", encoding="utf-8")

            result = DenseRetriever(catalog, config=DenseConfig(cache_dir=cache)).retrieve(
                _request()
            )

            self.assertTrue(result.diagnostics.fallback_used)
            self.assertIn("dense_cache_corrupt", result.diagnostics.notes)

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
            _write_compatible_cache(cache, catalog)
            backend = FakeBackend()

            retriever = DenseRetriever(
                catalog,
                config=DenseConfig(cache_dir=cache),
                backend_factory=lambda _config, _ids: backend,
            )
            result = retriever.retrieve(_request())

            self.assertEqual([item.parent_asin for item in result.candidates], ["B", "A"])
            self.assertEqual(result.candidates[0].source, "dense")
            self.assertEqual(result.candidates[0].score, 0.9)
            self.assertEqual(result.candidates[0].diagnostics["dense_rank"], 1)
            self.assertFalse(result.diagnostics.fallback_used)
            self.assertEqual(result.diagnostics.route, "dense")
            self.assertEqual(
                result.diagnostics.requested_route_weights,
                {"lexical": 0.72, "structured": 0.28, "dense": 0.0},
            )
            self.assertEqual(result.diagnostics.executed_routes, ["dense"])
            self.assertIsNone(result.diagnostics.fallback_route)
            snapshot = retriever.configuration_snapshot()
            self.assertEqual(snapshot["cache_status"], "compatible")
            self.assertTrue(snapshot["cache_available"])
            self.assertGreater(snapshot["cache_size_bytes"], 0)

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
            self.assertEqual(first.diagnostics.route, "structured")
            self.assertEqual(
                first.diagnostics.route_failures,
                {"dense": "dense_cache_missing"},
            )
            self.assertEqual(
                first.diagnostics.executed_routes,
                ["lexical", "structured"],
            )
            self.assertEqual(first.diagnostics.fallback_route, "structured")
            snapshot = retriever.configuration_snapshot()
            self.assertEqual(snapshot["cache_status"], "dense_cache_missing")
            self.assertFalse(snapshot["cache_available"])

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
