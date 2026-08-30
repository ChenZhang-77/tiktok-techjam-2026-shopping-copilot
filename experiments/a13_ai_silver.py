from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Mapping, Sequence

from starter.core.semantic_understanding import (
    ALLOWED_ATTRIBUTES,
    ConstraintProposal,
    UnderstandingDelta,
    TRIGGER_ORDER,
)
from starter.core.state import SessionState


APPLIED_STATE_SCHEMA_VERSION = "applied_state_delta_v1"
PRIOR_STATE_FIELDS = {
    "intent",
    "active_constraints",
    "rejected_constraints",
    "no_preference_attributes",
}
ROLE_MANIFEST_FIELDS = {
    "candidate",
    "generator",
    "duplicate_auditor",
    "labelers",
    "adjudicator",
}
ROLE_FIELDS = {
    "role",
    "provider",
    "family",
    "model_version",
    "prompt_sha256",
    "config_sha256",
}
ROLE_ARTIFACTS = {
    "candidate": ("candidate_prompt_v1.md", "candidate_config"),
    "generator": ("generator_prompt_v1.md", "generator"),
    "duplicate_auditor": ("semantic_duplicate_audit_prompt_v1.md", "duplicate_auditor"),
    "J1": ("judge_prompt_v1.md", "judge"),
    "J2": ("judge_prompt_v1.md", "judge"),
    "J3": ("judge_prompt_v1.md", "judge"),
    "adjudicator": ("adjudicator_prompt_v1.md", "adjudicator"),
}
ROLE_NAME_RE = re.compile(r"[A-Za-z0-9._:/-]+")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
APPLIED_STATE_FIELDS = {
    "schema_version",
    "intent_before",
    "intent_after",
    "active_constraints_added",
    "active_constraints_deactivated",
    "rejected_constraints_added",
    "no_preference_attributes_added",
    "no_preference_attributes_removed",
    "override_attributes",
    "stale_values_deactivated",
}
FIXTURE_ITEM_FIELDS = {
    "item_id",
    "trigger_type",
    "prior_state",
    "current_message",
    "source",
}
JUDGE_INPUT_FIELDS = {"item_id", "prior_state", "current_message"}
SEMANTIC_SCORE_ROW_FIELDS = {
    "item_id",
    "trigger_type",
    "reference_status",
    "reference_projection",
    "deterministic_projection",
    "candidate_projection",
    "repeat_reference_projection",
}
CANONICAL_REFERENCE_STATUSES = {"silver_unanimous", "silver_majority"}
NONCANONICAL_REFERENCE_STATUSES = {
    "silver_pending_adjudication",
    "silver_unresolved",
    "silver_invalid",
}
REACHABLE_TRIGGERS = tuple(
    trigger for trigger in TRIGGER_ORDER if trigger != "unexplained_intent_transition"
)
FORBIDDEN_FIXTURE_KEYS = {
    "target_asin",
    "ground_truth",
    "hit",
    "miss",
    "scenario_label",
    "scenario_type",
    "future_turn",
    "recommendations",
    "evaluator",
    "gold_delta",
    "comparator_output",
    "candidate_output",
    "model_output",
}
TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)


class AISilverProtocolError(ValueError):
    pass


def _normalized_value(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _constraint_keys(rows: Sequence[Mapping[str, object]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for row in rows:
        attribute = str(row.get("attribute") or "")
        value = _normalized_value(
            row.get("normalized_value") or row.get("value") or row.get("raw_value")
        )
        if attribute not in ALLOWED_ATTRIBUTES or not value:
            raise AISilverProtocolError("invalid prior constraint")
        key = (attribute, value)
        if key in keys:
            raise AISilverProtocolError("duplicate prior constraint")
        keys.add(key)
    return keys


def _constraint_rows(keys: set[tuple[str, str]]) -> list[dict[str, str]]:
    return [
        {"attribute": attribute, "value": value}
        for attribute, value in sorted(keys)
    ]


def _load_prior_state(prior_state: Mapping[str, object]) -> SessionState:
    if set(prior_state) != PRIOR_STATE_FIELDS:
        raise AISilverProtocolError("prior state fields do not match schema")
    intent = prior_state["intent"]
    if intent is not None and (
        not isinstance(intent, str) or intent not in {"buying", "browsing"}
    ):
        raise AISilverProtocolError("invalid prior intent")
    active = prior_state["active_constraints"]
    rejected = prior_state["rejected_constraints"]
    no_preference = prior_state["no_preference_attributes"]
    if (
        not isinstance(active, list)
        or not isinstance(rejected, list)
        or not isinstance(no_preference, list)
        or any(not isinstance(row, dict) for row in (*active, *rejected))
        or any(not isinstance(attribute, str) for attribute in no_preference)
    ):
        raise AISilverProtocolError("invalid prior state type")
    if any(set(row) != {"attribute", "value"} for row in (*active, *rejected)):
        raise AISilverProtocolError("prior constraint fields do not match schema")
    if any(
        not isinstance(row["attribute"], str) or not isinstance(row["value"], str)
        for row in (*active, *rejected)
    ):
        raise AISilverProtocolError("invalid prior constraint type")
    if any(attribute not in ALLOWED_ATTRIBUTES for attribute in no_preference):
        raise AISilverProtocolError("invalid prior no-preference attribute")
    if len(set(no_preference)) != len(no_preference):
        raise AISilverProtocolError("duplicate prior no-preference attribute")
    active_keys = _constraint_keys(active)
    rejected_keys = _constraint_keys(rejected)
    if active_keys & rejected_keys:
        raise AISilverProtocolError("prior active/rejected conflict")
    state = SessionState(session_id="a13-ai-silver-projection", user_profile={})
    state.current_turn = 1
    state.intent = intent
    state.active_constraints = [
        {"attribute": attribute, "normalized_value": value, "active": True}
        for attribute, value in sorted(active_keys)
    ]
    state.rejected_constraints = [
        {"attribute": attribute, "normalized_value": value, "active": False}
        for attribute, value in sorted(rejected_keys)
    ]
    state.no_preference_attributes = set(no_preference)
    return state


def _proposal_row(proposal: ConstraintProposal, *, active: bool) -> dict[str, object]:
    return {
        "attribute": proposal.attribute,
        "normalized_value": _normalized_value(proposal.value),
        "raw_value": proposal.evidence_span,
        "confidence": 1.0,
        "hard": proposal.hard,
        "active": active,
    }


def apply_understanding_delta(
    prior_state: Mapping[str, object],
    delta: UnderstandingDelta,
) -> dict[str, object]:
    """Project one validated proposal through production SessionState semantics."""

    state = _load_prior_state(prior_state)
    intent_before = state.intent
    active_before = _constraint_keys(state.active_constraints)
    rejected_before = _constraint_keys(state.rejected_constraints)
    no_preference_before = set(state.no_preference_attributes)

    override_attributes = set(delta.override_attributes)
    override_constraints = [
        _proposal_row(proposal, active=True)
        for proposal in delta.positive_constraints
        if proposal.attribute in override_attributes
    ]
    positive_override_attributes = {
        proposal.attribute
        for proposal in delta.positive_constraints
        if proposal.attribute in override_attributes
    }
    # Empty, non-explicit control rows activate production's attribute reset,
    # but SessionState.add_constraints never stores an empty value. This also
    # represents validator-legal rejected-only/no-preference overrides without
    # inventing a positive value or mutating production state code.
    override_constraints.extend(
        {
            "attribute": attribute,
            "normalized_value": "",
            "raw_value": "",
            "confidence": 0.0,
            "active": True,
        }
        for attribute in sorted(override_attributes - positive_override_attributes)
    )
    regular_constraints = [
        _proposal_row(proposal, active=True)
        for proposal in delta.positive_constraints
        if proposal.attribute not in override_attributes
    ]
    rejected_constraints = [
        _proposal_row(proposal, active=False)
        for proposal in delta.rejected_constraints
    ]
    state.apply_user_context(
        constraints=override_constraints,
        override=bool(override_constraints),
        no_preference_attributes=list(delta.no_preference_attributes),
        rejected_constraints=rejected_constraints,
    )
    if regular_constraints:
        state.apply_user_context(constraints=regular_constraints)
    if delta.intent_hint is not None:
        state.intent = delta.intent_hint

    active_after = _constraint_keys(state.active_constraints)
    rejected_after = _constraint_keys(state.rejected_constraints)
    no_preference_after = set(state.no_preference_attributes)
    active_deactivated = active_before - active_after
    effective_override_attributes = (
        set(ALLOWED_ATTRIBUTES)
        if "category" in override_attributes
        else override_attributes
    )
    return {
        "schema_version": APPLIED_STATE_SCHEMA_VERSION,
        "intent_before": intent_before,
        "intent_after": state.intent,
        "active_constraints_added": _constraint_rows(active_after - active_before),
        "active_constraints_deactivated": _constraint_rows(active_deactivated),
        "rejected_constraints_added": _constraint_rows(
            rejected_after - rejected_before
        ),
        "no_preference_attributes_added": sorted(
            no_preference_after - no_preference_before
        ),
        "no_preference_attributes_removed": sorted(
            no_preference_before - no_preference_after
        ),
        "override_attributes": sorted(override_attributes),
        "stale_values_deactivated": _constraint_rows(
            {
                key
                for key in active_deactivated
                if key[0] in effective_override_attributes
            }
        ),
    }


def serialize_applied_state_delta(projection: Mapping[str, object]) -> str:
    return json.dumps(
        dict(projection),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _validate_canonical_constraint_rows(
    value: object,
    field: str,
) -> set[tuple[str, str]]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise AISilverProtocolError(f"invalid {field}")
    if any(set(row) != {"attribute", "value"} for row in value):
        raise AISilverProtocolError(f"invalid {field}")
    keys = _constraint_keys(value)
    if value != _constraint_rows(keys):
        raise AISilverProtocolError(f"non-canonical {field}")
    return keys


def _validate_canonical_attributes(value: object, field: str) -> set[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or item not in ALLOWED_ATTRIBUTES for item in value)
        or value != sorted(set(value))
    ):
        raise AISilverProtocolError(f"invalid {field}")
    return set(value)


def validate_applied_state_delta(projection: object) -> dict[str, object]:
    if not isinstance(projection, dict) or set(projection) != APPLIED_STATE_FIELDS:
        raise AISilverProtocolError("applied-state fields do not match schema")
    if projection.get("schema_version") != APPLIED_STATE_SCHEMA_VERSION:
        raise AISilverProtocolError("invalid applied-state schema version")
    for field in ("intent_before", "intent_after"):
        intent = projection[field]
        if intent is not None and (
            not isinstance(intent, str) or intent not in {"buying", "browsing"}
        ):
            raise AISilverProtocolError(f"invalid {field}")
    added = _validate_canonical_constraint_rows(
        projection["active_constraints_added"], "active_constraints_added"
    )
    deactivated = _validate_canonical_constraint_rows(
        projection["active_constraints_deactivated"],
        "active_constraints_deactivated",
    )
    _validate_canonical_constraint_rows(
        projection["rejected_constraints_added"], "rejected_constraints_added"
    )
    no_preference_added = _validate_canonical_attributes(
        projection["no_preference_attributes_added"],
        "no_preference_attributes_added",
    )
    no_preference_removed = _validate_canonical_attributes(
        projection["no_preference_attributes_removed"],
        "no_preference_attributes_removed",
    )
    overrides = _validate_canonical_attributes(
        projection["override_attributes"], "override_attributes"
    )
    stale = _validate_canonical_constraint_rows(
        projection["stale_values_deactivated"], "stale_values_deactivated"
    )
    if added & deactivated:
        raise AISilverProtocolError("active constraint added/deactivated conflict")
    if no_preference_added & no_preference_removed:
        raise AISilverProtocolError("no-preference added/removed conflict")
    stale_attributes = set(ALLOWED_ATTRIBUTES) if "category" in overrides else overrides
    if not stale <= deactivated or any(
        attribute not in stale_attributes for attribute, _ in stale
    ):
        raise AISilverProtocolError("stale values must be override deactivations")
    return projection


def resolve_ai_silver_consensus(
    labeler_projections: Sequence[object | None],
    *,
    adjudicator_projection: object | None = None,
) -> dict[str, object]:
    """Resolve one item without dropping invalid or disagreeing votes."""

    if len(labeler_projections) != 3:
        raise AISilverProtocolError("consensus requires exactly three labelers")
    valid: list[dict[str, object] | None] = []
    for projection in labeler_projections:
        if projection is None:
            valid.append(None)
            continue
        try:
            valid.append(validate_applied_state_delta(projection))
        except AISilverProtocolError:
            valid.append(None)
    serialized = [
        serialize_applied_state_delta(projection) if projection is not None else None
        for projection in valid
    ]
    counts = Counter(value for value in serialized if value is not None)
    majority_serialized, majority_count = counts.most_common(1)[0] if counts else (None, 0)
    majority_projection = (
        valid[serialized.index(majority_serialized)]
        if majority_serialized is not None
        else None
    )
    status = "silver_unresolved"
    canonical: dict[str, object] | None = None
    if majority_count == 3:
        status = "silver_unanimous"
        canonical = majority_projection
    elif majority_count == 2:
        if adjudicator_projection is None:
            status = "silver_pending_adjudication"
        else:
            try:
                adjudicator = validate_applied_state_delta(adjudicator_projection)
            except AISilverProtocolError:
                adjudicator = None
            if (
                adjudicator is not None
                and serialize_applied_state_delta(adjudicator) == majority_serialized
            ):
                status = "silver_majority"
                canonical = majority_projection
    return {
        "status": status,
        "canonical_projection": canonical,
        "valid_labeler_count": sum(projection is not None for projection in valid),
        "majority_count": majority_count,
        "requires_adjudication": majority_count == 2,
    }


def _validated_role(value: object, expected_role: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != ROLE_FIELDS:
        raise AISilverProtocolError(f"{expected_role} role fields do not match schema")
    if value.get("role") != expected_role:
        raise AISilverProtocolError(f"invalid {expected_role} role name")
    normalized: dict[str, str] = {}
    for field in ("role", "provider", "family", "model_version"):
        field_value = value.get(field)
        if (
            not isinstance(field_value, str)
            or not ROLE_NAME_RE.fullmatch(field_value)
            or "replace" in field_value.casefold()
        ):
            raise AISilverProtocolError(f"invalid {expected_role} {field}")
        normalized[field] = field_value.casefold() if field != "model_version" else field_value
    for field in ("prompt_sha256", "config_sha256"):
        field_value = value.get(field)
        if not isinstance(field_value, str) or not SHA256_RE.fullmatch(field_value):
            raise AISilverProtocolError(f"invalid {expected_role} {field}")
        normalized[field] = field_value
    return normalized


def _role_identity(role: Mapping[str, str]) -> tuple[str, str]:
    return role["provider"], role["model_version"]


def validate_role_manifest(
    manifest: object,
    artifact_bindings: Mapping[str, Mapping[str, str]],
) -> dict[str, object]:
    """Fail closed unless all automated-reference roles are independent."""

    if not isinstance(manifest, dict) or set(manifest) != ROLE_MANIFEST_FIELDS:
        raise AISilverProtocolError("role manifest fields do not match schema")
    candidate = _validated_role(manifest["candidate"], "candidate")
    generator = _validated_role(manifest["generator"], "generator")
    duplicate_auditor = _validated_role(
        manifest["duplicate_auditor"], "duplicate_auditor"
    )
    raw_labelers = manifest["labelers"]
    if not isinstance(raw_labelers, list) or len(raw_labelers) != 3:
        raise AISilverProtocolError("exactly three labelers are required")
    labelers = [
        _validated_role(raw_labeler, expected_role)
        for raw_labeler, expected_role in zip(raw_labelers, ("J1", "J2", "J3"))
    ]
    adjudicator = _validated_role(manifest["adjudicator"], "adjudicator")
    if set(artifact_bindings) != set(ROLE_ARTIFACTS):
        raise AISilverProtocolError("role artifact bindings are incomplete")
    roles = [candidate, generator, duplicate_auditor, *labelers, adjudicator]
    for role_name, role in zip(ROLE_ARTIFACTS, roles):
        binding = artifact_bindings[role_name]
        if set(binding) != {"prompt_sha256", "config_sha256"}:
            raise AISilverProtocolError("role artifact bindings are incomplete")
        if any(role[field] != binding[field] for field in binding):
            raise AISilverProtocolError(f"{role_name} artifact hash mismatch")

    labeler_families = {role["family"] for role in labelers}
    if len(labeler_families) != 3:
        raise AISilverProtocolError("labeler families must be distinct")
    if candidate["family"] in labeler_families:
        raise AISilverProtocolError("labeler families must exclude candidate family")
    if adjudicator["family"] in labeler_families:
        raise AISilverProtocolError("adjudicator family must be distinct")
    if generator["family"] == candidate["family"]:
        raise AISilverProtocolError("generator family must exclude candidate family")
    if duplicate_auditor["family"] == candidate["family"]:
        raise AISilverProtocolError(
            "duplicate auditor family must exclude candidate family"
        )

    identities = [
        _role_identity(candidate),
        _role_identity(generator),
        _role_identity(duplicate_auditor),
        *(_role_identity(role) for role in labelers),
        _role_identity(adjudicator),
    ]
    if len(set(identities)) != len(identities):
        raise AISilverProtocolError("role model/version identities must be distinct")
    return {
        "candidate_family": candidate["family"],
        "generator_family": generator["family"],
        "duplicate_auditor_family": duplicate_auditor["family"],
        "labeler_families": sorted(labeler_families),
        "adjudicator_family": adjudicator["family"],
        "request_authorized": False,
    }


def _find_forbidden_key(value: object) -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = str(key).casefold()
            if normalized_key in FORBIDDEN_FIXTURE_KEYS:
                return normalized_key
            found = _find_forbidden_key(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_forbidden_key(nested)
            if found is not None:
                return found
    return None


def _validate_fresh_item(item: object) -> dict[str, object]:
    if not isinstance(item, dict) or set(item) != FIXTURE_ITEM_FIELDS:
        forbidden = _find_forbidden_key(item)
        if forbidden is not None:
            raise AISilverProtocolError(f"forbidden fixture key: {forbidden}")
        raise AISilverProtocolError("fixture item fields do not match schema")
    forbidden = _find_forbidden_key(item)
    if forbidden is not None:
        raise AISilverProtocolError(f"forbidden fixture key: {forbidden}")
    item_id = item["item_id"]
    trigger = item["trigger_type"]
    message = item["current_message"]
    if (
        not isinstance(item_id, str)
        or not ROLE_NAME_RE.fullmatch(item_id)
        or not isinstance(trigger, str)
        or trigger not in REACHABLE_TRIGGERS
        or not isinstance(message, str)
        or not message.strip()
        or len(message) > 2000
        or item["source"] != "fresh_independent_expression"
    ):
        raise AISilverProtocolError("invalid fresh fixture item")
    prior_state = item["prior_state"]
    if not isinstance(prior_state, dict):
        raise AISilverProtocolError("invalid fresh fixture prior state")
    _load_prior_state(prior_state)
    return item


def project_judge_input(item: object, *, blind_salt: str) -> dict[str, object]:
    validated = _validate_fresh_item(item)
    if not isinstance(blind_salt, str) or len(blind_salt) < 16:
        raise AISilverProtocolError("judge ID blinding requires a run-specific salt")
    blind_id = hashlib.sha256(
        f"{blind_salt}:{validated['item_id']}".encode("utf-8")
    ).hexdigest()[:24]
    projected = {
        "item_id": f"BLIND-{blind_id}",
        "prior_state": validated["prior_state"],
        "current_message": validated["current_message"],
    }
    if set(projected) != JUDGE_INPUT_FIELDS:
        raise AISilverProtocolError("judge input fields do not match schema")
    return projected


def _message_tokens(message: object) -> set[str]:
    return {token.casefold() for token in TOKEN_RE.findall(str(message or ""))}


def _jaccard(first: set[str], second: set[str]) -> float:
    union = first | second
    return len(first & second) / len(union) if union else 1.0


def _canonical_json_sha256(value: object) -> str:
    serialized = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def canonical_item_collection_sha256(items: Sequence[Mapping[str, object]]) -> str:
    return _canonical_json_sha256(
        sorted(items, key=lambda item: str(item.get("item_id") or ""))
    )


def audit_fresh_fixture(
    items: Sequence[object],
    legacy_items: Sequence[Mapping[str, object]],
    *,
    expected_legacy_item_count: int,
    expected_legacy_fixture_sha256: str,
    candidate_trigger: str,
    near_duplicate_threshold: float,
    semantic_audited_item_ids: Sequence[str],
    semantic_duplicate_pairs: Sequence[Sequence[str]],
) -> dict[str, object]:
    """Validate AS1F input without inspecting labels, comparator, or Candidate output."""

    if candidate_trigger not in REACHABLE_TRIGGERS:
        raise AISilverProtocolError("invalid candidate trigger")
    if not 0.0 < near_duplicate_threshold <= 1.0:
        raise AISilverProtocolError("near-duplicate threshold must be in (0, 1]")
    if len(items) < 60:
        raise AISilverProtocolError("fresh fixture requires at least 60 items")
    validated = [_validate_fresh_item(item) for item in items]
    identifiers = [str(item["item_id"]) for item in validated]
    if len(set(identifiers)) != len(identifiers):
        raise AISilverProtocolError("duplicate fresh fixture item_id")
    trigger_counts = Counter(str(item["trigger_type"]) for item in validated)
    for trigger in REACHABLE_TRIGGERS:
        if trigger_counts[trigger] < 10:
            raise AISilverProtocolError(f"trigger requires at least 10 items: {trigger}")
    if trigger_counts[candidate_trigger] < 20:
        raise AISilverProtocolError("candidate trigger requires at least 20 items")

    if expected_legacy_item_count != 60 or len(legacy_items) != expected_legacy_item_count:
        raise AISilverProtocolError("legacy fixture count must match frozen 60 items")
    if (
        not isinstance(expected_legacy_fixture_sha256, str)
        or not SHA256_RE.fullmatch(expected_legacy_fixture_sha256)
        or canonical_item_collection_sha256(legacy_items)
        != expected_legacy_fixture_sha256
    ):
        raise AISilverProtocolError("legacy fixture hash mismatch")

    legacy_messages = [str(item.get("current_message") or "") for item in legacy_items]
    legacy_ids = {str(item.get("item_id") or "") for item in legacy_items}
    duplicate_pairs: list[dict[str, object]] = []
    for item in validated:
        item_id = str(item["item_id"])
        if item_id in legacy_ids:
            duplicate_pairs.append(
                {"item_id": item_id, "legacy_item_id": item_id, "similarity": 1.0}
            )
            continue
        normalized = _normalized_value(item["current_message"])
        tokens = _message_tokens(item["current_message"])
        for legacy, legacy_message in zip(legacy_items, legacy_messages):
            legacy_normalized = _normalized_value(legacy_message)
            similarity = _jaccard(tokens, _message_tokens(legacy_message))
            if normalized == legacy_normalized or similarity >= near_duplicate_threshold:
                duplicate_pairs.append(
                    {
                        "item_id": item_id,
                        "legacy_item_id": str(legacy.get("item_id") or ""),
                        "similarity": similarity,
                    }
                )
    semantic_pairs = [tuple(pair) for pair in semantic_duplicate_pairs]
    if any(len(pair) != 2 or not all(isinstance(value, str) for value in pair) for pair in semantic_pairs):
        raise AISilverProtocolError("invalid semantic duplicate audit")
    if (
        len(semantic_audited_item_ids) != len(set(semantic_audited_item_ids))
        or set(semantic_audited_item_ids) != set(identifiers)
    ):
        raise AISilverProtocolError("semantic duplicate audit coverage must be 100%")
    if any(pair[0] not in identifiers or pair[1] not in legacy_ids for pair in semantic_pairs):
        raise AISilverProtocolError("invalid semantic duplicate audit pair")
    if duplicate_pairs or semantic_pairs:
        raise AISilverProtocolError("legacy duplicate detected before scoring")
    return {
        "item_count": len(validated),
        "trigger_counts": dict(sorted(trigger_counts.items())),
        "candidate_trigger": candidate_trigger,
        "candidate_trigger_count": trigger_counts[candidate_trigger],
        "near_duplicate_threshold": near_duplicate_threshold,
        "duplicate_count": 0,
        "semantic_duplicate_count": 0,
        "semantic_audited_item_count": len(semantic_audited_item_ids),
        "legacy_fixture_sha256": expected_legacy_fixture_sha256,
        "fixture_manifest": {
            "version": "a13-frozen-fixture-manifest-v1",
            "fixture_sha256": canonical_item_collection_sha256(validated),
            "item_inventory": [
                {"item_id": item["item_id"], "trigger_type": item["trigger_type"]}
                for item in sorted(validated, key=lambda item: str(item["item_id"]))
            ],
        },
        "judge_input_fields": sorted(JUDGE_INPUT_FIELDS),
        "provider_calls": 0,
    }


def _validated_projection_or_none(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    try:
        return validate_applied_state_delta(value)
    except AISilverProtocolError:
        return None


def _validated_frozen_inventory(
    manifest: Mapping[str, object], candidate_trigger: str
) -> dict[str, str]:
    if not isinstance(manifest, dict) or set(manifest) != {
        "version", "fixture_sha256", "item_inventory"
    }:
        raise AISilverProtocolError("frozen fixture manifest fields do not match schema")
    digest = manifest["fixture_sha256"]
    if (
        manifest["version"] != "a13-frozen-fixture-manifest-v1"
        or not isinstance(digest, str)
        or not SHA256_RE.fullmatch(digest)
        or not isinstance(manifest["item_inventory"], list)
    ):
        raise AISilverProtocolError("invalid frozen fixture manifest")
    inventory: dict[str, str] = {}
    for item in manifest["item_inventory"]:
        if not isinstance(item, dict) or set(item) != {"item_id", "trigger_type"}:
            raise AISilverProtocolError("invalid frozen fixture inventory item")
        item_id = item["item_id"]
        trigger = item["trigger_type"]
        if (
            not isinstance(item_id, str)
            or not item_id
            or item_id in inventory
            or not isinstance(trigger, str)
            or trigger not in REACHABLE_TRIGGERS
        ):
            raise AISilverProtocolError("invalid frozen fixture inventory item")
        inventory[item_id] = trigger
    counts = Counter(inventory.values())
    if len(inventory) < 60 or any(counts[trigger] < 10 for trigger in REACHABLE_TRIGGERS):
        raise AISilverProtocolError("frozen fixture trigger inventory is incomplete")
    if counts[candidate_trigger] < 20:
        raise AISilverProtocolError("frozen fixture candidate trigger requires 20 items")
    return inventory


def summarize_semantic_gate(
    rows: Sequence[object],
    *,
    candidate_trigger: str,
    fixture_manifest: Mapping[str, object],
) -> dict[str, object]:
    """Compute every semantic KPI against frozen all-item denominators."""

    if not rows:
        raise AISilverProtocolError("semantic gate rows must not be empty")
    if candidate_trigger not in REACHABLE_TRIGGERS:
        raise AISilverProtocolError("invalid candidate trigger")
    inventory = _validated_frozen_inventory(fixture_manifest, candidate_trigger)
    identifiers: set[str] = set()
    grouped: dict[str, list[dict[str, object]]] = {}
    candidate_valid_count = 0
    for index, raw_row in enumerate(rows, start=1):
        if not isinstance(raw_row, dict) or set(raw_row) != SEMANTIC_SCORE_ROW_FIELDS:
            raise AISilverProtocolError(f"semantic row {index} fields do not match schema")
        item_id = raw_row["item_id"]
        trigger = raw_row["trigger_type"]
        status = raw_row["reference_status"]
        if not isinstance(item_id, str) or not item_id or item_id in identifiers:
            raise AISilverProtocolError("invalid or duplicate semantic item_id")
        if not isinstance(trigger, str) or trigger not in REACHABLE_TRIGGERS:
            raise AISilverProtocolError("invalid semantic trigger")
        if not isinstance(status, str) or status not in (
            CANONICAL_REFERENCE_STATUSES | NONCANONICAL_REFERENCE_STATUSES
        ):
            raise AISilverProtocolError("invalid reference status")
        identifiers.add(item_id)
        grouped.setdefault(trigger, []).append(raw_row)
        candidate_valid_count += int(
            _validated_projection_or_none(raw_row["candidate_projection"]) is not None
        )

    if identifiers != set(inventory) or any(
        raw_row["trigger_type"] != inventory[raw_row["item_id"]]
        for raw_row in rows
    ):
        raise AISilverProtocolError("frozen fixture accounting mismatch")

    by_trigger: dict[str, dict[str, object]] = {}
    overall = Counter()
    for trigger, trigger_rows in sorted(grouped.items()):
        counts = Counter()
        for row in trigger_rows:
            status = str(row["reference_status"])
            reference = _validated_projection_or_none(row["reference_projection"])
            deterministic = _validated_projection_or_none(
                row["deterministic_projection"]
            )
            candidate = _validated_projection_or_none(row["candidate_projection"])
            repeat = _validated_projection_or_none(
                row["repeat_reference_projection"]
            )
            canonical = status in CANONICAL_REFERENCE_STATUSES and reference is not None
            if status in CANONICAL_REFERENCE_STATUSES and reference is None:
                counts["invalid_reference_count"] += 1
            elif status == "silver_invalid":
                counts["invalid_reference_count"] += 1
            elif status in {
                "silver_pending_adjudication",
                "silver_unresolved",
            }:
                counts["unresolved_reference_count"] += 1
            if canonical:
                counts["canonical_reference_count"] += 1
                reference_json = serialize_applied_state_delta(reference)
                if (
                    deterministic is not None
                    and serialize_applied_state_delta(deterministic) == reference_json
                ):
                    counts["deterministic_exact_count"] += 1
                if (
                    candidate is not None
                    and serialize_applied_state_delta(candidate) == reference_json
                ):
                    counts["candidate_exact_count"] += 1
                if (
                    repeat is not None
                    and serialize_applied_state_delta(repeat) == reference_json
                ):
                    counts["repeat_stable_count"] += 1
            counts["candidate_invalid_count"] += int(candidate is None)
            counts["deterministic_invalid_count"] += int(deterministic is None)
        denominator = len(trigger_rows)
        trigger_report = {
            "denominator": denominator,
            "canonical_reference_count": counts["canonical_reference_count"],
            "unresolved_reference_count": counts["unresolved_reference_count"],
            "invalid_reference_count": counts["invalid_reference_count"],
            "reference_coverage": counts["canonical_reference_count"] / denominator,
            "candidate_exact_count": counts["candidate_exact_count"],
            "candidate_exact_rate": counts["candidate_exact_count"] / denominator,
            "candidate_invalid_count": counts["candidate_invalid_count"],
            "deterministic_exact_count": counts["deterministic_exact_count"],
            "deterministic_exact_rate": counts["deterministic_exact_count"] / denominator,
            "deterministic_invalid_count": counts["deterministic_invalid_count"],
            "net_exact_items": (
                counts["candidate_exact_count"] - counts["deterministic_exact_count"]
            ),
            "semantic_delta": (
                counts["candidate_exact_count"] - counts["deterministic_exact_count"]
            )
            / denominator,
            "repeat_stable_count": counts["repeat_stable_count"],
            "repeat_stability": counts["repeat_stable_count"] / denominator,
        }
        by_trigger[trigger] = trigger_report
        overall["denominator"] += denominator
        for key in (
            "canonical_reference_count",
            "unresolved_reference_count",
            "invalid_reference_count",
            "candidate_exact_count",
            "candidate_invalid_count",
            "deterministic_exact_count",
            "deterministic_invalid_count",
            "repeat_stable_count",
        ):
            overall[key] += counts[key]

    denominator = overall["denominator"]
    candidate_report = by_trigger.get(candidate_trigger)
    failures: list[str] = []
    if overall["canonical_reference_count"] / denominator < 0.95:
        failures.append("overall_reference_coverage")
    if candidate_valid_count / denominator < 0.99:
        failures.append("candidate_schema_success")
    if candidate_report is None or candidate_report["denominator"] < 20:
        failures.append("candidate_trigger_item_count")
    else:
        if candidate_report["reference_coverage"] < 1.0:
            failures.append("candidate_trigger_reference_coverage")
        if candidate_report["repeat_stability"] < 0.90:
            failures.append("candidate_trigger_repeat_stability")
        if candidate_report["semantic_delta"] < 0.10:
            failures.append("candidate_trigger_semantic_delta")
        if candidate_report["net_exact_items"] < 5:
            failures.append("candidate_trigger_net_exact_items")
    if any(
        trigger != candidate_trigger and report["semantic_delta"] < -0.05
        for trigger, report in by_trigger.items()
    ):
        failures.append("other_trigger_regression")
    return {
        "fixture_sha256": fixture_manifest["fixture_sha256"],
        "denominator": denominator,
        "canonical_reference_count": overall["canonical_reference_count"],
        "reference_coverage": overall["canonical_reference_count"] / denominator,
        "candidate_schema_valid_count": candidate_valid_count,
        "candidate_schema_success": candidate_valid_count / denominator,
        "candidate_trigger": candidate_trigger,
        "by_trigger": by_trigger,
        "gate_passed": not failures,
        "gate_failures": failures,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_role_artifact_bindings(
    contract_directory: str | Path,
) -> dict[str, dict[str, str]]:
    contract_path = Path(contract_directory)
    try:
        policy = json.loads((contract_path / "as0_policy.json").read_text())
        bindings = {}
        for role_name, (prompt_file, config_key) in ROLE_ARTIFACTS.items():
            config = (
                policy["candidate_config"]
                if role_name == "candidate"
                else policy["reference_configs"][config_key]
            )
            if not isinstance(config, dict) or not config:
                raise AISilverProtocolError("role config must not be empty")
            bindings[role_name] = {
                "prompt_sha256": _sha256(contract_path / prompt_file),
                "config_sha256": _canonical_json_sha256(config),
            }
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise AISilverProtocolError("role artifacts are incomplete") from error
    return bindings


def build_as0_preflight_report(
    contract_directory: str | Path,
    role_manifest_path: str | Path,
) -> dict[str, object]:
    """Hash offline contracts and report the authorization blocker honestly."""

    contract_path = Path(contract_directory)
    if not contract_path.is_dir():
        raise AISilverProtocolError("AS0 contract directory does not exist")
    forbidden_names = {"items.jsonl", "labels.jsonl", "provider_raw.jsonl"}
    present_forbidden = sorted(
        path.name for path in contract_path.iterdir() if path.name in forbidden_names
    )
    if present_forbidden:
        raise AISilverProtocolError("AS0 contract directory contains execution data")
    artifacts = sorted(
        path for path in contract_path.iterdir() if path.is_file() and path.suffix in {".json", ".md"}
    )
    if not artifacts:
        raise AISilverProtocolError("AS0 contract directory is empty")
    policy_path = contract_path / "as0_policy.json"
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        role_manifest = json.loads(Path(role_manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AISilverProtocolError("invalid AS0 JSON artifact") from error
    authorization = policy.get("authorization") if isinstance(policy, dict) else None
    if not isinstance(authorization, dict) or any(
        authorization.get(field) is not False
        for field in (
            "reference_builder_provider_authorized",
            "candidate_provider_authorized",
            "a13_c1_authorized",
        )
    ):
        raise AISilverProtocolError("AS0 policy must keep provider authorization false")
    role_error: str | None = None
    try:
        role_summary = validate_role_manifest(
            role_manifest, build_role_artifact_bindings(contract_path)
        )
        candidate_config = policy["candidate_config"]
        if (
            role_manifest["candidate"]["provider"] != candidate_config["provider"]
            or role_manifest["candidate"]["model_version"]
            != candidate_config["expected_model_version"]
        ):
            raise AISilverProtocolError("candidate identity differs from frozen config")
    except AISilverProtocolError as error:
        role_summary = None
        role_error = str(error)
    return {
        "version": "a13-ai-silver-as0-preflight-v1",
        "status": "blocked_execution_runner" if role_summary else "blocked_role_manifest",
        "execution_runner_ready": False,
        "role_manifest_frozen": role_summary is not None,
        "role_manifest_error": role_error,
        "role_summary": role_summary,
        "role_manifest_sha256": _sha256(Path(role_manifest_path)),
        "implementation_sha256": {
            "comparator": _sha256(Path(__file__)),
            "validator": _sha256(
                Path(__file__).parents[1] / "starter/core/semantic_understanding.py"
            ),
            "state_semantics": _sha256(
                Path(__file__).parents[1] / "starter/core/state.py"
            ),
        },
        "artifact_sha256": {
            path.name: _sha256(path)
            for path in artifacts
        },
        "provider_calls": 0,
        "reference_builder_provider_authorized": False,
        "candidate_provider_authorized": False,
        "a13_c1_authorized": False,
    }
