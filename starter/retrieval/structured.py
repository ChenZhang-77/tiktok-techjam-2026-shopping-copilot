from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


EVIDENCE_FIELDS = ("title", "categories", "features", "details", "store", "description")
FILTERABLE_ATTRIBUTES = frozenset(
    {"category", "material", "color", "size", "style", "brand", "feature", "use_case"}
)
AMOUNT_RE = re.compile(r"\d+(?:\.\d{1,2})?")


def evidence_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(f"{key} {item}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value)


@dataclass(frozen=True)
class StructuredConfig:
    enabled: bool = True
    minimum_confidence: float = 0.75
    minimum_filter_matches: int = 10
    minimum_filter_coverage: float = 0.10
    allow_price_filter: bool = False


@dataclass(frozen=True)
class ProductEvidence:
    parent_asin: str
    fields: Mapping[str, str]
    price: float | None

    @classmethod
    def from_product(cls, product: Mapping[str, object]) -> ProductEvidence:
        parent_asin = str(product.get("parent_asin") or "").strip()
        raw_price = product.get("price")
        price = None
        if isinstance(raw_price, (int, float)) and not isinstance(raw_price, bool):
            price = float(raw_price)
        elif isinstance(raw_price, str):
            match = AMOUNT_RE.search(raw_price.replace(",", ""))
            if match:
                price = float(match.group(0))
        return cls(
            parent_asin=parent_asin,
            fields={field_name: evidence_text(product.get(field_name)) for field_name in EVIDENCE_FIELDS},
            price=price,
        )

    @property
    def combined_text(self) -> str:
        return " ".join(self.fields[field_name] for field_name in EVIDENCE_FIELDS)

    def matching_fields(self, constraint: Mapping[str, object]) -> list[str]:
        attribute = str(constraint.get("attribute") or "")
        value = str(constraint.get("normalized_value") or constraint.get("raw_value") or "").strip().lower()
        if not value:
            return []
        if attribute == "budget":
            match = AMOUNT_RE.search(value.replace(",", ""))
            if match and self.price is not None and self.price <= float(match.group(0)):
                return ["price"]
            return []
        pattern = re.compile(rf"\b{re.escape(value)}\b", re.IGNORECASE)
        return [field_name for field_name in EVIDENCE_FIELDS if pattern.search(self.fields[field_name])]


@dataclass(frozen=True)
class StructuredOutcome:
    ordered_ids: list[str]
    filter_applied: bool = False
    relaxed_constraints: list[dict[str, Any]] = field(default_factory=list)
    pool_sizes: list[dict[str, Any]] = field(default_factory=list)


def constraint_summary(constraint: Mapping[str, object]) -> dict[str, Any]:
    return {
        "attribute": str(constraint.get("attribute") or ""),
        "value": str(constraint.get("normalized_value") or constraint.get("raw_value") or ""),
        "confidence": float(constraint.get("confidence") or 0.0),
    }


def structured_matches(
    evidence: ProductEvidence,
    constraints: Sequence[Mapping[str, object]],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for constraint in constraints:
        fields = evidence.matching_fields(constraint)
        if fields:
            item = constraint_summary(constraint)
            item["fields"] = fields
            matches.append(item)
    return matches


def apply_guarded_filters(
    candidate_ids: Sequence[str],
    *,
    evidence_by_id: Mapping[str, ProductEvidence],
    constraints: Sequence[Mapping[str, object]],
    top_k: int,
    config: StructuredConfig,
) -> StructuredOutcome:
    unfiltered = list(candidate_ids)
    if not config.enabled or not unfiltered:
        return StructuredOutcome(unfiltered)

    eligible: list[Mapping[str, object]] = []
    for constraint in constraints:
        attribute = str(constraint.get("attribute") or "")
        confidence = float(constraint.get("confidence") or 0.0)
        if not constraint.get("active", True) or not constraint.get("hard"):
            continue
        if confidence < config.minimum_confidence:
            continue
        if attribute == "budget" and not config.allow_price_filter:
            continue
        if attribute not in FILTERABLE_ATTRIBUTES and attribute != "budget":
            continue
        match_count = sum(
            bool(evidence_by_id[parent_asin].matching_fields(constraint))
            for parent_asin in unfiltered
        )
        coverage = match_count / len(unfiltered)
        if match_count < config.minimum_filter_matches or coverage < config.minimum_filter_coverage:
            continue
        eligible.append(constraint)

    if not eligible:
        return StructuredOutcome(unfiltered)

    active = sorted(
        eligible,
        key=lambda item: (
            -float(item.get("confidence") or 0.0),
            str(item.get("attribute") or ""),
            str(item.get("normalized_value") or item.get("raw_value") or ""),
        ),
    )
    relaxed: list[dict[str, Any]] = []
    pool_sizes: list[dict[str, Any]] = []
    required = min(top_k, len(unfiltered))

    def filtered_ids(current: Sequence[Mapping[str, object]]) -> list[str]:
        selected = list(unfiltered)
        for constraint in current:
            before = len(selected)
            selected = [
                parent_asin
                for parent_asin in selected
                if evidence_by_id[parent_asin].matching_fields(constraint)
            ]
            pool_sizes.append(
                {
                    "constraint": constraint_summary(constraint),
                    "before": before,
                    "after": len(selected),
                }
            )
        return selected

    selected = filtered_ids(active)
    while len(selected) < required and active:
        relaxed_constraint = min(
            active,
            key=lambda item: (
                float(item.get("confidence") or 0.0),
                str(item.get("attribute") or ""),
                str(item.get("normalized_value") or item.get("raw_value") or ""),
            ),
        )
        active.remove(relaxed_constraint)
        relaxed.append(constraint_summary(relaxed_constraint))
        relaxation_step = {
            "relaxed": constraint_summary(relaxed_constraint),
            "before": len(selected),
            "after": None,
        }
        pool_sizes.append(relaxation_step)
        selected = filtered_ids(active) if active else list(unfiltered)
        relaxation_step["after"] = len(selected)

    selected_set = set(selected)
    ordered = selected + [parent_asin for parent_asin in unfiltered if parent_asin not in selected_set]
    return StructuredOutcome(
        ordered_ids=ordered,
        filter_applied=True,
        relaxed_constraints=relaxed,
        pool_sizes=pool_sizes,
    )
