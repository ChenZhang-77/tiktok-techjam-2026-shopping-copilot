from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from starter.core.context_engine import CATEGORY_TERMS, COLORS, MATERIALS, STYLE_TERMS, USE_CASES
from starter.core.response_guard import ALLOWED_ASK_ATTRIBUTES
from starter.core.state import SessionState

if TYPE_CHECKING:
    from starter.core.decision_evidence import DecisionEvidence


QuestionSelectionReason = Literal[
    "final_turn",
    "no_available_attribute",
    "candidate_question_value",
    "concrete_buying_material",
    "legacy_feature_fallback",
    "top_k_candidate_fallback",
    "priority_fallback",
]
QuestionScoreSource = Literal[
    "decision_evidence_full_pool",
    "recommendation_top_k",
    "none",
]


@dataclass(frozen=True)
class QuestionSelection:
    ask_attribute: str | None
    question: str
    reason: QuestionSelectionReason
    score_source: QuestionScoreSource
    question_value: float | None

    def to_diagnostics(self) -> dict:
        return {
            "ask_attribute": self.ask_attribute,
            "reason": self.reason,
            "score_source": self.score_source,
            "question_value": self.question_value,
        }


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
CANDIDATE_SINGLE_TERMS = {
    attribute: {term for term in terms if " " not in term}
    for attribute, terms in CANDIDATE_TERMS.items()
}
CANDIDATE_PHRASE_PATTERNS = {
    attribute: {
        term: re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        for term in terms
        if " " in term
    }
    for attribute, terms in CANDIDATE_TERMS.items()
}
WORD_RE = re.compile(r"\w+", re.UNICODE)


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


def candidate_attribute_scores(candidate_texts: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {}
    token_sets = [set(WORD_RE.findall(text.lower())) for text in candidate_texts]
    for attribute, terms in CANDIDATE_SINGLE_TERMS.items():
        counts: Counter[str] = Counter()
        covered = 0
        phrase_patterns = CANDIDATE_PHRASE_PATTERNS[attribute]
        for text, tokens in zip(candidate_texts, token_sets):
            hits = terms & tokens
            hits.update(
                term for term, pattern in phrase_patterns.items() if pattern.search(text)
            )
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


def select_clarification(
    state: SessionState,
    *,
    turn: int,
    candidate_texts: list[str] | None = None,
    decision_evidence: DecisionEvidence | None = None,
) -> QuestionSelection:
    if turn >= 10:
        return QuestionSelection(None, "", "final_turn", "none", None)

    priority = BUYING_PRIORITY if state.intent == "buying" else BROWSING_PRIORITY
    available = _available_attributes(state, priority)
    if not available:
        return QuestionSelection(None, "", "no_available_attribute", "none", None)

    concrete_attribute = _frontload_concrete_buying_attribute(state, available)
    if concrete_attribute is not None:
        return QuestionSelection(
            concrete_attribute,
            QUESTION_TEXT[concrete_attribute],
            "concrete_buying_material",
            "none",
            None,
        )

    if "feature" in available:
        return QuestionSelection(
            "feature",
            QUESTION_TEXT["feature"],
            "legacy_feature_fallback",
            "none",
            None,
        )

    if (
        decision_evidence is not None
        and decision_evidence.source_status == "available"
        and not decision_evidence.degraded
        and decision_evidence.evidence_candidate_count >= 2
    ):
        full_pool_scores = {
            attribute: score
            for attribute, score in decision_evidence.attribute_partition_scores.items()
            if attribute in available and score > 0.0
        }
        ranked_full_pool = sorted(
            full_pool_scores,
            key=lambda attribute: (-full_pool_scores[attribute], priority.index(attribute)),
        )
        if ranked_full_pool:
            attribute = ranked_full_pool[0]
            return QuestionSelection(
                attribute,
                QUESTION_TEXT[attribute],
                "candidate_question_value",
                "decision_evidence_full_pool",
                full_pool_scores[attribute],
            )

    scores = candidate_attribute_scores(candidate_texts or [])
    ranked = sorted(
        [attribute for attribute in available if attribute in scores],
        key=lambda attribute: (-scores[attribute], priority.index(attribute)),
    )
    if ranked:
        attribute = ranked[0]
        return QuestionSelection(
            attribute,
            QUESTION_TEXT[attribute],
            "top_k_candidate_fallback",
            "recommendation_top_k",
            scores[attribute],
        )

    attribute = available[0]
    return QuestionSelection(
        attribute,
        QUESTION_TEXT[attribute],
        "priority_fallback",
        "none",
        None,
    )


def choose_clarification(
    state: SessionState,
    *,
    turn: int,
    candidate_texts: list[str] | None = None,
    decision_evidence: DecisionEvidence | None = None,
) -> tuple[str | None, str]:
    """Compatibility wrapper for callers that only need the public question."""

    selection = select_clarification(
        state,
        turn=turn,
        candidate_texts=candidate_texts,
        decision_evidence=decision_evidence,
    )
    return selection.ask_attribute, selection.question
