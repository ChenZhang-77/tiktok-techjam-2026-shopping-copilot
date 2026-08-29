from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


ALLOWED_ATTRIBUTES = (
    "category",
    "material",
    "color",
    "size",
    "style",
    "brand",
    "budget",
    "feature",
    "use_case",
)
SCHEMA_VERSION = "a13-understanding-schema-v1"
DEFAULT_PROMPT_VERSION = "a13-understanding-v1"
DEFAULT_CONFIG_VERSION = "a13-s0-config-v1"
OUTPUT_FIELDS = {
    "intent_hint",
    "positive_constraints",
    "rejected_constraints",
    "no_preference_attributes",
    "override_attributes",
    "semantic_terms",
    "abstain",
}
TRIGGER_ORDER = (
    "override_without_value",
    "mixed_polarity_clause",
    "low_confidence_residual_feature",
    "multi_clause_without_structure",
    "positive_rejected_attribute_conflict",
    "unexplained_intent_transition",
)
SAFE_FALLBACK_REASONS = {
    "abstain_conflict",
    "backend_error",
    "bad_attribute",
    "bad_span",
    "bad_value",
    "duplicate_attribute",
    "duplicate_term",
    "deadline_exceeded",
    "empty_response",
    "extra_field",
    "internal_error",
    "invalid_telemetry",
    "invalid_provider_json",
    "malformed_json",
    "missing_field",
    "missing_no_preference_evidence",
    "positive_no_preference_conflict",
    "positive_rejected_conflict",
    "provider_error",
    "state_conflict",
    "timeout",
    "truncated_json",
    "unsupported_override",
    "value_evidence_mismatch",
    "wrong_type",
}
TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
SHOPPING_RE = re.compile(r"\b(?:shop|shopping|need|want|find|show|looking)\b", re.I)
CLAUSE_RE = re.compile(r"[;,]|\b(?:but|however|although|while)\b", re.I)
NO_PREFERENCE_RE = re.compile(
    r"\b(?:no preference|don't care|do not care|doesn't matter|does not matter|any\s+\w+\s+(?:is\s+)?(?:fine|works))\b",
    re.I,
)


def _normalize(value: object) -> str:
    return " ".join(token.lower() for token in TOKEN_RE.findall(str(value or "")))


def _safe_fallback_reason(value: object) -> str:
    reason = str(value or "").strip().lower()
    if reason in SAFE_FALLBACK_REASONS or re.fullmatch(
        r"http_(?:401|403|429|5\d\d)", reason
    ):
        return reason
    return "backend_error"


def _safe_provider_model(value: object) -> str | None:
    model = str(value or "").strip()
    if model and len(model) <= 100 and re.fullmatch(r"[A-Za-z0-9._:/-]+", model):
        return model
    return None


def _safe_nonnegative_float(value: object) -> float:
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    ):
        return float(value)
    return 0.0


def _safe_nonnegative_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


@dataclass(frozen=True)
class ConstraintEvidence:
    attribute: str
    value: str
    evidence_span: str = ""
    confidence: float = 1.0
    hard: bool = True
    source: str = "state"

    def __post_init__(self) -> None:
        if self.attribute not in ALLOWED_ATTRIBUTES:
            raise ValueError("invalid constraint attribute")
        if not self.value.strip():
            raise ValueError("constraint value must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("constraint confidence must be between 0 and 1")


@dataclass(frozen=True)
class ConstraintProposal:
    attribute: str
    value: str
    evidence_span: str
    hard: bool


@dataclass(frozen=True)
class UnderstandingDelta:
    intent_hint: str | None
    positive_constraints: tuple[ConstraintProposal, ...]
    rejected_constraints: tuple[ConstraintProposal, ...]
    no_preference_attributes: tuple[str, ...]
    override_attributes: tuple[str, ...]
    semantic_terms: tuple[str, ...]
    abstain: bool


@dataclass(frozen=True)
class UnderstandingRequest:
    current_message: str
    turn: int
    active_constraints: tuple[ConstraintEvidence, ...] = ()
    rejected_constraints: tuple[ConstraintEvidence, ...] = ()
    no_preference_attributes: tuple[str, ...] = ()
    overridden_constraints: tuple[ConstraintEvidence, ...] = ()
    deterministic_constraints: tuple[ConstraintEvidence, ...] = ()
    deterministic_rejected_constraints: tuple[ConstraintEvidence, ...] = ()
    deterministic_no_preference_attributes: tuple[str, ...] = ()
    override_detected: bool = False
    prior_intent: str | None = None
    deterministic_intent: str | None = None
    intent_evidence: tuple[str, ...] = ()
    allowed_values: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    prompt_version: str = DEFAULT_PROMPT_VERSION
    config_version: str = DEFAULT_CONFIG_VERSION
    deadline_monotonic_ms: float | None = None
    timeout_ms: int = 2500

    def __post_init__(self) -> None:
        if not self.current_message.strip():
            raise ValueError("current_message must not be empty")
        if self.turn < 1:
            raise ValueError("turn must be positive")
        if (
            not isinstance(self.timeout_ms, int)
            or isinstance(self.timeout_ms, bool)
            or self.timeout_ms <= 0
        ):
            raise ValueError("timeout_ms must be positive")
        if (
            not isinstance(self.prompt_version, str)
            or not isinstance(self.config_version, str)
            or not self.prompt_version.strip()
            or not self.config_version.strip()
        ):
            raise ValueError("prompt_version and config_version must not be empty")
        if self.deadline_monotonic_ms is not None and (
            not isinstance(self.deadline_monotonic_ms, (int, float))
            or isinstance(self.deadline_monotonic_ms, bool)
            or not math.isfinite(self.deadline_monotonic_ms)
        ):
            raise ValueError("deadline_monotonic_ms must be finite numeric or None")
        for intent in (self.prior_intent, self.deterministic_intent):
            if intent not in {None, "buying", "browsing"}:
                raise ValueError("intent must be buying, browsing, or None")
        for attribute in (
            *self.no_preference_attributes,
            *self.deterministic_no_preference_attributes,
            *self.allowed_values.keys(),
        ):
            if attribute not in ALLOWED_ATTRIBUTES:
                raise ValueError("invalid request attribute")


@dataclass(frozen=True)
class InterpreterConfig:
    enabled: bool = False
    key_available: bool = False
    max_user_chars: int = 2000
    max_state_chars: int = 2000
    max_vocab_items: int = 200

    def __post_init__(self) -> None:
        if min(self.max_user_chars, self.max_state_chars, self.max_vocab_items) <= 0:
            raise ValueError("interpreter input limits must be positive")


@dataclass(frozen=True)
class BackendResult:
    payload: object
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    provider_model: str | None = None
    provider_request_id: str | None = None


@dataclass(frozen=True)
class UnderstandingOutcome:
    delta: UnderstandingDelta | None
    trigger_signals: tuple[str, ...]
    fallback_reason: str | None
    backend_called: bool
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    provider_model: str | None = None

    def to_diagnostics(self) -> dict[str, object]:
        delta = self.delta
        status = "valid_shadow_delta" if delta is not None else "fallback"
        return {
            "status": status,
            "trigger_signals": list(self.trigger_signals),
            "backend_called": self.backend_called,
            "fallback_reason": self.fallback_reason,
            "latency_ms": round(_safe_nonnegative_float(self.latency_ms), 6),
            "prompt_tokens": _safe_nonnegative_int(self.prompt_tokens),
            "completion_tokens": _safe_nonnegative_int(self.completion_tokens),
            "provider_model": _safe_provider_model(self.provider_model),
            "proposed_counts": {
                "positive": len(delta.positive_constraints) if delta else 0,
                "rejected": len(delta.rejected_constraints) if delta else 0,
                "no_preference": len(delta.no_preference_attributes) if delta else 0,
                "override": len(delta.override_attributes) if delta else 0,
                "semantic_terms": len(delta.semantic_terms) if delta else 0,
            },
            "abstain": delta.abstain if delta else None,
        }


class SemanticInterpreter(Protocol):
    def interpret(self, request: UnderstandingRequest) -> UnderstandingOutcome:
        ...


class SemanticBackend(Protocol):
    def infer(self, request: UnderstandingRequest) -> BackendResult:
        ...


class SemanticUnderstandingError(RuntimeError):
    pass


class FakeSemanticBackend:
    """Deterministic test backend. It never performs network I/O."""

    def __init__(
        self,
        result: BackendResult | object | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls = 0
        self.requests: list[UnderstandingRequest] = []

    def infer(self, request: UnderstandingRequest) -> BackendResult:
        self.calls += 1
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if isinstance(self.result, BackendResult):
            return self.result
        return BackendResult(payload=self.result)


def detect_trigger_signals(request: UnderstandingRequest) -> tuple[str, ...]:
    found: set[str] = set()
    positive_attributes = {
        item.attribute for item in request.deterministic_constraints
    }
    rejected_attributes = {
        item.attribute for item in request.deterministic_rejected_constraints
    }
    if request.override_detected and not request.deterministic_constraints:
        found.add("override_without_value")
    if request.deterministic_constraints and (
        request.deterministic_rejected_constraints
        or request.deterministic_no_preference_attributes
    ):
        found.add("mixed_polarity_clause")
    if any(
        item.attribute == "feature" and item.confidence <= 0.35
        for item in request.deterministic_constraints
    ):
        found.add("low_confidence_residual_feature")
    if (
        not request.deterministic_constraints
        and SHOPPING_RE.search(request.current_message)
        and len(CLAUSE_RE.findall(request.current_message)) >= 1
    ):
        found.add("multi_clause_without_structure")
    if positive_attributes & rejected_attributes:
        found.add("positive_rejected_attribute_conflict")
    if (
        request.prior_intent is not None
        and request.deterministic_intent is not None
        and request.prior_intent != request.deterministic_intent
        and not request.intent_evidence
    ):
        found.add("unexplained_intent_transition")
    return tuple(signal for signal in TRIGGER_ORDER if signal in found)


class GuardedSemanticInterpreter:
    """Validates a single optional Shadow proposal and otherwise falls back."""

    def __init__(
        self,
        backend: SemanticBackend,
        *,
        config: InterpreterConfig | None = None,
    ) -> None:
        self.backend = backend
        self.config = config or InterpreterConfig()

    def interpret(self, request: UnderstandingRequest) -> UnderstandingOutcome:
        signals = detect_trigger_signals(request)
        if not self.config.enabled:
            return self._fallback(signals, "disabled", False)
        if not signals:
            return self._fallback(signals, "ineligible", False)
        if not self.config.key_available:
            return self._fallback(signals, "no_key", False)
        if (
            request.deadline_monotonic_ms is not None
            and time.monotonic() * 1000 >= request.deadline_monotonic_ms
        ):
            return self._fallback(signals, "deadline_exceeded", False)
        if self._input_too_large(request):
            return self._fallback(signals, "input_too_large", False)

        started = time.perf_counter()
        result, error, timed_out = self._infer_with_timeout(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if timed_out:
            return self._fallback(signals, "timeout", True, latency_ms=elapsed_ms)
        if isinstance(error, SemanticUnderstandingError):
            reason = _safe_fallback_reason(error)
            return self._fallback(
                signals,
                reason,
                True,
                latency_ms=elapsed_ms,
            )
        if error is not None:
            return self._fallback(
                signals,
                "internal_error",
                True,
                latency_ms=elapsed_ms,
            )
        if not isinstance(result, BackendResult):
            return self._fallback(
                signals,
                "internal_error",
                True,
                latency_ms=elapsed_ms,
            )
        if not self._valid_telemetry(result):
            return self._fallback(
                signals,
                "invalid_telemetry",
                True,
                latency_ms=elapsed_ms,
            )

        try:
            delta = validate_understanding_delta(result.payload, request)
        except SemanticUnderstandingError as error:
            return self._fallback(
                signals,
                str(error),
                True,
                result=result,
            )
        return UnderstandingOutcome(
            delta=delta,
            trigger_signals=signals,
            fallback_reason=None,
            backend_called=True,
            latency_ms=result.latency_ms,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            provider_model=result.provider_model,
        )

    def _infer_with_timeout(
        self,
        request: UnderstandingRequest,
    ) -> tuple[BackendResult | None, Exception | None, bool]:
        """Return by the request deadline even if a backend implementation blocks.

        Provider adapters must still set their own transport timeout so the daemon
        worker does not retain network resources after this guard has fallen back.
        """

        remaining_ms = float(request.timeout_ms)
        if request.deadline_monotonic_ms is not None:
            remaining_ms = min(
                remaining_ms,
                request.deadline_monotonic_ms - time.monotonic() * 1000,
            )
        if remaining_ms <= 0:
            return None, None, True

        completed = threading.Event()
        result_box: list[BackendResult] = []
        error_box: list[Exception] = []

        def invoke() -> None:
            try:
                result_box.append(self.backend.infer(request))
            except Exception as error:  # isolated and never rendered verbatim
                error_box.append(error)
            finally:
                completed.set()

        worker = threading.Thread(target=invoke, daemon=True, name="a13-shadow-backend")
        worker.start()
        if not completed.wait(remaining_ms / 1000):
            return None, None, True
        if error_box:
            return None, error_box[0], False
        return (result_box[0] if result_box else None), None, False

    @staticmethod
    def _valid_telemetry(result: BackendResult) -> bool:
        return (
            isinstance(result.latency_ms, (int, float))
            and not isinstance(result.latency_ms, bool)
            and math.isfinite(result.latency_ms)
            and result.latency_ms >= 0
            and isinstance(result.prompt_tokens, int)
            and not isinstance(result.prompt_tokens, bool)
            and result.prompt_tokens >= 0
            and isinstance(result.completion_tokens, int)
            and not isinstance(result.completion_tokens, bool)
            and result.completion_tokens >= 0
        )

    def _input_too_large(self, request: UnderstandingRequest) -> bool:
        state_items = (
            *request.active_constraints,
            *request.rejected_constraints,
            *request.overridden_constraints,
        )
        state_chars = sum(
            len(item.attribute) + len(item.value) + len(item.evidence_span)
            for item in state_items
        ) + sum(len(item) for item in request.no_preference_attributes)
        vocab_items = sum(len(values) for values in request.allowed_values.values())
        return (
            len(request.current_message) > self.config.max_user_chars
            or state_chars > self.config.max_state_chars
            or vocab_items > self.config.max_vocab_items
        )

    @staticmethod
    def _fallback(
        signals: tuple[str, ...],
        reason: str,
        backend_called: bool,
        *,
        latency_ms: float = 0.0,
        result: BackendResult | None = None,
    ) -> UnderstandingOutcome:
        return UnderstandingOutcome(
            delta=None,
            trigger_signals=signals,
            fallback_reason=reason,
            backend_called=backend_called,
            latency_ms=result.latency_ms if result is not None else latency_ms,
            prompt_tokens=result.prompt_tokens if result is not None else 0,
            completion_tokens=result.completion_tokens if result is not None else 0,
            provider_model=result.provider_model if result is not None else None,
        )


def validate_understanding_delta(
    payload: object,
    request: UnderstandingRequest,
) -> UnderstandingDelta:
    if not isinstance(payload, dict):
        raise SemanticUnderstandingError("wrong_type")
    if set(payload) != OUTPUT_FIELDS:
        reason = "extra_field" if set(payload) - OUTPUT_FIELDS else "missing_field"
        raise SemanticUnderstandingError(reason)
    if not isinstance(payload["abstain"], bool):
        raise SemanticUnderstandingError("wrong_type")
    intent_hint = payload["intent_hint"]
    if intent_hint not in {None, "buying", "browsing"}:
        raise SemanticUnderstandingError("wrong_type")

    positive = _parse_constraints(
        payload["positive_constraints"], request, rejected=False
    )
    rejected = _parse_constraints(
        payload["rejected_constraints"], request, rejected=True
    )
    no_preference = _parse_attributes(payload["no_preference_attributes"])
    overrides = _parse_attributes(payload["override_attributes"])
    semantic_terms = _parse_semantic_terms(payload["semantic_terms"], request)

    positive_keys = {(item.attribute, item.value) for item in positive}
    rejected_keys = {(item.attribute, item.value) for item in rejected}
    if positive_keys & rejected_keys:
        raise SemanticUnderstandingError("positive_rejected_conflict")
    if {item.attribute for item in positive} & set(no_preference):
        raise SemanticUnderstandingError("positive_no_preference_conflict")

    prior_rejected = {
        (item.attribute, _normalize(item.value)) for item in request.rejected_constraints
    }
    prior_no_preference = set(request.no_preference_attributes)
    if any(
        not item.hard
        and (
            (item.attribute, item.value) in prior_rejected
            or item.attribute in prior_no_preference
        )
        for item in positive
    ):
        raise SemanticUnderstandingError("state_conflict")

    current_evidence_attributes = {
        item.attribute for item in (*positive, *rejected)
    } | set(no_preference)
    if any(attribute not in current_evidence_attributes for attribute in overrides):
        raise SemanticUnderstandingError("unsupported_override")
    if overrides and not request.override_detected:
        raise SemanticUnderstandingError("unsupported_override")
    detected_no_preference = set(request.deterministic_no_preference_attributes)
    for attribute in no_preference:
        aliases = {attribute, attribute.replace("_", " ")}
        explicit_attribute = any(
            re.search(
                rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])",
                request.current_message,
                re.I,
            )
            for alias in aliases
        )
        if attribute not in detected_no_preference and not (
            explicit_attribute and NO_PREFERENCE_RE.search(request.current_message)
        ):
            raise SemanticUnderstandingError("missing_no_preference_evidence")

    if payload["abstain"] and (
        intent_hint is not None
        or positive
        or rejected
        or no_preference
        or overrides
        or semantic_terms
    ):
        raise SemanticUnderstandingError("abstain_conflict")

    return UnderstandingDelta(
        intent_hint=intent_hint,
        positive_constraints=positive,
        rejected_constraints=rejected,
        no_preference_attributes=no_preference,
        override_attributes=overrides,
        semantic_terms=semantic_terms,
        abstain=payload["abstain"],
    )


def _parse_constraints(
    value: object,
    request: UnderstandingRequest,
    *,
    rejected: bool,
) -> tuple[ConstraintProposal, ...]:
    if not isinstance(value, list):
        raise SemanticUnderstandingError("wrong_type")
    expected_fields = {"attribute", "value", "evidence_span"}
    if not rejected:
        expected_fields.add("hard")
    proposals: list[ConstraintProposal] = []
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != expected_fields:
            raise SemanticUnderstandingError("wrong_type")
        attribute = raw.get("attribute")
        raw_value = raw.get("value")
        evidence_span = raw.get("evidence_span")
        hard = False if rejected else raw.get("hard")
        if (
            not isinstance(attribute, str)
            or not isinstance(raw_value, str)
            or not isinstance(evidence_span, str)
            or not isinstance(hard, bool)
        ):
            raise SemanticUnderstandingError("wrong_type")
        if attribute not in ALLOWED_ATTRIBUTES:
            raise SemanticUnderstandingError("bad_attribute")
        if not evidence_span or evidence_span.casefold() not in request.current_message.casefold():
            raise SemanticUnderstandingError("bad_span")
        normalized = _validated_value(attribute, raw_value, request)
        normalized_evidence = _normalize(evidence_span)
        if f" {normalized} " not in f" {normalized_evidence} ":
            raise SemanticUnderstandingError("value_evidence_mismatch")
        proposals.append(
            ConstraintProposal(
                attribute=attribute,
                value=normalized,
                evidence_span=evidence_span,
                hard=hard,
            )
        )
    return tuple(proposals)


def _validated_value(
    attribute: str,
    value: str,
    request: UnderstandingRequest,
) -> str:
    normalized = _normalize(value)
    if not normalized:
        raise SemanticUnderstandingError("bad_value")
    allowed = {
        _normalize(item): _normalize(item)
        for item in request.allowed_values.get(attribute, ())
        if _normalize(item)
    }
    if allowed and normalized not in allowed:
        raise SemanticUnderstandingError("bad_value")
    if not allowed and attribute not in {"brand", "budget", "feature"}:
        raise SemanticUnderstandingError("bad_value")
    return normalized


def _parse_attributes(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SemanticUnderstandingError("wrong_type")
    if any(item not in ALLOWED_ATTRIBUTES for item in value):
        raise SemanticUnderstandingError("bad_attribute")
    if len(set(value)) != len(value):
        raise SemanticUnderstandingError("duplicate_attribute")
    return tuple(value)


def _parse_semantic_terms(
    value: object,
    request: UnderstandingRequest,
) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SemanticUnderstandingError("wrong_type")
    terms: list[str] = []
    for item in value:
        if not item or item.casefold() not in request.current_message.casefold():
            raise SemanticUnderstandingError("bad_span")
        normalized = _normalize(item)
        if not normalized:
            raise SemanticUnderstandingError("bad_value")
        terms.append(normalized)
    if len(set(terms)) != len(terms):
        raise SemanticUnderstandingError("duplicate_term")
    return tuple(terms)
