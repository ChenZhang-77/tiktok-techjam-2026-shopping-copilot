from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Protocol

from starter.contracts import RetrievalRequest, RetrievalResult
from starter.core.context_engine import (
    CATEGORY_TERMS,
    COLORS,
    MATERIALS,
    STYLE_TERMS,
    TOKEN_RE,
    USE_CASES,
    CatalogVocabulary,
    detect_no_preference_attributes,
    detect_override,
    detect_rejected_constraints,
    assess_intent,
    extract_constraints,
)
from starter.core.diagnostics import state_diagnostics
from starter.core.planner import Strategy, StrategyConfig, plan_strategy
from starter.core.query_builder import QueryPlan, build_query_plan
from starter.core.question_policy import QuestionPolicy
from starter.core.response_guard import guard_response
from starter.core.semantic_understanding import (
    ALLOWED_ATTRIBUTES,
    DEFAULT_CONFIG_VERSION,
    ConstraintEvidence,
    SemanticInterpreter,
    UnderstandingRequest,
)
from starter.core.state import SessionState
from starter.retrieval import ConditionalDenseRetriever


class Retriever(Protocol):
    catalog_ids: frozenset[str]
    fallback_ids: tuple[str, ...]

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        ...


class Agent:
    """Stateful Control Plane backed by the shared local retrieval seam."""

    def __init__(
        self,
        catalog_path: str | Path | None = None,
        strategy_config: StrategyConfig | None = None,
        retriever: Retriever | None = None,
        semantic_interpreter: SemanticInterpreter | None = None,
    ) -> None:
        requested_catalog_path = Path(catalog_path) if catalog_path is not None else None
        retriever_catalog_path = getattr(retriever, "catalog_path", None)
        if retriever is not None and retriever_catalog_path is not None:
            effective_catalog_path = Path(retriever_catalog_path)
            if (
                requested_catalog_path is not None
                and requested_catalog_path.resolve() != effective_catalog_path.resolve()
            ):
                raise ValueError(
                    "catalog_path must match the injected retriever.catalog_path"
                )
        else:
            effective_catalog_path = requested_catalog_path or Path("data/catalog.jsonl")
        self.catalog_path = effective_catalog_path
        self.strategy_config = strategy_config or StrategyConfig()
        catalog_backed_retriever = retriever is None or retriever_catalog_path is not None
        self.context_vocabulary = (
            CatalogVocabulary.from_catalog(self.catalog_path)
            if catalog_backed_retriever
            else CatalogVocabulary.empty()
        )
        if retriever is None:
            self.retriever = ConditionalDenseRetriever.from_catalog(self.catalog_path)
        else:
            self.retriever = retriever
        self._sessions: dict[str, SessionState] = {}
        self.semantic_interpreter = semantic_interpreter
        self._semantic_diagnostics: dict[tuple[str, int], dict[str, object]] = {}
        self._semantic_attempted_turns: set[tuple[str, int]] = set()
        self._semantic_static_allowed_values = {
            "material": tuple(sorted(MATERIALS)),
            "color": tuple(sorted(COLORS)),
            "size": (
                "xxs", "xs", "s", "m", "l", "xl", "xxl", "xxxl",
                "small", "medium", "large", "wide", "narrow",
            ),
            "style": tuple(sorted(STYLE_TERMS)),
            "use_case": tuple(sorted(USE_CASES)),
        }
        self._catalog_ids = set(self.retriever.catalog_ids)
        self._fallback_ids = list(self.retriever.fallback_ids)
        self.question_policy = QuestionPolicy()

    def reset(self, session_id: str, user_profile: dict) -> None:
        # The profile is anonymized and may be used for personalization.
        self._sessions[session_id] = SessionState(session_id=session_id, user_profile=dict(user_profile or {}))
        self._semantic_diagnostics = {
            key: value
            for key, value in self._semantic_diagnostics.items()
            if key[0] != session_id
        }
        self._semantic_attempted_turns = {
            key for key in self._semantic_attempted_turns if key[0] != session_id
        }

    def semantic_diagnostics(self, session_id: str, turn: int) -> dict[str, object] | None:
        """Return safe Shadow-only diagnostics without changing the response schema."""

        diagnostics = self._semantic_diagnostics.get((session_id, turn))
        return copy.deepcopy(diagnostics) if diagnostics is not None else None

    def _respond_impl(
        self,
        session_id: str,
        query_text: str,
        turn: int,
        top_k: int,
        strategy: Strategy | None = None,
    ) -> tuple[dict, RetrievalResult]:
        if session_id not in self._sessions:
            raise RuntimeError("reset must be called before respond")
        if strategy is None:
            raise RuntimeError("strategy must be planned before retrieval")
        state = self._sessions[session_id]
        request = RetrievalRequest(
            session_id=session_id,
            turn=turn,
            top_k=top_k,
            query=query_text,
            intent=strategy.intent,
            strategy=strategy,
            active_constraints=[dict(item) for item in state.active_constraints],
            no_preference_attributes=sorted(state.no_preference_attributes),
            rejected_constraints=[dict(item) for item in state.rejected_constraints],
            asked_attributes=sorted(state.asked_attributes),
        )
        result = self.retriever.retrieve(request)
        recommendations = result.recommendations(top_k)
        fallback_used = result.diagnostics.fallback_used or len(recommendations) < top_k
        response = {
            "message": "Here are the closest matches I found.",
            "ask_attribute": None,
            "recommendations": recommendations,
            "diagnostics": {
                "strategy": strategy.to_dict(),
                "retrieval": result.diagnostics.to_dict(),
                "fallback_used": fallback_used,
            },
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }
        return response, result

    def respond(
        self,
        session_id: str,
        user_message: str,
        turn: int,
        top_k: int,
    ) -> dict:
        state = self._sessions.get(session_id)
        query_text = user_message
        query_plan: QueryPlan | None = None
        strategy = None
        if state is not None:
            state.record_user_turn(turn, user_message)
            constraints = extract_constraints(
                user_message,
                turn,
                vocabulary=self.context_vocabulary,
            )
            override = detect_override(user_message)
            no_preference_attributes = detect_no_preference_attributes(user_message)
            rejected_constraints = detect_rejected_constraints(
                user_message,
                turn,
                vocabulary=self.context_vocabulary,
            )
            try:
                self._run_semantic_shadow(
                    state=state,
                    user_message=user_message,
                    turn=turn,
                    constraints=constraints,
                    override=override,
                    no_preference_attributes=no_preference_attributes,
                    rejected_constraints=rejected_constraints,
                )
            except Exception:
                self._semantic_diagnostics[(session_id, turn)] = (
                    self._semantic_fallback_diagnostics("interpreter_error")
                )
            state.apply_user_context(
                constraints=constraints,
                override=override,
                no_preference_attributes=no_preference_attributes,
                rejected_constraints=rejected_constraints,
            )
            state.set_intent_assessment(
                assess_intent(
                    user_message,
                    constraints,
                    active_constraints=state.active_constraints,
                    turn=turn,
                    previous=state.intent_assessment,
                    override=override,
                    no_preference_attributes=tuple(
                        sorted(state.no_preference_attributes)
                    ),
                )
            )
            strategy = plan_strategy(state, turn=turn, top_k=top_k, config=self.strategy_config)
            state.previous_strategy = strategy.to_dict()
            query_plan = build_query_plan(
                user_message,
                state.active_constraints,
                rejected_constraints=state.rejected_constraints,
                overridden_constraints=state.overridden_constraints,
            )
            query_text = query_plan.rendered_query
            state.previous_distilled_query = query_text
        try:
            response, retrieval_result = self._respond_impl(
                session_id, query_text, turn, top_k, strategy
            )
        except Exception:
            retrieval_result = None
            response = {
                "message": "Here are the closest matches I found.",
                "ask_attribute": None,
                "recommendations": [],
                "diagnostics": {
                    "strategy": strategy.to_dict() if strategy else None,
                    "retrieval": {
                        "route": "fallback",
                        "candidate_count": 0,
                        "fallback_used": True,
                        "latency_ms": None,
                        "notes": ["retrieval_error"],
                    },
                    "fallback_used": True,
                },
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }
        if state is not None:
            raw_recommendations = (
                response.get("recommendations") if isinstance(response, dict) else []
            )
            if not isinstance(raw_recommendations, list):
                raw_recommendations = []
            valid_response_ids: set[str] = set()
            for item in raw_recommendations:
                if not isinstance(item, dict):
                    continue
                parent_asin = str(item.get("parent_asin", "")).strip()
                if parent_asin in self._catalog_ids:
                    valid_response_ids.add(parent_asin)
            response_diagnostics = (
                response.get("diagnostics") if isinstance(response, dict) else {}
            )
            response_fallback_used = bool(
                isinstance(response_diagnostics, dict)
                and response_diagnostics.get("fallback_used")
            ) or len(valid_response_ids) < top_k
            question_outcome = self.question_policy.decide(
                state=state,
                result=retrieval_result,
                turn=turn,
                top_k=top_k,
                response_fallback_used=response_fallback_used,
            )
            decision_evidence = question_outcome.decision_evidence
            diagnostics = response.get("diagnostics") if isinstance(response, dict) else {}
            if not isinstance(diagnostics, dict):
                diagnostics = {}
            diagnostics["decision_evidence"] = decision_evidence.to_diagnostics()
            diagnostics["question_policy"] = dict(question_outcome.diagnostics)
            diagnostics.update(state_diagnostics(state))
            if query_plan is not None:
                diagnostics["query_plan"] = query_plan.to_diagnostics()
            response["diagnostics"] = diagnostics
            ask_attribute = question_outcome.decision.attribute
            question = question_outcome.decision.question
            if ask_attribute:
                response["ask_attribute"] = ask_attribute
                base_message = response.get("message") if isinstance(response, dict) else ""
                response["message"] = f"{base_message} {question}".strip()
        guarded = guard_response(
            response,
            catalog_ids=self._catalog_ids,
            fallback_ids=self._fallback_ids,
            top_k=top_k,
        )
        if state is not None:
            diagnostics = guarded.get("diagnostics")
            state.previous_diagnostics = diagnostics if isinstance(diagnostics, dict) else None
            state.record_agent_response(guarded)
        return guarded

    def _run_semantic_shadow(
        self,
        *,
        state: SessionState,
        user_message: str,
        turn: int,
        constraints: list,
        override: bool,
        no_preference_attributes: list[str],
        rejected_constraints: list[dict],
    ) -> None:
        if self.semantic_interpreter is None:
            return
        attempt_key = (state.session_id, turn)
        if attempt_key in self._semantic_attempted_turns:
            return
        self._semantic_attempted_turns.add(attempt_key)
        deterministic_intent = assess_intent(
            user_message,
            constraints,
            active_constraints=state.active_constraints,
            turn=turn,
            previous=state.intent_assessment,
            override=override,
            no_preference_attributes=tuple(
                sorted(
                    attribute
                    for attribute in state.no_preference_attributes
                    if attribute in ALLOWED_ATTRIBUTES
                )
            ),
        )
        request = UnderstandingRequest(
            current_message=user_message,
            turn=turn,
            active_constraints=self._state_constraint_evidence(
                state.active_constraints,
                source="active_state",
            ),
            rejected_constraints=self._state_constraint_evidence(
                state.rejected_constraints,
                source="rejected_state",
            ),
            no_preference_attributes=tuple(
                sorted(
                    attribute
                    for attribute in state.no_preference_attributes
                    if attribute in ALLOWED_ATTRIBUTES
                )
            ),
            overridden_constraints=self._state_constraint_evidence(
                state.overridden_constraints,
                source="overridden_state",
            ),
            deterministic_constraints=self._state_constraint_evidence(
                constraints,
                source="parser",
            ),
            deterministic_rejected_constraints=self._state_constraint_evidence(
                rejected_constraints,
                source="parser_rejected",
            ),
            deterministic_no_preference_attributes=tuple(
                sorted(
                    attribute
                    for attribute in no_preference_attributes
                    if attribute in ALLOWED_ATTRIBUTES
                )
            ),
            override_detected=override,
            prior_intent=state.intent,
            deterministic_intent=deterministic_intent.intent,
            intent_evidence=deterministic_intent.evidence,
            allowed_values=self._semantic_allowed_values_for(
                state=state,
                user_message=user_message,
                constraints=constraints,
                rejected_constraints=rejected_constraints,
            ),
            config_version=DEFAULT_CONFIG_VERSION,
            deadline_monotonic_ms=time.monotonic() * 1000 + 2500,
        )
        try:
            outcome = self.semantic_interpreter.interpret(request)
            diagnostics = outcome.to_diagnostics()
        except Exception:
            diagnostics = self._semantic_fallback_diagnostics("interpreter_error")
        self._semantic_diagnostics[(state.session_id, turn)] = diagnostics

    @staticmethod
    def _semantic_fallback_diagnostics(reason: str) -> dict[str, object]:
        return {
            "status": "fallback",
            "trigger_signals": [],
            "backend_called": False,
            "fallback_reason": reason,
            "latency_ms": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "provider_model": None,
            "proposed_counts": {
                "positive": 0,
                "rejected": 0,
                "no_preference": 0,
                "override": 0,
                "semantic_terms": 0,
            },
            "abstain": None,
        }

    @staticmethod
    def _state_constraint_evidence(
        items: list[dict],
        *,
        source: str,
    ) -> tuple[ConstraintEvidence, ...]:
        evidence: list[ConstraintEvidence] = []
        for item in items:
            attribute = str(item.get("attribute") or "")
            value = str(item.get("normalized_value") or item.get("raw_value") or "")
            if not attribute or not value:
                continue
            try:
                evidence.append(
                    ConstraintEvidence(
                        attribute=attribute,
                        value=value,
                        evidence_span=str(item.get("source_text") or ""),
                        confidence=float(item.get("confidence", 1.0)),
                        hard=bool(item.get("hard", False)),
                        source=source,
                    )
                )
            except (TypeError, ValueError):
                continue
        return tuple(evidence)

    def _semantic_allowed_values_for(
        self,
        *,
        state: SessionState,
        user_message: str,
        constraints: list[dict],
        rejected_constraints: list[dict],
    ) -> dict[str, tuple[str, ...]]:
        """Build a relevant vocabulary summary capped by the A13-S0 contract."""

        allowed = dict(self._semantic_static_allowed_values)
        category_values = set(CATEGORY_TERMS)
        for item in (
            *state.active_constraints,
            *state.rejected_constraints,
            *state.overridden_constraints,
            *constraints,
            *rejected_constraints,
        ):
            if item.get("attribute") != "category":
                continue
            value = str(item.get("normalized_value") or item.get("raw_value") or "").strip()
            if value:
                category_values.add(value)

        message_tokens = {
            token.group(0).lower() for token in TOKEN_RE.finditer(user_message)
        }
        related_catalog_values = sorted(
            value
            for value in self.context_vocabulary.category_terms
            if message_tokens & set(value.split())
        )
        static_count = sum(len(values) for values in allowed.values())
        remaining = max(0, 200 - static_count)
        ordered_categories = sorted(category_values)
        for value in related_catalog_values:
            if value not in category_values:
                ordered_categories.append(value)
        allowed["category"] = tuple(ordered_categories[:remaining])
        return allowed
