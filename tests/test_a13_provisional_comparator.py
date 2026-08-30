from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from experiments.a13_annotation_pack import load_jsonl
from experiments.a13_provisional_comparator import evaluate_provisional_comparator
from starter.core.context_engine import CatalogVocabulary


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "experiments/fixtures/a13_annotation_pack_v1"


def _item(
    item_id: str,
    trigger_type: str,
    message: str,
    *,
    prior_intent: str | None = None,
) -> dict:
    return {
        "item_id": item_id,
        "trigger_type": trigger_type,
        "prior_state": {
            "intent": prior_intent,
            "active_constraints": [],
            "rejected_constraints": [],
            "no_preference_attributes": [],
        },
        "current_message": message,
        "source": "independent_boundary_expression",
    }


def _annotation(item_id: str, label: dict) -> dict:
    return {
        "item_id": item_id,
        "annotator_id": "ai-provisional-adjudicator",
        "confidence": "medium",
        "label": label,
        "notes": "synthetic comparator test",
    }


class A13ProvisionalComparatorTest(unittest.TestCase):
    def test_reports_valid_exact_and_invalid_predictions_without_sanitizing_them(self) -> None:
        items = [
            _item(
                "MCS-T01",
                "multi_clause_without_structure",
                "Any color is fine; please browse some options.",
            ),
            _item(
                "PRC-T01",
                "positive_rejected_attribute_conflict",
                "I want black, but not black.",
                prior_intent="buying",
            ),
        ]
        annotations = [
            _annotation(
                "MCS-T01",
                {
                    "intent_hint": "browsing",
                    "positive_constraints": [],
                    "rejected_constraints": [],
                    "no_preference_attributes": ["color"],
                    "override_attributes": [],
                    "semantic_terms": [],
                    "abstain": False,
                },
            ),
            _annotation(
                "PRC-T01",
                {
                    "intent_hint": None,
                    "positive_constraints": [],
                    "rejected_constraints": [],
                    "no_preference_attributes": [],
                    "override_attributes": [],
                    "semantic_terms": [],
                    "abstain": True,
                },
            ),
        ]

        report = evaluate_provisional_comparator(
            items,
            annotations,
            CatalogVocabulary.empty(),
        )

        self.assertEqual(
            report["protocol"],
            {
                "status": "provisional_not_gold",
                "provider_or_candidate_authorized": False,
                "prediction_projection": "deterministic_request_fields_v1",
                "invalid_predictions_are_not_sanitized": True,
            },
        )
        self.assertEqual(
            report["summary"],
            {
                "item_count": 2,
                "exact_match_count": 1,
                "exact_match_rate": 0.5,
                "invalid_prediction_count": 1,
            },
        )
        self.assertEqual(
            report["by_trigger"],
            {
                "multi_clause_without_structure": {
                    "item_count": 1,
                    "exact_match_count": 1,
                    "invalid_prediction_count": 0,
                },
                "positive_rejected_attribute_conflict": {
                    "item_count": 1,
                    "exact_match_count": 0,
                    "invalid_prediction_count": 1,
                },
            },
        )
        self.assertEqual(
            report["field_exact"],
            {
                "abstain": {"count": 1, "rate": 0.5},
                "intent_hint": {"count": 1, "rate": 0.5},
                "no_preference_attributes": {"count": 2, "rate": 1.0},
                "override_attributes": {"count": 2, "rate": 1.0},
                "positive_constraints": {"count": 1, "rate": 0.5},
                "rejected_constraints": {"count": 1, "rate": 0.5},
                "semantic_terms": {"count": 2, "rate": 1.0},
            },
        )
        self.assertEqual(
            report["invalid_prediction_reasons"],
            {"positive/rejected conflict": 1},
        )
        self.assertEqual(
            report["applied_state_invariants"],
            {
                "positive_rejected_conflict_item_count": 0,
                "positive_rejected_conflict_items": [],
            },
        )
        rows = {row["item_id"]: row for row in report["items"]}
        self.assertEqual(rows["MCS-T01"]["prediction_status"], "valid")
        self.assertTrue(rows["MCS-T01"]["exact_match"])
        self.assertEqual(rows["PRC-T01"]["prediction_status"], "invalid")
        self.assertIn("positive/rejected conflict", rows["PRC-T01"]["validation_error"])
        self.assertEqual(
            rows["PRC-T01"]["applied_state_positive_rejected_conflicts"],
            [],
        )
        self.assertFalse(rows["PRC-T01"]["exact_match"])

    def test_cli_binds_valid_subset_and_input_hashes(self) -> None:
        items = load_jsonl(PACK / "items.jsonl")
        annotations = [
            _annotation(
                item["item_id"],
                {
                    "intent_hint": None,
                    "positive_constraints": [],
                    "rejected_constraints": [],
                    "no_preference_attributes": [],
                    "override_attributes": [],
                    "semantic_terms": [],
                    "abstain": True,
                },
            )
            for item in items[:2]
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            annotation_path = temporary / "annotations.jsonl"
            catalog_path = temporary / "catalog.jsonl"
            output_path = temporary / "report.json"
            annotation_path.write_text(
                "".join(json.dumps(row) + "\n" for row in annotations),
                encoding="utf-8",
            )
            annotation_sha256 = hashlib.sha256(annotation_path.read_bytes()).hexdigest()
            catalog_path.write_text(
                json.dumps({"categories": ["Shoes", "Sneakers"]}) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "experiments.a13_provisional_comparator",
                    "--items",
                    str(PACK / "items.jsonl"),
                    "--annotations",
                    str(annotation_path),
                    "--catalog",
                    str(catalog_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(report["summary"]["item_count"], 2)
        self.assertEqual(report["annotation_subset"]["annotation_count"], 2)
        self.assertEqual(report["annotation_subset"]["annotator_id"], "ai-provisional-adjudicator")
        self.assertEqual(
            report["input_sha256"]["annotations"],
            annotation_sha256,
        )
        self.assertIn("commit", report["code_provenance"])
        self.assertIn("worktree_clean", report["code_provenance"])


if __name__ == "__main__":
    unittest.main()
