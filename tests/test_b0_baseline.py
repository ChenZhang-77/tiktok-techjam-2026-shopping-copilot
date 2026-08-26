from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


class B0BaselineRecordTest(unittest.TestCase):
    def test_official_result_artifact_matches_recorded_provenance(self) -> None:
        baseline = json.loads(Path("docs/b0_development_baseline.json").read_text(encoding="utf-8"))
        artifact_path = Path(baseline["result_artifact"])
        artifact_bytes = artifact_path.read_bytes()
        artifact = json.loads(artifact_bytes)

        self.assertEqual(
            baseline["evaluation_command"],
            "python3 -m evaluator.local_evaluator --split development "
            "--output docs/b0_development_results.json",
        )
        self.assertEqual(
            artifact["evaluation"],
            {
                "dataset": "data/public_set.jsonl",
                "split": "development",
                "split_manifest": "docs/public_split_v1.json",
                "split_version": "public-split-v1",
            },
        )
        self.assertEqual(hashlib.sha256(artifact_bytes).hexdigest(), baseline["result_artifact_sha256"])

    def test_external_report_artifact_matches_recorded_provenance(self) -> None:
        baseline = json.loads(Path("docs/b0_development_baseline.json").read_text(encoding="utf-8"))
        artifact_bytes = Path(baseline["development_report_artifact"]).read_bytes()

        self.assertEqual(
            hashlib.sha256(artifact_bytes).hexdigest(),
            baseline["development_report_artifact_sha256"],
        )

    def test_every_scenario_records_all_official_score_components(self) -> None:
        baseline = json.loads(Path("docs/b0_development_baseline.json").read_text(encoding="utf-8"))

        expected_fields = {
            "sample_count",
            "hit_rate_at_10",
            "mrr",
            "mttc",
            "efficiency",
            "recommended_technical_score",
        }
        for scenario, metrics in baseline["scenario_metrics"].items():
            with self.subTest(scenario=scenario):
                self.assertEqual(set(metrics), expected_fields)

    def test_external_report_records_latency(self) -> None:
        report = json.loads(Path("docs/b0_development_report.json").read_text(encoding="utf-8"))

        self.assertGreater(report["timing"]["evaluation_wall_ms"], 0.0)
        expected_response_count = sum(
            session["first_hit_turn"] if session["hit"] else 10
            for session in report["sessions"]
        )
        self.assertEqual(report["timing"]["responses"]["response_count"], expected_response_count)


if __name__ == "__main__":
    unittest.main()
