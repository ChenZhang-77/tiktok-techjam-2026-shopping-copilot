from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from starter.contracts import RetrievalRequest
from starter.core.planner import Strategy
from starter.retrieval import HybridRetriever, StructuredConfig


def _write_catalog(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _request(
    query: str,
    constraints: list[dict],
    *,
    top_k: int = 2,
    intent: str = "buying",
    allow_hard_filter: bool = True,
) -> RetrievalRequest:
    return RetrievalRequest(
        session_id="structured-session",
        turn=1,
        top_k=top_k,
        query=query,
        intent=intent,
        strategy=Strategy(
            intent=intent,
            lexical_weight=0.72,
            structured_weight=0.28,
            semantic_weight=0.0,
            retrieval_depth=20,
            allow_hard_filter=allow_hard_filter,
            clarification_enabled=True,
            fallback_mode="lexical",
            reason="structured fixture",
        ),
        active_constraints=constraints,
    )


class StructuredRetrievalTest(unittest.TestCase):
    def test_route_bundle_exposes_lexical_and_structured_orders_from_one_seam(self) -> None:
        rows = [
            {"parent_asin": "A", "title": "cotton walking shoes"},
            {"parent_asin": "B", "title": "leather walking shoes"},
        ]
        constraint = {
            "attribute": "material",
            "normalized_value": "leather",
            "confidence": 1.0,
            "hard": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path, rows)
            retriever = HybridRetriever(catalog_path)
            request = _request(
                "walking shoes",
                [constraint],
                allow_hard_filter=False,
            )

            routes = retriever.retrieve_routes(request)

            self.assertEqual(
                [candidate.parent_asin for candidate in routes["lexical"].candidates],
                ["A", "B"],
            )
            self.assertEqual(
                [candidate.parent_asin for candidate in routes["structured"].candidates],
                ["B", "A"],
            )
            self.assertEqual(routes["lexical"].candidates[0].source, "lexical")
            self.assertEqual(routes["structured"].candidates[0].source, "structured")
            self.assertGreater(
                routes["structured"].candidates[0].diagnostics["constraint_score"],
                routes["structured"].candidates[1].diagnostics["constraint_score"],
            )
            self.assertIn("ranking_score", routes["structured"].candidates[0].diagnostics)
            self.assertEqual(
                [candidate.parent_asin for candidate in retriever.retrieve(request).candidates],
                ["B", "A"],
            )

    def test_retained_structured_filter_is_the_runtime_default(self) -> None:
        rows = [
            {
                "parent_asin": f"W{index:02d}",
                "title": "white leather walking shoes",
            }
            for index in range(10)
        ] + [
            {
                "parent_asin": f"B{index:02d}",
                "title": "black cotton walking shoes",
            }
            for index in range(10)
        ]
        constraints = [
            {
                "attribute": "color",
                "normalized_value": "black",
                "confidence": 0.9,
                "hard": True,
            },
            {
                "attribute": "material",
                "normalized_value": "leather",
                "confidence": 0.8,
                "hard": True,
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path, rows)
            retriever = HybridRetriever(catalog_path)

            result = retriever.retrieve(_request("walking shoes", constraints))

            self.assertEqual(
                [candidate.parent_asin for candidate in result.candidates[:2]],
                ["B00", "B01"],
            )
            self.assertTrue(result.diagnostics.structured_filter_applied)
            self.assertEqual(
                result.diagnostics.route_candidate_counts,
                {"lexical": 20, "structured": 20},
            )
            self.assertEqual(
                result.diagnostics.route_overlap_counts,
                {"lexical|structured": 20},
            )
            self.assertEqual(
                result.diagnostics.cache_state,
                {"lexical_index": "memory_ready", "structured_evidence": "memory_ready"},
            )
            self.assertEqual(
                result.diagnostics.ranking_pool_sizes,
                {
                    "pre_constraint_rerank": 20,
                    "post_constraint_rerank": 20,
                    "post_structured_filter": 10,
                },
            )
            self.assertEqual(
                result.diagnostics.relaxed_constraints,
                [{"attribute": "material", "value": "leather", "confidence": 0.8}],
            )

    def test_lexical_only_runtime_bypasses_constraint_reranking(self) -> None:
        rows = [
            {"parent_asin": "A", "title": "white walking shoes"},
            {"parent_asin": "B", "title": "black walking shoes"},
        ]
        constraint = {
            "attribute": "color",
            "normalized_value": "black",
            "confidence": 1.0,
            "hard": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path, rows)
            lexical = HybridRetriever(
                catalog_path,
                structured_config=StructuredConfig(enabled=False),
                constraint_rerank_enabled=False,
            )

            result = lexical.retrieve(_request("walking shoes", [constraint]))

            self.assertEqual(
                [candidate.parent_asin for candidate in result.candidates],
                ["A", "B"],
            )
            self.assertTrue(
                all(
                    not candidate.diagnostics["constraint_reranked"]
                    for candidate in result.candidates
                )
            )

    def test_zero_result_combination_relaxes_lowest_confidence_constraint(self) -> None:
        rows = [
            {"parent_asin": "A", "title": "black cotton running shoes", "price": 50.0},
            {"parent_asin": "B", "title": "white leather running shoes", "price": 90.0},
            {"parent_asin": "C", "title": "black nylon trail shoes", "price": None},
            {"parent_asin": "D", "title": "red leather dress shoes", "price": 20.0},
        ]
        constraints = [
            {
                "attribute": "color",
                "normalized_value": "black",
                "confidence": 0.9,
                "hard": True,
            },
            {
                "attribute": "material",
                "normalized_value": "leather",
                "confidence": 0.8,
                "hard": True,
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path, rows)
            retriever = HybridRetriever(
                catalog_path,
                structured_config=StructuredConfig(
                    enabled=True,
                    minimum_filter_matches=1,
                    minimum_filter_coverage=0.0,
                ),
            )

            result = retriever.retrieve(_request("black leather shoes", constraints))

            self.assertEqual([candidate.parent_asin for candidate in result.candidates[:2]], ["A", "C"])
            self.assertTrue(result.diagnostics.structured_filter_applied)
            self.assertEqual(
                result.diagnostics.relaxed_constraints,
                [{"attribute": "material", "value": "leather", "confidence": 0.8}],
            )
            self.assertTrue(
                any(step.get("after") == 0 for step in result.diagnostics.filtered_pool_sizes)
            )
            self.assertIn("structured_filter_relaxed", result.diagnostics.notes)

    def test_sparse_price_is_evidence_but_not_a_default_hard_filter(self) -> None:
        rows = [
            {"parent_asin": "A", "title": "walking shoes", "price": "$49.99"},
            {"parent_asin": "B", "title": "running shoes", "price": None},
            {"parent_asin": "C", "title": "trail shoes"},
            {"parent_asin": "D", "title": "dress shoes", "price": None},
        ]
        budget = {
            "attribute": "budget",
            "normalized_value": "$60",
            "confidence": 0.95,
            "hard": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path, rows)
            retriever = HybridRetriever(
                catalog_path,
                structured_config=StructuredConfig(
                    enabled=True,
                    minimum_filter_matches=1,
                    minimum_filter_coverage=0.0,
                ),
            )

            result = retriever.retrieve(_request("shoes", [budget], top_k=4))

            self.assertEqual(len(result.candidates), 4)
            self.assertFalse(result.diagnostics.structured_filter_applied)
            by_id = {candidate.parent_asin: candidate for candidate in result.candidates}
            self.assertEqual(by_id["A"].diagnostics["structured_matches"][0]["fields"], ["price"])

    def test_sparse_details_evidence_does_not_eliminate_the_pool(self) -> None:
        rows = [
            {
                "parent_asin": f"P{index}",
                "title": "walking shoes",
                "details": {"special": "marker"} if index == 0 else {},
            }
            for index in range(12)
        ]
        constraint = {
            "attribute": "feature",
            "normalized_value": "marker",
            "confidence": 1.0,
            "hard": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path, rows)
            retriever = HybridRetriever(
                catalog_path,
                structured_config=StructuredConfig(enabled=True),
            )

            result = retriever.retrieve(_request("walking shoes", [constraint], top_k=10))

            self.assertEqual(len(result.candidates), 12)
            self.assertFalse(result.diagnostics.structured_filter_applied)
            marker = next(candidate for candidate in result.candidates if candidate.parent_asin == "P0")
            self.assertEqual(marker.diagnostics["structured_matches"][0]["fields"], ["details"])

    def test_structured_matches_preserve_cross_field_provenance(self) -> None:
        rows = [
            {"parent_asin": "TITLE", "title": "marker product"},
            {"parent_asin": "CATEGORY", "title": "product", "categories": ["marker"]},
            {"parent_asin": "FEATURE", "title": "product", "features": ["marker"]},
            {"parent_asin": "DETAIL", "title": "product", "details": {"kind": "marker"}},
            {"parent_asin": "STORE", "title": "product", "store": "marker"},
            {"parent_asin": "DESCRIPTION", "title": "product", "description": ["marker"]},
        ]
        constraint = {
            "attribute": "feature",
            "normalized_value": "marker",
            "confidence": 0.5,
            "hard": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path, rows)
            retriever = HybridRetriever(
                catalog_path,
                structured_config=StructuredConfig(enabled=True),
            )

            result = retriever.retrieve(_request("marker", [constraint], top_k=6))

            fields_by_id = {
                candidate.parent_asin: candidate.diagnostics["structured_matches"][0]["fields"]
                for candidate in result.candidates
            }
            self.assertEqual(
                fields_by_id,
                {
                    "TITLE": ["title"],
                    "CATEGORY": ["categories"],
                    "FEATURE": ["features"],
                    "DETAIL": ["details"],
                    "STORE": ["store"],
                    "DESCRIPTION": ["description"],
                },
            )

    def test_browsing_order_remains_lexical_when_hard_filter_is_not_allowed(self) -> None:
        rows = [
            {"parent_asin": "A", "title": "black running shoes"},
            {"parent_asin": "B", "title": "white running shoes"},
            {"parent_asin": "C", "title": "blue running shoes"},
        ]
        constraint = {
            "attribute": "color",
            "normalized_value": "black",
            "confidence": 1.0,
            "hard": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            _write_catalog(catalog_path, rows)
            baseline = HybridRetriever(catalog_path)
            structured = HybridRetriever(
                catalog_path,
                structured_config=StructuredConfig(
                    enabled=True,
                    minimum_filter_matches=1,
                    minimum_filter_coverage=0.0,
                ),
            )
            request = _request(
                "running shoes",
                [constraint],
                top_k=3,
                intent="browsing",
                allow_hard_filter=False,
            )

            baseline_ids = [candidate.parent_asin for candidate in baseline.retrieve(request).candidates]
            structured_result = structured.retrieve(request)

            self.assertEqual(
                [candidate.parent_asin for candidate in structured_result.candidates],
                baseline_ids,
            )
            self.assertFalse(structured_result.diagnostics.structured_filter_applied)


if __name__ == "__main__":
    unittest.main()
