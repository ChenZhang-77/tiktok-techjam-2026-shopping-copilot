from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from experiments.a13_ai_silver import (
    AISilverProtocolError,
    APPLIED_STATE_FIELDS,
    build_as0_preflight_report,
    build_role_artifact_bindings,
    canonical_item_collection_sha256,
    REACHABLE_TRIGGERS,
    apply_understanding_delta,
    audit_fresh_fixture,
    project_judge_input,
    resolve_ai_silver_consensus,
    serialize_applied_state_delta,
    summarize_semantic_gate,
    validate_role_manifest,
)
from starter.core.semantic_understanding import ConstraintProposal, UnderstandingDelta


ROOT = Path(__file__).resolve().parents[1]
SILVER_CONTRACT = ROOT / "experiments/fixtures/a13_ai_silver_v1"


def _proposal(attribute: str, value: str, *, hard: bool = True) -> ConstraintProposal:
    return ConstraintProposal(
        attribute=attribute,
        value=value,
        evidence_span=value,
        hard=hard,
    )


def _applied_projection(intent_after: str | None) -> dict:
    return {
        "schema_version": "applied_state_delta_v1",
        "intent_before": None,
        "intent_after": intent_after,
        "active_constraints_added": [],
        "active_constraints_deactivated": [],
        "rejected_constraints_added": [],
        "no_preference_attributes_added": [],
        "no_preference_attributes_removed": [],
        "override_attributes": [],
        "stale_values_deactivated": [],
    }


class AppliedStateDeltaTest(unittest.TestCase):
    def test_projects_one_validated_delta_through_production_state_semantics(self) -> None:
        prior_state = {
            "intent": "buying",
            "active_constraints": [
                {"attribute": "material", "value": "leather"},
                {"attribute": "color", "value": "black"},
            ],
            "rejected_constraints": [],
            "no_preference_attributes": ["size"],
        }
        delta = UnderstandingDelta(
            intent_hint="browsing",
            positive_constraints=(
                _proposal("material", "cotton"),
                _proposal("size", "large"),
            ),
            rejected_constraints=(_proposal("color", "black", hard=False),),
            no_preference_attributes=("brand",),
            override_attributes=("material",),
            semantic_terms=(),
            abstain=False,
        )

        projection = apply_understanding_delta(prior_state, delta)

        self.assertEqual(
            projection,
            {
                "schema_version": "applied_state_delta_v1",
                "intent_before": "buying",
                "intent_after": "browsing",
                "active_constraints_added": [
                    {"attribute": "material", "value": "cotton"},
                    {"attribute": "size", "value": "large"},
                ],
                "active_constraints_deactivated": [
                    {"attribute": "color", "value": "black"},
                    {"attribute": "material", "value": "leather"},
                ],
                "rejected_constraints_added": [
                    {"attribute": "color", "value": "black"},
                ],
                "no_preference_attributes_added": ["brand"],
                "no_preference_attributes_removed": ["size"],
                "override_attributes": ["material"],
                "stale_values_deactivated": [
                    {"attribute": "material", "value": "leather"},
                ],
            },
        )

    def test_serializer_is_canonical_when_proposal_order_differs(self) -> None:
        prior_state = {
            "intent": None,
            "active_constraints": [],
            "rejected_constraints": [],
            "no_preference_attributes": [],
        }
        first = UnderstandingDelta(
            intent_hint=None,
            positive_constraints=(
                _proposal("color", "black"),
                _proposal("material", "cotton"),
            ),
            rejected_constraints=(),
            no_preference_attributes=(),
            override_attributes=(),
            semantic_terms=(),
            abstain=False,
        )
        second = UnderstandingDelta(
            intent_hint=None,
            positive_constraints=tuple(reversed(first.positive_constraints)),
            rejected_constraints=(),
            no_preference_attributes=(),
            override_attributes=(),
            semantic_terms=(),
            abstain=False,
        )

        self.assertEqual(
            serialize_applied_state_delta(apply_understanding_delta(prior_state, first)),
            serialize_applied_state_delta(apply_understanding_delta(prior_state, second)),
        )

    def test_projection_rejects_extra_prior_constraint_fields(self) -> None:
        prior_state = {
            "intent": None,
            "active_constraints": [
                {"attribute": "color", "value": "black", "target_asin": "FORBIDDEN"}
            ],
            "rejected_constraints": [],
            "no_preference_attributes": [],
        }
        abstain = UnderstandingDelta(
            intent_hint=None,
            positive_constraints=(),
            rejected_constraints=(),
            no_preference_attributes=(),
            override_attributes=(),
            semantic_terms=(),
            abstain=True,
        )

        with self.assertRaisesRegex(
            AISilverProtocolError, "prior constraint fields do not match schema"
        ):
            apply_understanding_delta(prior_state, abstain)

    def test_rejected_only_override_deactivates_every_stale_attribute_value(self) -> None:
        prior_state = {
            "intent": "buying",
            "active_constraints": [
                {"attribute": "color", "value": "red"},
                {"attribute": "color", "value": "blue"},
            ],
            "rejected_constraints": [],
            "no_preference_attributes": [],
        }
        delta = UnderstandingDelta(
            intent_hint=None,
            positive_constraints=(),
            rejected_constraints=(_proposal("color", "blue", hard=False),),
            no_preference_attributes=(),
            override_attributes=("color",),
            semantic_terms=(),
            abstain=False,
        )

        projection = apply_understanding_delta(prior_state, delta)

        expected = [
            {"attribute": "color", "value": "blue"},
            {"attribute": "color", "value": "red"},
        ]
        self.assertEqual(projection["active_constraints_deactivated"], expected)
        self.assertEqual(projection["stale_values_deactivated"], expected)

    def test_category_override_records_all_dependent_stale_values(self) -> None:
        prior_state = {
            "intent": "buying",
            "active_constraints": [
                {"attribute": "category", "value": "shoes"},
                {"attribute": "color", "value": "red"},
            ],
            "rejected_constraints": [],
            "no_preference_attributes": [],
        }
        delta = UnderstandingDelta(
            intent_hint=None,
            positive_constraints=(_proposal("category", "bags"),),
            rejected_constraints=(),
            no_preference_attributes=(),
            override_attributes=("category",),
            semantic_terms=(),
            abstain=False,
        )

        projection = apply_understanding_delta(prior_state, delta)

        self.assertEqual(
            projection["stale_values_deactivated"],
            [
                {"attribute": "category", "value": "shoes"},
                {"attribute": "color", "value": "red"},
            ],
        )


def _role(
    role: str,
    provider: str,
    family: str,
    model_version: str,
    bindings: dict[str, dict[str, str]],
) -> dict:
    return {
        "role": role,
        "provider": provider,
        "family": family,
        "model_version": model_version,
        **bindings[role],
    }


class RoleManifestTest(unittest.TestCase):
    def _manifest(self) -> dict:
        bindings = build_role_artifact_bindings(SILVER_CONTRACT)
        return {
            "candidate": _role(
                "candidate",
                "deepseek",
                "deepseek",
                "deepseek-candidate-v1",
                bindings,
            ),
            "generator": _role(
                "generator",
                "mistral",
                "mistral",
                "mistral-generator-v1",
                bindings,
            ),
            "duplicate_auditor": _role(
                "duplicate_auditor",
                "cohere",
                "cohere",
                "cohere-duplicate-auditor-v1",
                bindings,
            ),
            "labelers": [
                _role("J1", "openai", "openai", "openai-judge-v1", bindings),
                _role(
                    "J2", "anthropic", "anthropic", "anthropic-judge-v1", bindings
                ),
                _role("J3", "google", "google", "google-judge-v1", bindings),
            ],
            "adjudicator": _role(
                "adjudicator", "xai", "xai", "xai-adjudicator-v1", bindings
            ),
        }

    def test_preflight_accepts_independent_role_identities_and_families(self) -> None:
        self.assertEqual(
            validate_role_manifest(
                self._manifest(), build_role_artifact_bindings(SILVER_CONTRACT)
            ),
            {
                "candidate_family": "deepseek",
                "generator_family": "mistral",
                "duplicate_auditor_family": "cohere",
                "labeler_families": ["anthropic", "google", "openai"],
                "adjudicator_family": "xai",
                "request_authorized": False,
            },
        )

    def test_preflight_fails_closed_when_a_labeler_family_has_two_votes(self) -> None:
        manifest = self._manifest()
        manifest["labelers"][2]["family"] = "openai"

        with self.assertRaisesRegex(
            AISilverProtocolError, "labeler families must be distinct"
        ):
            validate_role_manifest(
                manifest, build_role_artifact_bindings(SILVER_CONTRACT)
            )

    def test_preflight_fails_closed_when_adjudicator_can_share_a_vote_family(self) -> None:
        manifest = self._manifest()
        manifest["adjudicator"]["family"] = "google"

        with self.assertRaisesRegex(
            AISilverProtocolError, "adjudicator family must be distinct"
        ):
            validate_role_manifest(
                manifest, build_role_artifact_bindings(SILVER_CONTRACT)
            )

    def test_preflight_rejects_well_formed_but_unbound_artifact_hash(self) -> None:
        manifest = self._manifest()
        manifest["candidate"]["prompt_sha256"] = "f" * 64

        with self.assertRaisesRegex(AISilverProtocolError, "artifact hash mismatch"):
            validate_role_manifest(
                manifest, build_role_artifact_bindings(SILVER_CONTRACT)
            )

    def test_candidate_proxy_cannot_be_an_independent_adjudicator(self) -> None:
        manifest = self._manifest()
        manifest["adjudicator"].update(
            provider="candidate-proxy",
            family=manifest["candidate"]["family"],
            model_version=manifest["candidate"]["model_version"],
        )

        with self.assertRaisesRegex(
            AISilverProtocolError, "adjudicator family must exclude candidate"
        ):
            validate_role_manifest(
                manifest, build_role_artifact_bindings(SILVER_CONTRACT)
            )

    def test_bound_roles_cannot_bypass_the_missing_execution_runner(self) -> None:
        manifest = self._manifest()
        manifest["candidate"]["model_version"] = "DeepSeek-V4-Flash-0731"
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = Path(temporary) / "roles.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            report = build_as0_preflight_report(SILVER_CONTRACT, manifest_path)

        self.assertTrue(report["role_manifest_frozen"])
        self.assertEqual(report["status"], "blocked_execution_runner")
        self.assertFalse(report["execution_runner_ready"])
        self.assertFalse(report["reference_builder_provider_authorized"])


class ConsensusTest(unittest.TestCase):
    def test_two_of_three_requires_matching_adjudication(self) -> None:
        majority = _applied_projection("buying")
        dissent = _applied_projection("browsing")

        pending = resolve_ai_silver_consensus([majority, majority, dissent])
        accepted = resolve_ai_silver_consensus(
            [majority, majority, dissent], adjudicator_projection=majority
        )

        self.assertEqual(pending["status"], "silver_pending_adjudication")
        self.assertIsNone(pending["canonical_projection"])
        self.assertEqual(accepted["status"], "silver_majority")
        self.assertEqual(accepted["canonical_projection"], majority)

    def test_adjudicator_disagreement_and_three_way_disagreement_stay_unresolved(self) -> None:
        buying = _applied_projection("buying")
        browsing = _applied_projection("browsing")
        unchanged = _applied_projection(None)

        adjudicator_disagreement = resolve_ai_silver_consensus(
            [buying, buying, browsing], adjudicator_projection=unchanged
        )
        three_way = resolve_ai_silver_consensus([buying, browsing, unchanged])

        self.assertEqual(adjudicator_disagreement["status"], "silver_unresolved")
        self.assertIsNone(adjudicator_disagreement["canonical_projection"])
        self.assertEqual(three_way["status"], "silver_unresolved")
        self.assertIsNone(three_way["canonical_projection"])

    def test_malformed_projection_type_is_retained_as_an_invalid_vote(self) -> None:
        invalid = _applied_projection("buying")
        invalid["intent_after"] = ["buying"]

        result = resolve_ai_silver_consensus([invalid, invalid, invalid])

        self.assertEqual(result["status"], "silver_unresolved")
        self.assertEqual(result["valid_labeler_count"], 0)


class FreshFixtureAuditTest(unittest.TestCase):
    def _fresh_items(self) -> list[dict]:
        counts = {
            "override_without_value": 10,
            "mixed_polarity_clause": 10,
            "low_confidence_residual_feature": 20,
            "multi_clause_without_structure": 10,
            "positive_rejected_attribute_conflict": 10,
        }
        rows: list[dict] = []
        index = 0
        for trigger, count in counts.items():
            for offset in range(count):
                index += 1
                rows.append(
                    {
                        "item_id": f"FRESH-{index:03d}",
                        "trigger_type": trigger,
                        "prior_state": {
                            "intent": None,
                            "active_constraints": [],
                            "rejected_constraints": [],
                            "no_preference_attributes": [],
                        },
                        "current_message": (
                            f"Fresh boundary expression {index} token-{offset}."
                        ),
                        "source": "fresh_independent_expression",
                    }
                )
        return rows

    @staticmethod
    def _legacy_items(*, duplicate_message: str | None = None) -> list[dict]:
        return [
            {
                "item_id": f"LEGACY-{index:03d}",
                "current_message": (
                    duplicate_message
                    if duplicate_message is not None and index == 1
                    else f"Legacy exposed expression {index}."
                ),
            }
            for index in range(1, 61)
        ]

    def test_audit_requires_fresh_balanced_items_and_projects_target_free_judge_input(self) -> None:
        fresh = self._fresh_items()
        legacy = self._legacy_items()

        report = audit_fresh_fixture(
            fresh,
            legacy,
            expected_legacy_item_count=60,
            expected_legacy_fixture_sha256=canonical_item_collection_sha256(legacy),
            candidate_trigger="low_confidence_residual_feature",
            near_duplicate_threshold=0.9,
            semantic_audited_item_ids=[item["item_id"] for item in fresh],
            semantic_duplicate_pairs=[],
        )
        judge_input = project_judge_input(
            fresh[0], blind_salt="independent-blind-salt-v1"
        )

        self.assertEqual(report["item_count"], 60)
        self.assertEqual(report["candidate_trigger_count"], 20)
        self.assertEqual(report["duplicate_count"], 0)
        self.assertEqual(
            set(judge_input), {"item_id", "prior_state", "current_message"}
        )
        self.assertNotIn("trigger_type", judge_input)
        self.assertNotIn(fresh[0]["trigger_type"], judge_input["item_id"])
        self.assertEqual(len(report["fixture_manifest"]["item_inventory"]), 60)

    def test_audit_rejects_legacy_duplicates_and_target_keys_before_scoring(self) -> None:
        fresh = self._fresh_items()
        legacy = self._legacy_items(duplicate_message=fresh[0]["current_message"])
        with self.assertRaisesRegex(AISilverProtocolError, "legacy duplicate"):
            audit_fresh_fixture(
                fresh,
                legacy,
                expected_legacy_item_count=60,
                expected_legacy_fixture_sha256=canonical_item_collection_sha256(
                    legacy
                ),
                candidate_trigger="low_confidence_residual_feature",
                near_duplicate_threshold=0.9,
                semantic_audited_item_ids=[item["item_id"] for item in fresh],
                semantic_duplicate_pairs=[],
            )

        fresh = self._fresh_items()
        fresh[0]["target_asin"] = "FORBIDDEN"
        with self.assertRaisesRegex(AISilverProtocolError, "forbidden fixture key"):
            audit_fresh_fixture(
                fresh,
                self._legacy_items(),
                expected_legacy_item_count=60,
                expected_legacy_fixture_sha256=canonical_item_collection_sha256(
                    self._legacy_items()
                ),
                candidate_trigger="low_confidence_residual_feature",
                near_duplicate_threshold=0.9,
                semantic_audited_item_ids=[item["item_id"] for item in fresh],
                semantic_duplicate_pairs=[],
            )

    def test_audit_requires_semantic_duplicate_accounting_for_every_fresh_item(self) -> None:
        fresh = self._fresh_items()

        with self.assertRaisesRegex(
            AISilverProtocolError, "semantic duplicate audit coverage"
        ):
            audit_fresh_fixture(
                fresh,
                self._legacy_items(),
                expected_legacy_item_count=60,
                expected_legacy_fixture_sha256=canonical_item_collection_sha256(
                    self._legacy_items()
                ),
                candidate_trigger="low_confidence_residual_feature",
                near_duplicate_threshold=0.9,
                semantic_audited_item_ids=[item["item_id"] for item in fresh[:-1]],
                semantic_duplicate_pairs=[],
            )

    def test_audit_rejects_an_incomplete_or_unbound_legacy_fixture(self) -> None:
        fresh = self._fresh_items()
        legacy = self._legacy_items()[:-1]

        with self.assertRaisesRegex(AISilverProtocolError, "legacy fixture count"):
            audit_fresh_fixture(
                fresh,
                legacy,
                expected_legacy_item_count=60,
                expected_legacy_fixture_sha256=canonical_item_collection_sha256(
                    self._legacy_items()
                ),
                candidate_trigger="low_confidence_residual_feature",
                near_duplicate_threshold=0.9,
                semantic_audited_item_ids=[item["item_id"] for item in fresh],
                semantic_duplicate_pairs=[],
            )

    def test_audit_rejects_a_changed_legacy_fixture_hash(self) -> None:
        fresh = self._fresh_items()

        with self.assertRaisesRegex(AISilverProtocolError, "legacy fixture hash"):
            audit_fresh_fixture(
                fresh,
                self._legacy_items(),
                expected_legacy_item_count=60,
                expected_legacy_fixture_sha256="f" * 64,
                candidate_trigger="low_confidence_residual_feature",
                near_duplicate_threshold=0.9,
                semantic_audited_item_ids=[item["item_id"] for item in fresh],
                semantic_duplicate_pairs=[],
            )

    def test_judge_id_blinding_removes_trigger_encoded_private_ids(self) -> None:
        item = self._fresh_items()[0]
        item["item_id"] = "override_without_value-001"

        projected = project_judge_input(item, blind_salt="independent-run-salt-v1")

        self.assertRegex(projected["item_id"], r"^BLIND-[0-9a-f]{24}$")
        self.assertNotIn("override", projected["item_id"])


class SemanticGateMetricTest(unittest.TestCase):
    @staticmethod
    def _manifest(rows: list[dict]) -> dict:
        return {
            "version": "a13-frozen-fixture-manifest-v1",
            "fixture_sha256": "f" * 64,
            "item_inventory": [
                {"item_id": row["item_id"], "trigger_type": row["trigger_type"]}
                for row in rows
            ],
        }

    def _other_trigger_rows(self) -> list[dict]:
        rows: list[dict] = []
        for trigger in REACHABLE_TRIGGERS:
            if trigger != "low_confidence_residual_feature":
                rows += self._rows(
                    trigger, 10, candidate_matches=8, deterministic_matches=8
                )
        return rows

    def _rows(
        self,
        trigger: str,
        count: int,
        *,
        unresolved: int = 0,
        candidate_matches: int,
        deterministic_matches: int,
        repeat_matches: int | None = None,
    ) -> list[dict]:
        reference = _applied_projection("buying")
        mismatch = _applied_projection("browsing")
        repeat_matches = count if repeat_matches is None else repeat_matches
        rows: list[dict] = []
        for index in range(count):
            is_unresolved = index < unresolved
            rows.append(
                {
                    "item_id": f"{trigger}-{index:03d}",
                    "trigger_type": trigger,
                    "reference_status": (
                        "silver_unresolved" if is_unresolved else "silver_unanimous"
                    ),
                    "reference_projection": None if is_unresolved else reference,
                    "deterministic_projection": (
                        reference if index < deterministic_matches else mismatch
                    ),
                    "candidate_projection": (
                        reference if index < candidate_matches else mismatch
                    ),
                    "repeat_reference_projection": (
                        reference if index < repeat_matches and not is_unresolved else None
                    ),
                }
            )
        return rows

    def test_unresolved_items_remain_in_every_fixed_denominator(self) -> None:
        rows = self._rows(
            "low_confidence_residual_feature",
            20,
            unresolved=2,
            candidate_matches=15,
            deterministic_matches=10,
        )
        rows += self._other_trigger_rows()

        report = summarize_semantic_gate(
            rows,
            candidate_trigger="low_confidence_residual_feature",
            fixture_manifest=self._manifest(rows),
        )
        trigger = report["by_trigger"]["low_confidence_residual_feature"]

        self.assertEqual(trigger["denominator"], 20)
        self.assertEqual(trigger["canonical_reference_count"], 18)
        self.assertEqual(trigger["reference_coverage"], 0.9)
        self.assertEqual(trigger["candidate_exact_count"], 13)
        self.assertEqual(trigger["candidate_exact_rate"], 0.65)
        self.assertEqual(trigger["deterministic_exact_count"], 8)
        self.assertEqual(trigger["deterministic_exact_rate"], 0.4)
        self.assertEqual(trigger["net_exact_items"], 5)
        self.assertEqual(trigger["semantic_delta"], 0.25)
        self.assertEqual(trigger["repeat_stable_count"], 18)
        self.assertEqual(trigger["repeat_stability"], 0.9)
        self.assertFalse(report["gate_passed"])
        self.assertIn("candidate_trigger_reference_coverage", report["gate_failures"])

    def test_gate_passes_only_when_candidate_and_other_trigger_rules_pass(self) -> None:
        rows = self._rows(
            "low_confidence_residual_feature",
            20,
            candidate_matches=15,
            deterministic_matches=10,
        )
        rows += self._other_trigger_rows()

        report = summarize_semantic_gate(
            rows,
            candidate_trigger="low_confidence_residual_feature",
            fixture_manifest=self._manifest(rows),
        )

        self.assertTrue(report["gate_passed"])
        self.assertEqual(report["gate_failures"], [])

    def test_gate_rejects_missing_rows_against_the_frozen_inventory(self) -> None:
        rows = self._rows(
            "low_confidence_residual_feature",
            20,
            candidate_matches=15,
            deterministic_matches=10,
        ) + self._other_trigger_rows()

        with self.assertRaisesRegex(AISilverProtocolError, "frozen fixture accounting"):
            summarize_semantic_gate(
                rows[:-1],
                candidate_trigger="low_confidence_residual_feature",
                fixture_manifest=self._manifest(rows),
            )

    def test_gate_rejects_an_incomplete_trigger_inventory(self) -> None:
        rows = self._rows(
            "low_confidence_residual_feature",
            20,
            candidate_matches=15,
            deterministic_matches=10,
        )

        with self.assertRaisesRegex(AISilverProtocolError, "frozen fixture trigger"):
            summarize_semantic_gate(
                rows,
                candidate_trigger="low_confidence_residual_feature",
                fixture_manifest=self._manifest(rows),
            )


class CommittedAS0ContractTest(unittest.TestCase):
    def test_schema_and_policy_match_the_offline_protocol_engine(self) -> None:
        schema = json.loads(
            (SILVER_CONTRACT / "applied_state_delta_v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        policy = json.loads(
            (SILVER_CONTRACT / "as0_policy.json").read_text(encoding="utf-8")
        )
        fixture_schema = json.loads(
            (SILVER_CONTRACT / "fresh_fixture_item.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(set(schema["required"]), APPLIED_STATE_FIELDS)
        self.assertEqual(
            tuple(fixture_schema["properties"]["trigger_type"]["enum"]),
            REACHABLE_TRIGGERS,
        )
        self.assertEqual(
            policy["candidate_trigger"], "low_confidence_residual_feature"
        )
        self.assertEqual(
            policy["candidate_config"]["requested_model"], "deepseek-v4-flash"
        )
        self.assertEqual(
            policy["semantic_gate"]["denominator"],
            "all_frozen_items_per_trigger",
        )
        self.assertFalse(
            policy["authorization"]["reference_builder_provider_authorized"]
        )
        self.assertFalse(policy["authorization"]["candidate_provider_authorized"])
        legacy_path = ROOT / "experiments/fixtures/a13_annotation_pack_v1/items.jsonl"
        legacy_items = [
            json.loads(line)
            for line in legacy_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(legacy_items), policy["fixture"]["legacy_item_count"])
        self.assertEqual(
            canonical_item_collection_sha256(legacy_items),
            policy["fixture"]["legacy_fixture_canonical_sha256"],
        )

    def test_role_template_is_deliberately_not_a_frozen_manifest(self) -> None:
        template = json.loads(
            (SILVER_CONTRACT / "role_manifest.template.json").read_text(
                encoding="utf-8"
            )
        )

        with self.assertRaises(AISilverProtocolError):
            validate_role_manifest(
                template, build_role_artifact_bindings(SILVER_CONTRACT)
            )

        self.assertFalse((SILVER_CONTRACT / "items.jsonl").exists())
        self.assertFalse((SILVER_CONTRACT / "labels.jsonl").exists())

    def test_preflight_report_is_hash_bound_and_stops_before_provider_work(self) -> None:
        report = build_as0_preflight_report(
            SILVER_CONTRACT,
            SILVER_CONTRACT / "role_manifest.template.json",
        )

        self.assertEqual(report["status"], "blocked_role_manifest")
        self.assertFalse(report["role_manifest_frozen"])
        self.assertFalse(report["execution_runner_ready"])
        self.assertEqual(report["provider_calls"], 0)
        self.assertFalse(report["reference_builder_provider_authorized"])
        self.assertIn("as0_policy.json", report["artifact_sha256"])
        self.assertIn("candidate_prompt_v1.md", report["artifact_sha256"])
        self.assertTrue(
            all(len(digest) == 64 for digest in report["artifact_sha256"].values())
        )

if __name__ == "__main__":
    unittest.main()
