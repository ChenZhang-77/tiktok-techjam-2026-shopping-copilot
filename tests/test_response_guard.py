from __future__ import annotations

import unittest

from starter.core.response_guard import guard_response


class ResponseGuardTest(unittest.TestCase):
    def test_guard_normalizes_schema_and_recommendations(self) -> None:
        guarded = guard_response(
            {
                "message": 123,
                "ask_attribute": "illegal",
                "recommendations": [
                    {"parent_asin": "A"},
                    {"parent_asin": "missing"},
                    {"parent_asin": "A"},
                    "B",
                ],
                "usage": {"prompt_tokens": -1, "completion_tokens": 0},
            },
            catalog_ids={"A", "B", "C", "D"},
            fallback_ids=["A", "C", "D"],
            top_k=4,
        )

        self.assertEqual(guarded["message"], "Here are the closest matches I found.")
        self.assertIsNone(guarded["ask_attribute"])
        self.assertEqual(guarded["recommendations"], [
            {"parent_asin": "A"},
            {"parent_asin": "B"},
            {"parent_asin": "C"},
            {"parent_asin": "D"},
        ])
        self.assertNotIn("usage", guarded)

    def test_guard_preserves_valid_usage_and_allowed_ask_attribute(self) -> None:
        guarded = guard_response(
            {
                "message": "Do you care about material?",
                "ask_attribute": "material",
                "recommendations": [{"parent_asin": "A"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2},
            },
            catalog_ids={"A"},
            fallback_ids=[],
            top_k=10,
        )

        self.assertEqual(guarded["ask_attribute"], "material")
        self.assertEqual(guarded["usage"], {"prompt_tokens": 1, "completion_tokens": 2})
        self.assertEqual(guarded["recommendations"], [{"parent_asin": "A"}])

    def test_guard_handles_invalid_payload_and_zero_top_k(self) -> None:
        guarded = guard_response(
            None,
            catalog_ids={"A"},
            fallback_ids=["A"],
            top_k=0,
        )

        self.assertEqual(guarded["recommendations"], [])
        self.assertIsNone(guarded["ask_attribute"])


if __name__ == "__main__":
    unittest.main()
