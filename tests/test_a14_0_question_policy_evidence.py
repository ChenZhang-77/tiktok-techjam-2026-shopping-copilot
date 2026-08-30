from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class A140QuestionPolicyEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/a14_0_question_policy_evidence.json").read_text(
                encoding="utf-8"
            )
        )

    def test_bound_inputs_and_reports_match_recorded_hashes(self) -> None:
        provenance = self.record["provenance"]
        for group in ("inputs", "run_artifacts"):
            for item in provenance[group].values():
                path = Path(item["path"])
                self.assertFalse(path.is_absolute())
                self.assertEqual(
                    hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                    item["sha256"],
                )
        # Runtime source hashes describe the historical f594601 snapshot. Later
        # behavior-neutral A14 slices may evolve those files; the clean report
        # provenance below binds the snapshot without freezing live sources.
        for item in provenance["runtime_sources"].values():
            self.assertFalse(Path(item["path"]).is_absolute())
            self.assertEqual(len(item["sha256"]), 64)

    def test_legacy_and_current_visible_traces_are_exactly_equal(self) -> None:
        artifacts = self.record["provenance"]["run_artifacts"]
        legacy = json.loads(
            (ROOT / artifacts["legacy_visible_trace"]["path"]).read_text(
                encoding="utf-8"
            )
        )
        audit = json.loads(
            (ROOT / artifacts["turn_audit"]["path"]).read_text(encoding="utf-8")
        )
        parity = self.record["visible_behavior_parity"]
        self.assertEqual(legacy["code_provenance"], {"commit": "2e4108a", "worktree_clean": True})
        self.assertEqual(audit["code_provenance"], {"commit": "f594601", "worktree_clean": True})
        self.assertTrue(audit["parity"]["exact"])
        self.assertEqual(audit["parity"], {
            "ask_attribute_mismatches": 0,
            "compared_turns": 649,
            "exact": True,
            "input_hashes_match": True,
            "message_mismatches": 0,
            "metric_parity": True,
            "recommendation_mismatches": 0,
            "session_shape_mismatches": 0,
            "turn_shape_mismatches": 0,
        })
        self.assertEqual(
            legacy["visible_response_trace_sha256"],
            parity["visible_response_trace_sha256"],
        )
        self.assertEqual(
            audit["visible_response_trace_sha256"],
            parity["visible_response_trace_sha256"],
        )
        self.assertEqual(audit["question_trace_sha256"], self.record["turn_audit"]["question_trace_sha256"])

    def test_turn_audit_is_complete_bounded_and_violation_free(self) -> None:
        audit_path = self.record["provenance"]["run_artifacts"]["turn_audit"]["path"]
        audit = json.loads((ROOT / audit_path).read_text(encoding="utf-8"))
        summary = audit["summary"]
        self.assertEqual(summary["session_count"], 160)
        self.assertEqual(summary["turn_count"], 649)
        self.assertEqual(summary["ask_count"] + summary["stop_count"], 649)
        self.assertEqual(summary["policy_violation_count"], 0)
        self.assertEqual(summary["policy_latency_ms"]["count"], 649)
        self.assertEqual(audit["protocol"]["behavior_parity_status"], "verified_exact")
        self.assertFalse(audit["protocol"]["full_or_holdout_used"])
        self.assertFalse(audit["protocol"]["candidate_ids_or_text_recorded"])
        self.assertFalse(audit["protocol"]["private_product_identifiers_recorded"])
        for session in audit["sessions"]:
            for turn in session["turns"]:
                self.assertEqual(turn["policy_version"], "a14-0-legacy-parity-v1")
                self.assertEqual(turn["mode"], "legacy_parity")
                self.assertEqual(turn["policy_flags"], [])
                self.assertGreaterEqual(turn["latency_ms"], 0)
                self.assertEqual(len(turn["message_sha256"]), 64)
                self.assertEqual(len(turn["recommendations_sha256"]), 64)
                self.assertEqual(len(turn["visible_response_sha256"]), 64)
        serialized = json.dumps(audit, sort_keys=True).lower()
        for forbidden in ("target_asin", "ground_truth", "candidate_text"):
            self.assertNotIn(forbidden, serialized)

    def test_metrics_folds_and_reliability_are_derived_from_raw_reports(self) -> None:
        artifacts = self.record["provenance"]["run_artifacts"]
        for evidence_name, artifact_name in (("development_160", "development"),):
            expected = self.record[evidence_name]
            raw = json.loads((ROOT / artifacts[artifact_name]["path"]).read_text(encoding="utf-8"))
            for evidence_key, report_key in (
                ("sample_count", "sample_count"),
                ("hit_rate_at_10", "hit_rate_at_10"),
                ("mrr", "mrr"),
                ("mttc", "mttc"),
                ("efficiency", "efficiency"),
                ("technical_score", "recommended_technical_score"),
            ):
                self.assertEqual(expected[evidence_key], raw[report_key])
            self.assertEqual(raw["timing"]["responses"]["response_count"], expected["response_count"])
            for key in ("respond_exceptions", "invalid_response_payloads", "reported_fallbacks"):
                self.assertEqual(raw["observed_run_counts"][key], expected[key])
        for fold_name, expected in self.record["folds"].items():
            raw = json.loads((ROOT / artifacts[fold_name]["path"]).read_text(encoding="utf-8"))
            for evidence_key, report_key in (
                ("sample_count", "sample_count"),
                ("hit_rate_at_10", "hit_rate_at_10"),
                ("mrr", "mrr"),
                ("mttc", "mttc"),
                ("efficiency", "efficiency"),
                ("technical_score", "recommended_technical_score"),
            ):
                self.assertEqual(expected[evidence_key], raw[report_key])

    def test_scope_and_next_slice_remain_guarded(self) -> None:
        boundaries = self.record["boundaries"]
        self.assertFalse(boundaries["runtime_behavior_changed"])
        self.assertFalse(boundaries["shared_contract_changed"])
        self.assertFalse(boundaries["route_weight_semantics_changed"])
        self.assertFalse(boundaries["state_mutation_order_changed"])
        self.assertEqual(boundaries["llm_calls"], 0)
        self.assertEqual(boundaries["full_or_holdout_runs"], 0)
        self.assertTrue(self.record["next_allowed_slice"].startswith("A14-1"))


if __name__ == "__main__":
    unittest.main()
