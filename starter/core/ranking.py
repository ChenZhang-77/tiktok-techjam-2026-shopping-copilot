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
REJECTION_CONFIDENCE_THRESHOLD = 0.80
MAX_REJECTION_PENALTY = 0.18


@dataclass(frozen=True)
class RejectedConstraintMatch:
    attribute: str
    normalized_value: str
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return {
            "attribute": self.attribute,
            "normalized_value": self.normalized_value,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class RankingScore:
    parent_asin: str
    lexical_rank: int
    lexical_score: float
    constraint_score: float
    ranking_score: float
    rejection_penalty: float = 0.0
    rejected_constraint_matches: tuple[RejectedConstraintMatch, ...] = ()


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


def _constraint_key(constraint: Mapping[str, object]) -> tuple[str, str]:
    return (
        str(constraint.get("attribute") or "feature").strip().lower(),
        str(
            constraint.get("normalized_value")
            or constraint.get("raw_value")
            or ""
        ).strip().lower(),
    )


def _confidence(constraint: Mapping[str, object]) -> float:
    value = constraint.get("confidence")
    if isinstance(value, bool):
        return 0.0
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return confidence if 0.0 <= confidence <= 1.0 else 0.0


def _eligible_rejections(
    rejected_constraints: Sequence[Mapping[str, object]],
    *,
    active_constraints: Sequence[Mapping[str, object]],
    no_preference_attributes: frozenset[str],
) -> list[Mapping[str, object]]:
    active_keys = {
        _constraint_key(constraint)
        for constraint in active_constraints
        if constraint.get("active", True)
    }
    strongest: dict[tuple[str, str], tuple[float, Mapping[str, object]]] = {}
    for rejection in rejected_constraints:
        key = _constraint_key(rejection)
        confidence = _confidence(rejection)
        if (
            not key[1]
            or key[0] in no_preference_attributes
            or key in active_keys
            or confidence < REJECTION_CONFIDENCE_THRESHOLD
        ):
            continue
        previous = strongest.get(key)
        if previous is None or confidence > previous[0]:
            strongest[key] = (confidence, rejection)
    return [item for _, item in strongest.values()]


def _rejection_evidence(
    product_text: str,
    rejected_constraints: Sequence[Mapping[str, object]],
) -> tuple[RejectedConstraintMatch, ...]:
    if not product_text:
        return ()
    text = product_text.lower()
    matches: list[RejectedConstraintMatch] = []
    for rejection in rejected_constraints:
        attribute, value = _constraint_key(rejection)
        if re.search(rf"\b{re.escape(value)}\b", text):
            matches.append(
                RejectedConstraintMatch(
                    attribute=attribute,
                    normalized_value=value,
                    confidence=_confidence(rejection),
                )
            )
    return tuple(matches)


def rank_candidates(
    candidate_ids: Sequence[str],
    *,
    product_texts: Mapping[str, str],
    active_constraints: Sequence[Mapping[str, object]],
    lexical_weight: float,
    structured_weight: float,
    rejected_constraints: Sequence[Mapping[str, object]] = (),
    no_preference_attributes: Sequence[str] = (),
) -> list[RankingScore]:
    no_preference = frozenset(
        str(attribute).strip().lower()
        for attribute in no_preference_attributes
        if str(attribute).strip()
    )
    constraints = _deduplicate_constraints(
        [
            constraint
            for constraint in active_constraints
            if _constraint_key(constraint)[0] not in no_preference
        ]
    )
    rejections = _eligible_rejections(
        rejected_constraints,
        active_constraints=constraints,
        no_preference_attributes=no_preference,
    )
    scored: list[RankingScore] = []
    for rank, parent_asin in enumerate(candidate_ids):
        lexical_score = 1.0 / (rank + 1)
        product_text = product_texts.get(parent_asin, "")
        structured_score = sum(
            _constraint_score(product_text, item) for item in constraints
        )
        rejected_matches = _rejection_evidence(product_text, rejections)
        rejection_penalty = min(
            MAX_REJECTION_PENALTY,
            sum(
                structured_weight
                * ATTRIBUTE_WEIGHTS.get(match.attribute, 0.35)
                * match.confidence
                for match in rejected_matches
            ),
        )
        score = (
            lexical_weight * lexical_score
            + structured_weight * structured_score
            - rejection_penalty
        )
        scored.append(
            RankingScore(
                parent_asin=parent_asin,
                lexical_rank=rank + 1,
                lexical_score=lexical_score,
                constraint_score=structured_score,
                ranking_score=score,
                rejection_penalty=rejection_penalty,
                rejected_constraint_matches=rejected_matches,
            )
        )
    if structured_weight > 0 and (
        constraints or any(item.rejection_penalty > 0 for item in scored)
    ):
        scored.sort(key=lambda item: (-item.ranking_score, item.lexical_rank))
    return scored


def rerank_candidates(
    candidate_ids: Sequence[str],
    *,
    product_texts: Mapping[str, str],
    active_constraints: Sequence[Mapping[str, object]],
    lexical_weight: float,
    structured_weight: float,
    rejected_constraints: Sequence[Mapping[str, object]] = (),
    no_preference_attributes: Sequence[str] = (),
) -> list[str]:
    return [
        item.parent_asin
        for item in rank_candidates(
            candidate_ids,
            product_texts=product_texts,
            active_constraints=active_constraints,
            lexical_weight=lexical_weight,
            structured_weight=structured_weight,
            rejected_constraints=rejected_constraints,
            no_preference_attributes=no_preference_attributes,
        )
    ]
