from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


MATERIALS = {
    "alloy", "canvas", "cotton", "denim", "fabric", "fleece", "gold", "lace",
    "leather", "linen", "metal", "nylon", "polyester", "rayon", "rubber",
    "silicone", "silk", "silver", "spandex", "stainless steel", "suede", "wool",
}
COLORS = {
    "beige", "black", "blue", "brown", "clear", "gold", "gray", "green", "grey",
    "orange", "pink", "purple", "red", "silver", "white", "yellow",
}
USE_CASES = {
    "beach", "casual", "cycling", "dance", "everyday", "formal", "gym", "hiking",
    "outdoor", "party", "rain", "running", "school", "skiing", "sleep", "travel",
    "walking", "wedding", "winter", "work", "workout", "yoga",
}
CATEGORY_TERMS = {
    "backpack", "bag", "belt", "boot", "boots", "bracelet", "bra", "cap", "coat",
    "dress", "earrings", "gloves", "hat", "hoodie", "jacket", "jeans", "leggings",
    "necklace", "pants", "ring", "sandals", "shirt", "shoe", "shoes", "shorts",
    "skirt", "sneakers", "socks", "sweater", "swimsuit", "top", "wallet", "watch",
}
STYLE_TERMS = {
    "athletic", "boho", "classic", "comfortable", "cute", "dressy", "elegant",
    "gothic", "lightweight", "loose", "minimalist", "modern", "padded", "retro",
    "slim", "stretchy", "vintage", "warm", "waterproof",
}
SIZE_RE = re.compile(r"\b(?:size\s*)?(?:xxs|xs|s|m|l|xl|xxl|xxxl|\d{1,2}(?:\.\d)?|small|medium|large|wide|narrow)\b", re.I)
BUDGET_RE = re.compile(r"\b(?:under|below|less than|around|about|up to|budget)\s*\$?\s*(\d+(?:\.\d{1,2})?)\b|\$\s*(\d+(?:\.\d{1,2})?)", re.I)
BRAND_RE = re.compile(r"\b(?:brand|from|by)\s+([A-Z][A-Za-z0-9&' -]{1,30})")
TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
OVERRIDE_RE = re.compile(
    r"\b(?:actually|instead|ignore|forget|rather|change|changed my mind|what i need)\b",
    re.I,
)
NO_PREFERENCE_RE = re.compile(
    r"\b(?:no preference|don't care|do not care|don't have a preference|do not have a preference|doesn't matter|does not matter|any|use your judgment)\b",
    re.I,
)
REJECTION_WINDOW_RE = re.compile(
    r"\b(?:not|avoid|without|except|exclude|don't want|do not want|anything except|anything but)\b[^.?!;]*",
    re.I,
)
EXPLORATION_RE = re.compile(
    r"\b(?:browse|browsing|explore|exploring|just looking|not sure|ideas|open to options)\b",
    re.I,
)
INTENT_RELAXATION_RE = re.compile(
    r"\b(?:no|do not|don't)\s+(?:have\s+)?(?:an\s+)?(?:additional\s+)?preference\b",
    re.I,
)
CONCRETE_INTENT_ATTRIBUTES = {
    "brand",
    "budget",
    "category",
    "color",
    "material",
    "size",
    "style",
    "use_case",
}
TRANSITION_REASONS = {"retained", "accumulated", "relaxed", "explicit_override"}


@dataclass(frozen=True)
class IntentAssessment:
    intent: Literal["buying", "browsing"]
    confidence: float
    evidence: tuple[str, ...]
    source_turn: int
    transition_reason: str

    def __post_init__(self) -> None:
        if self.intent not in {"buying", "browsing"}:
            raise ValueError("intent must be buying or browsing")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.source_turn < 1:
            raise ValueError("source_turn must be positive")
        if self.transition_reason not in TRANSITION_REASONS:
            raise ValueError("invalid transition_reason")

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "source_turn": self.source_turn,
            "transition_reason": self.transition_reason,
        }


@dataclass(frozen=True)
class Constraint:
    attribute: str
    raw_value: str
    normalized_value: str
    source_turn: int
    source_text: str
    confidence: float
    hard: bool
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "attribute": self.attribute,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "source_turn": self.source_turn,
            "source_text": self.source_text,
            "confidence": self.confidence,
            "hard": self.hard,
            "active": self.active,
        }


def _word_matches(text: str, phrases: set[str]) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    for phrase in sorted(phrases, key=lambda item: (-len(item), item)):
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            matches.append(phrase)
    return matches


def _constraint(attribute: str, raw: str, turn: int, text: str, confidence: float, hard: bool) -> Constraint:
    normalized = re.sub(r"\s+", " ", raw.lower()).strip()
    return Constraint(
        attribute=attribute,
        raw_value=raw.strip(),
        normalized_value=normalized,
        source_turn=turn,
        source_text=text,
        confidence=confidence,
        hard=hard,
    )


def _is_hard_request(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in (
        "must", "need", "require", "requirement", "has to", "have to", "key requirement",
        "what i need", "looking for",
    ))


def extract_constraints(user_message: str, turn: int) -> list[dict]:
    text = str(user_message or "")
    lowered = text.lower()
    hard = _is_hard_request(text)
    constraints: list[Constraint] = []

    for value in _word_matches(text, MATERIALS):
        constraints.append(_constraint("material", value, turn, text, 0.86, hard))
    for value in _word_matches(text, COLORS):
        constraints.append(_constraint("color", value, turn, text, 0.82, hard))
    for value in _word_matches(text, CATEGORY_TERMS):
        constraints.append(_constraint("category", value, turn, text, 0.78, hard))
    for value in _word_matches(text, USE_CASES):
        constraints.append(_constraint("use_case", value, turn, text, 0.72, False))
    for value in _word_matches(text, STYLE_TERMS):
        constraints.append(_constraint("style", value, turn, text, 0.70, False))

    for match in SIZE_RE.finditer(text):
        raw = match.group(0)
        if raw.lower() not in {"i", "a"}:
            constraints.append(_constraint("size", raw, turn, text, 0.74, hard))

    for match in BUDGET_RE.finditer(text):
        amount = match.group(1) or match.group(2)
        if amount:
            constraints.append(_constraint("budget", f"${amount}", turn, text, 0.84, hard))

    for match in BRAND_RE.finditer(text):
        raw = match.group(1).strip(" .,!?:;")
        if raw and raw.lower() not in {"a", "an", "the"}:
            constraints.append(_constraint("brand", raw, turn, text, 0.62, False))

    if not constraints and len(TOKEN_RE.findall(lowered)) >= 2:
        constraints.append(_constraint("feature", text[:160], turn, text, 0.35, False))

    unique: dict[tuple[str, str], Constraint] = {}
    for item in constraints:
        key = (item.attribute, item.normalized_value)
        if key not in unique or item.confidence > unique[key].confidence:
            unique[key] = item
    return [item.to_dict() for item in unique.values()]


def detect_override(user_message: str) -> bool:
    return OVERRIDE_RE.search(str(user_message or "")) is not None


def detect_no_preference_attributes(user_message: str) -> list[str]:
    text = str(user_message or "")
    if NO_PREFERENCE_RE.search(text) is None:
        return []
    lowered = text.lower()
    attributes = [
        attribute
        for attribute in ("category", "material", "color", "size", "style", "brand", "budget", "feature", "use_case")
        if re.search(rf"\b{re.escape(attribute.replace('_', ' '))}\b", lowered)
    ]
    if "use case" in lowered and "use_case" not in attributes:
        attributes.append("use_case")
    return attributes


def detect_rejected_constraints(user_message: str, turn: int) -> list[dict]:
    text = str(user_message or "")
    rejected: list[Constraint] = []
    for match in REJECTION_WINDOW_RE.finditer(text):
        window = match.group(0)
        hard = True
        for value in _word_matches(window, MATERIALS):
            rejected.append(_constraint("material", value, turn, text, 0.82, hard))
        for value in _word_matches(window, COLORS):
            rejected.append(_constraint("color", value, turn, text, 0.80, hard))
        for value in _word_matches(window, CATEGORY_TERMS):
            rejected.append(_constraint("category", value, turn, text, 0.72, hard))
        for value in _word_matches(window, STYLE_TERMS):
            rejected.append(_constraint("style", value, turn, text, 0.68, hard))
        for value in _word_matches(window, USE_CASES):
            rejected.append(_constraint("use_case", value, turn, text, 0.65, hard))
        for size_match in SIZE_RE.finditer(window):
            raw = size_match.group(0)
            if raw.lower() not in {"i", "a"}:
                rejected.append(_constraint("size", raw, turn, text, 0.70, hard))

    unique: dict[tuple[str, str], Constraint] = {}
    for item in rejected:
        key = (item.attribute, item.normalized_value)
        if key not in unique or item.confidence > unique[key].confidence:
            unique[key] = item
    return [item.to_dict() for item in unique.values()]


def infer_intent(user_message: str, constraints: list[dict]) -> str:
    turn = max(
        (
            int(item.get("source_turn") or 1)
            for item in constraints
            if not isinstance(item.get("source_turn"), bool)
        ),
        default=1,
    )
    return assess_intent(
        user_message,
        constraints,
        active_constraints=constraints,
        turn=turn,
        previous=None,
        override=False,
    ).intent


def _active_concrete_attributes(constraints: list[dict]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(item.get("attribute"))
                for item in constraints
                if item.get("active", True)
                and str(item.get("attribute")) in CONCRETE_INTENT_ATTRIBUTES
            }
        )
    )


def assess_intent(
    user_message: str,
    constraints: list[dict],
    *,
    active_constraints: list[dict],
    turn: int,
    previous: IntentAssessment | None,
    override: bool,
    no_preference_attributes: tuple[str, ...] = (),
) -> IntentAssessment:
    """Assess intent from conversation evidence with explicit cross-turn hysteresis."""

    text = str(user_message or "")
    explicit_exploration = EXPLORATION_RE.search(text) is not None
    explicit_relaxation = INTENT_RELAXATION_RE.search(text) is not None
    current_attributes = _active_concrete_attributes(constraints)
    active_attributes = _active_concrete_attributes(active_constraints)
    has_current_hard = any(
        bool(item.get("hard"))
        and str(item.get("attribute")) in CONCRETE_INTENT_ATTRIBUTES
        for item in constraints
    )
    sufficient_specific_evidence = bool(current_attributes) and (
        has_current_hard or len(active_attributes) >= 2 or len(current_attributes) >= 2
    )
    evidence: list[str] = []
    if explicit_exploration:
        evidence.append("explicit_exploration")
    if explicit_relaxation:
        evidence.append("explicit_preference_relaxation")
    if has_current_hard:
        evidence.append("current_hard_constraint")
    if current_attributes:
        evidence.append(f"current_concrete_attributes:{','.join(current_attributes)}")
    if active_attributes:
        evidence.append(f"active_concrete_attributes:{','.join(active_attributes)}")
    if override:
        evidence.append("override_seen")
    normalized_no_preference = tuple(sorted(set(no_preference_attributes)))
    if normalized_no_preference:
        evidence.append(
            f"no_preference_attributes:{','.join(normalized_no_preference)}"
        )

    if override:
        if explicit_exploration:
            intent = "browsing"
            confidence = 0.92
        elif sufficient_specific_evidence:
            intent = "buying"
            confidence = 0.90 if has_current_hard else 0.84
        elif previous is not None:
            intent = previous.intent
            confidence = previous.confidence
            evidence.append(f"previous_intent:{previous.intent}")
        else:
            intent = "browsing"
            confidence = 0.60
        return IntentAssessment(
            intent=intent,
            confidence=confidence,
            evidence=tuple(evidence),
            source_turn=turn,
            transition_reason="explicit_override",
        )

    if previous is not None and previous.intent == "buying":
        if explicit_exploration:
            return IntentAssessment(
                intent="browsing",
                confidence=0.90,
                evidence=tuple(evidence),
                source_turn=turn,
                transition_reason="relaxed",
            )
        if previous.transition_reason == "explicit_override" and explicit_relaxation:
            return IntentAssessment(
                intent="browsing",
                confidence=0.72,
                evidence=tuple(evidence),
                source_turn=turn,
                transition_reason="relaxed",
            )
        if (
            not current_attributes
            and (
                len(normalized_no_preference) >= 2
                or (explicit_relaxation and turn - previous.source_turn >= 2)
            )
        ):
            return IntentAssessment(
                intent="browsing",
                confidence=0.72,
                evidence=tuple(evidence),
                source_turn=turn,
                transition_reason="relaxed",
            )
        evidence.append("previous_intent:buying")
        evidence.append("retained_without_explicit_relaxation")
        return IntentAssessment(
            intent="buying",
            confidence=previous.confidence,
            evidence=tuple(evidence),
            source_turn=previous.source_turn,
            transition_reason="retained",
        )

    if previous is not None and previous.intent == "browsing":
        if sufficient_specific_evidence and not explicit_exploration:
            return IntentAssessment(
                intent="buying",
                confidence=0.88 if has_current_hard else 0.82,
                evidence=tuple(evidence),
                source_turn=turn,
                transition_reason="accumulated",
            )
        evidence.append("previous_intent:browsing")
        return IntentAssessment(
            intent="browsing",
            confidence=max(previous.confidence, 0.65),
            evidence=tuple(evidence),
            source_turn=previous.source_turn,
            transition_reason="retained",
        )

    if explicit_exploration:
        return IntentAssessment(
            intent="browsing",
            confidence=0.90,
            evidence=tuple(evidence),
            source_turn=turn,
            transition_reason="relaxed",
        )
    if sufficient_specific_evidence:
        return IntentAssessment(
            intent="buying",
            confidence=0.90 if has_current_hard else 0.82,
            evidence=tuple(evidence),
            source_turn=turn,
            transition_reason="accumulated",
        )
    return IntentAssessment(
        intent="browsing",
        confidence=0.60,
        evidence=tuple(evidence or ["insufficient_specific_evidence"]),
        source_turn=turn,
        transition_reason="accumulated",
    )
