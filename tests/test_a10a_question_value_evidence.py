from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from starter.core.clarification import CANDIDATE_TERMS, QUESTION_TEXT


ROOT = Path(__file__).resolve().parents[1]
METRICS = ("hit_rate_at_10", "mrr", "mttc", "efficiency", "recommended_technical_score")


class A10aQuestionValueEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/a10a_question_value_evidence.json").read_text(encoding="utf-8")
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
        self.assertEqual(self.candidate["code_provenance"]["commit"], "304a3d6")
        self.assertTrue(self.candidate["code_provenance"]["worktree_clean"])
        self.assertEqual(self.candidate["evaluation"]["split"], "development")

    def test_metric_deltas_fail_the_keep_gate(self) -> None:
        for metric in METRICS:
            expected = round(self.candidate[metric] - self.baseline[metric], 6)
            self.assertEqual(self.record["development_160"]["delta"][metric], expected)
        self.assertLess(self.record["development_160"]["delta"]["hit_rate_at_10"], 0)
        self.assertGreater(self.record["development_160"]["delta"]["mttc"], 0)
        self.assertEqual(self.record["development_160"]["gained_sessions"], [])
        self.assertEqual(self.record["development_160"]["lost_sessions"], ["public_0064"])

    def test_partition_coverage_and_runtime_disposition_are_explicit(self) -> None:
        audit = self.record["partition_coverage_audit"]
        self.assertEqual(audit["supported_attributes"], list(CANDIDATE_TERMS))
        self.assertEqual(
            audit["uncovered_question_attributes"],
            [attribute for attribute in QUESTION_TEXT if attribute not in CANDIDATE_TERMS],
        )
        self.assertEqual(audit["status"], "partial_not_comparable_across_all_question_attributes")
        self.assertEqual(self.record["runtime_disposition"], "reverted")
        self.assertEqual(self.record["decision"], "reject_and_revert")
        self.assertEqual(self.record["candidate_rule"]["shared_contract_change"], "none")
        self.assertFalse(self.record["candidate_rule"]["query_construction_changed"])
        self.assertEqual(self.record["holdout_status"], "not run during A10a")
        self.assertEqual(self.record["full_status"], "not run during A10a")
        self.assertEqual(self.record["next_module"], "A10b Internal QueryPlan")


if __name__ == "__main__":
    unittest.main()
