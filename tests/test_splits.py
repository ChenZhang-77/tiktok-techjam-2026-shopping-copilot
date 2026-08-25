from __future__ import annotations

import unittest

from evaluator.splits import build_split_manifest, filter_samples


def _sample(sample_id: str, scenario: str) -> dict:
    return {"sample_id": sample_id, "scenario_type": scenario}


class SplitTest(unittest.TestCase):
    def test_public_split_counts_are_stratified_and_disjoint(self) -> None:
        samples = [
            *[_sample(f"buying_{index:03d}", "buying") for index in range(80)],
            *[_sample(f"browsing_{index:03d}", "browsing") for index in range(80)],
            *[_sample(f"override_{index:03d}", "intent_override") for index in range(30)],
            *[_sample(f"boundary_{index:03d}", "boundary") for index in range(10)],
        ]
        manifest = build_split_manifest(samples)

        self.assertEqual(manifest["counts"]["development"], 160)
        self.assertEqual(manifest["counts"]["holdout"], 40)
        self.assertEqual(manifest["counts"]["development_by_scenario"], {
            "boundary": 8,
            "browsing": 64,
            "buying": 64,
            "intent_override": 24,
        })
        self.assertEqual(manifest["counts"]["holdout_by_scenario"], {
            "boundary": 2,
            "browsing": 16,
            "buying": 16,
            "intent_override": 6,
        })
        self.assertFalse(set(manifest["development"]) & set(manifest["holdout"]))

    def test_filter_samples_uses_manifest_ids_only(self) -> None:
        samples = [_sample("a", "buying"), _sample("b", "buying"), _sample("c", "buying")]
        manifest = {"development": ["a", "c"], "holdout": ["b"]}

        self.assertEqual([sample["sample_id"] for sample in filter_samples(samples, "development", manifest)], ["a", "c"])
        self.assertEqual([sample["sample_id"] for sample in filter_samples(samples, "holdout", manifest)], ["b"])
        self.assertEqual(filter_samples(samples, "full"), samples)


if __name__ == "__main__":
    unittest.main()
