from __future__ import annotations

import unittest

from starter.core.ranking import rank_candidates, rerank_candidates


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

    def test_exact_high_confidence_rejection_lowers_a_matching_candidate(self) -> None:
        scores = rank_candidates(
            ["X", "A", "B"],
            product_texts={
                "X": "trail shoe",
                "A": "black walking shoe",
                "B": "white walking shoe",
            },
            active_constraints=[],
            lexical_weight=0.72,
            structured_weight=0.28,
            rejected_constraints=[
                {
                    "attribute": "color",
                    "normalized_value": "black",
                    "confidence": 0.8,
                    "source_turn": 2,
                }
            ],
        )

        self.assertEqual([item.parent_asin for item in scores], ["X", "B", "A"])
        black = next(item for item in scores if item.parent_asin == "A")
        self.assertGreater(black.rejection_penalty, 0.0)
        self.assertLessEqual(black.rejection_penalty, 0.18)
        self.assertEqual(
            [match.normalized_value for match in black.rejected_constraint_matches],
            ["black"],
        )

    def test_missing_product_evidence_and_low_confidence_are_neutral(self) -> None:
        for product_texts, rejection in (
            (
                {"A": "", "B": "white walking shoe"},
                {"attribute": "color", "normalized_value": "black", "confidence": 1.0},
            ),
            (
                {"A": "black walking shoe", "B": "white walking shoe"},
                {"attribute": "color", "normalized_value": "black", "confidence": 0.79},
            ),
        ):
            with self.subTest(product_texts=product_texts, rejection=rejection):
                scores = rank_candidates(
                    ["A", "B"],
                    product_texts=product_texts,
                    active_constraints=[],
                    lexical_weight=0.72,
                    structured_weight=0.28,
                    rejected_constraints=[rejection],
                )

                self.assertEqual([item.parent_asin for item in scores], ["A", "B"])
                self.assertEqual(scores[0].rejection_penalty, 0.0)
                self.assertEqual(scores[0].rejected_constraint_matches, ())

    def test_active_positive_value_overrides_an_older_rejection(self) -> None:
        scores = rank_candidates(
            ["B", "A"],
            product_texts={"A": "black shoe", "B": "white shoe"},
            active_constraints=[
                {"attribute": "color", "normalized_value": "black", "confidence": 1.0, "hard": True}
            ],
            lexical_weight=0.5,
            structured_weight=0.5,
            rejected_constraints=[
                {"attribute": "color", "normalized_value": "black", "confidence": 1.0, "source_turn": 1}
            ],
        )

        self.assertEqual([item.parent_asin for item in scores], ["A", "B"])
        black = next(item for item in scores if item.parent_asin == "A")
        self.assertEqual(black.rejection_penalty, 0.0)

    def test_no_preference_removes_positive_and_negative_influence(self) -> None:
        scores = rank_candidates(
            ["A", "B"],
            product_texts={"A": "black shoe", "B": "white shoe"},
            active_constraints=[
                {"attribute": "color", "normalized_value": "black", "confidence": 1.0, "hard": True}
            ],
            lexical_weight=0.5,
            structured_weight=0.5,
            rejected_constraints=[
                {"attribute": "color", "normalized_value": "white", "confidence": 1.0}
            ],
            no_preference_attributes=["color"],
        )

        self.assertEqual([item.parent_asin for item in scores], ["A", "B"])
        self.assertTrue(all(item.constraint_score == 0.0 for item in scores))
        self.assertTrue(all(item.rejection_penalty == 0.0 for item in scores))


if __name__ == "__main__":
    unittest.main()
