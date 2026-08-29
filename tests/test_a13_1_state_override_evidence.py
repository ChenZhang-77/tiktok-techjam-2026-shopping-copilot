from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class A131StateOverrideEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/a13_1_state_override_evidence.json").read_text(
                encoding="utf-8"
            )
        )

    def test_reports_are_tracked_hash_bound_clean_development_runs(self) -> None:
        for item in self.record["provenance"]["reports"].values():
            path = Path(item["path"])
            self.assertFalse(path.is_absolute())
            self.assertEqual(path.parts[:2], ("docs", "a13_1_reports"))
            self.assertEqual(
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                item["sha256"],
            )

        candidate = self._report("candidate_development")
        reverted = self._report("reverted_development")
        self.assertEqual(
            candidate["code_provenance"],
            {"commit": "1cd1f05", "worktree_clean": True},
        )
        self.assertEqual(
            reverted["code_provenance"],
            {"commit": "19657e0", "worktree_clean": True},
        )
        self.assertEqual(candidate["evaluation"]["split"], "development")
        self.assertEqual(reverted["evaluation"]["split"], "development")

    def test_candidate_metrics_deltas_and_losses_derive_from_raw_reports(self) -> None:
        baseline = json.loads(
            (ROOT / "docs/a13_0_reports/development.json").read_text(encoding="utf-8")
        )
        candidate = self._report("candidate_development")
        recorded = self.record["development_160"]

        for evidence_key, report_key in (
            ("hit_rate_at_10", "hit_rate_at_10"),
            ("mrr", "mrr"),
            ("mttc", "mttc"),
            ("efficiency", "efficiency"),
            ("technical_score", "recommended_technical_score"),
        ):
            self.assertEqual(recorded["baseline"][evidence_key], baseline[report_key])
            self.assertEqual(recorded["candidate"][evidence_key], candidate[report_key])
            self.assertAlmostEqual(
                recorded["delta"][evidence_key],
                candidate[report_key] - baseline[report_key],
                places=6,
            )

        baseline_sessions = {item["sample_id"]: item for item in baseline["sessions"]}
        candidate_sessions = {item["sample_id"]: item for item in candidate["sessions"]}
        gained = sorted(
            sample_id
            for sample_id in baseline_sessions
            if not baseline_sessions[sample_id]["hit"]
            and candidate_sessions[sample_id]["hit"]
        )
        lost = sorted(
            sample_id
            for sample_id in baseline_sessions
            if baseline_sessions[sample_id]["hit"]
            and not candidate_sessions[sample_id]["hit"]
        )
        self.assertEqual(self.record["session_outcomes"]["gained"], gained)
        self.assertEqual(self.record["session_outcomes"]["lost"], lost)

    def test_all_four_folds_regress_and_revert_restores_exact_metrics(self) -> None:
        for index in range(1, 5):
            baseline = json.loads(
                (ROOT / f"docs/a13_0_reports/fold_{index}.json").read_text(
                    encoding="utf-8"
                )
            )
            candidate = self._report(f"candidate_fold_{index}")
            recorded = self.record["folds"][f"fold_{index}"]
            self.assertEqual(
                recorded["technical_score_delta"],
                round(
                    candidate["recommended_technical_score"]
                    - baseline["recommended_technical_score"],
                    6,
                ),
            )
            self.assertLess(recorded["technical_score_delta"], 0)

        baseline = json.loads(
            (ROOT / "docs/a13_0_reports/development.json").read_text(encoding="utf-8")
        )
        reverted = self._report("reverted_development")
        for key in (
            "sample_count",
            "hit_rate_at_10",
            "mrr",
            "mttc",
            "efficiency",
            "recommended_technical_score",
        ):
            self.assertEqual(reverted[key], baseline[key])

    def test_scenario_and_operational_summaries_derive_from_candidate_report(self) -> None:
        baseline = json.loads(
            (ROOT / "docs/a13_0_reports/development.json").read_text(encoding="utf-8")
        )
        candidate = self._report("candidate_development")
        intent_override = self.record["intent_override_scenario"]
        for evidence_key, report_key in (
            ("hit_rate_at_10", "hit_rate_at_10"),
            ("mrr", "mrr"),
            ("mttc", "mttc"),
            ("technical_score", "recommended_technical_score"),
        ):
            baseline_value = baseline["scenario_metrics"]["intent_override"][report_key]
            candidate_value = candidate["scenario_metrics"]["intent_override"][report_key]
            self.assertEqual(intent_override["baseline"][evidence_key], baseline_value)
            self.assertEqual(intent_override["candidate"][evidence_key], candidate_value)
            self.assertAlmostEqual(
                intent_override["delta"][evidence_key],
                candidate_value - baseline_value,
                places=6,
            )

        for scenario in self.record["unchanged_scenarios"]:
            self.assertEqual(
                candidate["scenario_metrics"][scenario],
                baseline["scenario_metrics"][scenario],
            )

        impact = self.record["operational_impact"]
        observed = candidate["observed_run_counts"]
        tokens = candidate["reported_token_usage"]
        responses = candidate["timing"]["responses"]
        self.assertEqual(impact["candidate_response_count"], responses["response_count"])
        self.assertEqual(impact["respond_exceptions"], observed["respond_exceptions"])
        self.assertEqual(
            impact["invalid_response_payloads"], observed["invalid_response_payloads"]
        )
        self.assertEqual(impact["reported_fallbacks"], observed["reported_fallbacks"])
        self.assertEqual(impact["prompt_tokens"], tokens["prompt_tokens"])
        self.assertEqual(impact["completion_tokens"], tokens["completion_tokens"])
        self.assertEqual(impact["candidate_response_mean_ms"], responses["mean_ms"])
        self.assertEqual(impact["candidate_response_p95_ms"], responses["p95_ms"])
        self.assertEqual(
            impact["candidate_initialization_ms"], candidate["timing"]["initialization_ms"]
        )
        self.assertEqual(
            impact["candidate_peak_rss_bytes"], candidate["resources"]["peak_rss_bytes"]
        )

    def test_state_goal_was_met_but_keep_gate_failed_without_llm_or_scope_drift(self) -> None:
        taxonomy = self._report("candidate_taxonomy")
        selected = {
            session["sample_id"]: session
            for session in taxonomy["sessions"]
            if session["sample_id"] in {"public_0002", "public_0096"}
        }
        self.assertEqual(set(selected), {"public_0002", "public_0096"})
        self.assertTrue(
            all(
                not turn["state_override_flags"]
                for session in selected.values()
                for turn in session["turns"]
                if turn["eligible"]
            )
        )
        self.assertEqual(self.record["decision"], "rejected_and_reverted")
        self.assertFalse(self.record["boundaries"]["shared_contract_changed"])
        self.assertFalse(self.record["boundaries"]["route_weight_semantics_changed"])
        self.assertFalse(self.record["boundaries"]["retrieval_ranking_changed"])
        self.assertFalse(self.record["boundaries"]["question_policy_changed"])
        self.assertEqual(self.record["boundaries"]["deepseek_api_calls"], 0)
        self.assertEqual(self.record["boundaries"]["full_or_holdout_runs"], 0)

    def _report(self, name: str) -> dict:
        path = ROOT / self.record["provenance"]["reports"][name]["path"]
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
