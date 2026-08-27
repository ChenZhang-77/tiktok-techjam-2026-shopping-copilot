from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRICS = (
    "hit_rate_at_10",
    "mrr",
    "mttc",
    "efficiency",
    "recommended_technical_score",
)


class A11ExtractionScopeEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/a11_extraction_scope_evidence.json").read_text(
                encoding="utf-8"
            )
        )
        cls.baseline = json.loads(
            (ROOT / cls.record["baseline"]["report"]).read_text(encoding="utf-8")
        )
        cls.candidate = json.loads(
            (ROOT / cls.record["candidate"]["report"]).read_text(encoding="utf-8")
        )

    def test_reports_are_hash_bound_clean_development_only_evidence(self) -> None:
        report_records = [
            self.record["baseline"],
            self.record["candidate"],
            self.record["failure_audit"],
            self.record["rejected_broad_candidate"],
            *self.record["fold_reports"].values(),
        ]
        for report in report_records:
            path = ROOT / report.get("report", report.get("path"))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), report["sha256"])

        self.assertEqual(self.candidate["code_provenance"]["commit"], "f40e265")
        self.assertTrue(self.candidate["code_provenance"]["worktree_clean"])
        self.assertEqual(self.candidate["evaluation"]["split"], "development")
        for report in [
            self.record["failure_audit"],
            *self.record["fold_reports"].values(),
        ]:
            payload = json.loads(
                (ROOT / report.get("report", report.get("path"))).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["code_provenance"]["commit"], "f40e265")
            self.assertTrue(payload["code_provenance"]["worktree_clean"])
        self.assertFalse(self.record["evaluation_boundary"]["full_or_holdout_used"])
        self.assertFalse(self.record["evaluation_boundary"]["target_information_in_runtime"])

    def test_development_metrics_gains_losses_and_folds_are_derived(self) -> None:
        for metric in METRICS:
            self.assertEqual(self.record["baseline"]["metrics"][metric], self.baseline[metric])
            self.assertEqual(self.record["candidate"]["metrics"][metric], self.candidate[metric])
            self.assertEqual(
                self.record["candidate"]["delta"][metric],
                round(self.candidate[metric] - self.baseline[metric], 6),
            )

        baseline_sessions = {item["sample_id"]: item for item in self.baseline["sessions"]}
        candidate_sessions = {item["sample_id"]: item for item in self.candidate["sessions"]}
        gained = sorted(
            sample_id
            for sample_id, before in baseline_sessions.items()
            if not before["hit"] and candidate_sessions[sample_id]["hit"]
        )
        lost = sorted(
            sample_id
            for sample_id, before in baseline_sessions.items()
            if before["hit"] and not candidate_sessions[sample_id]["hit"]
        )
        self.assertEqual(self.record["candidate"]["gained_session_ids"], gained)
        self.assertEqual(self.record["candidate"]["lost_session_ids"], lost)
        self.assertEqual((len(gained), len(lost)), (19, 3))
        session_bytes = json.dumps(
            self.candidate["sessions"], sort_keys=True, separators=(",", ":")
        ).encode()
        self.assertEqual(
            hashlib.sha256(session_bytes).hexdigest(),
            self.record["candidate"]["session_outcome_sha256"],
        )

        for index in range(1, 5):
            fold_name = f"fold_{index}"
            baseline = json.loads(
                (ROOT / f"docs/a8_reports/{fold_name}_structured.json").read_text(
                    encoding="utf-8"
                )
            )
            candidate = json.loads(
                (ROOT / self.record["fold_reports"][fold_name]["path"]).read_text(
                    encoding="utf-8"
                )
            )
            delta = round(
                candidate["recommended_technical_score"]
                - baseline["recommended_technical_score"],
                6,
            )
            self.assertEqual(self.record["fixed_fold_score_deltas"][fold_name], delta)
            self.assertGreater(delta, 0.0)

    def test_failure_audit_and_bounded_runtime_disposition_are_explicit(self) -> None:
        audit = json.loads(
            (ROOT / self.record["failure_audit"]["path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(audit["miss_count"], self.record["failure_audit"]["miss_count_after"])
        self.assertEqual(
            audit["failure_summary"]["primary_cause_counts"]["extraction"],
            self.record["failure_audit"]["primary_extraction_after"],
        )
        self.assertEqual(self.record["experiment"]["decision"], "retain_bounded_extraction_scope")
        self.assertFalse(self.record["evaluation_boundary"]["shared_contract_changed"])
        self.assertFalse(self.record["evaluation_boundary"]["question_policy_changed"])
        self.assertIn("broad_catalog_feature_vocabulary", self.record["rejected_or_deferred_scope"])
        for disposition in self.record["rejected_or_deferred_scope"].values():
            if disposition.startswith("not retained"):
                self.assertIn("unproven", disposition)
        self.assertLess(self.record["scenario_score_deltas"]["boundary"], 0.0)
        self.assertEqual(
            self.record["next_module"],
            "AB1 Shared Contract and Active-Route Semantics Freeze",
        )


if __name__ == "__main__":
    unittest.main()
