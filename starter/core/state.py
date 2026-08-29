from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starter.core.context_engine import IntentAssessment


def _normalized_words(value: object) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _contains_normalized_phrase(container: object, phrase: object) -> bool:
    normalized_container = _normalized_words(container)
    normalized_phrase = _normalized_words(phrase)
    return bool(
        normalized_phrase
        and f" {normalized_phrase} " in f" {normalized_container} "
    )


@dataclass
class TurnRecord:
    turn: int
    user_message: str
    agent_message: str = ""
    ask_attribute: str | None = None
    recommendation_ids: list[str] = field(default_factory=list)


@dataclass
class SessionState:
    session_id: str
    user_profile: dict
    current_turn: int = 0
    raw_history: list[TurnRecord] = field(default_factory=list)
    intent: str | None = None
    intent_assessment: IntentAssessment | None = None
    active_constraints: list[dict] = field(default_factory=list)
    overridden_constraints: list[dict] = field(default_factory=list)
    rejected_constraints: list[dict] = field(default_factory=list)
    no_preference_attributes: set[str] = field(default_factory=set)
    asked_attributes: set[str] = field(default_factory=set)
    previous_distilled_query: str = ""
    previous_candidate_ids: list[str] = field(default_factory=list)
    previous_strategy: dict | None = None
    previous_diagnostics: dict | None = None
    override_seen: bool = False
    override_events: list[dict] = field(default_factory=list)

    def set_intent_assessment(self, assessment: IntentAssessment) -> None:
        self.intent_assessment = assessment
        self.intent = assessment.intent

    def record_user_turn(self, turn: int, user_message: str) -> TurnRecord:
        self.current_turn = turn
        record = TurnRecord(turn=turn, user_message=str(user_message))
        self.raw_history.append(record)
        return record

    def add_constraints(self, constraints: list[dict]) -> None:
        existing = {
            (str(item.get("attribute")), str(item.get("normalized_value")))
            for item in self.active_constraints
            if item.get("active", True)
        }
        for constraint in constraints:
            key = (str(constraint.get("attribute")), str(constraint.get("normalized_value")))
            if not key[0] or not key[1] or key in existing:
                continue
            self.active_constraints.append(dict(constraint))
            existing.add(key)

    def apply_user_context(
        self,
        *,
        constraints: list[dict],
        override: bool = False,
        no_preference_attributes: list[str] | None = None,
        rejected_constraints: list[dict] | None = None,
    ) -> None:
        for attribute in no_preference_attributes or []:
            self.mark_no_preference(attribute)
            self._deactivate_attribute(attribute, destination=self.rejected_constraints)
        rejected_keys: set[tuple[str, str]] = set()
        for constraint in rejected_constraints or []:
            rejected = dict(constraint)
            rejected["active"] = False
            attribute = str(rejected.get("attribute") or "")
            value = str(rejected.get("normalized_value") or rejected.get("raw_value") or "")
            if not attribute or not value:
                continue
            rejected_keys.add((attribute, value))
            self._deactivate_value(attribute, value, destination=self.rejected_constraints)
            if not any(
                item.get("attribute") == attribute
                and str(item.get("normalized_value") or item.get("raw_value") or "") == value
                for item in self.rejected_constraints
            ):
                self.rejected_constraints.append(rejected)
        if override and constraints:
            from starter.core.context_engine import detect_prior_preference_reset

            reset_prior_preferences = bool(
                self.raw_history
                and detect_prior_preference_reset(
                    self.raw_history[-1].user_message
                )
            )
            self.override_seen = True
            override_attributes = {str(item.get("attribute")) for item in constraints if item.get("attribute")}
            if "category" in override_attributes:
                override_attributes.update({"material", "color", "size", "style", "brand", "budget", "feature", "use_case"})
            for attribute in override_attributes:
                self._deactivate_attribute(attribute, destination=self.overridden_constraints)
            if reset_prior_preferences and "category" not in override_attributes:
                override_attributes.update(
                    self._deactivate_initial_preferences(
                        destination=self.overridden_constraints
                    )
                )
            self.previous_candidate_ids = []
            self.override_events.append({
                "turn": self.current_turn,
                "attributes": sorted(override_attributes),
                "new_values": [
                    str(item.get("normalized_value") or item.get("raw_value") or "")
                    for item in constraints
                    if item.get("attribute")
                ],
                "reason": (
                    "category reset"
                    if "category" in override_attributes
                    else "preference reset"
                    if reset_prior_preferences
                    else "attribute replacement"
                ),
            })
        # "No preference" suppresses future questions, but it must not hide a
        # later explicit preference supplied by the user.
        for constraint in constraints:
            attribute = str(constraint.get("attribute") or "")
            confidence = constraint.get("confidence")
            is_explicit = (
                confidence is None
                or (isinstance(confidence, (int, float)) and confidence >= 0.50)
            )
            if attribute and is_explicit:
                self.no_preference_attributes.discard(attribute)
        filtered = [
            constraint
            for constraint in constraints
            if str(constraint.get("attribute")) not in self.no_preference_attributes
            and (
                str(constraint.get("attribute") or ""),
                str(constraint.get("normalized_value") or constraint.get("raw_value") or ""),
            ) not in rejected_keys
            and (
                override
                or not self._matches_overridden_constraint(constraint)
            )
        ]
        self.add_constraints(filtered)

    def _deactivate_initial_preferences(self, *, destination: list[dict]) -> set[str]:
        if len(self.raw_history) < 2:
            return set()
        initial_message = self.raw_history[0].user_message
        deactivated_attributes: set[str] = set()
        kept: list[dict] = []
        for constraint in self.active_constraints:
            attribute = str(constraint.get("attribute") or "")
            value = constraint.get("normalized_value") or constraint.get("raw_value")
            if (
                attribute == "category"
                or not constraint.get("active", True)
                or not _contains_normalized_phrase(initial_message, value)
            ):
                kept.append(constraint)
                continue
            inactive = dict(constraint)
            inactive["active"] = False
            destination.append(inactive)
            deactivated_attributes.add(attribute)
        self.active_constraints = kept
        return deactivated_attributes

    def _matches_overridden_constraint(self, constraint: dict) -> bool:
        attribute = str(constraint.get("attribute") or "")
        value = constraint.get("normalized_value") or constraint.get("raw_value")
        return any(
            str(item.get("attribute") or "") == attribute
            and (
                _contains_normalized_phrase(
                    item.get("normalized_value") or item.get("raw_value"),
                    value,
                )
                or _contains_normalized_phrase(
                    value,
                    item.get("normalized_value") or item.get("raw_value"),
                )
            )
            for item in self.overridden_constraints
        )

    def _deactivate_value(self, attribute: str, value: str, *, destination: list[dict]) -> None:
        kept: list[dict] = []
        for constraint in self.active_constraints:
            normalized = str(constraint.get("normalized_value") or constraint.get("raw_value") or "")
            if constraint.get("attribute") != attribute or normalized != value or not constraint.get("active", True):
                kept.append(constraint)
                continue
            inactive = dict(constraint)
            inactive["active"] = False
            destination.append(inactive)
        self.active_constraints = kept

    def _deactivate_attribute(self, attribute: str, *, destination: list[dict]) -> None:
        kept: list[dict] = []
        for constraint in self.active_constraints:
            if constraint.get("attribute") != attribute or not constraint.get("active", True):
                kept.append(constraint)
                continue
            inactive = dict(constraint)
            inactive["active"] = False
            destination.append(inactive)
        self.active_constraints = kept

    def active_constraint_values(self, attribute: str | None = None) -> list[str]:
        values: list[str] = []
        for constraint in self.active_constraints:
            if not constraint.get("active", True):
                continue
            if attribute is not None and constraint.get("attribute") != attribute:
                continue
            value = str(constraint.get("normalized_value") or "").strip()
            if value:
                values.append(value)
        return values

    def record_agent_response(self, response: dict) -> None:
        if not self.raw_history:
            return
        latest = self.raw_history[-1]
        latest.agent_message = str(response.get("message", ""))
        ask_attribute = response.get("ask_attribute")
        latest.ask_attribute = ask_attribute if isinstance(ask_attribute, str) else None
        if latest.ask_attribute:
            self.asked_attributes.add(latest.ask_attribute)
        recommendations = response.get("recommendations")
        if isinstance(recommendations, list):
            latest.recommendation_ids = [
                str(item.get("parent_asin", "")).strip()
                for item in recommendations
                if isinstance(item, dict) and str(item.get("parent_asin", "")).strip()
            ]
        self.previous_candidate_ids = list(latest.recommendation_ids)

    def mark_no_preference(self, attribute: str) -> None:
        if attribute:
            self.no_preference_attributes.add(attribute)

    def has_asked(self, attribute: str) -> bool:
        return attribute in self.asked_attributes
