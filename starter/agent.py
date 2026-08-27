from __future__ import annotations

from pathlib import Path
from typing import Protocol

from starter.contracts import RetrievalRequest, RetrievalResult
from starter.core.clarification import choose_clarification
from starter.core.context_engine import (
    detect_no_preference_attributes,
    detect_override,
    detect_rejected_constraints,
    assess_intent,
    extract_constraints,
)
from starter.core.diagnostics import state_diagnostics
from starter.core.decision_evidence import build_decision_evidence
from starter.core.planner import Strategy, StrategyConfig, plan_strategy
from starter.core.query_builder import build_distilled_query
from starter.core.response_guard import guard_response
from starter.core.state import SessionState
from starter.retrieval import HybridRetriever


class Retriever(Protocol):
    catalog_ids: frozenset[str]
    fallback_ids: tuple[str, ...]

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        ...


class Agent:
    """Stateful Control Plane backed by the shared local retrieval seam."""

    def __init__(
        self,
        catalog_path: str | Path = "data/catalog.jsonl",
        strategy_config: StrategyConfig | None = None,
        retriever: Retriever | None = None,
    ) -> None:
        self.catalog_path = Path(catalog_path)
        self.strategy_config = strategy_config or StrategyConfig()
        self.retriever = retriever if retriever is not None else HybridRetriever(self.catalog_path)
        self._sessions: dict[str, SessionState] = {}
        self._catalog_ids = set(self.retriever.catalog_ids)
        self._fallback_ids = list(self.retriever.fallback_ids)

    def reset(self, session_id: str, user_profile: dict) -> None:
        # The profile is anonymized and may be used for personalization.
        self._sessions[session_id] = SessionState(session_id=session_id, user_profile=dict(user_profile or {}))

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
        strategy = None
        if state is not None:
            state.record_user_turn(turn, user_message)
            constraints = extract_constraints(user_message, turn)
            override = detect_override(user_message)
            no_preference_attributes = detect_no_preference_attributes(user_message)
            rejected_constraints = detect_rejected_constraints(user_message, turn)
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
            query_text = build_distilled_query(user_message, state.active_constraints)
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
            decision_evidence = build_decision_evidence(
                retrieval_result,
                state=state,
                turn=turn,
                top_k=top_k,
                response_fallback_used=response_fallback_used,
            )
            diagnostics = response.get("diagnostics") if isinstance(response, dict) else {}
            if not isinstance(diagnostics, dict):
                diagnostics = {}
            diagnostics["decision_evidence"] = decision_evidence.to_diagnostics()
            diagnostics.update(state_diagnostics(state))
            response["diagnostics"] = diagnostics
            candidate_evidence = {
                candidate.parent_asin: candidate.evidence_text or ""
                for candidate in (retrieval_result.candidates[:top_k] if retrieval_result else [])
            }
            candidate_texts = [
                candidate_evidence.get(str(item.get("parent_asin", "")).strip(), "")
                for item in raw_recommendations
                if isinstance(item, dict)
            ]
            ask_attribute, question = choose_clarification(
                state,
                turn=turn,
                candidate_texts=candidate_texts,
                decision_evidence=decision_evidence,
            )
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
