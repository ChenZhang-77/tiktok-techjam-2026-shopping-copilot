from __future__ import annotations

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


def choose_clarification(state: SessionState, *, turn: int) -> tuple[str | None, str]:
    if turn >= 10:
        return None, ""

    known = {
        str(constraint.get("attribute"))
        for constraint in state.active_constraints
        if constraint.get("active", True)
    }
    unavailable = set(state.asked_attributes) | set(state.no_preference_attributes)
    priority = BUYING_PRIORITY if state.intent == "buying" else BROWSING_PRIORITY

    for attribute in priority:
        if attribute not in ALLOWED_ASK_ATTRIBUTES:
            continue
        if attribute in unavailable:
            continue
        if attribute in known and attribute != "other":
            continue
        return attribute, QUESTION_TEXT[attribute]
    return None, ""
