from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from starter.contracts import RetrievalRequest
from starter.core.planner import Strategy
from starter.retrieval import HybridRetriever


CATALOG_ROWS = [
    {
        "parent_asin": "A",
        "title": "Black leather running shoes",
        "categories": ["Footwear", "Running Shoes"],
        "features": ["road running"],
        "details": {},
        "store": "Alpha",
        "description": [],
    },
    {
        "parent_asin": "B",
        "title": "Running shoes",
        "categories": ["Footwear"],
        "features": ["black leather upper"],
        "details": {},
        "store": "Beta",
        "description": [],
    },
    {
        "parent_asin": "C",
        "title": "Black trail shoes",
        "categories": ["Footwear"],
        "features": ["leather"],
        "details": {},
        "store": "Gamma",
        "description": [],
    },
    {
        "parent_asin": "D",
        "title": "Leather dress shoes",
        "categories": ["Footwear"],
        "features": ["black formal"],
        "details": {},
        "store": "Delta",
        "description": [],
    },
    {
        "parent_asin": "E",
        "title": "Blue running shoes",
        "categories": ["Footwear"],
        "features": ["mesh"],
        "details": {},
        "store": "Epsilon",
        "description": [],
    },
    {
        "parent_asin": "F",
        "title": "Summer hiking backpack",
        "categories": ["Outdoor", "Backpacks"],
        "features": ["ventilated"],
        "details": {},
        "store": "Foxtrot",
        "description": [],
    },
    {
        "parent_asin": "G",
        "title": "Hiking backpack",
        "categories": ["Outdoor", "Backpacks"],
        "features": ["lightweight summer pack"],
        "details": {},
        "store": "Golf",
        "description": [],
    },
    {
        "parent_asin": "H",
        "title": "Travel backpack",
        "categories": ["Travel"],
        "features": [],
        "details": {},
        "store": "Hotel",
        "description": ["lightweight bag for summer hiking"],
    },
]


def _write_catalog(path: Path, rows: list[dict] | None = None) -> None:
    rows = CATALOG_ROWS if rows is None else rows
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _strategy(intent: str) -> Strategy:
    browsing = intent == "browsing"
    return Strategy(
        intent=intent,
        lexical_weight=0.62 if browsing else 0.72,
        structured_weight=0.20 if browsing else 0.28,
        semantic_weight=0.18 if browsing else 0.0,
        retrieval_depth=6,
        allow_hard_filter=not browsing,
        clarification_enabled=True,
        fallback_mode="broad_lexical" if browsing else "lexical",
        reason="parity fixture",
    )


def _request(intent: str) -> RetrievalRequest:
    buying = intent == "buying"
    return RetrievalRequest(
        session_id=f"{intent}-session",
        turn=1,
        top_k=4,
        query="black leather running shoes" if buying else "lightweight summer hiking backpack",
        intent=intent,
        strategy=_strategy(intent),
        active_constraints=(
            [
                {"attribute": "color", "normalized_value": "black", "confidence": 1.0, "hard": True},
                {"attribute": "material", "normalized_value": "leather", "confidence": 1.0, "hard": True},
                {"attribute": "category", "normalized_value": "shoes", "confidence": 1.0, "hard": True},
            ]
            if buying
            else []
        ),
    )


class HybridRetrieverTest(unittest.TestCase):
    def test_rejected_constraint_matches_are_explicit_and_missing_evidence_stays_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path)
            retriever = HybridRetriever(catalog_path)
            request = replace(
                _request("buying"),
                rejected_constraints=[
                    {
                        "attribute": "material",
                        "normalized_value": "leather",
                        "confidence": 0.95,
                        "active": True,
                    }
                ],
            )

            result = retriever.retrieve(request)
            by_id = {candidate.parent_asin: candidate for candidate in result.candidates}

            self.assertEqual(
                by_id["A"].diagnostics["rejected_constraint_matches"][0]["value"],
                "leather",
            )
            self.assertEqual(
                by_id["E"].diagnostics["rejected_constraint_matches"],
                [],
            )
            self.assertNotIn("constraint_guard_status", by_id["E"].diagnostics)

    def test_representative_orders_match_the_embedded_buying_and_browsing_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path)
            retriever = HybridRetriever(catalog_path)

            for intent in ("buying", "browsing"):
                with self.subTest(intent=intent):
                    request = _request(intent)
                    result = retriever.retrieve(request)
                    actual = [item["parent_asin"] for item in result.recommendations(request.top_k)]
                    golden = {
                        "buying": ["A", "B", "C", "D"],
                        "browsing": ["G", "H", "F"],
                    }[intent]

                    self.assertEqual(actual, golden)
                    self.assertEqual(
                        result.diagnostics.requested_route_weights,
                        {
                            "lexical": request.strategy.lexical_weight,
                            "structured": request.strategy.structured_weight,
                            "dense": request.strategy.semantic_weight,
                        },
                    )
                    self.assertEqual(
                        result.diagnostics.executed_routes,
                        ["lexical", "structured"],
                    )
                    self.assertIsNone(result.diagnostics.fallback_route)

    def test_field_weight_order_matches_the_embedded_bm25_baseline(self) -> None:
        rows = [
            {"parent_asin": "TITLE", "title": "signal"},
            {"parent_asin": "CATEGORY", "categories": ["signal"]},
            {"parent_asin": "FEATURE", "features": ["signal"]},
            {"parent_asin": "DETAIL", "details": {"kind": "signal"}},
            {"parent_asin": "STORE", "store": "signal"},
            {"parent_asin": "DESCRIPTION", "description": ["signal"]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path, rows)
            retriever = HybridRetriever(catalog_path)
            base = _request("browsing")
            request = replace(base, top_k=6, query="signal")

            actual = [item["parent_asin"] for item in retriever.retrieve(request).recommendations(6)]

            self.assertEqual(
                actual,
                ["TITLE", "CATEGORY", "FEATURE", "STORE", "DETAIL", "DESCRIPTION"],
            )

    def test_empty_query_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path)
            retriever = HybridRetriever(catalog_path)
            request = _request("browsing")
            request = replace(request, query="the and please")

            first = retriever.retrieve(request)
            second = retriever.retrieve(request)

            self.assertEqual(first.candidates, [])
            self.assertEqual(second.candidates, [])
            self.assertEqual(first.diagnostics.candidate_count, 0)
            self.assertFalse(first.diagnostics.fallback_used)

    def test_duplicate_catalog_asins_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path, [CATALOG_ROWS[0], CATALOG_ROWS[0]])

            with self.assertRaisesRegex(ValueError, "Duplicate parent_asin"):
                HybridRetriever(catalog_path)

    def test_invalid_request_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path)
            retriever = HybridRetriever(catalog_path)
            request = _request("buying")
            request = replace(request, top_k=-1)

            with self.assertRaisesRegex(ValueError, "top_k"):
                retriever.retrieve(request)

    def test_unbounded_retrieval_depth_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path)
            retriever = HybridRetriever(catalog_path)
            request = _request("buying")
            request = replace(
                request,
                strategy=replace(request.strategy, retrieval_depth=50_000),
            )

            with self.assertRaisesRegex(ValueError, "retrieval_depth"):
                retriever.retrieve(request)

    def test_malformed_strategy_is_rejected_at_the_public_seam(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path)
            retriever = HybridRetriever(catalog_path)
            request = replace(_request("buying"), strategy=None)

            with self.assertRaisesRegex(ValueError, "strategy"):
                retriever.retrieve(request)

    def test_equal_bm25_scores_preserve_catalog_insertion_order(self) -> None:
        rows = [
            {"parent_asin": "Z_FIRST", "title": "equal signal"},
            {"parent_asin": "A_SECOND", "title": "equal signal"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path, rows)
            retriever = HybridRetriever(catalog_path)
            request = replace(_request("browsing"), top_k=2, query="equal signal")

            actual = [item["parent_asin"] for item in retriever.retrieve(request).recommendations(2)]

            self.assertEqual(actual, ["Z_FIRST", "A_SECOND"])

    def test_provenance_and_latency_do_not_change_candidate_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path)
            retriever = HybridRetriever(catalog_path)
            request = _request("buying")

            first = retriever.retrieve(request)
            second = retriever.retrieve(request)

            self.assertEqual(
                [candidate.parent_asin for candidate in first.candidates],
                [candidate.parent_asin for candidate in second.candidates],
            )
            self.assertGreaterEqual(retriever.initialization_ms, 0.0)
            self.assertGreaterEqual(first.diagnostics.latency_ms, 0.0)
            for rank, candidate in enumerate(first.candidates, start=1):
                self.assertEqual(candidate.source, "structured")
                self.assertEqual(candidate.diagnostics["final_rank"], rank)
                self.assertFalse(
                    {"ground_truth", "target_asin", "scenario_type"} & set(candidate.diagnostics)
                )

    def test_full_catalog_loads_50000_unique_products_without_mutation(self) -> None:
        catalog_path = Path("data/catalog.jsonl")
        before = hashlib.sha256(catalog_path.read_bytes()).hexdigest()

        retriever = HybridRetriever(catalog_path)

        after = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
        self.assertEqual(retriever.catalog_size, 50_000)
        self.assertEqual(len(retriever.catalog_ids), 50_000)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
