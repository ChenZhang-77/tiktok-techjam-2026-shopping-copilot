from __future__ import annotations

import re
from dataclasses import asdict, dataclass


ATTRIBUTE_ORDER = {
    "category": 0,
    "material": 1,
    "color": 2,
    "size": 3,
    "style": 4,
    "brand": 5,
    "budget": 6,
    "use_case": 7,
    "feature": 8,
}


@dataclass(frozen=True)
class QueryPlan:
    category_terms: tuple[str, ...]
    hard_terms: tuple[str, ...]
    soft_terms: tuple[str, ...]
    semantic_terms: tuple[str, ...]
    residual_terms: tuple[str, ...]
    excluded_terms: tuple[str, ...]
    rendered_query: str
    fallback_to_message: bool

    def to_diagnostics(self) -> dict:
        return asdict(self)


def _value(constraint: dict) -> str:
    return str(
        constraint.get("normalized_value") or constraint.get("raw_value") or ""
    ).strip()


def _ordered_constraints(constraints: list[dict]) -> list[dict]:
    return sorted(
        [constraint for constraint in constraints if constraint.get("active", True)],
        key=lambda item: (
            ATTRIBUTE_ORDER.get(str(item.get("attribute")), 99),
            -float(item.get("confidence") or 0.0),
            int(item.get("source_turn") or 0),
        ),
    )


def _residual_text(
    user_message: str,
    *,
    consumed_terms: tuple[str, ...],
    excluded_terms: tuple[str, ...],
) -> str:
    result = str(user_message or "").strip()
    for term in (*consumed_terms, *excluded_terms):
        pattern = rf"(?<![A-Za-z0-9']){re.escape(term)}(?![A-Za-z0-9'])"
        result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", result).strip(" ,;:-")


def build_query_plan(
    user_message: str,
    active_constraints: list[dict],
    *,
    rejected_constraints: list[dict] | None = None,
    overridden_constraints: list[dict] | None = None,
    max_parts: int = 12,
) -> QueryPlan:
    buckets: dict[str, list[str]] = {
        "category": [],
        "hard": [],
        "soft": [],
        "semantic": [],
    }
    seen: set[str] = set()

    for constraint in _ordered_constraints(active_constraints):
        value = _value(constraint)
        normalized = value.casefold()
        if not value or normalized in seen:
            continue
        seen.add(normalized)
        attribute = str(constraint.get("attribute") or "")
        if attribute == "category":
            bucket = "category"
        elif attribute in {"feature", "use_case"}:
            bucket = "semantic"
        elif bool(constraint.get("hard")):
            bucket = "hard"
        else:
            bucket = "soft"
        buckets[bucket].append(value)
        if len(seen) >= max_parts:
            break

    excluded: list[str] = []
    excluded_seen: set[str] = set()
    for constraint in [*(rejected_constraints or []), *(overridden_constraints or [])]:
        value = _value(constraint)
        normalized = value.casefold()
        if not value or normalized in seen or normalized in excluded_seen:
            continue
        excluded_seen.add(normalized)
        excluded.append(value)

    parts = [
        *buckets["category"],
        *buckets["hard"],
        *buckets["soft"],
        *buckets["semantic"],
    ]
    residual = _residual_text(
        user_message,
        consumed_terms=tuple(parts),
        excluded_terms=tuple(excluded),
    )
    residual_terms = (residual,) if residual else ()
    fallback_to_message = not parts
    rendered_query = " ".join([*parts, *residual_terms])
    return QueryPlan(
        category_terms=tuple(buckets["category"]),
        hard_terms=tuple(buckets["hard"]),
        soft_terms=tuple(buckets["soft"]),
        semantic_terms=tuple(buckets["semantic"]),
        residual_terms=residual_terms,
        excluded_terms=tuple(excluded),
        rendered_query=rendered_query,
        fallback_to_message=fallback_to_message,
    )


def build_distilled_query(
    user_message: str,
    active_constraints: list[dict],
    *,
    max_parts: int = 12,
) -> str:
    """Compatibility wrapper that renders the A-owned QueryPlan."""

    return build_query_plan(
        user_message,
        active_constraints,
        max_parts=max_parts,
    ).rendered_query
