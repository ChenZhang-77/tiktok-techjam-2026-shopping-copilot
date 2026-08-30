from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from experiments.a13_annotation_pack import (
    AnnotationPackError,
    load_jsonl,
    validate_annotation_label,
    validate_annotation_subset,
    validate_items,
)
from experiments.a13_annotation_trigger_audit import (
    build_runtime_annotation_request,
)
from experiments.evaluation_reporting import code_provenance
from starter.core.context_engine import CatalogVocabulary
from starter.core.semantic_understanding import UnderstandingRequest
from starter.core.state import SessionState


PROJECTION_VERSION = "deterministic_request_fields_v1"
COMPARISON_FIELDS = (
    "abstain",
    "intent_hint",
    "no_preference_attributes",
    "override_attributes",
    "positive_constraints",
    "rejected_constraints",
    "semantic_terms",
)


def _current_intent_hint(request: UnderstandingRequest) -> str | None:
    evidence = set(request.intent_evidence)
    has_current_evidence = any(
        item == "explicit_exploration"
        or item.startswith("current_")
        or item.startswith("no_preference_attributes:")
        for item in evidence
    )
    if not has_current_evidence or "insufficient_specific_evidence" in evidence:
        return None
    return request.deterministic_intent


def _proposal(item: object, *, rejected: bool) -> dict[str, object]:
    proposal = {
        "attribute": str(getattr(item, "attribute")),
        "value": str(getattr(item, "value")),
        "evidence_span": str(getattr(item, "evidence_span")),
    }
    if not rejected:
        proposal["hard"] = bool(getattr(item, "hard"))
    return proposal


def project_deterministic_label(
    item: dict[str, Any],
    vocabulary: CatalogVocabulary,
) -> dict[str, object]:
    """Project current deterministic request evidence without sanitizing it."""

    request = build_runtime_annotation_request(item, vocabulary)
    positive = [
        _proposal(proposal, rejected=False)
        for proposal in request.deterministic_constraints
    ]
    rejected = [
        _proposal(proposal, rejected=True)
        for proposal in request.deterministic_rejected_constraints
    ]
    no_preference = list(request.deterministic_no_preference_attributes)
    current_attributes = {
        str(proposal["attribute"])
        for proposal in (*positive, *rejected)
    } | set(no_preference)
    overrides = sorted(current_attributes) if request.override_detected else []
    intent_hint = _current_intent_hint(request)
    has_delta = bool(
        intent_hint is not None
        or positive
        or rejected
        or no_preference
        or overrides
    )
    return {
        "intent_hint": intent_hint,
        "positive_constraints": positive,
        "rejected_constraints": rejected,
        "no_preference_attributes": no_preference,
        "override_attributes": overrides,
        "semantic_terms": [],
        "abstain": not has_delta,
    }


def _applied_state_positive_rejected_conflicts(
    item: dict[str, Any],
    vocabulary: CatalogVocabulary,
) -> list[str]:
    """Replay the default state mutation and report surviving state conflicts."""

    prior = item["prior_state"]
    request = build_runtime_annotation_request(item, vocabulary)
    state = SessionState(session_id="a13-provisional-audit", user_profile={})
    state.current_turn = 1
    state.active_constraints = [
        {
            "attribute": row["attribute"],
            "normalized_value": row["value"],
            "active": True,
        }
        for row in prior["active_constraints"]
    ]
    state.rejected_constraints = [
        {
            "attribute": row["attribute"],
            "normalized_value": row["value"],
            "active": False,
        }
        for row in prior["rejected_constraints"]
    ]
    state.no_preference_attributes = set(prior["no_preference_attributes"])
    constraints = [
        {
            "attribute": proposal.attribute,
            "normalized_value": proposal.value,
            "raw_value": proposal.evidence_span,
            "confidence": proposal.confidence,
            "hard": proposal.hard,
            "active": True,
        }
        for proposal in request.deterministic_constraints
    ]
    rejected = [
        {
            "attribute": proposal.attribute,
            "normalized_value": proposal.value,
            "raw_value": proposal.evidence_span,
            "confidence": proposal.confidence,
            "hard": proposal.hard,
            "active": False,
        }
        for proposal in request.deterministic_rejected_constraints
    ]
    state.apply_user_context(
        constraints=constraints,
        override=request.override_detected,
        no_preference_attributes=list(
            request.deterministic_no_preference_attributes
        ),
        rejected_constraints=rejected,
    )
    active_keys = {
        (
            str(row.get("attribute") or ""),
            str(row.get("normalized_value") or row.get("raw_value") or ""),
        )
        for row in state.active_constraints
        if row.get("active", True)
    }
    rejected_keys = {
        (
            str(row.get("attribute") or ""),
            str(row.get("normalized_value") or row.get("raw_value") or ""),
        )
        for row in state.rejected_constraints
    }
    return [
        f"{attribute}={value}"
        for attribute, value in sorted(active_keys & rejected_keys)
    ]


def evaluate_provisional_comparator(
    items: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
    vocabulary: CatalogVocabulary,
) -> dict[str, object]:
    """Audit a deterministic projection against an explicitly provisional subset."""

    annotation_summary = validate_annotation_subset(items, annotations)
    if len(items) != len(annotations):
        raise AnnotationPackError("provisional comparator requires aligned rows")
    if [item.get("item_id") for item in items] != [
        row.get("item_id") for row in annotations
    ]:
        raise AnnotationPackError("provisional comparator item order must match")

    rows: list[dict[str, object]] = []
    trigger_counts: dict[str, Counter[str]] = {}
    field_exact_counts: Counter[str] = Counter()
    invalid_reasons: Counter[str] = Counter()
    applied_state_conflict_items: list[str] = []
    exact_count = 0
    invalid_count = 0
    for item, annotation in zip(items, annotations):
        expected = annotation.get("label")
        validate_annotation_label(item, expected)
        prediction = project_deterministic_label(item, vocabulary)
        applied_state_conflicts = _applied_state_positive_rejected_conflicts(
            item,
            vocabulary,
        )
        if applied_state_conflicts:
            applied_state_conflict_items.append(str(item.get("item_id") or ""))
        prediction_status = "valid"
        validation_error: str | None = None
        try:
            validate_annotation_label(item, prediction)
        except AnnotationPackError as exc:
            prediction_status = "invalid"
            validation_error = str(exc)
            _, separator, reason = validation_error.partition(": ")
            invalid_reasons[reason if separator else validation_error] += 1
        exact = prediction_status == "valid" and prediction == expected
        for field in COMPARISON_FIELDS:
            field_exact_counts[field] += int(prediction[field] == expected[field])
        exact_count += int(exact)
        invalid_count += int(prediction_status == "invalid")
        trigger = str(item.get("trigger_type") or "")
        counts = trigger_counts.setdefault(trigger, Counter())
        counts["item_count"] += 1
        counts["exact_match_count"] += int(exact)
        counts["invalid_prediction_count"] += int(prediction_status == "invalid")
        rows.append(
            {
                "item_id": str(item.get("item_id") or ""),
                "trigger_type": trigger,
                "prediction_status": prediction_status,
                "validation_error": validation_error,
                "exact_match": exact,
                "applied_state_positive_rejected_conflicts": applied_state_conflicts,
                "prediction": prediction,
                "provisional_label": expected,
            }
        )

    item_count = len(rows)
    return {
        "version": "a13-provisional-comparator-audit-v1",
        "protocol": {
            "status": "provisional_not_gold",
            "provider_or_candidate_authorized": False,
            "prediction_projection": PROJECTION_VERSION,
            "invalid_predictions_are_not_sanitized": True,
        },
        "annotation_subset": annotation_summary,
        "summary": {
            "item_count": item_count,
            "exact_match_count": exact_count,
            "exact_match_rate": exact_count / item_count if item_count else 0.0,
            "invalid_prediction_count": invalid_count,
        },
        "by_trigger": {
            trigger: dict(counts)
            for trigger, counts in sorted(trigger_counts.items())
        },
        "field_exact": {
            field: {
                "count": field_exact_counts[field],
                "rate": field_exact_counts[field] / item_count if item_count else 0.0,
            }
            for field in COMPARISON_FIELDS
        },
        "invalid_prediction_reasons": dict(sorted(invalid_reasons.items())),
        "applied_state_invariants": {
            "positive_rejected_conflict_item_count": len(
                applied_state_conflict_items
            ),
            "positive_rejected_conflict_items": applied_state_conflict_items,
        },
        "items": rows,
    }


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_provisional_comparator(
    *,
    items_path: str | Path,
    annotations_path: str | Path,
    catalog_path: str | Path,
) -> dict[str, object]:
    """Load, bind, and run one provisional subset audit."""

    source_items = load_jsonl(items_path)
    validate_items(source_items)
    annotations = load_jsonl(annotations_path)
    validate_annotation_subset(source_items, annotations)
    item_by_id = {item["item_id"]: item for item in source_items}
    aligned_items = [item_by_id[row["item_id"]] for row in annotations]
    report = evaluate_provisional_comparator(
        aligned_items,
        annotations,
        CatalogVocabulary.from_catalog(catalog_path),
    )
    report["code_provenance"] = code_provenance()
    report["input_sha256"] = {
        "items": _sha256(items_path),
        "annotations": _sha256(annotations_path),
        "catalog": _sha256(catalog_path),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit deterministic A13 output against provisional labels."
    )
    parser.add_argument("--items", required=True)
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run_provisional_comparator(
        items_path=args.items,
        annotations_path=args.annotations,
        catalog_path=args.catalog,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
