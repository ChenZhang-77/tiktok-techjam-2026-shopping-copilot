from __future__ import annotations

import unittest

from starter.retrieval.semantic_ranker import (
    FakeSemanticRanker,
    GuardedSemanticRanker,
    SemanticRankError,
    SemanticRankItem,
    SemanticRankRequest,
    validate_permutation,
)


def _request() -> SemanticRankRequest:
    return SemanticRankRequest(
        query="comfortable black shoes",
        active_constraints=("color:black",),
        items=(
            SemanticRankItem("c0", "black running shoes"),
            SemanticRankItem("c1", "black leather shoes"),
            SemanticRankItem("c2", "white sandals"),
        ),
    )


class SemanticRankerTest(unittest.TestCase):
    def test_disabled_mode_returns_exact_pre_rank_order_without_calling_backend(self) -> None:
        backend = FakeSemanticRanker(ordered_ids=["c2", "c1", "c0"])
        result = GuardedSemanticRanker(backend, enabled=False).rank(_request())

        self.assertEqual(result.ordered_ids, ("c0", "c1", "c2"))
        self.assertEqual(result.fallback_reason, "disabled")
        self.assertEqual(backend.calls, 0)

    def test_enabled_fake_backend_can_reorder_only_known_candidates(self) -> None:
        backend = FakeSemanticRanker(ordered_ids=["c2", "c0", "c1"])
        result = GuardedSemanticRanker(backend, enabled=True).rank(_request())

        self.assertEqual(result.ordered_ids, ("c2", "c0", "c1"))
        self.assertIsNone(result.fallback_reason)
        self.assertEqual(backend.calls, 1)

    def test_invalid_permutation_falls_back_exactly(self) -> None:
        backend = FakeSemanticRanker(ordered_ids=["c2", "c2", "unknown"])
        result = GuardedSemanticRanker(backend, enabled=True).rank(_request())

        self.assertEqual(result.ordered_ids, ("c0", "c1", "c2"))
        self.assertEqual(result.fallback_reason, "invalid_permutation")

    def test_backend_error_falls_back_exactly(self) -> None:
        backend = FakeSemanticRanker(error=SemanticRankError("timeout"))
        result = GuardedSemanticRanker(backend, enabled=True).rank(_request())

        self.assertEqual(result.ordered_ids, ("c0", "c1", "c2"))
        self.assertEqual(result.fallback_reason, "timeout")

    def test_permutation_validator_rejects_duplicates_and_unknown_ids(self) -> None:
        with self.assertRaises(SemanticRankError):
            validate_permutation(["c0", "c0", "c2"], ("c0", "c1", "c2"))
        with self.assertRaises(SemanticRankError):
            validate_permutation(["c0", "c1", "c9"], ("c0", "c1", "c2"))


if __name__ == "__main__":
    unittest.main()
