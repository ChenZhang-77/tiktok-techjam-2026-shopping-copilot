from __future__ import annotations

import re
from collections import Counter

from starter.core.context_engine import CATEGORY_TERMS, COLORS, MATERIALS, STYLE_TERMS, USE_CASES
from starter.core.response_guard import ALLOWED_ASK_ATTRIBUTES
from starter.core.state import SessionState


QUESTION_TEXT = {
    "feature": "Which specific feature matters most to you?",
    "material": "Do you have a material preference?",
    "color": "Do you have a color preference?",
    "size": "Do you need a particular size or fit?",
    "style": "What style should I prioritize?",
    "brand": "Do you prefer a specific brand?",
    "budget": "Do you have a target budget?",
    "use_case": "What will you mainly use it for?",
    "category": "Which product category should I narrow this to?",
    "other": "What other detail should I prioritize?",
}

BUYING_PRIORITY = ("feature", "material", "color", "size", "style", "use_case", "brand", "budget", "other")
BROWSING_PRIORITY = ("feature", "use_case", "style", "material", "color", "size", "other")
CANDIDATE_TERMS = {
    "category": CATEGORY_TERMS,
    "material": MATERIALS,
    "color": COLORS,
    "style": STYLE_TERMS,
    "use_case": USE_CASES,
}


def _available_attributes(state: SessionState, priority: tuple[str, ...]) -> list[str]:
    known = {
        str(constraint.get("attribute"))
        for constraint in state.active_constraints
        if constraint.get("active", True)
    }
    unavailable = set(state.asked_attributes) | set(state.no_preference_attributes)
    return [
        attribute
        for attribute in priority
        if attribute in ALLOWED_ASK_ATTRIBUTES
        and attribute not in unavailable
        and (attribute not in known or attribute == "other")
    ]


def _term_hits(text: str, terms: set[str]) -> set[str]:
    lowered = text.lower()
    return {
        term
        for term in terms
        if re.search(rf"\b{re.escape(term)}\b", lowered)
    }


def candidate_attribute_scores(candidate_texts: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for attribute, terms in CANDIDATE_TERMS.items():
        counts: Counter[str] = Counter()
        covered = 0
        for text in candidate_texts:
            hits = _term_hits(text, terms)
            if hits:
                covered += 1
                counts.update(hits)
        if len(counts) < 2 or covered < 2:
            continue
        diversity = min(len(counts), 6) / 6.0
        coverage = covered / max(len(candidate_texts), 1)
        scores[attribute] = round(0.65 * diversity + 0.35 * coverage, 6)
    return scores


def _active_attributes(state: SessionState) -> set[str]:
    return {
        str(constraint.get("attribute"))
        for constraint in state.active_constraints
        if constraint.get("active", True)
    }


def _frontload_concrete_buying_attribute(state: SessionState, available: list[str]) -> str | None:
    active = _active_attributes(state)
    if state.intent != "buying" or not {"category", "color"}.issubset(active):
        return None
    return "material" if "material" in available else None


def choose_clarification(
    state: SessionState,
    *,
    turn: int,
    candidate_texts: list[str] | None = None,
) -> tuple[str | None, str]:
    if turn >= 10:
        return None, ""

    priority = BUYING_PRIORITY if state.intent == "buying" else BROWSING_PRIORITY
    available = _available_attributes(state, priority)
    if not available:
        return None, ""

    concrete_attribute = _frontload_concrete_buying_attribute(state, available)
    if concrete_attribute is not None:
        return concrete_attribute, QUESTION_TEXT[concrete_attribute]

    if "feature" in available:
        return "feature", QUESTION_TEXT["feature"]

    scores = candidate_attribute_scores(candidate_texts or [])
    ranked = sorted(
        [attribute for attribute in available if attribute in scores],
        key=lambda attribute: (-scores[attribute], priority.index(attribute)),
    )
    if ranked:
        return ranked[0], QUESTION_TEXT[ranked[0]]

    return available[0], QUESTION_TEXT[available[0]]
