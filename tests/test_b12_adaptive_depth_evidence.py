from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "docs" / "b12_adaptive_depth_evidence.json"
METRICS = (
    "hit_rate_at_10",
    "mrr",
    "mttc",
    "efficiency",
    "recommended_technical_score",
)


def _load(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def _sha256(relative_path: str) -> str:
    return hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()


def _delta(candidate: dict, baseline: dict, field: str) -> float:
    return round(candidate[field] - baseline[field], 6)


class B12AdaptiveDepthEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = _load("docs/b12_adaptive_depth_evidence.json")
        cls.baseline = _load(cls.record["baseline"]["report"])
        cls.default = _load(cls.record["current_default_parity"]["report"])
        cls.candidate = _load(cls.record["candidate"]["report"])

    def test_decision_is_exploratory_because_predeclared_gates_are_absent(self) -> None:
        self.assertEqual(
            self.record["experiment"]["decision"],
            "do_not_retain_as_default_keep_reproducible_exploratory_option",
        )
        discipline = self.record["experiment_discipline"]
        self.assertFalse(discipline["predeclared_keep_gate_available"])
        self.assertFalse(discipline["predeclared_revert_gate_available"])
        self.assertTrue(discipline["aggregate_run_before_fixed_folds"])
        self.assertFalse(discipline["posthoc_thresholds_used_for_selection"])
        self.assertFalse(self.record["policy"]["default_enabled"])

    def test_report_provenance_split_and_flag_are_machine_derived(self) -> None:
        reports = [self.default, self.candidate]
        reports.extend(
            _load(item["candidate_path"])
            for item in self.record["fold_reports"].values()
        )
        for report in reports:
            self.assertEqual(report["code_provenance"]["commit"], "46a9c53")
            self.assertTrue(report["code_provenance"]["worktree_clean"])
            self.assertEqual(report["evaluation"]["split"], "development")
        self.assertFalse(self.default["evaluation"]["adaptive_depth_enabled"])
        self.assertTrue(self.candidate["evaluation"]["adaptive_depth_enabled"])
        for fold_name, item in self.record["fold_reports"].items():
            report = _load(item["candidate_path"])
            self.assertTrue(report["evaluation"]["adaptive_depth_enabled"])
            self.assertEqual(report["evaluation"]["development_fold"], fold_name)

    def test_default_parity_and_aggregate_deltas_derive_from_raw_reports(self) -> None:
        self.assertEqual(
            {field: self.default[field] for field in METRICS},
            {field: self.baseline[field] for field in METRICS},
        )
        self.assertEqual(self.default["scenario_metrics"], self.baseline["scenario_metrics"])
        self.assertEqual(self.default["sessions"], self.baseline["sessions"])
        expected = self.record["candidate"]["delta_vs_b9"]
        self.assertEqual(
            {field: _delta(self.candidate, self.baseline, field) for field in METRICS},
            expected,
        )
        self.assertEqual(
            {field: self.candidate[field] for field in METRICS},
            self.record["candidate"]["metrics"],
        )

    def test_scenario_and_session_tradeoffs_derive_from_raw_reports(self) -> None:
        for scenario, expected in self.record["scenario_deltas"].items():
            self.assertEqual(
                {
                    field: _delta(
                        self.candidate["scenario_metrics"][scenario],
                        self.baseline["scenario_metrics"][scenario],
                        field,
                    )
                    for field in METRICS
                },
                expected,
            )
        baseline = {item["sample_id"]: item for item in self.baseline["sessions"]}
        candidate = {item["sample_id"]: item for item in self.candidate["sessions"]}
        changed = [key for key in baseline if baseline[key] != candidate[key]]
        session_record = self.record["session_changes"]
        self.assertEqual(changed, list(session_record["details"]))
        self.assertEqual(len(changed), session_record["changed"])
        self.assertEqual(
            sum(not baseline[key]["hit"] and candidate[key]["hit"] for key in changed),
            session_record["gained_hits"],
        )
        self.assertEqual(
            sum(baseline[key]["hit"] and not candidate[key]["hit"] for key in changed),
            session_record["lost_hits"],
        )
        self.assertEqual((baseline["public_0135"]["best_rank"], candidate["public_0135"]["best_rank"]), (4, 6))
        self.assertEqual((baseline["public_0178"]["first_hit_turn"], candidate["public_0178"]["first_hit_turn"]), (7, 5))
        self.assertEqual((baseline["public_0178"]["best_rank"], candidate["public_0178"]["best_rank"]), (7, 9))

    def test_fold_deltas_and_both_sides_are_hash_bound(self) -> None:
        for fold_name, item in self.record["fold_reports"].items():
            self.assertEqual(_sha256(item["baseline_path"]), item["baseline_sha256"])
            self.assertEqual(_sha256(item["candidate_path"]), item["candidate_sha256"])
            baseline = _load(item["baseline_path"])
            candidate = _load(item["candidate_path"])
            self.assertEqual(
                {
                    "hit_rate_delta": _delta(candidate, baseline, "hit_rate_at_10"),
                    "mrr_delta": _delta(candidate, baseline, "mrr"),
                    "mttc_delta": _delta(candidate, baseline, "mttc"),
                    "technical_score_delta": _delta(
                        candidate, baseline, "recommended_technical_score"
                    ),
                },
                {
                    key: item[key]
                    for key in (
                        "hit_rate_delta",
                        "mrr_delta",
                        "mttc_delta",
                        "technical_score_delta",
                    )
                },
                fold_name,
            )

    def test_hashes_cost_and_runtime_counts_derive_from_raw_reports(self) -> None:
        for section in ("baseline", "current_default_parity", "candidate"):
            item = self.record[section]
            self.assertEqual(_sha256(item["report"]), item["sha256"])
        default_pool = self.default["retrieval_diagnostics"]["route_candidate_counts"]["lexical"]
        candidate_pool = self.candidate["retrieval_diagnostics"]["route_candidate_counts"]["lexical"]
        cost = self.record["cost"]
        self.assertEqual(default_pool["response_count"], cost["default_response_count"])
        self.assertEqual(candidate_pool["response_count"], cost["candidate_response_count"])
        self.assertEqual(default_pool["mean"], cost["default_observed_lexical_candidate_mean"])
        self.assertEqual(candidate_pool["mean"], cost["candidate_observed_lexical_candidate_mean"])
        self.assertEqual(round(candidate_pool["mean"] - default_pool["mean"], 6), cost["observed_mean_delta"])
        self.assertFalse(cost["controlled_latency_or_memory_claim"])
        observations = self.record["runtime_observations"]
        diagnostics = self.candidate["retrieval_diagnostics"]
        counts = self.candidate["observed_run_counts"]
        self.assertEqual(diagnostics["executed_route_counts"]["dense"], observations["candidate_dense_executed_turns"])
        self.assertEqual(diagnostics["executed_route_counts"]["fusion"], observations["candidate_fusion_executed_turns"])
        self.assertEqual(len(diagnostics["route_failure_counts"]), observations["candidate_route_failures"])
        self.assertEqual(counts["respond_exceptions"], observations["candidate_respond_exceptions"])
        self.assertEqual(counts["invalid_response_payloads"], observations["candidate_invalid_response_payloads"])
        self.assertEqual(counts["reported_fallbacks"], observations["candidate_reported_fallbacks"])


if __name__ == "__main__":
    unittest.main()
