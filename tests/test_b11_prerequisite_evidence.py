from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class B11PrerequisiteEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/b11_prerequisite_evidence.json").read_text(
                encoding="utf-8"
            )
        )
        cls.report_path = ROOT / cls.record["current_r0_refresh"]["report"]
        cls.report_text = cls.report_path.read_text(encoding="utf-8")
        cls.report = json.loads(cls.report_text)

    def test_report_is_hash_bound_clean_and_development_only(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.report_path.read_bytes()).hexdigest(),
            self.record["current_r0_refresh"]["sha256"],
        )
        self.assertEqual(self.report["code_provenance"]["commit"], "6cf3948")
        self.assertTrue(self.report["code_provenance"]["worktree_clean"])
        self.assertFalse(self.report["protocol"]["full_or_holdout_used"])
        self.assertTrue(self.report["protocol"]["development_targets_used_offline_only"])

    def test_recall_is_not_a_primary_failure_bucket(self) -> None:
        summary = self.report["failure_summary"]
        self.assertEqual(summary["owner_counts"]["retrieval_ranking"], 0)
        self.assertEqual(
            summary["primary_cause_counts"],
            {"extraction": 4, "intent_strategy_routing": 16, "state_override": 2},
        )
        self.assertEqual(
            self.report["target_recall"]["retained_depth"],
            {"hits": 157, "recall": 0.98125, "sessions": 160},
        )
        self.assertEqual(self.record["decision"], "do_not_start_b11_prerequisite_not_met")

    def test_offline_report_contains_no_target_asin_value(self) -> None:
        target_ids = {
            str(row["ground_truth"]["parent_asin"])
            for line in (ROOT / "data/public_set.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            for row in [json.loads(line)]
        }
        self.assertFalse(target_ids.intersection(self.report_text))


if __name__ == "__main__":
    unittest.main()
