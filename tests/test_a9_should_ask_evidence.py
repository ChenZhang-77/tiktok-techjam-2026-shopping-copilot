from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRICS = ("hit_rate_at_10", "mrr", "mttc", "efficiency", "recommended_technical_score")


class A9ShouldAskEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/a9_should_ask_evidence.json").read_text(encoding="utf-8")
        )
        cls.baseline = json.loads(
            (ROOT / cls.record["reports"]["baseline"]["path"]).read_text(encoding="utf-8")
        )
        cls.candidate = json.loads(
            (ROOT / cls.record["reports"]["candidate"]["path"]).read_text(encoding="utf-8")
        )

    def test_reports_are_hash_bound_and_candidate_run_was_clean(self) -> None:
        for report in self.record["reports"].values():
            path = ROOT / report["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), report["sha256"])
        self.assertEqual(self.candidate["code_provenance"]["commit"], "30765cd")
        self.assertTrue(self.candidate["code_provenance"]["worktree_clean"])
        self.assertEqual(self.candidate["evaluation"]["split"], "development")

    def test_metric_deltas_are_exact_and_fail_the_keep_gate(self) -> None:
        for metric in METRICS:
            expected = round(self.candidate[metric] - self.baseline[metric], 6)
            self.assertEqual(self.record["development_160"]["delta"][metric], expected)
        self.assertLess(self.record["development_160"]["delta"]["hit_rate_at_10"], 0)
        self.assertGreater(self.record["development_160"]["delta"]["mttc"], 0)
        self.assertEqual(self.record["development_160"]["gained_sessions"], [])
        self.assertEqual(
            self.record["development_160"]["lost_sessions"],
            ["public_0097", "public_0098"],
        )

    def test_rejected_runtime_and_evaluation_boundaries_are_explicit(self) -> None:
        self.assertEqual(self.record["runtime_disposition"], "reverted")
        self.assertEqual(self.record["decision"], "reject_and_revert")
        self.assertFalse(self.record["candidate_rule"]["score_margin_used"])
        self.assertFalse(self.record["candidate_rule"]["target_or_evaluator_label_used_at_runtime"])
        self.assertEqual(self.record["candidate_rule"]["shared_contract_change"], "none")
        self.assertEqual(self.record["holdout_status"], "not run during A9")
        self.assertEqual(self.record["full_status"], "not run during A9")
        self.assertEqual(self.record["next_module"], "A10a Candidate Question Value")


if __name__ == "__main__":
    unittest.main()
