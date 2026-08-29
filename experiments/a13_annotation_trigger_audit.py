from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path
from typing import Any

from starter.core.context_engine import (
    CatalogVocabulary,
    assess_intent,
    detect_no_preference_attributes,
    detect_override,
    detect_rejected_constraints,
    extract_constraints,
)
from starter.core.semantic_understanding import (
    ALLOWED_ATTRIBUTES,
    ConstraintEvidence,
    UnderstandingRequest,
    detect_trigger_signals,
)


def validate_runtime_trigger_assignments(
    items: list[dict[str, Any]],
    catalog_path: str | Path,
) -> dict[str, object]:
    """Replay fixture strata through the same deterministic A13 trigger gate."""

    vocabulary = CatalogVocabulary.from_catalog(catalog_path)
    observed_counts: Counter[str] = Counter()
    assigned_counts: Counter[str] = Counter()
    mismatches: list[dict[str, object]] = []
    for item in items:
        request = _runtime_request(item, vocabulary)
        signals = detect_trigger_signals(request)
        observed_counts.update(signals)
        assigned = item["trigger_type"]
        if assigned in signals:
            assigned_counts[assigned] += 1
        else:
            mismatches.append(
                {
                    "item_id": item["item_id"],
                    "assigned_trigger": assigned,
                    "observed_signals": list(signals),
                }
            )
    return {
        "item_count": len(items),
        "assigned_trigger_matches": len(items) - len(mismatches),
        "assigned_trigger_counts": dict(sorted(assigned_counts.items())),
        "observed_signal_counts": dict(sorted(observed_counts.items())),
        "mismatches": mismatches,
        "catalog_sha256": hashlib.sha256(Path(catalog_path).read_bytes()).hexdigest(),
    }


def _runtime_request(
    item: dict[str, Any],
    vocabulary: CatalogVocabulary,
) -> UnderstandingRequest:
    message = item["current_message"]
    prior = item["prior_state"]
    constraints = extract_constraints(message, 1, vocabulary=vocabulary)
    rejected = detect_rejected_constraints(message, 1, vocabulary=vocabulary)
    no_preference = detect_no_preference_attributes(message)
    override = detect_override(message)
    active_constraints = [
        {
            "attribute": row["attribute"],
            "normalized_value": row["value"],
            "confidence": 1.0,
            "hard": True,
        }
        for row in prior["active_constraints"]
    ]
    intent = assess_intent(
        message,
        constraints,
        active_constraints=active_constraints,
        turn=1,
        previous=None,
        override=override,
        no_preference_attributes=tuple(no_preference),
    )
    return UnderstandingRequest(
        current_message=message,
        turn=1,
        active_constraints=_constraint_evidence(active_constraints, "active_state"),
        rejected_constraints=_constraint_evidence(
            [
                {
                    "attribute": row["attribute"],
                    "normalized_value": row["value"],
                    "confidence": 1.0,
                    "hard": True,
                }
                for row in prior["rejected_constraints"]
            ],
            "rejected_state",
        ),
        no_preference_attributes=tuple(prior["no_preference_attributes"]),
        deterministic_constraints=_constraint_evidence(constraints, "parser"),
        deterministic_rejected_constraints=_constraint_evidence(
            rejected,
            "parser_rejected",
        ),
        deterministic_no_preference_attributes=tuple(no_preference),
        override_detected=override,
        prior_intent=prior["intent"],
        deterministic_intent=intent.intent,
        intent_evidence=intent.evidence,
    )


def _constraint_evidence(
    rows: list[dict[str, Any]],
    source: str,
) -> tuple[ConstraintEvidence, ...]:
    evidence: list[ConstraintEvidence] = []
    for row in rows:
        attribute = str(row.get("attribute") or "")
        value = str(row.get("normalized_value") or row.get("raw_value") or "")
        if attribute not in ALLOWED_ATTRIBUTES or not value:
            continue
        evidence.append(
            ConstraintEvidence(
                attribute=attribute,
                value=value,
                evidence_span=str(row.get("evidence_span") or row.get("raw_value") or value),
                confidence=float(row.get("confidence", 1.0)),
                hard=bool(row.get("hard", True)),
                source=source,
            )
        )
    return tuple(evidence)
