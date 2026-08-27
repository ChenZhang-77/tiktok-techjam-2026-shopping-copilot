from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import fields
from pathlib import Path

from starter.core.decision_evidence import DecisionEvidence


ROOT = Path(__file__).resolve().parents[1]
METRICS = ("hit_rate_at_10", "mrr", "mttc", "efficiency", "recommended_technical_score")


class AB0DecisionEvidenceRecordTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads((ROOT / "docs/ab0_decision_evidence.json").read_text(encoding="utf-8"))
        cls.candidate = json.loads((ROOT / cls.record["raw_report"]["path"]).read_text(encoding="utf-8"))
        cls.baseline = json.loads((ROOT / cls.record["comparator_report"]["path"]).read_text(encoding="utf-8"))

    def test_field_inventory_covers_the_complete_runtime_type(self) -> None:
        runtime_fields = {item.name for item in fields(DecisionEvidence)}
        self.assertEqual(set(self.record["field_inventory"]), runtime_fields)
        for definition in self.record["field_inventory"].values():
            self.assertEqual(
                set(definition),
                {"producer", "type_range", "lifecycle", "fallback", "ownership", "seam"},
            )
            self.assertTrue(all(str(value).strip() for value in definition.values()))
        margin = self.record["field_inventory"]["score_margin_usable"]
        self.assertIn("false", margin["fallback"])

    def test_clean_report_is_hash_bound_and_exactly_matches_A8_behavior(self) -> None:
        for key in ("raw_report", "comparator_report"):
            item = self.record[key]
            self.assertEqual(hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest(), item["sha256"])
        self.assertEqual(self.candidate["code_provenance"]["commit"], self.record["run_code_commit"])
        self.assertTrue(self.candidate["code_provenance"]["worktree_clean"])
        self.assertEqual(self.candidate["evaluation"]["split"], "development")
        for metric in METRICS:
            self.assertEqual(self.candidate[metric], self.baseline[metric])
            self.assertEqual(self.record["development_160"]["metric_delta"][metric], 0.0)
        self.assertEqual(self.candidate["scenario_metrics"], self.baseline["scenario_metrics"])
        self.assertEqual(self.candidate["sessions"], self.baseline["sessions"])

    def test_dialogue_policy_and_contract_boundaries_are_explicit(self) -> None:
        parity = self.record["dialogue_parity"]
        self.assertEqual(parity["baseline_trace_sha256"], parity["candidate_trace_sha256"])
        self.assertEqual(parity["decision"], "exact_match")
        self.assertEqual(parity["session_count"], 160)
        self.assertEqual(parity["turn_count"], 818)
        self.assertEqual(self.record["shared_contract_change"], "none")
        self.assertEqual(self.record["decision"], "retain_A_side_decision_evidence_adapter")
        self.assertEqual(self.record["next_module"], "A9 Should-Ask Over-Generality Gate")
        self.assertEqual(self.record["holdout_status"], "not_run_during_AB0")
        self.assertEqual(self.record["full_status"], "not_run_during_AB0")


if __name__ == "__main__":
    unittest.main()
