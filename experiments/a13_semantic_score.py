"""Deadline semantic experiment; production Agent and evaluator remain unchanged."""
from dataclasses import replace
import copy
import hashlib
import json
import multiprocessing
from pathlib import Path
import time
import urllib.error
import urllib.request

from starter.agent import Agent
from starter.core.semantic_understanding import (
    BackendResult, UnderstandingOutcome, SemanticUnderstandingError, SAFE_FALLBACK_REASONS, detect_trigger_signals,
    validate_understanding_delta,
)
from experiments.a13_light_review import PROMPT, NoRedirect


def provider_input(request):
    def rows(items):
        return [{"attribute": c.attribute, "value": c.value, "hard": c.hard} for c in items]
    prior = {"active_constraints": rows(request.active_constraints),
             "rejected_constraints": rows(request.rejected_constraints),
             "no_preference_attributes": list(request.no_preference_attributes)}
    if (len(request.current_message) > 2000 or len(json.dumps(prior)) > 2000
        or sum(map(len, request.allowed_values.values())) > 200):
        raise SemanticUnderstandingError("input_too_large")
    return {"current_message": request.current_message, "prior_state": prior,
            "allowed_values": dict(request.allowed_values), "override_detected": request.override_detected}


def _provider_worker(connection, key, request):
    try:
        encoded = encoded_request(request)
        http = urllib.request.Request("https://api.deepseek.com/chat/completions", data=encoded,
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        with urllib.request.build_opener(NoRedirect()).open(http, timeout=2) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise SemanticUnderstandingError("invalid_provider_json")
        body = json.loads(raw)
        connection.send({"body": body, "request_sha256": hashlib.sha256(encoded).hexdigest(),
                         "response_sha256": hashlib.sha256(raw).hexdigest()})
    except urllib.error.HTTPError as error:
        connection.send({"error": f"http_{error.code}"})
    except Exception:
        connection.send({"error": "provider_error"})
    finally:
        connection.close()


def encoded_request(request):
    payload = {"model": "deepseek-v4-flash", "temperature": 0,
        "thinking": {"type": "disabled"}, "response_format": {"type": "json_object"}, "max_tokens": 512,
        "messages": [{"role": "system", "content": PROMPT},
                     {"role": "user", "content": json.dumps(provider_input(request), ensure_ascii=False)}]}
    encoded = json.dumps(payload, ensure_ascii=False).encode()
    if len(encoded) > 16000:
        raise SemanticUnderstandingError("input_too_large")
    return encoded


class ProcessBackend:
    """Killable transport: no late result survives a caller timeout."""

    def __init__(self, key, *, worker=_provider_worker, timeout_seconds=2.4):
        self.key, self.worker, self.timeout_seconds = key, worker, timeout_seconds
        self.metadata = {}

    def infer(self, request):
        self.metadata = {}
        context = multiprocessing.get_context("spawn")
        reader, writer = context.Pipe(duplex=False)
        process = context.Process(target=self.worker, args=(writer, self.key, request))
        started = time.monotonic()
        remaining = self.timeout_seconds
        if request.deadline_monotonic_ms is not None:
            remaining = min(remaining, request.deadline_monotonic_ms / 1000 - started)
        if remaining <= 0:
            reader.close()
            writer.close()
            raise SemanticUnderstandingError("deadline_exceeded")
        process.start()
        writer.close()
        try:
            if not reader.poll(max(0, remaining - (time.monotonic() - started))):
                raise SemanticUnderstandingError("timeout")
            reply = reader.recv()
        finally:
            reader.close()
            if process.is_alive():
                process.terminate()
            process.join(timeout=.2)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()
        if "error" in reply:
            raise SemanticUnderstandingError(reply["error"])
        self.metadata = {k: reply[k] for k in ("request_sha256", "response_sha256")}
        body = reply["body"]
        usage = body.get("usage", {})
        self.metadata["finish_reason"] = body["choices"][0].get("finish_reason")
        try:
            payload = json.loads(body["choices"][0]["message"]["content"])
        except (ValueError, TypeError):
            payload = None
        if self.metadata["finish_reason"] != "stop":
            payload = None
        return BackendResult(payload, (time.monotonic() - started) * 1000,
            usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
            body.get("model"), body.get("id"))


class TrialInterpreter:
    def __init__(self, backend, *, enabled=True, key_available=True, max_calls=300, max_usd=1.0, journal=None):
        self.backend = backend
        self.records = []
        self.last = None
        self.enabled, self.key_available = enabled, key_available
        self.max_calls, self.max_usd, self.journal = max_calls, max_usd, journal
        self.total_cost = 0.0
        self.attempts = 0
        self.consecutive_errors = 0
        self.started = None
        self.stop_reason = None

    def interpret(self, request):
        signals = detect_trigger_signals(request)
        self.last = None
        if "low_confidence_residual_feature" not in signals:
            return UnderstandingOutcome(None, signals, "ineligible", False)
        started = time.monotonic()
        if self.started is None:
            self.started = started
        called, known, cost = False, False, 0.0
        result, delta, reason, request_hash = None, None, None, None
        try:
            if not self.enabled:
                raise SemanticUnderstandingError("disabled")
            if not self.key_available:
                raise SemanticUnderstandingError("no_key")
            encoded = encoded_request(request)
            request_hash = hashlib.sha256(encoded).hexdigest()
            cost = ((len(encoded) * 2 + 4096) * .44 + 512 * 1.32) / 1e6
            if self.attempts >= self.max_calls:
                self.stop_reason = "call_budget"
            elif self.total_cost + cost > self.max_usd:
                self.stop_reason = "cost_budget"
            elif started - self.started >= 1200:
                self.stop_reason = "time_budget"
            if self.stop_reason:
                raise SemanticUnderstandingError(self.stop_reason)
            called = True
            self.attempts += 1
            result = self.backend.infer(request)
            counts = (result.prompt_tokens, result.completion_tokens)
            if any(type(n) is not int or n < 0 for n in counts) or counts[0] == 0:
                raise SemanticUnderstandingError("invalid_telemetry")
            known = True
            cost = (counts[0] * .44 + counts[1] * 1.32) / 1e6
            self.consecutive_errors = 0
            delta = validate_understanding_delta(result.payload, request)
            if delta.intent_hint is not None or delta.semantic_terms:
                raise SemanticUnderstandingError("unsupported_scope")
            forbidden = {(c.attribute, c.value) for c in
                         (*request.rejected_constraints, *request.deterministic_rejected_constraints)}
            indifferent = set(request.no_preference_attributes) | set(request.deterministic_no_preference_attributes)
            if any(c.attribute in indifferent or (c.attribute, c.value) in forbidden for c in delta.positive_constraints):
                raise SemanticUnderstandingError("state_conflict")
        except Exception as error:
            allowed = SAFE_FALLBACK_REASONS | {"disabled", "no_key", "input_too_large", "call_budget",
                "cost_budget", "time_budget", "consecutive_errors", "authorization_failure", "unsupported_scope"}
            value = str(error)
            reason = value if value in allowed or (value.startswith("http_") and value[5:].isdigit()) else "backend_error"
            delta = None
            if called and not known:
                self.consecutive_errors += 1
                if reason in {"http_401", "http_403"}:
                    self.stop_reason = "authorization_failure"
                elif self.consecutive_errors >= 3:
                    self.stop_reason = "consecutive_errors"
        elapsed = (time.monotonic() - started) * 1000
        if not called:
            cost = 0
        self.total_cost += cost
        outcome = UnderstandingOutcome(delta, signals, reason, called, elapsed,
            result.prompt_tokens if known else 0, result.completion_tokens if known else 0,
            result.provider_model if known else None)
        self.last = (request, outcome)
        record = {**outcome.to_diagnostics(), "usage_known": known,
                  "cost_allowance_usd": cost, "request_sha256": request_hash}
        if known:
            record.update(getattr(self.backend, "metadata", {}))
            record["provider_request_id"] = str(result.provider_request_id or "")[:160]
        self.records.append(record)
        if self.journal:
            self.journal.write(json.dumps(record) + "\n")
            self.journal.flush()
            if self.attempts and self.attempts % 10 == 0:
                print(json.dumps({"semantic_attempts": self.attempts, "cost_usd": round(self.total_cost, 6)}), flush=True)
        return outcome


def _merged_inputs(request, delta, constraints, rejected, no_preference, turn):
    if delta.abstain:
        return None
    if delta.intent_hint is not None or delta.semantic_terms:
        raise SemanticUnderstandingError("unsupported_scope")
    preserved = [dict(c) for c in constraints if not
                 (c.get("attribute") == "feature" and c.get("confidence", 1) <= .35)]
    positives = {(c["attribute"], c["normalized_value"]) for c in preserved}
    for item in delta.positive_constraints:
        if any(a == item.attribute and v != item.value for a, v in positives):
            raise SemanticUnderstandingError("deterministic_conflict")
        if item.attribute in request.no_preference_attributes or any(
            c.attribute == item.attribute and c.value == item.value for c in request.rejected_constraints):
            raise SemanticUnderstandingError("state_conflict")
    if any((c.attribute, c.value) in positives for c in delta.rejected_constraints) or any(
        a in delta.no_preference_attributes for a, _ in positives):
        raise SemanticUnderstandingError("deterministic_conflict")
    if not (delta.positive_constraints or delta.rejected_constraints or delta.no_preference_attributes):
        return None
    def row(item, active):
        return {"attribute": item.attribute, "raw_value": item.value, "normalized_value": item.value,
                "source_text": item.evidence_span, "source_turn": turn, "confidence": .85,
                "hard": item.hard if active else False, "active": active}
    preserved.extend(row(item, True) for item in delta.positive_constraints
                     if (item.attribute, item.value) not in positives)
    negatives = [dict(c) for c in rejected] + [row(c, False) for c in delta.rejected_constraints]
    indifferent = sorted(set(no_preference) | set(delta.no_preference_attributes))
    return preserved, negatives, indifferent


class TrialAgent(Agent):
    def __init__(self, *args, candidate=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidate = candidate
        self.records = []
        self.trace = []
        self.session_order = []
        self.asked = {}

    def reset(self, session_id, user_profile):
        self.session_order.append(session_id)
        self.asked[session_id] = set()
        super().reset(session_id, user_profile)

    def _run_semantic_shadow(self, **kwargs):
        if self.semantic_interpreter is None:
            return
        self.semantic_interpreter.last = None
        super()._run_semantic_shadow(**kwargs)
        proposal = self.semantic_interpreter.last
        applied, compatible, state_effect, reason = False, False, False, None
        if proposal and proposal[1].delta is not None:
            request, outcome = proposal
            try:
                merged = _merged_inputs(request, outcome.delta, kwargs["constraints"],
                    kwargs["rejected_constraints"], kwargs["no_preference_attributes"], kwargs["turn"])
                compatible = merged is not None
                if compatible:
                    baseline_state = copy.deepcopy(kwargs["state"])
                    candidate_state = copy.deepcopy(kwargs["state"])
                    baseline_state.apply_user_context(constraints=kwargs["constraints"], override=kwargs["override"],
                        rejected_constraints=kwargs["rejected_constraints"], no_preference_attributes=kwargs["no_preference_attributes"])
                    candidate_state.apply_user_context(constraints=merged[0], override=kwargs["override"],
                        rejected_constraints=merged[1], no_preference_attributes=merged[2])
                    state_effect = baseline_state != candidate_state
                if self.candidate and compatible:
                    positive, negative, indifferent = merged
                    applied = (positive, negative, indifferent) != (kwargs["constraints"], kwargs["rejected_constraints"], kwargs["no_preference_attributes"])
                    kwargs["constraints"][:] = positive
                    kwargs["rejected_constraints"][:] = negative
                    kwargs["no_preference_attributes"][:] = indifferent
            except SemanticUnderstandingError as error:
                reason = str(error)
        self.records.append({"session_id": kwargs["state"].session_id, "turn": kwargs["turn"],
                             "compatible": compatible, "state_effect_changed": state_effect,
                             "applied": applied, "merge_failure": reason})

    def respond(self, session_id, user_message, turn, top_k):
        start = len(self.semantic_interpreter.records) if self.semantic_interpreter else 0
        response = super().respond(session_id, user_message, turn, top_k)
        if self.semantic_interpreter:
            for key in ("prompt_tokens", "completion_tokens"):
                response["usage"][key] += sum(r[key] for r in self.semantic_interpreter.records[start:])
        from experiments.a13_shadow import response_behavior_projection
        projection = response_behavior_projection({k: v for k, v in response.items() if k != "usage"})
        diagnostics = response.get("diagnostics", {})
        ask = response.get("ask_attribute")
        active = {(r["attribute"], r["value"]) for r in diagnostics.get("active_constraints", [])}
        rejected = {(r["attribute"], r["value"]) for r in diagnostics.get("rejected_constraints", [])}
        indifferent = set(diagnostics.get("no_preference_attributes", []))
        self.trace.append({"session_index": len(self.session_order) - 1, "turn": turn,
            "behavior_sha256": hashlib.sha256(json.dumps(projection, sort_keys=True).encode()).hexdigest(),
            "ask_attribute": ask, "recommendations": response["recommendations"],
            "upstream_failures": diagnostics.get("retrieval", {}).get("route_failures", {}),
            "fallback_used": diagnostics.get("fallback_used", False),
            "state_invariant_violation": bool(active & rejected) or any(a in indifferent for a, _ in active),
            "question_violation": bool(ask and (ask in indifferent or ask in self.asked[session_id] or turn >= 10))})
        if ask:
            self.asked[session_id].add(ask)
        return response


def _summary(report):
    from experiments.evaluation_reporting import AgentObserver
    rows = report["semantic_records"]
    attempts = [r for r in rows if r["backend_called"]]
    provider_errors = sum(not r["usage_known"] for r in attempts)
    schema_valid = sum(r["status"] == "valid_shadow_delta" for r in rows)
    merge_errors = sum(bool(r["merge_failure"]) for r in report["application_records"])
    trace = report["trace"]
    return {"eligible_turns": len(rows), "attempted_calls": len(attempts), "provider_errors": provider_errors,
        "schema_valid": schema_valid, "merge_rejections": merge_errors,
        "valid_rate": (schema_valid - merge_errors) / len(rows) if rows else 0,
        "compatible_proposals": sum(r["compatible"] for r in report["application_records"]),
        "counterfactual_state_changes": sum(r["state_effect_changed"] for r in report["application_records"]),
        "applied_turns": sum(r["applied"] for r in report["application_records"]),
        "upstream_failure_turns": sum(bool(r["upstream_failures"]) or r["fallback_used"] for r in trace),
        "invariant_violations": sum(r["state_invariant_violation"] or r["question_violation"] for r in trace),
        "latency": AgentObserver._timing_summary([r["latency_ms"] for r in attempts])}


def _candidate_gate(baseline, report):
    key = "recommended_technical_score"
    stats = report["semantic_summary"]
    folds = {f: round(report["fixed_folds"][f][key] - baseline["fixed_folds"][f][key], 6)
             for f in baseline["fixed_folds"]}
    scenarios = {s: round(report["scenario_metrics"][s][key] - baseline["scenario_metrics"][s][key], 6)
                 for s in baseline["scenario_metrics"]}
    gates = {"score": report[key] > baseline[key], "hit_rate": report["hit_rate_at_10"] >= baseline["hit_rate_at_10"],
        "mrr": report["mrr"] >= baseline["mrr"], "folds": sum(v >= 0 for v in folds.values()) >= 3,
        "scenarios": min(scenarios.values()) >= -.01, "valid_rate": stats["valid_rate"] >= .95,
        "provider_errors": stats["attempted_calls"] > 0 and stats["provider_errors"] / stats["attempted_calls"] <= .02,
        "latency": stats["latency"]["p95_ms"] <= 2000, "upstream": stats["upstream_failure_turns"] == 0,
        "invariants": stats["invariant_violations"] == 0, "budget": not report["stop_reason"],
        "schema": report["observed_run_counts"]["respond_exceptions"] == report["observed_run_counts"]["invalid_response_payloads"] == 0}
    return {"score_delta": round(report[key] - baseline[key], 6), "fold_deltas": folds,
            "scenario_deltas": scenarios, "gates": gates, "passes": all(gates.values())}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import argparse
    from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
    from evaluator.splits import filter_samples, load_split_manifest
    from experiments.a14_deadline_selection import score_sessions
    from experiments.development_folds import validate_development_fold_manifest
    from experiments.evaluation_reporting import AgentObserver, code_provenance
    from starter.contracts import RetrievalRequest
    from starter.core.planner import Strategy
    from starter.retrieval import ConditionalDenseRetriever, DenseConfig

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--key-env-file", type=Path, default=Path("../shopping-copilot-chen/.env.local"))
    args = parser.parse_args()
    if not args.execute: parser.error("--execute is required for paid calls")
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()): parser.error("output directory must be empty")
    key = ""
    for line in args.key_env_file.read_text().splitlines():
        name, separator, value = line.strip().removeprefix("export ").partition("=")
        if separator and name.strip() == "DEEPSEEK_API_KEY": key = value.strip().strip("\"").strip("'")
    if not key: parser.error("missing local key; do not paste secrets into chat")
    code = code_provenance()
    if not code["worktree_clean"]: parser.error("freeze a clean source commit before paid execution")
    paths = {"catalog": "data/catalog.jsonl", "dataset": "data/public_set.jsonl",
             "split": "docs/public_split_v1.json", "folds": "docs/development_folds_v1.json"}
    samples = load_jsonl(paths["dataset"])
    split, folds = load_split_manifest(paths["split"]), load_split_manifest(paths["folds"])
    validate_development_fold_manifest(samples, split, folds)
    development = filter_samples(samples, "development", split)
    if len(development) != 160: raise ValueError("fixed Development-160 required")
    source_paths = list(Path("starter").rglob("*.py")) + list(Path("evaluator").rglob("*.py"))
    source_paths += [Path("experiments") / f for f in ("a13_semantic_score.py", "a13_light_review.py",
        "a13_ai_silver.py", "a13_shadow.py", "a14_deadline_selection.py", "evaluation_reporting.py", "development_folds.py")]
    provenance = {"code": code, "scope": "fixed Development-160 only; isolated deadline A13-F1",
        "input_sha256": {name: _sha(path) for name, path in paths.items()},
        "source_sha256": {str(p): _sha(p) for p in source_paths}, "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "requested_model": "deepseek-v4-flash", "runtime_default_changed": False,
        "limits": {"calls": 300, "usd": 1, "seconds": 1200, "max_output_tokens": 512,
                   "process_wait_seconds": 2.4, "thinking": False, "temperature": 0},
        "pricing": {"input_usd_per_m": .44, "output_usd_per_m": 1.32, "basis": "peak cache-miss conservative estimate"}}
    (args.output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    ids, categories, products = catalog_index(paths["catalog"])
    retriever = ConditionalDenseRetriever.from_catalog(paths["catalog"], dense_config=DenseConfig(
        cache_dir=Path("../shopping-copilot/embeddings/minilm-l6-v2-v1"),
        model_cache_dir=Path("../shopping-copilot/models/huggingface/hub")))
    warm = RetrievalRequest("synthetic_warmup", 1, 10, "shoes", "browsing", Strategy(
        "browsing", .6, .2, .2, 120, False, True, "broad_lexical", "synthetic prewarm"))
    retriever.retrieve(warm)
    reports, comparisons = {}, {}
    try:
        with (args.output / "provider_journal.jsonl").open("x") as journal:
            interpreter = TrialInterpreter(ProcessBackend(key), journal=journal)
            for mode in ("baseline", "shadow", "candidate", "repeat"):
                if mode == "candidate" and not comparisons["shadow"]["passes"]: break
                if mode == "repeat" and not comparisons["candidate"]["passes"]: break
                first = len(interpreter.records)
                agent = TrialAgent(paths["catalog"], retriever=retriever,
                    semantic_interpreter=None if mode == "baseline" else interpreter,
                    candidate=mode in {"candidate", "repeat"})
                observer = AgentObserver(agent, catalog_ids=ids)
                print(json.dumps({"starting": mode, "sessions": 160}), flush=True)
                report = evaluate(observer, development, ids, categories, products)
                report.update(score_sessions(report["sessions"]))
                report.update(provenance=provenance, trace=agent.trace, application_records=agent.records,
                    semantic_records=list(interpreter.records[first:]), stop_reason=interpreter.stop_reason,
                    observed_run_counts=observer.counts(), timing=observer.timing(), retrieval_diagnostics=observer.retrieval_diagnostics(),
                    retrieval_configuration=retriever.configuration_snapshot(), dense_configuration=retriever.dense_configuration(),
                    fixed_folds={f: score_sessions([r for r in report["sessions"] if r["sample_id"] in members])
                                 for f, members in folds["folds"].items()})
                if len(report["sessions"]) != 160 or len(agent.session_order) != 160:
                    raise ValueError("incomplete evaluation")
                report["semantic_summary"] = _summary(report)
                reports[mode] = report
                (args.output / (mode + ".json")).write_text(json.dumps(report, indent=2) + "\n")
                print(json.dumps({"finished": mode, **score_sessions(report["sessions"]), "semantic_summary": report["semantic_summary"]}), flush=True)
                if mode == "shadow":
                    baseline = reports["baseline"]
                    parity = [(r["session_index"], r["turn"], r["behavior_sha256"]) for r in baseline["trace"]] == [
                        (r["session_index"], r["turn"], r["behavior_sha256"]) for r in report["trace"]]
                    stats = report["semantic_summary"]
                    gates = {"behavior_parity": parity, "upstream": stats["upstream_failure_turns"] == baseline["semantic_summary"]["upstream_failure_turns"] == 0,
                        "valid_rate": stats["valid_rate"] >= .95, "provider_errors": stats["attempted_calls"] > 0 and stats["provider_errors"] / stats["attempted_calls"] <= .02,
                        "useful_proposal": stats["counterfactual_state_changes"] > 0, "budget": not interpreter.stop_reason,
                        "invariants": stats["invariant_violations"] == 0,
                        "schema": observer.counts()["respond_exceptions"] == observer.counts()["invalid_response_payloads"] == 0}
                    comparisons[mode] = {"gates": gates, "passes": all(gates.values())}
                elif mode != "baseline": comparisons[mode] = _candidate_gate(reports["baseline"], report)
                if mode != "baseline": print(json.dumps({"comparison": mode, **comparisons[mode]}), flush=True)
            unchanged = all(_sha(p) == digest for p, digest in provenance["source_sha256"].items()) and all(
                _sha(paths[name]) == digest for name, digest in provenance["input_sha256"].items())
            summary = {"provenance": provenance, "source_and_inputs_unchanged": unchanged,
                "runtime_default_changed": False, "comparisons": comparisons,
                "decision": "retain_opt_in_experiment" if unchanged and "repeat" in comparisons and all(r["passes"] for r in comparisons.values()) else "do_not_promote",
                "total_attempted_calls": interpreter.attempts, "total_cost_allowance_usd": round(interpreter.total_cost, 8),
                "unknown_usage_calls": sum(r["backend_called"] and not r["usage_known"] for r in interpreter.records),
                "stop_reason": interpreter.stop_reason,
                "arms": {m: {k: v for k, v in r.items() if k not in {"provenance", "trace", "application_records", "semantic_records", "sessions"}}
                         for m, r in reports.items()}, "session_outcomes": {m: r["sessions"] for m, r in reports.items()},
                "raw_sha256": {p.name: _sha(p) for p in args.output.iterdir() if p.is_file()}}
            (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            print(json.dumps({k: summary[k] for k in ("decision", "total_attempted_calls", "total_cost_allowance_usd", "stop_reason")}), flush=True)
    finally:
        retriever.close()


if __name__ == "__main__":
    main()
