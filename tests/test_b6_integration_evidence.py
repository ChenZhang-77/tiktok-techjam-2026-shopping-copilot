from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from starter.agent import Agent


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {
    "ground_truth",
    "target",
    "target_asin",
    "target_parent_asin",
    "scenario_type",
    "difficulty_bucket",
    "intent_card",
    "behavior",
}


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value), set())
    return set()


class B6IntegrationEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads((ROOT / "docs/b6_integration_hardening.json").read_text())
        report_path = ROOT / cls.record["development_report"]["path"]
        cls.report_bytes = report_path.read_bytes()
        cls.report = json.loads(cls.report_bytes)

    def test_clean_development_report_preserves_retained_metrics(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.report_bytes).hexdigest(),
            self.record["development_report"]["sha256"],
        )
        self.assertEqual(self.report["code_provenance"]["commit"], self.record["run_code_commit"])
        self.assertTrue(self.report["code_provenance"]["worktree_clean"])
        retained = json.loads((ROOT / "docs/b2_reports/development_structured.json").read_text())
        for metric in ("hit_rate_at_10", "mrr", "mttc", "recommended_technical_score"):
            self.assertEqual(self.report[metric], retained[metric])
            self.assertEqual(self.record["development_160"][metric], retained[metric])

    def test_report_records_route_filter_cache_failure_and_cost_diagnostics(self) -> None:
        diagnostics = self.report["retrieval_diagnostics"]
        recorded = self.record["diagnostics"]
        self.assertEqual(
            diagnostics["route_candidate_counts"]["lexical"]["response_count"],
            recorded["lexical_route_response_count"],
        )
        self.assertEqual(
            diagnostics["route_candidate_counts"]["structured"]["response_count"],
            recorded["structured_route_response_count"],
        )
        for key in (
            "structured_filter_applied_responses",
            "relaxed_constraint_responses",
            "filtered_pool_step_count",
            "cache_state_counts",
            "route_failure_counts",
        ):
            self.assertEqual(diagnostics[key], recorded[key])
        cost = self.record["operational_cost"]
        self.assertEqual(cost["initialization_ms"], self.report["timing"]["initialization_ms"])
        self.assertEqual(cost["retrieval_mean_ms"], self.report["timing"]["retrieval"]["latency"]["mean_ms"])
        self.assertEqual(cost["peak_rss_bytes"], self.report["resources"]["peak_rss_bytes"])

    def test_live_agent_diagnostics_do_not_contain_evaluator_labels(self) -> None:
        rows = [
            {"parent_asin": "A", "title": "black leather walking shoes"},
            {"parent_asin": "B", "title": "white canvas walking shoes"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "catalog.jsonl"
            catalog.write_text("".join(json.dumps(row) + "\n" for row in rows))
            agent = Agent(catalog)
            agent.reset("diagnostic-fixture", {"summary": "anonymous"})
            response = agent.respond(
                "diagnostic-fixture",
                "I need black leather walking shoes",
                1,
                2,
            )

        self.assertFalse(_keys(response["diagnostics"]) & FORBIDDEN)

    def test_failure_matrix_and_split_boundary_are_frozen(self) -> None:
        self.assertEqual(len(self.record["deterministic_failure_fixtures"]), 6)
        self.assertEqual(self.record["holdout_status"], "not_run_during_b6")
        self.assertEqual(self.record["full_status"], "not_run_during_b6")
        self.assertFalse(self.record["control_plane_integration"]["route_weight_semantics_changed"])


if __name__ == "__main__":
    unittest.main()
