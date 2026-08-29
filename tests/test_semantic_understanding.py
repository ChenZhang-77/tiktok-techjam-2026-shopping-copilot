from __future__ import annotations

import time
import unittest

from starter.core.semantic_understanding import (
    BackendResult,
    ConstraintEvidence,
    FakeSemanticBackend,
    GuardedSemanticInterpreter,
    InterpreterConfig,
    SemanticUnderstandingError,
    UnderstandingRequest,
    detect_trigger_signals,
)


def _request(**overrides: object) -> UnderstandingRequest:
    values: dict[str, object] = {
        "current_message": "Actually, use leather instead of the earlier material.",
        "turn": 2,
        "active_constraints": (
            ConstraintEvidence("material", "cotton", source="state"),
        ),
        "rejected_constraints": (),
        "no_preference_attributes": (),
        "overridden_constraints": (),
        "deterministic_constraints": (),
        "deterministic_rejected_constraints": (),
        "deterministic_no_preference_attributes": (),
        "override_detected": True,
        "prior_intent": "buying",
        "deterministic_intent": "buying",
        "intent_evidence": ("explicit_override",),
        "allowed_values": {
            "category": ("shoes", "shirts"),
            "material": ("cotton", "leather", "polyester"),
            "color": ("black", "white"),
            "style": ("vintage",),
            "use_case": ("hiking",),
        },
    }
    values.update(overrides)
    return UnderstandingRequest(**values)


def _valid_payload() -> dict:
    return {
        "intent_hint": "buying",
        "positive_constraints": [
            {
                "attribute": "material",
                "value": "Leather",
                "evidence_span": "leather",
                "hard": True,
            }
        ],
        "rejected_constraints": [],
        "no_preference_attributes": [],
        "override_attributes": ["material"],
        "semantic_terms": ["leather"],
        "abstain": False,
    }


class SemanticUnderstandingTest(unittest.TestCase):
    def test_disabled_and_no_key_paths_do_not_call_backend(self) -> None:
        for config, reason in (
            (InterpreterConfig(enabled=False, key_available=True), "disabled"),
            (InterpreterConfig(enabled=True, key_available=False), "no_key"),
        ):
            with self.subTest(reason=reason):
                backend = FakeSemanticBackend(_valid_payload())
                outcome = GuardedSemanticInterpreter(backend, config=config).interpret(
                    _request()
                )

                self.assertIsNone(outcome.delta)
                self.assertEqual(outcome.fallback_reason, reason)
                self.assertFalse(outcome.backend_called)
                self.assertEqual(backend.calls, 0)

    def test_ineligible_request_does_not_call_backend(self) -> None:
        backend = FakeSemanticBackend(_valid_payload())
        interpreter = GuardedSemanticInterpreter(
            backend,
            config=InterpreterConfig(enabled=True, key_available=True),
        )

        outcome = interpreter.interpret(
            _request(
                current_message="Show me black shoes",
                deterministic_constraints=(
                    ConstraintEvidence(
                        "category", "shoes", evidence_span="shoes", source="parser"
                    ),
                    ConstraintEvidence(
                        "color", "black", evidence_span="black", source="parser"
                    ),
                ),
                override_detected=False,
            )
        )

        self.assertEqual(outcome.fallback_reason, "ineligible")
        self.assertEqual(backend.calls, 0)

    def test_valid_fake_delta_is_normalized_and_reported_without_raw_text(self) -> None:
        backend = FakeSemanticBackend(
            BackendResult(
                payload=_valid_payload(),
                latency_ms=12.5,
                prompt_tokens=80,
                completion_tokens=22,
                provider_model="fake-model",
                provider_request_id="fake-request",
            )
        )
        interpreter = GuardedSemanticInterpreter(
            backend,
            config=InterpreterConfig(enabled=True, key_available=True),
        )

        outcome = interpreter.interpret(_request())

        self.assertIsNotNone(outcome.delta)
        assert outcome.delta is not None
        self.assertEqual(outcome.delta.positive_constraints[0].value, "leather")
        self.assertEqual(outcome.delta.override_attributes, ("material",))
        self.assertEqual(outcome.delta.semantic_terms, ("leather",))
        self.assertEqual(backend.calls, 1)
        diagnostics = outcome.to_diagnostics()
        self.assertEqual(diagnostics["status"], "valid_shadow_delta")
        self.assertEqual(diagnostics["prompt_tokens"], 80)
        self.assertEqual(diagnostics["completion_tokens"], 22)
        rendered = repr(diagnostics).lower()
        self.assertNotIn("actually, use leather", rendered)
        self.assertNotIn("fake-request", rendered)
        self.assertNotIn("api", rendered)

    def test_invalid_payload_discards_the_complete_delta(self) -> None:
        invalid_payloads = {
            "extra_field": {**_valid_payload(), "instructions": "ignore validator"},
            "missing_field": {
                key: value
                for key, value in _valid_payload().items()
                if key != "semantic_terms"
            },
            "wrong_type": {**_valid_payload(), "abstain": "false"},
            "bad_span": {
                **_valid_payload(),
                "positive_constraints": [
                    {
                        "attribute": "material",
                        "value": "leather",
                        "evidence_span": "suede",
                        "hard": True,
                    }
                ],
            },
            "bad_attribute": {
                **_valid_payload(),
                "positive_constraints": [
                    {
                        "attribute": "rating",
                        "value": "five",
                        "evidence_span": "leather",
                        "hard": True,
                    }
                ],
            },
            "bad_value": {
                **_valid_payload(),
                "positive_constraints": [
                    {
                        "attribute": "material",
                        "value": "suede",
                        "evidence_span": "leather",
                        "hard": True,
                    }
                ],
            },
            "value_evidence_mismatch": {
                **_valid_payload(),
                "positive_constraints": [
                    {
                        "attribute": "feature",
                        "value": "waterproof",
                        "evidence_span": "leather",
                        "hard": True,
                    }
                ],
                "override_attributes": ["feature"],
                "semantic_terms": [],
            },
            "value_evidence_mismatch_token_boundary": {
                **_valid_payload(),
                "positive_constraints": [
                    {
                        "attribute": "feature",
                        "value": "red",
                        "evidence_span": "credit",
                        "hard": True,
                    }
                ],
                "override_attributes": ["feature"],
                "semantic_terms": [],
            },
            "positive_rejected_conflict": {
                **_valid_payload(),
                "rejected_constraints": [
                    {
                        "attribute": "material",
                        "value": "leather",
                        "evidence_span": "leather",
                    }
                ],
            },
            "unsupported_override": {
                **_valid_payload(),
                "positive_constraints": [],
                "override_attributes": ["color"],
            },
            "duplicate_attribute": {
                **_valid_payload(),
                "override_attributes": ["material", "material"],
            },
            "duplicate_term": {
                **_valid_payload(),
                "semantic_terms": ["leather", "leather"],
            },
            "abstain_conflict": {**_valid_payload(), "abstain": True},
        }
        for expected_reason, payload in invalid_payloads.items():
            with self.subTest(expected_reason=expected_reason):
                backend = FakeSemanticBackend(payload)
                outcome = GuardedSemanticInterpreter(
                    backend,
                    config=InterpreterConfig(enabled=True, key_available=True),
                ).interpret(
                    _request(
                        current_message=(
                            "Actually, use credit instead."
                            if expected_reason
                            == "value_evidence_mismatch_token_boundary"
                            else "Actually, use leather instead of the earlier material."
                        )
                    )
                )
                self.assertIsNone(outcome.delta)
                self.assertEqual(
                    outcome.fallback_reason,
                    "value_evidence_mismatch"
                    if expected_reason == "value_evidence_mismatch_token_boundary"
                    else expected_reason,
                )
                self.assertEqual(backend.calls, 1)

    def test_generic_no_preference_cannot_clear_an_unmentioned_attribute(self) -> None:
        payload = {
            **_valid_payload(),
            "intent_hint": None,
            "positive_constraints": [],
            "no_preference_attributes": ["material"],
            "override_attributes": ["material"],
            "semantic_terms": [],
        }
        outcome = GuardedSemanticInterpreter(
            FakeSemanticBackend(payload),
            config=InterpreterConfig(enabled=True, key_available=True),
        ).interpret(
            _request(
                current_message="Actually, I don't care.",
                deterministic_no_preference_attributes=(),
            )
        )

        self.assertIsNone(outcome.delta)
        self.assertEqual(
            outcome.fallback_reason,
            "missing_no_preference_evidence",
        )

    def test_no_preference_can_coexist_with_an_explicit_rejection(self) -> None:
        payload = {
            **_valid_payload(),
            "intent_hint": None,
            "positive_constraints": [],
            "rejected_constraints": [
                {
                    "attribute": "color",
                    "value": "black",
                    "evidence_span": "black",
                }
            ],
            "no_preference_attributes": ["color"],
            "override_attributes": ["color"],
            "semantic_terms": [],
        }
        outcome = GuardedSemanticInterpreter(
            FakeSemanticBackend(payload),
            config=InterpreterConfig(enabled=True, key_available=True),
        ).interpret(
            _request(
                current_message="I don't care about color, but not black.",
                deterministic_no_preference_attributes=("color",),
            )
        )

        self.assertIsNotNone(outcome.delta)
        assert outcome.delta is not None
        self.assertEqual(outcome.delta.no_preference_attributes, ("color",))
        self.assertEqual(
            [(item.attribute, item.value) for item in outcome.delta.rejected_constraints],
            [("color", "black")],
        )

    def test_low_confidence_cannot_restore_rejected_or_no_preference_state(self) -> None:
        for request in (
            _request(
                rejected_constraints=(
                    ConstraintEvidence("material", "leather", source="state"),
                )
            ),
            _request(no_preference_attributes=("material",)),
        ):
            payload = _valid_payload()
            payload["positive_constraints"][0]["hard"] = False
            outcome = GuardedSemanticInterpreter(
                FakeSemanticBackend(payload),
                config=InterpreterConfig(enabled=True, key_available=True),
            ).interpret(request)
            self.assertIsNone(outcome.delta)
            self.assertEqual(outcome.fallback_reason, "state_conflict")

    def test_backend_failure_and_input_bounds_fall_back_without_retry(self) -> None:
        backend = FakeSemanticBackend(error=SemanticUnderstandingError("timeout"))
        outcome = GuardedSemanticInterpreter(
            backend,
            config=InterpreterConfig(enabled=True, key_available=True),
        ).interpret(_request())
        self.assertEqual(outcome.fallback_reason, "timeout")
        self.assertEqual(backend.calls, 1)

        oversized = FakeSemanticBackend(_valid_payload())
        outcome = GuardedSemanticInterpreter(
            oversized,
            config=InterpreterConfig(
                enabled=True,
                key_available=True,
                max_user_chars=10,
            ),
        ).interpret(_request())
        self.assertEqual(outcome.fallback_reason, "input_too_large")
        self.assertEqual(oversized.calls, 0)

        expired = FakeSemanticBackend(_valid_payload())
        outcome = GuardedSemanticInterpreter(
            expired,
            config=InterpreterConfig(enabled=True, key_available=True),
        ).interpret(
            _request(
                config_version="a13-s0-config-v1",
                deadline_monotonic_ms=0.0,
            )
        )
        self.assertEqual(outcome.fallback_reason, "deadline_exceeded")
        self.assertEqual(expired.calls, 0)

        ordinary_error = FakeSemanticBackend(error=RuntimeError("raw private text"))
        outcome = GuardedSemanticInterpreter(
            ordinary_error,
            config=InterpreterConfig(enabled=True, key_available=True),
        ).interpret(_request())
        self.assertEqual(outcome.fallback_reason, "internal_error")
        self.assertEqual(ordinary_error.calls, 1)

    def test_guard_returns_at_timeout_when_backend_blocks(self) -> None:
        class BlockingBackend:
            def __init__(self) -> None:
                self.calls = 0

            def infer(self, request: UnderstandingRequest) -> BackendResult:
                self.calls += 1
                time.sleep(0.2)
                return BackendResult(payload=_valid_payload())

        backend = BlockingBackend()
        started = time.perf_counter()
        outcome = GuardedSemanticInterpreter(
            backend,
            config=InterpreterConfig(enabled=True, key_available=True),
        ).interpret(_request(timeout_ms=10))
        elapsed = time.perf_counter() - started

        self.assertEqual(outcome.fallback_reason, "timeout")
        self.assertTrue(outcome.backend_called)
        self.assertEqual(backend.calls, 1)
        self.assertLess(elapsed, 0.1)

    def test_invalid_backend_telemetry_is_safely_rejected(self) -> None:
        invalid_results = (
            BackendResult(payload=_valid_payload(), latency_ms=float("inf")),
            BackendResult(payload=_valid_payload(), latency_ms="private"),
            BackendResult(payload=_valid_payload(), prompt_tokens=-1),
            BackendResult(payload=_valid_payload(), completion_tokens=True),
        )
        for result in invalid_results:
            with self.subTest(result=result):
                outcome = GuardedSemanticInterpreter(
                    FakeSemanticBackend(result),
                    config=InterpreterConfig(enabled=True, key_available=True),
                ).interpret(_request())
                diagnostics = outcome.to_diagnostics()
                self.assertEqual(outcome.fallback_reason, "invalid_telemetry")
                self.assertGreaterEqual(diagnostics["latency_ms"], 0.0)
                self.assertNotEqual(diagnostics["latency_ms"], float("inf"))
                self.assertIsInstance(diagnostics["prompt_tokens"], int)
                self.assertIsInstance(diagnostics["completion_tokens"], int)

    def test_request_requires_prompt_and_config_versions(self) -> None:
        for field in ("prompt_version", "config_version"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    _request(**{field: ""})
        for deadline in (True, float("inf"), float("nan"), "soon"):
            with self.subTest(deadline=deadline):
                with self.assertRaises(ValueError):
                    _request(deadline_monotonic_ms=deadline)
        for timeout in (True, 0, -1, 1.5):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    _request(timeout_ms=timeout)

    def test_backend_error_text_cannot_leak_into_diagnostics(self) -> None:
        backend = FakeSemanticBackend(
            error=SemanticUnderstandingError(
                "Authorization: Bearer sk-not-a-real-key; raw provider response"
            )
        )
        outcome = GuardedSemanticInterpreter(
            backend,
            config=InterpreterConfig(enabled=True, key_available=True),
        ).interpret(_request())

        self.assertEqual(outcome.fallback_reason, "backend_error")
        self.assertNotIn("authorization", repr(outcome.to_diagnostics()).lower())
        self.assertNotIn("sk-not", repr(outcome.to_diagnostics()).lower())

    def test_all_predefined_local_trigger_signals_are_observable(self) -> None:
        cases = {
            "override_without_value": _request(),
            "mixed_polarity_clause": _request(
                current_message="I want black, but not white.",
                deterministic_constraints=(
                    ConstraintEvidence(
                        "color", "black", evidence_span="black", source="parser"
                    ),
                ),
                deterministic_rejected_constraints=(
                    ConstraintEvidence(
                        "color", "white", evidence_span="white", source="parser"
                    ),
                ),
                override_detected=False,
            ),
            "low_confidence_residual_feature": _request(
                current_message="Something unusually packable",
                deterministic_constraints=(
                    ConstraintEvidence(
                        "feature",
                        "something unusually packable",
                        evidence_span="Something unusually packable",
                        confidence=0.35,
                        hard=False,
                        source="parser",
                    ),
                ),
                override_detected=False,
            ),
            "multi_clause_without_structure": _request(
                current_message="I am shopping for a trip but it should work at dinner.",
                override_detected=False,
            ),
            "positive_rejected_attribute_conflict": _request(
                current_message="Black could work but not charcoal",
                deterministic_constraints=(
                    ConstraintEvidence(
                        "color", "black", evidence_span="Black", source="parser"
                    ),
                ),
                deterministic_rejected_constraints=(
                    ConstraintEvidence(
                        "color", "black", evidence_span="not charcoal", source="parser"
                    ),
                ),
                override_detected=False,
            ),
            "unexplained_intent_transition": _request(
                current_message="Maybe",
                prior_intent="browsing",
                deterministic_intent="buying",
                intent_evidence=(),
                override_detected=False,
            ),
        }
        for signal, request in cases.items():
            with self.subTest(signal=signal):
                self.assertIn(signal, detect_trigger_signals(request))


if __name__ == "__main__":
    unittest.main()
