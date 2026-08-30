"""Plan Two only: real prewarmed retrieval, strict paired gates, unchanged F1 ranking."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from experiments.a13_shadow import response_behavior_projection
from experiments.b10b_full_rerank import BudgetedRanker, ProductReranker, TracedAgent, compare, NoRedirect


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class ObservedRetriever:
    """Identity wrapper recording actual upstream behavior before optional ranking."""

    def __init__(self, base):
        self.base = base
        self.catalog_ids, self.fallback_ids = base.catalog_ids, base.fallback_ids
        self.records = []
        if hasattr(base, "catalog_path"):
            self.catalog_path = base.catalog_path

    def retrieve(self, request):
        result = self.base.retrieve(request)
        inputs = request.to_dict()
        inputs.pop("session_id")
        diagnostics = result.diagnostics
        self.records.append({"turn": request.turn, "request_sha256": digest(inputs),
            "result_sha256": digest(response_behavior_projection(asdict(result))),
            "fallback_used": diagnostics.fallback_used, "route_failures": dict(diagnostics.route_failures),
            "executed_routes": list(diagnostics.executed_routes), "latency_ms": diagnostics.latency_ms,
            "stage_latencies_ms": dict(diagnostics.stage_latencies_ms)})
        return result


def paired_checks(baseline, report):
    before, after = baseline["upstream_records"], report["upstream_records"]
    keys = lambda rows, field: [(r["turn"], r[field]) for r in rows]
    return {"request_parity": keys(before, "request_sha256") == keys(after, "request_sha256"),
        "upstream_result_parity": keys(before, "result_sha256") == keys(after, "result_sha256"),
        "upstream_no_failures": all(not r["fallback_used"] and not r["route_failures"] for r in before + after),
        "turn_coverage": len(before) == len(baseline["trace"]) and len(after) == len(report["trace"]),
        "valid_responses": all(arm["observed_run_counts"][key] == 0 for arm in (baseline, report)
                               for key in ("respond_exceptions", "invalid_response_payloads"))}


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import argparse
    import urllib.request
    from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
    from evaluator.splits import filter_samples, load_split_manifest
    from experiments.a14_deadline_selection import score_sessions
    from experiments.development_folds import validate_development_fold_manifest
    from experiments.evaluation_reporting import AgentObserver, code_provenance
    from starter.contracts import RetrievalRequest
    from starter.core.planner import Strategy
    from starter.retrieval import ConditionalDenseRetriever, DenseConfig
    from starter.retrieval.semantic_ranker import DeepSeekSemanticRanker

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--key-env-file", type=Path, default=Path("../shopping-copilot-chen/.env.local"))
    args = parser.parse_args()
    code = code_provenance()
    if not code["worktree_clean"]:
        parser.error("freeze clean source before verification")
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        parser.error("output must be empty; never overwrite an earlier run")
    paths = {"catalog": "data/catalog.jsonl", "dataset": "data/public_set.jsonl",
             "split": "docs/public_split_v1.json", "folds": "docs/development_folds_v1.json"}
    samples = load_jsonl(paths["dataset"])
    split, folds = load_split_manifest(paths["split"]), load_split_manifest(paths["folds"])
    validate_development_fold_manifest(samples, split, folds)
    development = filter_samples(samples, "development", split)
    if len(development) != 160:
        raise ValueError("fixed Development-160 required")
    source_paths = sorted(Path("starter").rglob("*.py")) + sorted(Path("evaluator").rglob("*.py"))
    source_paths += [Path("experiments") / name for name in ("b10b_paired_rerank.py", "b10b_full_rerank.py",
        "a13_shadow.py", "a14_deadline_selection.py", "development_folds.py", "evaluation_reporting.py")]
    provenance = {"code": code, "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "fixed Development-160; Plan Two verification; actual prewarmed B9 retrieval",
        "source_sha256": {str(p): file_sha(p) for p in source_paths},
        "input_sha256": {k: file_sha(p) for k, p in paths.items()},
        "runtime_default_changed": False, "model": "deepseek-v4-flash", "prompt_version": "b10b-f1",
        "limits": {"max_calls": 900, "max_usd": 1, "max_seconds": 1200, "timeout_ms": 8000},
        "pricing": {"input_usd_per_m": .44, "output_usd_per_m": 1.32, "basis": "peak cache-miss estimate, not invoice"}}
    (args.output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    ids, categories, products = catalog_index(paths["catalog"])
    base = ConditionalDenseRetriever.from_catalog(paths["catalog"], dense_config=DenseConfig(
        cache_dir=Path("../shopping-copilot/embeddings/minilm-l6-v2-v1"),
        model_cache_dir=Path("../shopping-copilot/models/huggingface/hub")))
    reports, comparisons, ledger = {}, {}, None
    try:
        warm = base.retrieve(RetrievalRequest("synthetic_warmup", 1, 10, "shoes", "browsing",
            Strategy("browsing", .6, .2, .2, 120, False, True, "broad_lexical", "synthetic prewarm")))
        (args.output / "warmup.json").write_text(json.dumps(warm.diagnostics.to_dict(), indent=2) + "\n")
        with (args.output / "provider_journal.jsonl").open("x") as journal:
            for arm in ("baseline", "placebo", "candidate", "repeat"):
                if arm == "candidate" and (args.offline or not comparisons["placebo"]["passes"]):
                    break
                if arm == "repeat" and not comparisons["candidate"]["passes"]:
                    break
                if arm == "candidate":
                    key = ""
                    for line in args.key_env_file.read_text().splitlines():
                        name, sep, value = line.strip().removeprefix("export ").partition("=")
                        if sep and name.strip() == "DEEPSEEK_API_KEY": key = value.strip().strip("\"").strip("'")
                    if not key: raise ValueError("missing local key; never paste credentials")
                    urllib.request.install_opener(urllib.request.build_opener(NoRedirect()))
                    ledger = BudgetedRanker(DeepSeekSemanticRanker(api_key=key),
                        max_calls=900, max_usd=1, max_seconds=1200, journal=journal)
                started = time.monotonic()
                first = len(ledger.records) if ledger else 0
                upstream = ObservedRetriever(base)
                retriever = ProductReranker(upstream, ledger) if ledger else upstream
                agent = TracedAgent(paths["catalog"], retriever=retriever, ledger=ledger)
                observer = AgentObserver(agent, catalog_ids=ids)
                print(json.dumps({"starting": arm, "sessions": 160}), flush=True)
                report = evaluate(observer, development, ids, categories, products)
                if len(agent.session_order) != 160 or len(report["sessions"]) != 160:
                    raise ValueError("incomplete Development evaluation")
                report.update(score_sessions(report["sessions"]))
                report.update(provenance=provenance, observed_run_counts=observer.counts(),
                    timing=observer.timing(), elapsed_seconds=time.monotonic() - started,
                    retrieval_diagnostics=observer.retrieval_diagnostics(),
                    retrieval_configuration=base.configuration_snapshot(), dense_configuration=base.dense_configuration(),
                    trace=agent.trace, upstream_records=upstream.records,
                    provider_records=ledger.records[first:] if ledger else [],
                    provider_stop_reason=ledger.stop_reason if ledger else None,
                    rerank_records=retriever.records if ledger else [],
                    fixed_folds={f: score_sessions([r for r in report["sessions"] if r["sample_id"] in members])
                                 for f, members in folds["folds"].items()})
                reports[arm] = report
                (args.output / (arm + ".json")).write_text(json.dumps(report, indent=2) + "\n")
                print(json.dumps({"finished": arm, **score_sessions(report["sessions"])}), flush=True)
                if arm != "baseline":
                    pairing = paired_checks(reports["baseline"], report)
                    if arm == "placebo":
                        pairing.update(visible_parity=reports["baseline"]["trace"] == report["trace"],
                            outcome_parity=reports["baseline"]["sessions"] == report["sessions"])
                        comparisons[arm] = {"gates": pairing, "passes": all(pairing.values())}
                    else:
                        comparisons[arm] = compare(reports["baseline"], report)
                        comparisons[arm]["gates"].update(pairing)
                        comparisons[arm]["passes"] = all(comparisons[arm]["gates"].values())
                    print(json.dumps({"comparison": arm, **comparisons[arm]}), flush=True)
            unchanged = all(file_sha(p) == h for p, h in provenance["source_sha256"].items()) and all(
                file_sha(paths[k]) == h for k, h in provenance["input_sha256"].items())
            records = ledger.records if ledger else []
            retained = unchanged and "repeat" in comparisons and all(r["passes"] for r in comparisons.values())
            summary = {"provenance": provenance, "comparisons": comparisons,
                "source_and_inputs_unchanged": unchanged, "runtime_default_changed": False,
                "decision": "verified_optional_plan_two" if retained else "do_not_promote",
                "total_provider_calls": len(records), "total_cost_allowance_usd": round(sum(r["cost_allowance_usd"] for r in records), 8),
                "unknown_usage_calls": sum(not r["usage_known"] for r in records),
                "stop_reason": ledger.stop_reason if ledger else None,
                "arms": {a: {k: v for k, v in r.items() if k not in {"trace", "upstream_records", "provider_records",
                    "rerank_records", "sessions", "provenance"}} for a, r in reports.items()},
                "session_outcomes": {a: r["sessions"] for a, r in reports.items()},
                "raw_sha256": {p.name: file_sha(p) for p in args.output.iterdir() if p.is_file()}}
            (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            print(json.dumps({k: summary[k] for k in ("decision", "total_provider_calls", "total_cost_allowance_usd")}), flush=True)
    finally:
        base.close()


if __name__ == "__main__":
    main()
