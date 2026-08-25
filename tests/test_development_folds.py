from __future__ import annotations

import json
import unittest
from pathlib import Path

from experiments.development_folds import (
    build_development_fold_manifest,
    filter_development_fold,
    validate_development_fold_manifest,
)


def _sample(sample_id: str, scenario: str) -> dict:
    return {"sample_id": sample_id, "scenario_type": scenario}


class DevelopmentFoldTest(unittest.TestCase):
    def test_filters_samples_to_one_named_development_fold(self) -> None:
        samples = [
            _sample("sample_a", "buying"),
            _sample("sample_b", "buying"),
            _sample("sample_c", "buying"),
        ]
        manifest = {
            "folds": {
                "fold_1": ["sample_a", "sample_c"],
                "fold_2": ["sample_b"],
            }
        }

        selected = filter_development_fold(samples, manifest, "fold_1")

        self.assertEqual([sample["sample_id"] for sample in selected], ["sample_a", "sample_c"])

    def test_v1_protocol_rejects_a_different_fold_count(self) -> None:
        samples = [_sample(f"buying_{index}", "buying") for index in range(8)]
        public_split = {
            "version": "public-split-v1",
            "development": [sample["sample_id"] for sample in samples],
            "holdout": [],
        }

        with self.assertRaisesRegex(ValueError, "fixed at 4"):
            build_development_fold_manifest(samples, public_split, fold_count=5)

    def test_builds_complete_disjoint_stratified_folds_from_development_ids(self) -> None:
        scenarios = ("buying", "browsing", "intent_override", "boundary")
        samples = [
            _sample(f"{scenario}_{index}", scenario)
            for scenario in scenarios
            for index in range(6)
        ]
        development_ids = [
            f"{scenario}_{index}"
            for scenario in scenarios
            for index in range(4)
        ]
        public_split = {
            "version": "public-split-v1",
            "development": development_ids,
            "holdout": [
                f"{scenario}_{index}"
                for scenario in scenarios
                for index in range(4, 6)
            ],
        }

        manifest = build_development_fold_manifest(samples, public_split)

        self.assertEqual(manifest["sample_count"], 16)
        self.assertEqual(manifest["fold_count"], 4)
        self.assertEqual(set(manifest["folds"]), {"fold_1", "fold_2", "fold_3", "fold_4"})
        self.assertEqual({len(ids) for ids in manifest["folds"].values()}, {4})
        self.assertEqual(
            set().union(*(set(ids) for ids in manifest["folds"].values())),
            set(development_ids),
        )
        fold_sets = [set(ids) for ids in manifest["folds"].values()]
        for index, left in enumerate(fold_sets):
            for right in fold_sets[index + 1:]:
                self.assertFalse(left & right)

        by_id = {sample["sample_id"]: sample["scenario_type"] for sample in samples}
        for fold_ids in manifest["folds"].values():
            counts = {scenario: 0 for scenario in scenarios}
            for sample_id in fold_ids:
                counts[by_id[sample_id]] += 1
            self.assertEqual(counts, {scenario: 1 for scenario in scenarios})

    def test_validation_rejects_an_id_assigned_to_multiple_folds(self) -> None:
        samples = [
            _sample("buying_1", "buying"),
            _sample("buying_2", "buying"),
        ]
        public_split = {
            "version": "public-split-v1",
            "development": ["buying_1", "buying_2"],
            "holdout": [],
        }
        manifest = {
            "version": "development-folds-v1",
            "public_split_version": "public-split-v1",
            "sample_count": 2,
            "fold_count": 2,
            "folds": {
                "fold_1": ["buying_1"],
                "fold_2": ["buying_1", "buying_2"],
            },
        }

        with self.assertRaisesRegex(ValueError, "assigned to multiple folds"):
            validate_development_fold_manifest(samples, public_split, manifest)

    def test_committed_manifest_matches_the_public_development_set(self) -> None:
        samples = [
            json.loads(line)
            for line in Path("data/public_set.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        public_split = json.loads(Path("docs/public_split_v1.json").read_text(encoding="utf-8"))
        committed = json.loads(Path("docs/development_folds_v1.json").read_text(encoding="utf-8"))

        rebuilt = build_development_fold_manifest(samples, public_split)

        self.assertEqual(committed, rebuilt)
        validate_development_fold_manifest(samples, public_split, committed)


if __name__ == "__main__":
    unittest.main()
