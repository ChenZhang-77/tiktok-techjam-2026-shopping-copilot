from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


ATTRIBUTE_WEIGHTS = {
    "category": 1.10,
    "material": 1.00,
    "color": 0.75,
    "brand": 0.85,
    "style": 0.65,
    "use_case": 0.60,
    "size": 0.45,
    "feature": 0.35,
    "budget": 0.20,
}
TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)


@dataclass(frozen=True)
class RankingScore:
    parent_asin: str
    lexical_rank: int
    lexical_score: float
    constraint_score: float
    ranking_score: float


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(value) if len(token) > 1}


def _constraint_score(product_text: str, constraint: Mapping[str, object]) -> float:
    value = str(constraint.get("normalized_value") or constraint.get("raw_value") or "").strip().lower()
    if not value:
        return 0.0
    text = product_text.lower()
    attribute = str(constraint.get("attribute") or "feature")
    weight = ATTRIBUTE_WEIGHTS.get(attribute, 0.35)
    confidence = float(constraint.get("confidence") or 0.5)
    hard_multiplier = 1.35 if constraint.get("hard") else 1.0

    if re.search(rf"\b{re.escape(value)}\b", text):
        return weight * confidence * hard_multiplier

    value_tokens = _tokens(value)
    if not value_tokens:
        return 0.0
    overlap = len(value_tokens & _tokens(text)) / len(value_tokens)
    if overlap == 0.0:
        return 0.0
    return weight * confidence * hard_multiplier * overlap * 0.45


def _deduplicate_constraints(
    active_constraints: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    """Keep one strongest explicit constraint for each attribute/value pair."""
    strongest: dict[tuple[str, str], tuple[tuple[bool, float], Mapping[str, object]]] = {}
    for constraint in active_constraints:
        if not constraint.get("active", True):
            continue
        attribute = str(constraint.get("attribute") or "feature").strip().lower()
        value = str(
            constraint.get("normalized_value") or constraint.get("raw_value") or ""
        ).strip().lower()
        key = (attribute, value)
        strength = (bool(constraint.get("hard")), float(constraint.get("confidence") or 0.5))
        previous = strongest.get(key)
        if previous is None or strength > previous[0]:
            strongest[key] = (strength, constraint)
    return [item for _, item in strongest.values()]


def rank_candidates(
    candidate_ids: Sequence[str],
    *,
    product_texts: Mapping[str, str],
    active_constraints: Sequence[Mapping[str, object]],
    lexical_weight: float,
    structured_weight: float,
) -> list[RankingScore]:
    constraints = _deduplicate_constraints(active_constraints)
    scored: list[RankingScore] = []
    for rank, parent_asin in enumerate(candidate_ids):
        lexical_score = 1.0 / (rank + 1)
        structured_score = sum(_constraint_score(product_texts.get(parent_asin, ""), item) for item in constraints)
        score = lexical_weight * lexical_score + structured_weight * structured_score
        scored.append(
            RankingScore(
                parent_asin=parent_asin,
                lexical_rank=rank + 1,
                lexical_score=lexical_score,
                constraint_score=structured_score,
                ranking_score=score,
            )
        )
    if constraints and structured_weight > 0:
        scored.sort(key=lambda item: (-item.ranking_score, item.lexical_rank))
    return scored


def rerank_candidates(
    candidate_ids: Sequence[str],
    *,
    product_texts: Mapping[str, str],
    active_constraints: Sequence[Mapping[str, object]],
    lexical_weight: float,
    structured_weight: float,
) -> list[str]:
    return [
        item.parent_asin
        for item in rank_candidates(
            candidate_ids,
            product_texts=product_texts,
            active_constraints=active_constraints,
            lexical_weight=lexical_weight,
            structured_weight=structured_weight,
        )
    ]
