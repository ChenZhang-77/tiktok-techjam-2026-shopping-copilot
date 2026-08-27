from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping


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
EXPLICIT_SIZE_RE = re.compile(
    r"\bsize(?:d)?\s*(?:is\s*)?(xxs|xs|s|m|l|xl|xxl|xxxl|\d{1,2}(?:\.\d)?|small|medium|large|wide|narrow)\b",
    re.I,
)
STANDALONE_SIZE_RE = re.compile(
    r"^\s*(xxs|xs|s|m|l|xl|xxl|xxxl|\d{1,2}(?:\.\d)?|small|medium|large|wide|narrow)\s*[.!]?\s*$",
    re.I,
)
DESCRIPTIVE_SIZE_RE = re.compile(r"\b(small|medium|large|wide|narrow)\b", re.I)
BUDGET_RE = re.compile(r"\b(?:under|below|less than|around|about|up to|budget)\s*\$?\s*(\d+(?:\.\d{1,2})?)\b|\$\s*(\d+(?:\.\d{1,2})?)", re.I)
BRAND_RE = re.compile(
    r"\b(?:brand|from|by)\s+"
    r"([A-Z][A-Za-z0-9&'-]*(?:\s+[A-Z][A-Za-z0-9&'-]*){0,2})"
)
TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
OVERRIDE_RE = re.compile(
    r"\b(?:actually|instead|ignore|forget|rather|change|changed my mind|what i need)\b",
    re.I,
)
NO_PREFERENCE_RE = re.compile(
    r"\b(?:no preference|don't care|do not care|don't have (?:an?\s+)?(?:additional\s+)?preference|do not have (?:an?\s+)?(?:additional\s+)?preference|doesn't matter|does not matter|any\s+(?:category|material|color|size|style|brand|budget|feature|use[ _]case|other)\s+(?:is\s+)?(?:fine|okay|ok|works)|use your judgment)\b",
    re.I,
)
NEGATION_MARKER_RE = re.compile(
    r"\b(?:anything except|anything but|don't want|do not want|instead of|avoid|without|except|exclude|ignore|not)\b",
    re.I,
)
CLAUSE_END_RE = re.compile(r"[.;?!]|\b(?:but|however|rather)\b", re.I)
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


def _normalized_phrase(value: object) -> str:
    return " ".join(token.lower() for token in TOKEN_RE.findall(str(value or "")))


def _flatten_catalog_values(value: object) -> list[str]:
    if isinstance(value, dict):
        return [str(item) for item in value.values() if item not in (None, "", [])]
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)] if value not in (None, "") else []


@dataclass(frozen=True)
class CatalogVocabulary:
    """A-side category vocabulary derived only from the frozen runtime catalog."""

    category_terms: frozenset[str]

    @classmethod
    def empty(cls) -> CatalogVocabulary:
        return cls(frozenset())

    @classmethod
    def from_catalog(cls, catalog_path: str | Path) -> CatalogVocabulary:
        def products() -> Iterable[Mapping[str, object]]:
            with Path(catalog_path).open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        yield json.loads(line)

        return cls.from_products(products())

    @classmethod
    def from_products(
        cls,
        products: Iterable[Mapping[str, object]],
    ) -> CatalogVocabulary:
        categories: set[str] = set()
        for product in products:
            for raw in _flatten_catalog_values(product.get("categories")):
                normalized = _normalized_phrase(raw)
                if 2 <= len(normalized.split()) <= 8:
                    categories.add(normalized)
        return cls(category_terms=frozenset(categories))


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
            "confidence_band": self.confidence_band,
            "evidence": list(self.evidence),
            "source_turn": self.source_turn,
            "transition_reason": self.transition_reason,
        }

    @property
    def confidence_band(self) -> Literal["low", "medium", "high"]:
        """Return an ordinal stability band; the numeric value is not a probability."""

        if self.confidence < 0.65:
            return "low"
        if self.confidence < 0.80:
            return "medium"
        return "high"


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
        if re.search(
            rf"(?<![A-Za-z0-9'-]){re.escape(phrase)}(?![A-Za-z0-9'-])",
            lowered,
        ):
            matches.append(phrase)
    return matches


def _phrase_spans(text: str, phrase: str) -> list[tuple[int, int]]:
    return [
        match.span()
        for match in re.finditer(
            rf"(?<![A-Za-z0-9'-]){re.escape(phrase)}(?![A-Za-z0-9'-])",
            text,
            re.I,
        )
    ]


def _catalog_separator_is_supported(
    left: re.Match[str],
    right: re.Match[str],
    separator: str,
) -> bool:
    if re.fullmatch(r"(?:\s+|\s*-\s*)", separator) is not None:
        return True
    if right.group(0).lower() == "s" and separator in {"'", "’"}:
        return True
    return (
        left.group(0).lower().endswith("s")
        and re.fullmatch(r"['’]\s*", separator) is not None
    )


def _catalog_phrase_spans(
    text: str,
    phrases: frozenset[str],
) -> list[tuple[int, int, str]]:
    token_matches = list(TOKEN_RE.finditer(text))
    if not token_matches or not phrases:
        return []
    maximum = min(
        12,
        len(token_matches),
        max(len(phrase.split()) for phrase in phrases),
    )
    occupied = [False] * len(token_matches)
    matches: list[tuple[int, int, int, str]] = []
    for width in range(maximum, 0, -1):
        for start in range(0, len(token_matches) - width + 1):
            end = start + width
            if any(occupied[start:end]):
                continue
            selected = token_matches[start:end]
            if any(
                not _catalog_separator_is_supported(
                    left,
                    right,
                    text[left.end():right.start()],
                )
                for left, right in zip(selected, selected[1:])
            ):
                continue
            phrase = " ".join(token.group(0).lower() for token in selected)
            if phrase not in phrases:
                continue
            matches.append(
                (start, selected[0].start(), selected[-1].end(), phrase)
            )
            occupied[start:end] = [True] * width
    return [
        (character_start, character_end, phrase)
        for _, character_start, character_end, phrase in sorted(matches)
    ]


def _catalog_phrase_matches(
    text: str,
    phrases: frozenset[str],
) -> list[str]:
    return [phrase for _, _, phrase in _catalog_phrase_spans(text, phrases)]


def _size_matches(text: str) -> list[str]:
    matches = [match.group(1) for match in EXPLICIT_SIZE_RE.finditer(text)]
    standalone = STANDALONE_SIZE_RE.match(text)
    if standalone:
        matches.append(standalone.group(1))
    matches.extend(match.group(1) for match in DESCRIPTIVE_SIZE_RE.finditer(text))
    return list(dict.fromkeys(value.lower() for value in matches))


def _negative_spans(text: str) -> list[tuple[int, int]]:
    markers = list(NEGATION_MARKER_RE.finditer(text))
    spans: list[tuple[int, int]] = []
    for index, marker in enumerate(markers):
        remainder = text[marker.end():]
        boundary = CLAUSE_END_RE.search(remainder)
        clause_end = marker.end() + boundary.start() if boundary else len(text)
        next_marker_start = (
            markers[index + 1].start() if index + 1 < len(markers) else len(text)
        )
        end = min(clause_end, next_marker_start)
        spans.append((marker.start(), end))
    return spans


def _mask_spans(text: str, spans: list[tuple[int, int]]) -> str:
    characters = list(text)
    for start, end in spans:
        characters[start:end] = "\0" * (end - start)
    return "".join(characters)


def _no_preference_spans(text: str) -> list[tuple[int, int]]:
    separators = list(CLAUSE_END_RE.finditer(text))
    spans: list[tuple[int, int]] = []
    for marker in NO_PREFERENCE_RE.finditer(text):
        start = max(
            (separator.end() for separator in separators if separator.end() <= marker.start()),
            default=0,
        )
        end = min(
            (separator.start() for separator in separators if separator.start() >= marker.end()),
            default=len(text),
        )
        spans.append((start, end))
    return spans


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


def _matched_constraints(
    text: str,
    turn: int,
    source_text: str,
    *,
    vocabulary: CatalogVocabulary | None,
    hard: bool,
    rejected: bool,
) -> list[Constraint]:
    confidence = {
        "material": 0.82 if rejected else 0.86,
        "color": 0.80 if rejected else 0.82,
        "category": 0.72 if rejected else 0.78,
        "use_case": 0.65 if rejected else 0.72,
        "style": 0.68 if rejected else 0.70,
        "catalog_category": 0.76 if rejected else 0.80,
        "size": 0.70 if rejected else 0.74,
        "budget": 0.80 if rejected else 0.84,
        "brand": 0.68 if rejected else 0.62,
    }
    constraints: list[Constraint] = []
    matchers = (
        ("material", MATERIALS),
        ("color", COLORS),
        ("category", CATEGORY_TERMS),
        ("use_case", USE_CASES),
        ("style", STYLE_TERMS),
    )
    for attribute, phrases in matchers:
        attribute_hard = hard if attribute in {"material", "color", "category"} else False
        if rejected:
            attribute_hard = True
        for value in _word_matches(text, phrases):
            constraints.append(
                _constraint(
                    attribute,
                    value,
                    turn,
                    source_text,
                    confidence[attribute],
                    attribute_hard,
                )
            )

    if vocabulary is not None:
        for value in _catalog_phrase_matches(text, vocabulary.category_terms):
            constraints.append(
                _constraint(
                    "category",
                    value,
                    turn,
                    source_text,
                    confidence["catalog_category"],
                    True if rejected else hard,
                )
            )

    for value in _size_matches(text):
        constraints.append(
            _constraint(
                "size",
                value,
                turn,
                source_text,
                confidence["size"],
                True if rejected else hard,
            )
        )

    for match in BUDGET_RE.finditer(text):
        amount = match.group(1) or match.group(2)
        if amount:
            constraints.append(
                _constraint(
                    "budget",
                    f"${amount}",
                    turn,
                    source_text,
                    confidence["budget"],
                    True if rejected else hard,
                )
            )

    for match in BRAND_RE.finditer(text):
        raw = match.group(1).strip(" .,!?:;")
        if raw and raw.lower() not in {"a", "an", "the"}:
            constraints.append(
                _constraint(
                    "brand",
                    raw,
                    turn,
                    source_text,
                    confidence["brand"],
                    rejected,
                )
            )
    return constraints


def _negative_head_categories(
    text: str,
    vocabulary: CatalogVocabulary | None,
) -> set[str]:
    """Keep a category positive only when a modifier directly precedes its head."""

    category_spans = [
        (start, end, category)
        for category in _word_matches(text, CATEGORY_TERMS)
        for start, end in _phrase_spans(text, category)
    ]
    if vocabulary is not None:
        category_spans.extend(
            _catalog_phrase_spans(text, vocabulary.category_terms)
        )
    modifier_groups = (MATERIALS, COLORS, STYLE_TERMS, USE_CASES)
    heads: set[str] = set()
    direct_head_spans: list[tuple[int, int]] = []
    for category_start, category_end, category in category_spans:
        for phrases in modifier_groups:
            modifier_spans = [
                span
                for modifier in _word_matches(text[:category_start], phrases)
                for span in _phrase_spans(text[:category_start], modifier)
            ]
            if not modifier_spans:
                continue
            last_modifier_end = max(end for _, end in modifier_spans)
            if re.fullmatch(r"\s+", text[last_modifier_end:category_start]):
                heads.add(category)
                direct_head_spans.append((category_start, category_end))
                break
    for category_start, category_end, category in category_spans:
        if any(
            head_start <= category_start and category_end <= head_end
            for head_start, head_end in direct_head_spans
        ):
            heads.add(category)
    return heads


def extract_constraints(
    user_message: str,
    turn: int,
    *,
    vocabulary: CatalogVocabulary | None = None,
) -> list[dict]:
    text = str(user_message or "")
    positive_text = _mask_spans(
        text,
        [*_negative_spans(text), *_no_preference_spans(text)],
    )
    lowered = positive_text.lower()
    hard = _is_hard_request(text)
    constraints = _matched_constraints(
        positive_text,
        turn,
        text,
        vocabulary=vocabulary,
        hard=hard,
        rejected=False,
    )
    for start, end in _negative_spans(text):
        for value in _negative_head_categories(text[start:end], vocabulary):
            constraints.append(_constraint("category", value, turn, text, 0.78, hard))

    if (
        not constraints
        and NO_PREFERENCE_RE.search(text) is None
        and len(TOKEN_RE.findall(lowered)) >= 2
    ):
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
    lowered = " ".join(
        text[start:end].lower()
        for start, end in _no_preference_spans(text)
    )
    attributes = []
    for attribute in (
        "category", "material", "color", "size", "style", "brand", "budget",
        "feature", "use_case", "other",
    ):
        aliases = {attribute, attribute.replace("_", " ")}
        if any(
            re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", lowered)
            for alias in aliases
        ):
            attributes.append(attribute)
    return attributes


def detect_rejected_constraints(
    user_message: str,
    turn: int,
    *,
    vocabulary: CatalogVocabulary | None = None,
) -> list[dict]:
    text = str(user_message or "")
    rejected: list[Constraint] = []
    for start, end in _negative_spans(text):
        window = text[start:end]
        positive_category_heads = _negative_head_categories(window, vocabulary)
        rejected.extend(
            item
            for item in _matched_constraints(
                    window,
                    turn,
                    text,
                    vocabulary=vocabulary,
                    hard=True,
                    rejected=True,
                )
            if not (
                item.attribute == "category"
                and item.normalized_value in positive_category_heads
            )
        )

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
