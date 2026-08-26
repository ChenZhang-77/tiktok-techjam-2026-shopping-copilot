from __future__ import annotations

import unittest

from starter.core.ranking import rerank_candidates


class RankingTest(unittest.TestCase):
    def test_matching_constraints_can_promote_candidate(self) -> None:
        ranked = rerank_candidates(
            ["A", "B"],
            product_texts={
                "A": "canvas shoe",
                "B": "black leather shoe",
            },
            active_constraints=[
                {"attribute": "material", "normalized_value": "leather", "confidence": 0.9, "hard": True},
                {"attribute": "color", "normalized_value": "black", "confidence": 0.8, "hard": True},
            ],
            lexical_weight=0.50,
            structured_weight=0.50,
        )

        self.assertEqual(ranked[0], "B")

    def test_without_constraints_preserves_order(self) -> None:
        self.assertEqual(
            rerank_candidates(
                ["A", "B"],
                product_texts={},
                active_constraints=[],
                lexical_weight=0.7,
                structured_weight=0.3,
            ),
            ["A", "B"],
        )

    def test_equivalent_constraints_are_counted_once(self) -> None:
        ranked = rerank_candidates(
            ["A", "B"],
            product_texts={
                "A": "canvas shoe",
                "B": "leather shoe",
            },
            active_constraints=[
                {
                    "attribute": "material",
                    "normalized_value": "leather",
                    "confidence": 1.0,
                    "hard": True,
                    "source_turn": 1,
                },
                {
                    "attribute": "material",
                    "raw_value": "Leather",
                    "confidence": 1.0,
                    "hard": True,
                    "source_turn": 2,
                },
            ],
            lexical_weight=0.8,
            structured_weight=0.2,
        )

        self.assertEqual(ranked, ["A", "B"])

    def test_hard_constraint_wins_over_equivalent_soft_duplicate(self) -> None:
        ranked = rerank_candidates(
            ["A", "B"],
            product_texts={
                "A": "canvas shoe",
                "B": "leather shoe",
            },
            active_constraints=[
                {
                    "attribute": "material",
                    "normalized_value": "leather",
                    "confidence": 1.0,
                    "hard": False,
                },
                {
                    "attribute": "material",
                    "raw_value": "Leather",
                    "confidence": 1.0,
                    "hard": True,
                },
            ],
            lexical_weight=0.7,
            structured_weight=0.3,
        )

        self.assertEqual(ranked, ["B", "A"])


if __name__ == "__main__":
    unittest.main()
