from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class R0FailureTaxonomyEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report_path = ROOT / "docs/r0_development_failure_taxonomy.json"
        cls.report_text = cls.report_path.read_text(encoding="utf-8")
        cls.report = json.loads(cls.report_text)

    def test_report_is_a_clean_development_only_run(self) -> None:
        self.assertEqual(self.report["version"], "r0-v2")
        self.assertEqual(self.report["sample_count"], 160)
        self.assertEqual(self.report["code_provenance"]["commit"], "0b9bc74")
        self.assertTrue(self.report["code_provenance"]["worktree_clean"])
        self.assertEqual(
            self.report["protocol"],
            {
                "development_targets_used_offline_only": True,
                "full_or_holdout_used": False,
                "runtime_behavior_changed": False,
                "target_identifiers_written_to_report": False,
            },
        )
        self.assertEqual(
            self.report["experiment_record"]["decision"],
            "retain_offline_audit_and_follow_dependency_order",
        )
        self.assertEqual(
            self.report["experiment_record"]["gained_lost_sessions"],
            {"gained": 0, "lost": 0, "reason": "no runtime behavior comparator"},
        )

    def test_all_misses_use_the_canonical_taxonomy_and_fixed_folds(self) -> None:
        self.assertEqual(self.report["hit_count"], 122)
        self.assertEqual(self.report["miss_count"], 38)
        self.assertEqual(
            self.report["failure_summary"]["primary_cause_counts"],
            {"extraction": 6, "intent_strategy_routing": 25, "state_override": 7},
        )
        self.assertEqual(
            {name: fold["sample_count"] for name, fold in self.report["fold_summary"].items()},
            {"fold_1": 40, "fold_2": 40, "fold_3": 40, "fold_4": 40},
        )

    def test_offline_report_contains_no_target_asin_value(self) -> None:
        target_ids = {
            str(row["ground_truth"]["parent_asin"])
            for line in (ROOT / "data/public_set.jsonl").read_text(encoding="utf-8").splitlines()
            for row in [json.loads(line)]
        }
        self.assertFalse(target_ids.intersection(self.report_text))

    def test_report_preserves_recall_evidence_and_dependency_order(self) -> None:
        self.assertEqual(
            self.report["target_recall"]["retained_depth"],
            {"hits": 145, "recall": 0.90625, "sessions": 160},
        )
        self.assertEqual(self.report["next_experiment"]["id"], "A8")


if __name__ == "__main__":
    unittest.main()
