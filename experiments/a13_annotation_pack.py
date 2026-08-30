from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

ALLOWED_ATTRIBUTES = (
    "category",
    "material",
    "color",
    "size",
    "style",
    "brand",
    "budget",
    "feature",
    "use_case",
)
CLOSED_ALLOWED_VALUES = {
    "category": frozenset(
        {
            "backpack", "bag", "belt", "boot", "boots", "bracelet", "bra",
            "cap", "coat", "dress", "earrings", "gloves", "hat", "hoodie",
            "jacket", "jeans", "leggings", "necklace", "pants", "ring",
            "sandals", "shirt", "shoe", "shoes", "shorts", "skirt",
            "sneakers", "socks", "sweater", "swimsuit", "top", "wallet",
            "watch",
        }
    ),
    "material": frozenset(
        {
            "alloy", "canvas", "cotton", "denim", "fabric", "fleece", "gold",
            "lace", "leather", "linen", "metal", "nylon", "polyester",
            "rayon", "rubber", "silicone", "silk", "silver", "spandex",
            "stainless steel", "suede", "wool",
        }
    ),
    "color": frozenset(
        {
            "beige", "black", "blue", "brown", "clear", "gold", "gray",
            "green", "grey", "orange", "pink", "purple", "red", "silver",
            "white", "yellow",
        }
    ),
    "size": frozenset(
        {
            "xxs", "xs", "s", "m", "l", "xl", "xxl", "xxxl", "small",
            "medium", "large", "wide", "narrow",
        }
    ),
    "style": frozenset(
        {
            "athletic", "boho", "classic", "comfortable", "cute", "dressy",
            "elegant", "gothic", "lightweight", "loose", "minimalist",
            "modern", "padded", "retro", "slim", "stretchy", "vintage",
            "warm", "waterproof",
        }
    ),
    "use_case": frozenset(
        {
            "beach", "casual", "cycling", "dance", "everyday", "formal",
            "gym", "hiking", "outdoor", "party", "rain", "running", "school",
            "skiing", "sleep", "travel", "walking", "wedding", "winter",
            "work", "workout", "yoga",
        }
    ),
}
ITEM_FIELDS = {
    "item_id",
    "trigger_type",
    "prior_state",
    "current_message",
    "source",
}
PRIOR_STATE_FIELDS = {
    "intent",
    "active_constraints",
    "rejected_constraints",
    "no_preference_attributes",
}
ANNOTATION_FIELDS = {
    "item_id",
    "annotator_id",
    "confidence",
    "label",
    "notes",
}
LABEL_FIELDS = {
    "intent_hint",
    "positive_constraints",
    "rejected_constraints",
    "no_preference_attributes",
    "override_attributes",
    "semantic_terms",
    "abstain",
}
FORBIDDEN_ITEM_KEYS = {
    "target_asin",
    "hit",
    "miss",
    "scenario_label",
    "future_turn",
    "recommendations",
    "evaluator",
    "gold_delta",
    "comparator_output",
    "model_output",
}
EXPECTED_TRIGGER_COUNTS = {
    "override_without_value": 10,
    "mixed_polarity_clause": 10,
    "low_confidence_residual_feature": 20,
    "multi_clause_without_structure": 10,
    "positive_rejected_attribute_conflict": 10,
}
ID_PREFIX = {
    "override_without_value": "OWV",
    "mixed_polarity_clause": "MPC",
    "low_confidence_residual_feature": "LRF",
    "multi_clause_without_structure": "MCS",
    "positive_rejected_attribute_conflict": "PRC",
}
TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
NO_PREFERENCE_RE = re.compile(
    r"\b(?:no preference|don't care|do not care|doesn't matter|does not matter|"
    r"any\s+(?:category|material|color|size|style|brand|budget|feature|"
    r"use[ _]case|other)\s+(?:is\s+)?(?:fine|okay|ok|works))\b",
    re.I,
)
OVERRIDE_RE = re.compile(
    r"\b(?:actually|instead|ignore|forget|rather|change|changed my mind|"
    r"not that|anymore|replace|drop)\b",
    re.I,
)


class AnnotationPackError(ValueError):
    pass


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise AnnotationPackError(f"line {line_number}: invalid JSON") from error
        if not isinstance(row, dict):
            raise AnnotationPackError(f"line {line_number}: row must be an object")
        rows.append(row)
    return rows


def validate_items(items: list[dict[str, Any]]) -> dict[str, object]:
    if len(items) != 60:
        raise AnnotationPackError("items must contain exactly 60 rows")
    identifiers: set[str] = set()
    trigger_counts: Counter[str] = Counter()
    for index, item in enumerate(items, start=1):
        _require_exact_fields(item, ITEM_FIELDS, f"item row {index}")
        _reject_forbidden_keys(item, f"item row {index}")
        item_id = item["item_id"]
        trigger = item["trigger_type"]
        message = item["current_message"]
        if not isinstance(item_id, str) or not re.fullmatch(r"[A-Z]{3}-\d{3}", item_id):
            raise AnnotationPackError(f"item row {index}: invalid item_id")
        if item_id in identifiers:
            raise AnnotationPackError(f"item row {index}: duplicate item_id")
        identifiers.add(item_id)
        if trigger not in EXPECTED_TRIGGER_COUNTS:
            raise AnnotationPackError(f"item {item_id}: invalid trigger_type")
        if not item_id.startswith(f"{ID_PREFIX[trigger]}-"):
            raise AnnotationPackError(f"item {item_id}: trigger/id prefix mismatch")
        if not isinstance(message, str) or not message.strip() or len(message) > 2000:
            raise AnnotationPackError(f"item {item_id}: invalid current_message")
        if item["source"] != "independent_boundary_expression":
            raise AnnotationPackError(f"item {item_id}: invalid source")
        _validate_prior_state(item["prior_state"], item_id)
        trigger_counts[trigger] += 1
    if dict(trigger_counts) != EXPECTED_TRIGGER_COUNTS:
        raise AnnotationPackError("items do not match the required trigger distribution")
    return {
        "item_count": len(items),
        "trigger_counts": dict(sorted(trigger_counts.items())),
    }


def validate_annotation_pack(
    items: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
) -> dict[str, object]:
    validate_items(items)
    item_by_id = {item["item_id"]: item for item in items}
    expected_ids = list(item_by_id)
    submitted_ids = [row.get("item_id") for row in annotations]
    if submitted_ids != expected_ids:
        raise AnnotationPackError(
            "annotation coverage/order must exactly match items.jsonl"
        )

    annotator_ids: set[str] = set()
    abstain_count = 0
    for index, row in enumerate(annotations, start=1):
        item_id = expected_ids[index - 1]
        _require_exact_fields(row, ANNOTATION_FIELDS, f"annotation {item_id}")
        annotator_id = row["annotator_id"]
        if (
            not isinstance(annotator_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{2,40}", annotator_id)
            or annotator_id.lower().startswith("replace")
        ):
            raise AnnotationPackError(f"annotation {item_id}: invalid annotator_id")
        annotator_ids.add(annotator_id)
        if row["confidence"] not in {"low", "medium", "high"}:
            raise AnnotationPackError(f"annotation {item_id}: invalid confidence")
        if not isinstance(row["notes"], str) or len(row["notes"]) > 1000:
            raise AnnotationPackError(f"annotation {item_id}: invalid notes")
        _validate_label(row["label"], item_by_id[item_id])
        if row["label"]["abstain"]:
            abstain_count += 1
    if len(annotator_ids) != 1:
        raise AnnotationPackError("one annotation file must contain one annotator_id")
    return {
        "annotator_id": next(iter(annotator_ids)),
        "annotation_count": len(annotations),
        "abstain_count": abstain_count,
    }


def compare_annotation_sets(
    items: list[dict[str, Any]],
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> dict[str, object]:
    left_summary = validate_annotation_pack(items, left)
    right_summary = validate_annotation_pack(items, right)
    if left_summary["annotator_id"] == right_summary["annotator_id"]:
        raise AnnotationPackError("comparison requires two different annotator_id values")

    disagreements: list[dict[str, object]] = []
    for item, left_row, right_row in zip(items, left, right):
        if left_row["label"] == right_row["label"]:
            continue
        disagreements.append(
            {
                "item_id": item["item_id"],
                "trigger_type": item["trigger_type"],
                "prior_state": item["prior_state"],
                "current_message": item["current_message"],
                "left": {
                    "annotator_id": left_row["annotator_id"],
                    "confidence": left_row["confidence"],
                    "label": left_row["label"],
                    "notes": left_row["notes"],
                },
                "right": {
                    "annotator_id": right_row["annotator_id"],
                    "confidence": right_row["confidence"],
                    "label": right_row["label"],
                    "notes": right_row["notes"],
                },
            }
        )
    return {
        "left_annotator_id": left_summary["annotator_id"],
        "right_annotator_id": right_summary["annotator_id"],
        "item_count": len(items),
        "agreement_count": len(items) - len(disagreements),
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
    }


def _validate_prior_state(value: object, item_id: str) -> None:
    if not isinstance(value, dict):
        raise AnnotationPackError(f"item {item_id}: prior_state must be an object")
    _require_exact_fields(value, PRIOR_STATE_FIELDS, f"item {item_id} prior_state")
    if value["intent"] not in {None, "buying", "browsing"}:
        raise AnnotationPackError(f"item {item_id}: invalid prior intent")
    for key in ("active_constraints", "rejected_constraints"):
        constraints = value[key]
        if not isinstance(constraints, list):
            raise AnnotationPackError(f"item {item_id}: {key} must be a list")
        for constraint in constraints:
            _validate_state_constraint(constraint, item_id, key)
    _validate_attribute_list(
        value["no_preference_attributes"],
        item_id,
        "prior_state.no_preference_attributes",
    )


def _validate_state_constraint(value: object, item_id: str, field: str) -> None:
    if not isinstance(value, dict):
        raise AnnotationPackError(f"item {item_id}: {field} entry must be an object")
    _require_exact_fields(value, {"attribute", "value"}, f"item {item_id} {field}")
    if value["attribute"] not in ALLOWED_ATTRIBUTES:
        raise AnnotationPackError(f"item {item_id}: invalid state attribute")
    if not isinstance(value["value"], str) or not value["value"].strip():
        raise AnnotationPackError(f"item {item_id}: invalid state value")


def _validate_label(value: object, item: dict[str, Any]) -> None:
    item_id = item["item_id"]
    if not isinstance(value, dict):
        raise AnnotationPackError(f"annotation {item_id}: label must be an object")
    _require_exact_fields(value, LABEL_FIELDS, f"annotation {item_id} label")
    if value["intent_hint"] not in {None, "buying", "browsing"}:
        raise AnnotationPackError(f"annotation {item_id}: invalid intent_hint")
    if not isinstance(value["abstain"], bool):
        raise AnnotationPackError(f"annotation {item_id}: abstain must be boolean")

    positive = _validate_proposals(
        value["positive_constraints"], item, rejected=False
    )
    rejected = _validate_proposals(
        value["rejected_constraints"], item, rejected=True
    )
    no_preference = _validate_attribute_list(
        value["no_preference_attributes"], item_id, "no_preference_attributes"
    )
    overrides = _validate_attribute_list(
        value["override_attributes"], item_id, "override_attributes"
    )
    semantic_terms = value["semantic_terms"]
    if not isinstance(semantic_terms, list) or any(
        not isinstance(term, str) or not term.strip() for term in semantic_terms
    ):
        raise AnnotationPackError(f"annotation {item_id}: invalid semantic_terms")
    normalized_terms = [_normalize(term) for term in semantic_terms]
    if any(term != normalized for term, normalized in zip(semantic_terms, normalized_terms)):
        raise AnnotationPackError(f"annotation {item_id}: semantic_terms must be normalized")
    if len(set(normalized_terms)) != len(normalized_terms):
        raise AnnotationPackError(f"annotation {item_id}: duplicate semantic_terms")
    for term in semantic_terms:
        _require_message_span(term, item["current_message"], item_id, "semantic term")

    positive_keys = {(row["attribute"], _normalize(row["value"])) for row in positive}
    rejected_keys = {(row["attribute"], _normalize(row["value"])) for row in rejected}
    structured_values = {normalized for _, normalized in (*positive_keys, *rejected_keys)}
    if set(normalized_terms) & structured_values:
        raise AnnotationPackError(
            f"annotation {item_id}: semantic term duplicates structured value"
        )
    if positive_keys & rejected_keys:
        raise AnnotationPackError(f"annotation {item_id}: positive/rejected conflict")
    if {row["attribute"] for row in positive} & set(no_preference):
        raise AnnotationPackError(f"annotation {item_id}: positive/no-preference conflict")
    for attribute in no_preference:
        aliases = {attribute, attribute.replace("_", " ")}
        has_attribute = any(
            re.search(
                rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])",
                item["current_message"],
                re.I,
            )
            for alias in aliases
        )
        if not has_attribute or NO_PREFERENCE_RE.search(item["current_message"]) is None:
            raise AnnotationPackError(
                f"annotation {item_id}: missing no-preference evidence"
            )
    evidence_attributes = {
        row["attribute"] for row in (*positive, *rejected)
    } | set(no_preference)
    if any(attribute not in evidence_attributes for attribute in overrides):
        raise AnnotationPackError(f"annotation {item_id}: unsupported override")
    prior = item["prior_state"]
    prior_attributes = {
        row["attribute"]
        for row in (*prior["active_constraints"], *prior["rejected_constraints"])
    } | set(prior["no_preference_attributes"])
    if overrides and (
        OVERRIDE_RE.search(item["current_message"]) is None
        or any(attribute not in prior_attributes for attribute in overrides)
    ):
        raise AnnotationPackError(f"annotation {item_id}: missing override evidence")
    if value["abstain"] and (
        value["intent_hint"] is not None
        or positive
        or rejected
        or no_preference
        or overrides
        or semantic_terms
    ):
        raise AnnotationPackError(f"annotation {item_id}: abstain conflict")
    if not value["abstain"] and not (
        value["intent_hint"] is not None
        or positive
        or rejected
        or no_preference
        or overrides
        or semantic_terms
    ):
        raise AnnotationPackError(f"annotation {item_id}: empty non-abstain label")


def _validate_proposals(
    value: object,
    item: dict[str, Any],
    *,
    rejected: bool,
) -> list[dict[str, Any]]:
    item_id = item["item_id"]
    if not isinstance(value, list):
        raise AnnotationPackError(f"annotation {item_id}: proposals must be a list")
    expected = {"attribute", "value", "evidence_span"}
    if not rejected:
        expected.add("hard")
    seen: set[tuple[str, str]] = set()
    proposals: list[dict[str, Any]] = []
    for proposal in value:
        if not isinstance(proposal, dict):
            raise AnnotationPackError(f"annotation {item_id}: proposal must be an object")
        _require_exact_fields(proposal, expected, f"annotation {item_id} proposal")
        attribute = proposal["attribute"]
        proposal_value = proposal["value"]
        span = proposal["evidence_span"]
        if attribute not in ALLOWED_ATTRIBUTES:
            raise AnnotationPackError(f"annotation {item_id}: invalid proposal attribute")
        if not isinstance(proposal_value, str) or not _normalize(proposal_value):
            raise AnnotationPackError(f"annotation {item_id}: invalid proposal value")
        if proposal_value != _normalize(proposal_value):
            raise AnnotationPackError(
                f"annotation {item_id}: proposal value must be normalized"
            )
        allowed_values = CLOSED_ALLOWED_VALUES.get(attribute)
        if allowed_values is not None and proposal_value not in allowed_values:
            raise AnnotationPackError(
                f"annotation {item_id}: proposal value is outside allowed_values"
            )
        if not isinstance(span, str):
            raise AnnotationPackError(f"annotation {item_id}: invalid evidence_span")
        if not rejected and not isinstance(proposal["hard"], bool):
            raise AnnotationPackError(f"annotation {item_id}: hard must be boolean")
        _require_message_span(span, item["current_message"], item_id, "evidence_span")
        if f" {_normalize(proposal_value)} " not in f" {_normalize(span)} ":
            raise AnnotationPackError(
                f"annotation {item_id}: value must have token-bounded evidence_span"
            )
        key = (attribute, _normalize(proposal_value))
        if key in seen:
            raise AnnotationPackError(f"annotation {item_id}: duplicate proposal")
        seen.add(key)
        proposals.append(proposal)
    return proposals


def _validate_attribute_list(value: object, item_id: str, field: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(attribute, str) or attribute not in ALLOWED_ATTRIBUTES
        for attribute in value
    ):
        raise AnnotationPackError(f"item {item_id}: invalid {field}")
    if len(set(value)) != len(value):
        raise AnnotationPackError(f"item {item_id}: duplicate {field}")
    return value


def _require_message_span(span: str, message: str, item_id: str, field: str) -> None:
    if not span.strip() or span.casefold() not in message.casefold():
        raise AnnotationPackError(f"annotation {item_id}: {field} not in current_message")


def _require_exact_fields(value: dict[str, Any], fields: set[str], context: str) -> None:
    if set(value) != fields:
        raise AnnotationPackError(f"{context}: fields must be {sorted(fields)}")


def _reject_forbidden_keys(value: object, context: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_ITEM_KEYS:
                raise AnnotationPackError(f"{context}: forbidden key {key}")
            _reject_forbidden_keys(child, context)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_keys(child, context)


def _normalize(value: object) -> str:
    return " ".join(token.lower() for token in TOKEN_RE.findall(str(value or "")))


def _write_json(path: str | Path, value: object) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate or compare A13 annotations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_items_parser = subparsers.add_parser("validate-items")
    validate_items_parser.add_argument("--items", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--items", required=True)
    validate_parser.add_argument("--annotations", required=True)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--items", required=True)
    compare_parser.add_argument("--left", required=True)
    compare_parser.add_argument("--right", required=True)
    compare_parser.add_argument("--output", required=True)

    args = parser.parse_args()
    items = load_jsonl(args.items)
    if args.command == "validate-items":
        result = validate_items(items)
    elif args.command == "validate":
        result = validate_annotation_pack(items, load_jsonl(args.annotations))
    else:
        result = compare_annotation_sets(
            items,
            load_jsonl(args.left),
            load_jsonl(args.right),
        )
        _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
