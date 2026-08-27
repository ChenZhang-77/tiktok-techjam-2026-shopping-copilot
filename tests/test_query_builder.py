from __future__ import annotations

import unittest

from starter.core.query_builder import build_distilled_query, build_query_plan


class QueryBuilderTest(unittest.TestCase):
    def test_builds_query_from_active_constraints_before_current_message(self) -> None:
        query = build_distilled_query(
            "Something for winter",
            [
                {"attribute": "feature", "normalized_value": "waterproof", "confidence": 0.4, "source_turn": 1},
                {"attribute": "material", "normalized_value": "leather", "confidence": 0.9, "source_turn": 1},
                {"attribute": "color", "normalized_value": "black", "confidence": 0.8, "source_turn": 2},
            ],
        )

        self.assertEqual(query, "leather black waterproof Something for winter")

    def test_ignores_inactive_and_duplicate_constraints(self) -> None:
        query = build_distilled_query(
            "black shoes",
            [
                {"attribute": "color", "normalized_value": "black", "confidence": 0.8, "source_turn": 1},
                {"attribute": "color", "normalized_value": "black", "confidence": 0.7, "source_turn": 2},
                {"attribute": "material", "normalized_value": "cotton", "active": False},
            ],
        )

        self.assertEqual(query, "black shoes")

    def test_falls_back_to_user_message_without_constraints(self) -> None:
        self.assertEqual(build_distilled_query("plain request", []), "plain request")

    def test_query_plan_separates_roles_and_keeps_negative_terms_out_of_query(self) -> None:
        plan = build_query_plan(
            "Actually, avoid leather; cotton shoes for hiking",
            [
                {"attribute": "category", "normalized_value": "shoes", "hard": True},
                {"attribute": "material", "normalized_value": "cotton", "hard": True},
                {"attribute": "use_case", "normalized_value": "hiking", "hard": False},
            ],
            rejected_constraints=[
                {"attribute": "material", "normalized_value": "leather", "active": False}
            ],
        )

        self.assertEqual(plan.category_terms, ("shoes",))
        self.assertEqual(plan.hard_terms, ("cotton",))
        self.assertEqual(plan.semantic_terms, ("hiking",))
        self.assertEqual(plan.excluded_terms, ("leather",))
        self.assertEqual(plan.rendered_query, "shoes cotton hiking Actually, avoid ; for")
        self.assertNotIn("leather", plan.rendered_query)
        self.assertFalse(plan.fallback_to_message)

    def test_query_plan_deduplicates_values_across_roles(self) -> None:
        plan = build_query_plan(
            "black shoes",
            [
                {"attribute": "category", "normalized_value": "shoes", "hard": True},
                {"attribute": "feature", "normalized_value": "shoes", "hard": False},
                {"attribute": "color", "normalized_value": "black", "hard": True},
            ],
        )

        self.assertEqual(plan.rendered_query, "shoes black")
        self.assertEqual(plan.semantic_terms, ())

    def test_short_and_symbolic_excluded_values_never_render_positive(self) -> None:
        plan = build_query_plan(
            "avoid 8, not M, and avoid $50",
            [],
            rejected_constraints=[
                {"attribute": "size", "normalized_value": "8", "active": False},
                {"attribute": "size", "normalized_value": "m", "active": False},
            ],
            overridden_constraints=[
                {"attribute": "budget", "normalized_value": "$50", "active": False}
            ],
        )

        self.assertEqual(plan.excluded_terms, ("8", "m", "$50"))
        self.assertNotIn("8", plan.rendered_query)
        self.assertNotRegex(plan.rendered_query, r"(?i)(?<![a-z0-9'])m(?![a-z0-9'])")
        self.assertNotIn("$50", plan.rendered_query)

    def test_single_character_active_value_does_not_mutilate_contraction(self) -> None:
        plan = build_query_plan(
            "I'm looking for size M",
            [{"attribute": "size", "normalized_value": "m", "hard": True}],
        )

        self.assertEqual(plan.hard_terms, ("m",))
        self.assertEqual(plan.residual_terms, ("I'm looking for size",))
        self.assertEqual(plan.rendered_query, "m I'm looking for size")


if __name__ == "__main__":
    unittest.main()
