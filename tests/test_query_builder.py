from __future__ import annotations

import unittest

from starter.core.query_builder import build_distilled_query


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

        self.assertEqual(query, "black black shoes")

    def test_falls_back_to_user_message_without_constraints(self) -> None:
        self.assertEqual(build_distilled_query("plain request", []), "plain request")


if __name__ == "__main__":
    unittest.main()
