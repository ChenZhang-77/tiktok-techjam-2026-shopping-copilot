from __future__ import annotations

import copy
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


def _abstain_annotations(
    items: list[dict],
    *,
    annotator_id: str = "member_b",
) -> list[dict]:
    return [
        {
            "item_id": item["item_id"],
            "annotator_id": annotator_id,
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
        for item in items
    ]


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

    def test_override_without_value_items_are_natural_multiword_requests(self) -> None:
        override_items = [
            item
            for item in self.items
            if item["trigger_type"] == "override_without_value"
        ]

        self.assertEqual(len(override_items), 10)
        for item in override_items:
            with self.subTest(item_id=item["item_id"]):
                words = re.findall(r"[A-Za-z0-9']+", item["current_message"])
                self.assertGreaterEqual(
                    len(words),
                    5,
                    f'{item["item_id"]} should be a natural request, not a cue word',
                )

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

    def test_validator_accepts_multiword_use_case_no_preference(self) -> None:
        items = copy.deepcopy(self.items)
        items[0]["current_message"] = "Any use case is fine; show me some ideas."
        items[0]["prior_state"] = {
            "intent": None,
            "active_constraints": [],
            "rejected_constraints": [],
            "no_preference_attributes": [],
        }
        annotations = _abstain_annotations(items)
        annotations[0]["label"] = {
            "intent_hint": "browsing",
            "positive_constraints": [],
            "rejected_constraints": [],
            "no_preference_attributes": ["use_case"],
            "override_attributes": [],
            "semantic_terms": [],
            "abstain": False,
        }

        summary = validate_annotation_pack(items, annotations)

        self.assertEqual(summary["annotation_count"], 60)

    def test_validator_supports_closed_vocabulary_mixed_polarity_examples(self) -> None:
        items = copy.deepcopy(self.items)
        synthetic_messages = (
            "Any color is fine, but it must be wool.",
            "I need a coat, but avoid gothic styles.",
            "I need shoes, but no suede and any brand is fine.",
        )
        for item, message in zip(items, synthetic_messages):
            item["current_message"] = message
            item["prior_state"] = {
                "intent": None,
                "active_constraints": [],
                "rejected_constraints": [],
                "no_preference_attributes": [],
            }
        annotations = _abstain_annotations(items)
        labels = (
            {
                "intent_hint": "buying",
                "positive_constraints": [
                    {
                        "attribute": "material",
                        "value": "wool",
                        "evidence_span": "wool",
                        "hard": True,
                    }
                ],
                "rejected_constraints": [],
                "no_preference_attributes": ["color"],
                "override_attributes": [],
                "semantic_terms": [],
                "abstain": False,
            },
            {
                "intent_hint": "buying",
                "positive_constraints": [
                    {
                        "attribute": "category",
                        "value": "coat",
                        "evidence_span": "coat",
                        "hard": True,
                    }
                ],
                "rejected_constraints": [
                    {
                        "attribute": "style",
                        "value": "gothic",
                        "evidence_span": "gothic",
                    }
                ],
                "no_preference_attributes": [],
                "override_attributes": [],
                "semantic_terms": [],
                "abstain": False,
            },
            {
                "intent_hint": "buying",
                "positive_constraints": [
                    {
                        "attribute": "category",
                        "value": "shoes",
                        "evidence_span": "shoes",
                        "hard": True,
                    }
                ],
                "rejected_constraints": [
                    {
                        "attribute": "material",
                        "value": "suede",
                        "evidence_span": "suede",
                    }
                ],
                "no_preference_attributes": ["brand"],
                "override_attributes": [],
                "semantic_terms": [],
                "abstain": False,
            },
        )
        for index, label in enumerate(labels):
            annotations[index]["label"] = label

        summary = validate_annotation_pack(items, annotations)

        self.assertEqual(summary["annotation_count"], 60)

    def test_boundary_items_are_lexically_diverse_and_avoid_bad_templates(self) -> None:
        messages = {
            item["item_id"]: item["current_message"]
            for item in self.items
        }
        remaining_messages = list(messages.values())[10:]
        self.assertEqual(len(remaining_messages), len(set(remaining_messages)))
        self.assertTrue(
            all(
                len(re.findall(r"[A-Za-z0-9']+", message)) >= 5
                for message in remaining_messages
            )
        )
        rendered = "\n".join(remaining_messages).lower()
        for banned in (
            "formal styles",
            "no mesh",
            "although,",
            "any use case is fine",
        ):
            self.assertNotIn(banned, rendered)

        residual_messages = [
            item["current_message"].lower()
            for item in self.items
            if item["trigger_type"] == "low_confidence_residual_feature"
        ]
        self.assertLessEqual(
            sum("something" in message for message in residual_messages),
            2,
        )

        conflict_messages = [
            item["current_message"].lower()
            for item in self.items
            if item["trigger_type"] == "positive_rejected_attribute_conflict"
        ]
        connectors = {
            connector
            for connector in (";", "although", "but", "except", "however", "while", "yet")
            if any(connector in message for message in conflict_messages)
        }
        self.assertGreaterEqual(len(connectors), 5)

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

        duplicated_semantic_term = abstain_rows()
        duplicated_semantic_term[lrf_index]["label"] = {
            "intent_hint": None,
            "positive_constraints": [
                {
                    "attribute": "feature",
                    "value": "packability",
                    "evidence_span": "Packability",
                    "hard": False,
                }
            ],
            "rejected_constraints": [],
            "no_preference_attributes": [],
            "override_attributes": [],
            "semantic_terms": ["packability"],
            "abstain": False,
        }
        with self.assertRaisesRegex(AnnotationPackError, "duplicates structured"):
            validate_annotation_pack(self.items, duplicated_semantic_term)

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
            self.assertRegex(
                page,
                r'const STORAGE_KEY = "a13-annotation-pack-v1-draft-[0-9a-f]{12}";',
            )
            self.assertNotIn("fetch(", page)
            self.assertNotIn("https://", page)
            self.assertNotIn("触发原因", page)
            self.assertNotIn('id="trigger"', page)

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
                "feature 与 semantic_terms 的边界",
                "最小完整属性短语",
                "触发类型不会显示",
                "为什么这样标",
                "不要这样标",
            ):
                self.assertIn(expected, examples)
            self.assertIn("Show me ideas for a graduation gift.", examples)
            self.assertIn('"semantic_terms": ["graduation gift"]', examples)
            self.assertIn(
                '{"attribute":"feature","value":"quiet when it moves"',
                examples,
            )
            self.assertNotIn("https://", examples)

    def test_no_preference_override_example_matches_the_validator(self) -> None:
        current_message = "Actually, any material is fine now."
        examples = (PACK / "标注示例.html").read_text(encoding="utf-8")
        self.assertIn(current_message, examples)

        items = copy.deepcopy(self.items)
        items[0]["current_message"] = current_message
        items[0]["prior_state"] = {
            "intent": "buying",
            "active_constraints": [{"attribute": "material", "value": "cotton"}],
            "rejected_constraints": [],
            "no_preference_attributes": [],
        }
        annotations = [
            {
                "item_id": item["item_id"],
                "annotator_id": "example_reviewer",
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
            for item in items
        ]
        annotations[0]["label"] = {
            "intent_hint": None,
            "positive_constraints": [],
            "rejected_constraints": [],
            "no_preference_attributes": ["material"],
            "override_attributes": ["material"],
            "semantic_terms": [],
            "abstain": False,
        }

        summary = validate_annotation_pack(items, annotations)
        self.assertEqual(summary["annotation_count"], 60)

    def test_feature_and_semantic_term_examples_match_the_validator(self) -> None:
        items = copy.deepcopy(self.items)
        items[0]["current_message"] = "Show me something quiet when it moves."
        items[0]["prior_state"] = {
            "intent": "browsing",
            "active_constraints": [],
            "rejected_constraints": [],
            "no_preference_attributes": [],
        }
        items[1]["current_message"] = "Show me ideas for a graduation gift."
        items[1]["prior_state"] = {
            "intent": None,
            "active_constraints": [],
            "rejected_constraints": [],
            "no_preference_attributes": [],
        }
        annotations = [
            {
                "item_id": item["item_id"],
                "annotator_id": "example_reviewer",
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
            for item in items
        ]
        annotations[0]["label"] = {
            "intent_hint": "browsing",
            "positive_constraints": [
                {
                    "attribute": "feature",
                    "value": "quiet when it moves",
                    "evidence_span": "quiet when it moves",
                    "hard": True,
                }
            ],
            "rejected_constraints": [],
            "no_preference_attributes": [],
            "override_attributes": [],
            "semantic_terms": [],
            "abstain": False,
        }
        annotations[1]["label"] = {
            "intent_hint": "browsing",
            "positive_constraints": [],
            "rejected_constraints": [],
            "no_preference_attributes": [],
            "override_attributes": [],
            "semantic_terms": ["graduation gift"],
            "abstain": False,
        }

        summary = validate_annotation_pack(items, annotations)
        self.assertEqual(summary["annotation_count"], 60)


if __name__ == "__main__":
    unittest.main()
