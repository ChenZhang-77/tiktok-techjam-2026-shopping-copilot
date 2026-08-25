from __future__ import annotations


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


def build_distilled_query(user_message: str, active_constraints: list[dict], *, max_parts: int = 12) -> str:
    parts: list[str] = []
    seen: set[str] = set()

    ordered = sorted(
        [constraint for constraint in active_constraints if constraint.get("active", True)],
        key=lambda item: (
            ATTRIBUTE_ORDER.get(str(item.get("attribute")), 99),
            -float(item.get("confidence") or 0.0),
            int(item.get("source_turn") or 0),
        ),
    )
    for constraint in ordered:
        value = str(constraint.get("normalized_value") or constraint.get("raw_value") or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        parts.append(value)
        if len(parts) >= max_parts:
            break

    if not parts:
        return str(user_message or "")

    current = str(user_message or "").strip()
    if current and current.lower() not in seen:
        parts.append(current)
    return " ".join(parts)
