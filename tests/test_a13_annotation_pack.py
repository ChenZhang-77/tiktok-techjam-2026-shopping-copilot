from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from experiments.build_a13_annotation_bundle import build_annotation_bundle
from experiments.a13_annotation_pack import (
    AnnotationPackError,
    compare_annotation_sets,
    load_jsonl,
    validate_annotation_pack,
    validate_items,
)


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "experiments/fixtures/a13_annotation_pack_v1"


class A13AnnotationPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.items = load_jsonl(PACK / "items.jsonl")
        cls.template = load_jsonl(PACK / "annotations.template.jsonl")

    def test_shared_items_cover_the_frozen_trigger_distribution_without_labels(self) -> None:
        summary = validate_items(self.items)

        self.assertEqual(summary["item_count"], 70)
        self.assertEqual(
            summary["trigger_counts"],
            {
                "low_confidence_residual_feature": 20,
                "mixed_polarity_clause": 10,
                "multi_clause_without_structure": 10,
                "override_without_value": 10,
                "positive_rejected_attribute_conflict": 10,
                "unexplained_intent_transition": 10,
            },
        )
        rendered = json.dumps(self.items, sort_keys=True).lower()
        for forbidden in (
            "target_asin",
            "scenario_label",
            "recommendations",
            "future_turn",
            "gold_delta",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_template_matches_every_item_but_is_intentionally_not_a_valid_submission(self) -> None:
        self.assertEqual(
            [row["item_id"] for row in self.template],
            [row["item_id"] for row in self.items],
        )
        self.assertTrue(
            all(row["label"]["abstain"] is None for row in self.template)
        )

        with self.assertRaisesRegex(AnnotationPackError, "annotator_id"):
            validate_annotation_pack(self.items, self.template)

    def test_complete_abstain_submission_is_structurally_valid(self) -> None:
        annotations = [
            {
                "item_id": item["item_id"],
                "annotator_id": "member_b",
                "confidence": "high",
                "label": {
                    "intent_hint": None,
                    "positive_constraints": [],
                    "rejected_constraints": [],
                    "no_preference_attributes": [],
                    "override_attributes": [],
                    "semantic_terms": [],
                    "abstain": True,
                },
                "notes": "No safe delta.",
            }
            for item in self.items
        ]

        summary = validate_annotation_pack(self.items, annotations)

        self.assertEqual(summary["annotator_id"], "member_b")
        self.assertEqual(summary["annotation_count"], 70)
        self.assertEqual(summary["abstain_count"], 70)

    def test_validator_rejects_non_evidenced_span_and_incomplete_coverage(self) -> None:
        annotations = [
            {
                "item_id": self.items[0]["item_id"],
                "annotator_id": "member_b",
                "confidence": "high",
                "label": {
                    "intent_hint": "buying",
                    "positive_constraints": [
                        {
                            "attribute": "material",
                            "value": "leather",
                            "evidence_span": "not present in the message",
                            "hard": True,
                        }
                    ],
                    "rejected_constraints": [],
                    "no_preference_attributes": [],
                    "override_attributes": ["material"],
                    "semantic_terms": [],
                    "abstain": False,
                },
                "notes": "",
            }
        ]

        with self.assertRaisesRegex(AnnotationPackError, "coverage"):
            validate_annotation_pack(self.items, annotations)

        full = [dict(annotations[0]) for _ in self.items]
        for row, item in zip(full, self.items):
            row["item_id"] = item["item_id"]
        with self.assertRaisesRegex(AnnotationPackError, "evidence_span"):
            validate_annotation_pack(self.items, full)

    def test_validator_rejects_unnormalized_or_unsupported_state_changes(self) -> None:
        def abstain_rows() -> list[dict]:
            return [
                {
                    "item_id": item["item_id"],
                    "annotator_id": "member_b",
                    "confidence": "high",
                    "label": {
                        "intent_hint": None,
                        "positive_constraints": [],
                        "rejected_constraints": [],
                        "no_preference_attributes": [],
                        "override_attributes": [],
                        "semantic_terms": [],
                        "abstain": True,
                    },
                    "notes": "",
                }
                for item in self.items
            ]

        unnormalized = abstain_rows()
        lrf_index = next(
            index
            for index, item in enumerate(self.items)
            if item["item_id"] == "LRF-001"
        )
        unnormalized[lrf_index]["label"] = {
            "intent_hint": None,
            "positive_constraints": [
                {
                    "attribute": "feature",
                    "value": "Packable",
                    "evidence_span": "packable",
                    "hard": False,
                }
            ],
            "rejected_constraints": [],
            "no_preference_attributes": [],
            "override_attributes": [],
            "semantic_terms": [],
            "abstain": False,
        }
        with self.assertRaisesRegex(AnnotationPackError, "normalized"):
            validate_annotation_pack(self.items, unnormalized)

        unsupported_no_preference = abstain_rows()
        unsupported_no_preference[0]["label"] = {
            "intent_hint": None,
            "positive_constraints": [],
            "rejected_constraints": [],
            "no_preference_attributes": ["color"],
            "override_attributes": ["color"],
            "semantic_terms": [],
            "abstain": False,
        }
        with self.assertRaisesRegex(AnnotationPackError, "no-preference evidence"):
            validate_annotation_pack(self.items, unsupported_no_preference)

    def test_comparison_reports_only_label_disagreements_without_mutating_inputs(self) -> None:
        base_label = {
            "intent_hint": None,
            "positive_constraints": [],
            "rejected_constraints": [],
            "no_preference_attributes": [],
            "override_attributes": [],
            "semantic_terms": [],
            "abstain": True,
        }
        left = [
            {
                "item_id": item["item_id"],
                "annotator_id": "member_a",
                "confidence": "high",
                "label": dict(base_label),
                "notes": "",
            }
            for item in self.items
        ]
        right = [
            {**row, "annotator_id": "member_b", "label": dict(row["label"])}
            for row in left
        ]
        right[0]["label"]["abstain"] = False

        comparison = compare_annotation_sets(self.items, left, right)

        self.assertEqual(comparison["agreement_count"], 69)
        self.assertEqual(comparison["disagreement_count"], 1)
        self.assertEqual(comparison["disagreements"][0]["item_id"], "OWV-001")

    def test_built_zip_is_standalone_and_validates_its_shared_items(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "a13_annotation_pack_v1.zip"
            summary = build_annotation_bundle(ROOT, output)
            self.assertEqual(summary["item_count"], 70)
            self.assertTrue(output.is_file())

            with zipfile.ZipFile(output) as archive:
                members = set(archive.namelist())
                self.assertIn("a13_annotation_pack_v1/README.md", members)
                self.assertIn("a13_annotation_pack_v1/items.jsonl", members)
                self.assertIn(
                    "a13_annotation_pack_v1/annotations.template.jsonl",
                    members,
                )
                self.assertIn(
                    "a13_annotation_pack_v1/validate_annotations.py",
                    members,
                )
                archive.extractall(directory)

            extracted = Path(directory) / "a13_annotation_pack_v1"
            completed = subprocess.run(
                [
                    sys.executable,
                    "validate_annotations.py",
                    "validate-items",
                    "--items",
                    "items.jsonl",
                ],
                cwd=extracted,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('"item_count": 70', completed.stdout)


if __name__ == "__main__":
    unittest.main()
