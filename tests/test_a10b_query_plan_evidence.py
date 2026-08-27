from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import fields
from pathlib import Path

from starter.core.query_builder import QueryPlan


ROOT = Path(__file__).resolve().parents[1]
METRICS = ("hit_rate_at_10", "mrr", "mttc", "efficiency", "recommended_technical_score")


class A10bQueryPlanEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/a10b_query_plan_evidence.json").read_text(encoding="utf-8")
        )
        cls.baseline = json.loads(
            (ROOT / cls.record["reports"]["baseline"]["path"]).read_text(encoding="utf-8")
        )
        cls.candidate = json.loads(
            (ROOT / cls.record["reports"]["candidate"]["path"]).read_text(encoding="utf-8")
        )

    def test_inventory_covers_the_runtime_query_plan(self) -> None:
        self.assertEqual(
            set(self.record["query_plan_inventory"]),
            {item.name for item in fields(QueryPlan)},
        )
        required = {"producer", "type_range", "lifecycle", "fallback", "rendering"}
        for definition in self.record["query_plan_inventory"].values():
            self.assertEqual(set(definition), required)
            self.assertTrue(all(str(value).strip() for value in definition.values()))

    def test_reports_are_hash_bound_and_development_outcomes_are_identical(self) -> None:
        for report in self.record["reports"].values():
            path = ROOT / report["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), report["sha256"])
        self.assertEqual(self.candidate["code_provenance"]["commit"], "9560344")
        self.assertTrue(self.candidate["code_provenance"]["worktree_clean"])
        self.assertEqual(self.candidate["evaluation"]["split"], "development")
        for metric in METRICS:
            self.assertEqual(self.candidate[metric], self.baseline[metric])
            self.assertEqual(self.record["development_160"]["metric_delta"][metric], 0.0)
        self.assertEqual(self.candidate["scenario_metrics"], self.baseline["scenario_metrics"])
        self.assertEqual(self.candidate["sessions"], self.baseline["sessions"])
        session_bytes = json.dumps(
            self.candidate["sessions"], sort_keys=True, separators=(",", ":")
        ).encode()
        self.assertEqual(
            hashlib.sha256(session_bytes).hexdigest(),
            self.record["development_160"]["session_outcome_sha256"],
        )

    def test_runtime_and_evaluation_boundaries_are_explicit(self) -> None:
        boundaries = self.record["behavior_boundaries"]
        self.assertFalse(boundaries["question_policy_changed"])
        self.assertFalse(boundaries["intent_or_state_semantics_changed"])
        self.assertFalse(boundaries["retrieval_request_shape_changed"])
        self.assertFalse(boundaries["target_or_evaluator_label_used_at_runtime"])
        self.assertEqual(boundaries["shared_contract_change"], "none")
        self.assertEqual(self.record["holdout_status"], "not run during A10b")
        self.assertEqual(self.record["full_status"], "not run during A10b")
        self.assertEqual(self.record["decision"], "retain_A_internal_query_plan")
        self.assertEqual(self.record["next_module"], "A11 Extraction and Scope Hardening")


if __name__ == "__main__":
    unittest.main()
