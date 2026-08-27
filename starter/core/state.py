from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starter.core.context_engine import IntentAssessment


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
    expired_constraints: list[dict] = field(default_factory=list)
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
        self._expire_low_confidence_features()
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
            self.override_seen = True
            override_attributes = {str(item.get("attribute")) for item in constraints if item.get("attribute")}
            if "category" in override_attributes:
                override_attributes.update({"material", "color", "size", "style", "brand", "budget", "feature", "use_case"})
            for attribute in override_attributes:
                self._deactivate_attribute(attribute, destination=self.overridden_constraints)
            self.previous_candidate_ids = []
            self.override_events.append({
                "turn": self.current_turn,
                "attributes": sorted(override_attributes),
                "new_values": [
                    str(item.get("normalized_value") or item.get("raw_value") or "")
                    for item in constraints
                    if item.get("attribute")
                ],
                "reason": "category reset" if "category" in override_attributes else "attribute replacement",
            })
        filtered = [
            constraint
            for constraint in constraints
            if str(constraint.get("attribute")) not in self.no_preference_attributes
            and (
                str(constraint.get("attribute") or ""),
                str(constraint.get("normalized_value") or constraint.get("raw_value") or ""),
            ) not in rejected_keys
        ]
        self.add_constraints(filtered)

    def _expire_low_confidence_features(self) -> None:
        kept: list[dict] = []
        for constraint in self.active_constraints:
            source_turn = constraint.get("source_turn")
            age = (
                self.current_turn - source_turn
                if isinstance(source_turn, int) and not isinstance(source_turn, bool)
                else 0
            )
            if (
                constraint.get("attribute") == "feature"
                and float(constraint.get("confidence") or 0.0) <= 0.35
                and age >= 2
            ):
                expired = dict(constraint)
                expired["active"] = False
                self.expired_constraints.append(expired)
                continue
            kept.append(constraint)
        self.active_constraints = kept

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
