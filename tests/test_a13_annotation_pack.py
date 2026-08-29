from __future__ import annotations

import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from experiments.build_a13_annotation_bundle import build_annotation_bundle
from experiments.a13_annotation_trigger_audit import (
    validate_runtime_trigger_assignments,
)
from experiments.a13_annotation_pack import (
    ALLOWED_ATTRIBUTES as PACK_ALLOWED_ATTRIBUTES,
    CLOSED_ALLOWED_VALUES,
    AnnotationPackError,
    compare_annotation_sets,
    load_jsonl,
    validate_annotation_pack,
    validate_items,
)
from starter.core.context_engine import (
    CATEGORY_TERMS,
    COLORS,
    MATERIALS,
    STYLE_TERMS,
    USE_CASES,
)
from starter.core.semantic_understanding import ALLOWED_ATTRIBUTES


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "experiments/fixtures/a13_annotation_pack_v1"


class A13AnnotationPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.items = load_jsonl(PACK / "items.jsonl")
        cls.template = load_jsonl(PACK / "annotations.template.jsonl")

    def test_shared_items_cover_the_frozen_trigger_distribution_without_labels(self) -> None:
        summary = validate_items(self.items)

        self.assertEqual(summary["item_count"], 60)
        self.assertEqual(
            summary["trigger_counts"],
            {
                "low_confidence_residual_feature": 20,
                "mixed_polarity_clause": 10,
                "multi_clause_without_structure": 10,
                "override_without_value": 10,
                "positive_rejected_attribute_conflict": 10,
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
        self.assertEqual(summary["annotation_count"], 60)
        self.assertEqual(summary["abstain_count"], 60)

    def test_every_declared_stratum_is_reproduced_by_the_runtime_gate(self) -> None:
        summary = validate_runtime_trigger_assignments(
            self.items,
            ROOT / "data/catalog.jsonl",
        )

        self.assertEqual(summary["item_count"], 60)
        self.assertEqual(summary["assigned_trigger_matches"], 60)
        self.assertEqual(summary["mismatches"], [])
        self.assertEqual(
            summary["catalog_sha256"],
            "da979b05a68af864cb0dcf9ee6a81c010c7e66a57978ad286c7a2e005fc69a67",
        )

    def test_standalone_closed_vocabulary_matches_the_runtime_contract(self) -> None:
        self.assertEqual(PACK_ALLOWED_ATTRIBUTES, ALLOWED_ATTRIBUTES)
        self.assertEqual(CLOSED_ALLOWED_VALUES["category"], frozenset(CATEGORY_TERMS))
        self.assertEqual(CLOSED_ALLOWED_VALUES["material"], frozenset(MATERIALS))
        self.assertEqual(CLOSED_ALLOWED_VALUES["color"], frozenset(COLORS))
        self.assertEqual(CLOSED_ALLOWED_VALUES["style"], frozenset(STYLE_TERMS))
        self.assertEqual(CLOSED_ALLOWED_VALUES["use_case"], frozenset(USE_CASES))
        self.assertEqual(
            CLOSED_ALLOWED_VALUES["size"],
            frozenset(
                {
                    "xxs", "xs", "s", "m", "l", "xl", "xxl", "xxxl",
                    "small", "medium", "large", "wide", "narrow",
                }
            ),
        )

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

        empty_non_abstain = abstain_rows()
        empty_non_abstain[0]["label"]["abstain"] = False
        with self.assertRaisesRegex(AnnotationPackError, "empty non-abstain"):
            validate_annotation_pack(self.items, empty_non_abstain)

        disallowed_closed_value = abstain_rows()
        lrf_index = next(
            index
            for index, item in enumerate(self.items)
            if item["item_id"] == "LRF-001"
        )
        disallowed_closed_value[lrf_index]["label"] = {
            "intent_hint": None,
            "positive_constraints": [
                {
                    "attribute": "material",
                    "value": "packable",
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
        with self.assertRaisesRegex(AnnotationPackError, "allowed_values"):
            validate_annotation_pack(self.items, disallowed_closed_value)

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
        right[0]["label"]["intent_hint"] = "buying"
        right[0]["label"]["abstain"] = False

        comparison = compare_annotation_sets(self.items, left, right)

        self.assertEqual(comparison["agreement_count"], 59)
        self.assertEqual(comparison["disagreement_count"], 1)
        self.assertEqual(comparison["disagreements"][0]["item_id"], "OWV-001")

    def test_built_zip_is_standalone_and_validates_its_shared_items(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "a13_annotation_pack_v1.zip"
            summary = build_annotation_bundle(ROOT, output)
            self.assertEqual(summary["item_count"], 60)
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
            self.assertIn('"item_count": 60', completed.stdout)

    def test_built_zip_contains_a_double_click_offline_annotation_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "a13_annotation_pack_v1.zip"
            build_annotation_bundle(ROOT, output)

            with zipfile.ZipFile(output) as archive:
                page = archive.read(
                    "a13_annotation_pack_v1/开始标注.html"
                ).decode("utf-8")

            match = re.search(
                r'<script id="a13-items" type="application/json">(.*?)</script>',
                page,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(match)
            embedded_items = json.loads(match.group(1))
            self.assertEqual(
                [item["item_id"] for item in embedded_items],
                [item["item_id"] for item in self.items],
            )
            self.assertIn("localStorage", page)
            self.assertIn("downloadAnnotations", page)
            self.assertIn("下载 JSONL", page)
            self.assertNotIn("fetch(", page)
            self.assertNotIn("https://", page)

    def test_built_zip_contains_clear_double_click_annotation_examples(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "a13_annotation_pack_v1.zip"
            build_annotation_bundle(ROOT, output)

            with zipfile.ZipFile(output) as archive:
                examples = archive.read(
                    "a13_annotation_pack_v1/标注示例.html"
                ).decode("utf-8")

            for expected in (
                "先判断是否应该 abstain",
                "明确替换：标 override 和新值",
                "无偏好与排除值可以共存",
                "不完整的替换指令：必须 abstain",
                "同一个值既要又不要：必须 abstain",
                "evidence_span 与 value 的区别",
                "为什么这样标",
                "不要这样标",
            ):
                self.assertIn(expected, examples)
            self.assertNotIn("https://", examples)


if __name__ == "__main__":
    unittest.main()
