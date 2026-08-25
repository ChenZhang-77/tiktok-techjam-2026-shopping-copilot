from __future__ import annotations

import re
from dataclasses import dataclass


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
    r"\b(?:no preference|don't care|do not care|doesn't matter|does not matter|any|use your judgment)\b",
    re.I,
)


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
