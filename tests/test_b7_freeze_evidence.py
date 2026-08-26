from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from starter.retrieval.reranker import RerankerConfig


ROOT = Path(__file__).resolve().parents[1]


class B7FreezeEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((ROOT / "docs/b7_freeze_manifest.json").read_text())

    def test_frozen_inputs_and_evidence_hashes_match(self) -> None:
        expected = {
            "catalog_sha256": "data/catalog.jsonl",
            "public_set_sha256": "data/public_set.jsonl",
            "evaluator_sha256": "evaluator/local_evaluator.py",
            "public_split_sha256": "docs/public_split_v1.json",
            "development_folds_sha256": "docs/development_folds_v1.json",
        }
        for key, relative_path in expected.items():
            self.assertEqual(
                hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest(),
                self.manifest["frozen_inputs"][key],
            )
        for section in ("pre_freeze_development", "optional_reranker_clean_cache"):
            artifact = self.manifest[section]
            self.assertEqual(
                hashlib.sha256((ROOT / artifact["path"]).read_bytes()).hexdigest(),
                artifact["sha256"],
            )

    def test_runtime_default_and_ablation_decisions_are_frozen(self) -> None:
        runtime = self.manifest["runtime_default"]
        self.assertEqual(runtime["retrieval_mode"], "structured")
        self.assertTrue(runtime["constraint_rerank"])
        self.assertTrue(runtime["guarded_structured_filter"])
        self.assertFalse(runtime["dense_route"])
        self.assertFalse(runtime["fusion"])
        self.assertFalse(runtime["semantic_reranker"])
        retained = [item for item in self.manifest["ablations"] if item["decision"] == "retain_as_runtime_default"]
        self.assertEqual([item["name"] for item in retained], ["retained_structured"])

    def test_clean_cache_matches_current_reranker_configuration(self) -> None:
        cache = json.loads((ROOT / "docs/b7_clean_cache_reproduction.json").read_text())
        config = RerankerConfig()
        self.assertEqual(cache["model_id"], config.model_id)
        self.assertEqual(cache["model_revision"], config.model_revision)
        self.assertEqual(cache["candidate_limit"], config.candidate_limit)
        self.assertEqual(cache["timeout_ms"], config.timeout_ms)
        self.assertEqual(cache["snapshot_file_count"], 6)
        self.assertTrue(cache["validation"]["local_files_only"])
        self.assertTrue(cache["validation"]["smoke_score_is_finite"])

    def test_pre_run_freeze_snapshot_has_no_blocker_and_records_pending_run(self) -> None:
        review = self.manifest["review"]
        self.assertEqual(review["standards_hard_findings"], 0)
        self.assertEqual(review["spec_findings"], 0)
        self.assertEqual(review["blocking_findings"], 0)
        final_run = self.manifest["final_public_run"]
        self.assertEqual(final_run["status"], "pending_single_run_after_freeze_commit")
        self.assertFalse(final_run["separate_holdout_run"])


if __name__ == "__main__":
    unittest.main()
