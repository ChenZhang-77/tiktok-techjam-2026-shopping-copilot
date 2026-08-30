"""Isolated fixed-Development reranking trial; never changes runtime defaults."""
from dataclasses import replace
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request

from starter.agent import Agent
from starter.retrieval.semantic_ranker import (
    DeepSeekSemanticRanker, SemanticRankError, SemanticRankItem, SemanticRankRequest, validate_permutation,
)


def _key(row):
    return (str(row.get("attribute") or "").strip().lower(),
            str(row.get("normalized_value") or row.get("value") or row.get("raw_value") or "").strip().lower())


def _profiles(prefix, request):
    positive = {_key(c) for c in request.active_constraints if c.get("active", True)}
    hard = {_key(c) for c in request.active_constraints if c.get("active", True)
            and c.get("hard") and float(c.get("confidence") or 0) >= .75}
    rejected = {_key(c) for c in request.rejected_constraints
                if float(c.get("confidence") or 0) >= .75
                and _key(c)[0] not in request.no_preference_attributes} - positive
    return [(frozenset(hard & {_key(c) for c in item.diagnostics.get("structured_matches", [])}),
             frozenset(rejected & {_key(c) for c in item.diagnostics.get("rejected_constraint_matches", [])}))
            for item in prefix]


class BudgetedRanker:
    """One shared experiment budget; failed usage is unknown, never free."""

    def __init__(self, backend, *, max_calls=1400, max_usd=3.0, max_seconds=1800, journal=None):
        self.backend = backend
        self.max_calls = max_calls
        self.max_usd = max_usd
        self.max_seconds = max_seconds
        self.journal = journal
        self.records = []
        self.total_cost = 0.0
        self.consecutive_errors = 0
        self.stop_reason = None
        self.started = None

    def rank(self, request):
        now = time.monotonic()
        if self.started is None:
            self.started = now
        prompt = DeepSeekSemanticRanker._prompt(request)
        unknown_allowance = ((len(prompt.encode("utf-8")) * 2 + 4096) * .44 + 256 * 1.32) / 1e6
        if len(self.records) >= self.max_calls:
            self.stop_reason = "call_budget"
        elif self.total_cost + unknown_allowance > self.max_usd:
            self.stop_reason = "cost_budget"
        elif now - self.started >= self.max_seconds:
            self.stop_reason = "time_budget"
        if self.stop_reason:
            raise SemanticRankError(self.stop_reason)
        record = {"attempt": len(self.records) + 1,
            "request_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "prompt_tokens": 0, "completion_tokens": 0, "usage_known": False,
            "cost_allowance_usd": unknown_allowance, "failure": None}
        outcome = None
        try:
            outcome = self.backend.rank(request)
            if outcome.fallback_reason:
                raise SemanticRankError(outcome.fallback_reason)
            counts = (outcome.usage.prompt_tokens, outcome.usage.completion_tokens)
            if any(type(n) is not int or n < 0 for n in counts) or counts[0] == 0:
                raise SemanticRankError("invalid_usage")
            record.update(prompt_tokens=counts[0], completion_tokens=counts[1], usage_known=True,
                cost_allowance_usd=(counts[0] * .44 + counts[1] * 1.32) / 1e6,
                provider_model=outcome.provider_model, finish_reason=outcome.finish_reason,
                prompt_cache_hit_tokens=outcome.usage.prompt_cache_hit_tokens,
                prompt_cache_miss_tokens=outcome.usage.prompt_cache_miss_tokens)
            if outcome.finish_reason != "stop":
                raise SemanticRankError("incomplete_response")
            validate_permutation(outcome.ordered_ids, tuple(i.opaque_id for i in request.items))
            self.consecutive_errors = 0
        except (SemanticRankError, ValueError, TypeError, AttributeError) as error:
            safe = {"no_key", "provider_error", "invalid_provider_json", "invalid_json_or_permutation",
                    "invalid_usage", "incomplete_response", "invalid_permutation"}
            reason = str(error)
            record["failure"] = reason if reason in safe or (reason.startswith("http_") and reason[5:].isdigit()) else "invalid_outcome"
            self.consecutive_errors += 1
            if record["failure"] in {"http_401", "http_403", "no_key"}:
                self.stop_reason = "authorization_failure"
            elif self.consecutive_errors >= 3:
                self.stop_reason = "consecutive_errors"
        finally:
            record["latency_ms"] = (time.monotonic() - now) * 1000
            self.total_cost += record["cost_allowance_usd"]
            self.records.append(record)
            if self.journal:
                self.journal.write(json.dumps(record) + "\n")
                self.journal.flush()
            if self.journal and len(self.records) % 25 == 0:
                print(json.dumps({"attempts": len(self.records), "cost_allowance_usd": round(self.total_cost, 6),
                                  "failures": sum(bool(r["failure"]) for r in self.records)}), flush=True)
        if record["failure"]:
            raise SemanticRankError(record["failure"])
        return outcome


class ProductReranker:
    def __init__(self, base, ranker):
        self.base = base
        self.ranker = ranker
        self.records = []
        self.catalog_ids = base.catalog_ids
        self.fallback_ids = base.fallback_ids
        if hasattr(base, "catalog_path"):
            self.catalog_path = base.catalog_path

    def retrieve(self, request):
        result = self.base.retrieve(request)
        prefix = result.candidates[:min(10, request.top_k)]
        if request.intent != "browsing" or len(prefix) < 2 or result.diagnostics.fallback_used:
            return result
        aliases = [f"c{i}" for i in range(len(prefix))]
        started = time.perf_counter()
        reason = None
        ranked = prefix
        try:
            outcome = self.ranker.rank(SemanticRankRequest(query=request.query,
                active_constraints=tuple(f"{_key(c)[0]}={_key(c)[1]}"[:160]
                    for c in request.active_constraints if c.get("active", True))[:12],
                timeout_ms=8000, prompt_version="b10b-f1",
                items=tuple(SemanticRankItem(alias, candidate.evidence_text or "")
                            for alias, candidate in zip(aliases, prefix))))
            if outcome.fallback_reason:
                raise SemanticRankError(outcome.fallback_reason)
            validate_permutation(outcome.ordered_ids, aliases)
            profiles = _profiles(prefix, request)
            position = {a: i for i, a in enumerate(outcome.ordered_ids)}
            ranked = list(prefix)
            for profile in set(profiles):
                slots = [i for i, p in enumerate(profiles) if p == profile]
                preferred = sorted(slots, key=lambda i: position[aliases[i]])
                for slot, index in zip(slots, preferred):
                    ranked[slot] = prefix[index]
        except (SemanticRankError, ValueError) as error:
            reason = str(error) if isinstance(error, SemanticRankError) else "invalid_request"
        elapsed = (time.perf_counter() - started) * 1000
        self.records.append({"session_id": request.session_id, "turn": request.turn,
            "failure": reason, "changed": ranked != prefix,
            "membership_preserved": {c.parent_asin for c in ranked} == {c.parent_asin for c in prefix},
            "latency_ms": elapsed})
        diagnostics = result.diagnostics
        routes = list(diagnostics.executed_routes)
        fallback_route = diagnostics.fallback_route
        if reason and routes and not fallback_route:
            fallback_route = routes[0]
        if not reason and routes and "semantic_rerank" not in routes:
            routes.append("semantic_rerank")
        failures = dict(diagnostics.route_failures)
        if reason:
            failures["semantic_rerank"] = reason
        diagnostics = replace(diagnostics, fallback_used=bool(reason), fallback_route=fallback_route,
            executed_routes=routes, route_failures=failures, rerank_pool_size=len(prefix),
            latency_ms=(diagnostics.latency_ms or 0) + elapsed,
            stage_latencies_ms={**diagnostics.stage_latencies_ms, "semantic_rerank": elapsed})
        return replace(result, candidates=ranked + result.candidates[len(prefix):], diagnostics=diagnostics)


class TracedAgent(Agent):
    """Attach paid-call usage and observable traces at the public response seam."""

    def __init__(self, *args, ledger=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ledger = ledger
        self.trace = []
        self.session_order = []

    def reset(self, session_id, user_profile):
        self.session_order.append(session_id)
        super().reset(session_id, user_profile)

    def respond(self, session_id, user_message, turn, top_k):
        start = len(self.ledger.records) if self.ledger else 0
        response = super().respond(session_id, user_message, turn, top_k)
        if self.ledger:
            for key in ("prompt_tokens", "completion_tokens"):
                response["usage"][key] += sum(r[key] for r in self.ledger.records[start:])
        self.trace.append({"session_index": len(self.session_order) - 1, "turn": turn,
            "ask_attribute": response.get("ask_attribute"), "message": response.get("message"),
            "ids": [r["parent_asin"] for r in response["recommendations"]]})
        return response


def compare(baseline, candidate):
    score_key = "recommended_technical_score"
    before = {(r["session_index"], r["turn"]): r for r in baseline["trace"]}
    after = {(r["session_index"], r["turn"]): r for r in candidate["trace"]}
    same_turns = before.keys() == after.keys()
    same_members = same_turns and all(set(before[k]["ids"]) == set(after[k]["ids"]) for k in before)
    same_questions = same_turns and all((before[k]["ask_attribute"], before[k]["message"])
        == (after[k]["ask_attribute"], after[k]["message"]) for k in before)
    folds = {f: round(candidate["fixed_folds"][f][score_key] - baseline["fixed_folds"][f][score_key], 6)
             for f in baseline["fixed_folds"]}
    scenarios = {s: round(candidate["scenario_metrics"][s][score_key] - baseline["scenario_metrics"][s][score_key], 6)
                 for s in baseline["scenario_metrics"]}
    records = candidate["provider_records"]
    failures = sum(bool(r["failure"]) for r in records)
    from experiments.evaluation_reporting import AgentObserver
    latency = AgentObserver._timing_summary([r["latency_ms"] for r in records])
    eligibility_complete = len(records) == len(candidate["rerank_records"]) and bool(records)
    gates = {
        "positive_score": candidate[score_key] > baseline[score_key],
        "nondeclining_mrr": candidate["mrr"] >= baseline["mrr"],
        "unchanged_hr_mttc": all(candidate[k] == baseline[k] for k in ("hit_rate_at_10", "mttc")),
        "three_nonregressing_folds": sum(v >= 0 for v in folds.values()) >= 3,
        "bounded_scenario_loss": all(v >= -.01 for v in scenarios.values()),
        "complete_provider_coverage": eligibility_complete and not candidate["provider_stop_reason"],
        "failure_rate": bool(records) and failures / len(records) <= .02,
        "latency": bool(records) and latency["p95_ms"] <= 5000,
        "membership_parity": same_members and all(r["membership_preserved"] for r in candidate["rerank_records"]),
        "question_parity": same_questions,
        "valid_responses": all(candidate["observed_run_counts"][k] == 0 for k in ("respond_exceptions", "invalid_response_payloads")),
    }
    return {"score_delta": round(candidate[score_key] - baseline[score_key], 6),
            "mrr_delta": round(candidate["mrr"] - baseline["mrr"], 6),
            "fold_deltas": folds, "scenario_deltas": scenarios,
            "provider_calls": len(records), "provider_failures": failures,
            "provider_latency": latency, "gates": gates, "passes": all(gates.values())}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
    from evaluator.splits import filter_samples, load_split_manifest
    from experiments.a14_deadline_selection import score_sessions
    from experiments.development_folds import validate_development_fold_manifest
    from experiments.evaluation_reporting import AgentObserver, code_provenance
    from starter.retrieval import ConditionalDenseRetriever, DenseConfig

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="authorize bounded real-provider experiment")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--key-env-file", type=Path, default=Path("../shopping-copilot-chen/.env.local"))
    parser.add_argument("--dense-cache", type=Path, default=Path("../shopping-copilot/embeddings/minilm-l6-v2-v1"))
    parser.add_argument("--model-cache", type=Path, default=Path("../shopping-copilot/models/huggingface/hub"))
    args = parser.parse_args()
    if not args.execute:
        parser.error("explicit --execute is required")
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        parser.error("use an empty output directory")
    key = ""
    for line in args.key_env_file.read_text().splitlines():
        name, separator, value = line.strip().removeprefix("export ").partition("=")
        if separator and name.strip() == "DEEPSEEK_API_KEY":
            key = value.strip().strip("\"").strip("'")
    if not key:
        parser.error("missing local DEEPSEEK_API_KEY; do not paste credentials into chat")
    if not args.dense_cache.is_dir() or not args.model_cache.is_dir():
        parser.error("existing pinned local dense caches required")
    urllib.request.install_opener(urllib.request.build_opener(NoRedirect()))
    paths = {"catalog": "data/catalog.jsonl", "dataset": "data/public_set.jsonl",
             "split": "docs/public_split_v1.json", "folds": "docs/development_folds_v1.json"}
    samples = load_jsonl(paths["dataset"])
    split, folds = load_split_manifest(paths["split"]), load_split_manifest(paths["folds"])
    validate_development_fold_manifest(samples, split, folds)
    development = filter_samples(samples, "development", split)
    if len(development) != 160:
        raise ValueError("fixed Development-160 required")
    source_paths = sorted(Path("starter").rglob("*.py")) + sorted(Path("evaluator").rglob("*.py"))
    source_paths += [Path(__file__), Path("experiments/a14_deadline_selection.py"),
                     Path("experiments/evaluation_reporting.py"), Path("experiments/development_folds.py")]
    provenance = {"code": code_provenance(), "input_sha256": {k: _sha(v) for k, v in paths.items()},
        "source_sha256": {str(p.resolve().relative_to(Path.cwd())): _sha(p) for p in source_paths},
        "scope": "fixed Development-160; no holdout; no fitting", "runtime_default_changed": False,
        "model": "deepseek-v4-flash", "prompt_version": "b10b-f1",
        "limits": {"max_calls": 1400, "max_usd": 3, "max_seconds": 1800, "timeout_ms": 8000},
        "pricing": {"input_usd_per_m": .44, "output_usd_per_m": 1.32, "basis": "conservative peak cache-miss estimate, not invoice"}}
    if not provenance["code"]["worktree_clean"]:
        parser.error("freeze source in a clean commit before paid execution")
    (args.output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    ids, categories, products = catalog_index(paths["catalog"])
    reports, comparisons = {}, {}
    with (args.output / "provider_journal.jsonl").open("x") as journal:
        ledger = BudgetedRanker(DeepSeekSemanticRanker(api_key=key), journal=journal)
        for mode in ("baseline", "candidate", "repeat"):
            if mode == "repeat" and not comparisons["candidate"]["passes"]:
                break
            started = time.monotonic()
            first_record = len(ledger.records)
            base = ConditionalDenseRetriever.from_catalog(paths["catalog"],
                dense_config=DenseConfig(cache_dir=args.dense_cache, model_cache_dir=args.model_cache))
            retriever = base if mode == "baseline" else ProductReranker(base, ledger)
            agent = TracedAgent(paths["catalog"], retriever=retriever,
                                ledger=ledger if mode != "baseline" else None)
            observer = AgentObserver(agent, catalog_ids=ids)
            print(json.dumps({"starting": mode, "sessions": len(development)}), flush=True)
            try:
                report = evaluate(observer, development, ids, categories, products)
            finally:
                base.close()
            report.update(score_sessions(report["sessions"]))
            report.update(provenance=provenance, observed_run_counts=observer.counts(),
                timing=observer.timing(), elapsed_seconds=time.monotonic() - started,
                retrieval_diagnostics=observer.retrieval_diagnostics(),
                retrieval_configuration=base.configuration_snapshot(), dense_configuration=base.dense_configuration(),
                trace=agent.trace, provider_records=ledger.records[first_record:],
                provider_stop_reason=ledger.stop_reason,
                rerank_records=retriever.records if mode != "baseline" else [],
                fixed_folds={name: score_sessions([r for r in report["sessions"] if r["sample_id"] in set(members)])
                             for name, members in folds["folds"].items()})
            if len(agent.session_order) != 160 or len(report["sessions"]) != 160:
                raise ValueError("incomplete Development evaluation")
            reports[mode] = report
            (args.output / (mode + ".json")).write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps({"finished": mode, **score_sessions(report["sessions"])}), flush=True)
            if mode != "baseline":
                comparisons[mode] = compare(reports["baseline"], report)
                print(json.dumps({"comparison": mode, **comparisons[mode]}), flush=True)
        unchanged = all(_sha(path) == digest for path, digest in provenance["source_sha256"].items())
        unchanged &= all(_sha(paths[name]) == digest for name, digest in provenance["input_sha256"].items())
        retained = unchanged and set(comparisons) == {"candidate", "repeat"} and all(c["passes"] for c in comparisons.values())
        summary = {"provenance": provenance, "comparisons": comparisons,
            "source_and_inputs_unchanged": unchanged, "runtime_default_changed": False,
            "recommendation": "retain_as_opt_in_candidate" if retained else "do_not_promote",
            "total_provider_calls": len(ledger.records), "total_cost_allowance_usd": round(ledger.total_cost, 8),
            "reported_usage_peak_estimate_usd": round(sum(r["cost_allowance_usd"] for r in ledger.records if r["usage_known"]), 8),
            "unknown_usage_calls": sum(not r["usage_known"] for r in ledger.records),
            "stop_reason": ledger.stop_reason,
            "arms": {mode: {k: v for k, v in report.items() if k not in {"trace", "provider_records", "rerank_records", "sessions", "provenance"}}
                     for mode, report in reports.items()},
            "session_outcomes": {mode: report["sessions"] for mode, report in reports.items()},
            "raw_sha256": {p.name: _sha(p) for p in args.output.glob("*.json")}}
        summary["raw_sha256"]["provider_journal.jsonl"] = _sha(args.output / "provider_journal.jsonl")
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps({"recommendation": summary["recommendation"], "calls": len(ledger.records),
                          "cost_allowance_usd": summary["total_cost_allowance_usd"]}), flush=True)


if __name__ == "__main__":
    main()
