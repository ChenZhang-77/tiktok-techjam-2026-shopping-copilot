from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class A13S0OfflineEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            (ROOT / "docs/a13_s0_offline_evidence.json").read_text(encoding="utf-8")
        )

    def test_reports_are_hash_bound_clean_development_runs(self) -> None:
        for name, item in self.record["reports"].items():
            path = ROOT / item["path"]
            self.assertEqual(path.parts[-2], "a13_s0_reports")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
            report = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], name)
            self.assertEqual(
                report["code_provenance"],
                {"commit": "952803b", "worktree_clean": True},
            )
            self.assertEqual(report["inputs"], self.record["input_hashes"])
            semantic_config = dict(report["offline_semantic_config"])
            config_sha256 = semantic_config.pop("sha256")
            encoded = json.dumps(
                semantic_config,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            self.assertEqual(config_sha256, hashlib.sha256(encoded).hexdigest())
            self.assertEqual(
                config_sha256,
                self.record["offline_semantic_config_hashes"][name],
            )
            self.assertIsNone(semantic_config["transport"])
            self.assertIsNone(semantic_config["prompt_template"])
            self.assertEqual(report["boundaries"]["split"], "development")
            self.assertEqual(report["boundaries"]["sample_count"], 160)

    def test_all_modes_restore_the_bound_a13_comparator(self) -> None:
        baseline = json.loads(
            (ROOT / "docs/a13_0_reports/development.json").read_text(encoding="utf-8")
        )
        for item in self.record["reports"].values():
            report = json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
            evaluation = report["evaluation"]
            for key in (
                "sample_count",
                "hit_rate_at_10",
                "mrr",
                "mttc",
                "efficiency",
                "recommended_technical_score",
                "sessions",
            ):
                self.assertEqual(evaluation[key], baseline[key])
            for scenario, metrics in evaluation["scenario_metrics"].items():
                for key, value in metrics.items():
                    self.assertEqual(value, baseline["scenario_metrics"][scenario][key])
            self.assertEqual(report["shadow"]["public_response_mismatches"], 0)
            self.assertEqual(report["shadow"]["response_count"], 649)
            self.assertEqual(report["shadow"]["remote_api_calls"], 0)

    def test_disabled_no_key_and_fake_paths_have_the_expected_call_boundary(self) -> None:
        disabled = self._report("disabled")
        no_key = self._report("no_key")
        fake = self._report("fake")
        self.assertEqual(disabled["shadow"]["fake_backend_calls"], 0)
        self.assertEqual(disabled["shadow"]["fallback_reasons"], {"disabled": 649})
        self.assertEqual(no_key["shadow"]["fake_backend_calls"], 0)
        self.assertEqual(
            no_key["shadow"]["fallback_reasons"],
            {"ineligible": 582, "no_key": 67},
        )
        self.assertEqual(fake["shadow"]["fake_backend_calls"], 67)
        self.assertEqual(fake["shadow"]["backend_called_turns"], 67)
        self.assertEqual(fake["shadow"]["valid_delta_turns"], 67)
        self.assertEqual(fake["shadow"]["fallback_reasons"], {"ineligible": 582})
        self.assertLessEqual(
            fake["shadow"]["backend_called_turns"] / fake["shadow"]["response_count"],
            0.20,
        )

    def test_offline_stage_has_no_provider_or_evaluation_scope_drift(self) -> None:
        self.assertEqual(self.record["decision"], "offline_foundation_passed")
        boundaries = self.record["boundaries"]
        self.assertFalse(boundaries["llm_transport_implemented"])
        self.assertFalse(boundaries["api_key_read_or_logged"])
        self.assertEqual(boundaries["deepseek_api_calls"], 0)
        self.assertEqual(boundaries["full_or_holdout_runs"], 0)
        self.assertFalse(boundaries["semantic_delta_applied"])
        self.assertFalse(boundaries["shared_contract_changed"])
        self.assertFalse(boundaries["retrieval_ranking_changed"])
        self.assertFalse(boundaries["route_weight_semantics_changed"])
        self.assertFalse(self.record["next_gate"]["real_api_authorized"])
        self.assertFalse(self.record["next_gate"]["fixture_frozen"])
        self.assertFalse(self.record["next_gate"]["two_member_review_complete"])

    def _report(self, name: str) -> dict:
        path = ROOT / self.record["reports"][name]["path"]
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
