from __future__ import annotations

import json
import unittest
from pathlib import Path


class B0BaselineRecordTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
