"""Offline release comparison: unchanged B9 defaults, fixed Development-160 only."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl, metric_summary
from evaluator.splits import filter_samples, load_split_manifest
from experiments.development_folds import validate_development_fold_manifest
from experiments.evaluation_reporting import AgentObserver, add_scenario_scores
from starter.agent import Agent
from starter.contracts import RetrievalRequest
from starter.core.planner import Strategy
from starter.retrieval import ConditionalDenseRetriever, DenseConfig


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def score_sessions(sessions: list[dict]) -> dict:
    result = metric_summary(sessions)
    efficiency = max(0.0, min(1.0, (11.0 - result["mttc"]) / 10.0)) if sessions else 0.0
    result["efficiency"] = round(efficiency, 6)
    result["recommended_technical_score"] = round(
        0.5 * result["hit_rate_at_10"] + 0.3 * result["mrr"] + 0.2 * efficiency, 6
    )
    result["scenario_metrics"] = {
        scenario: metric_summary([row for row in sessions if row["scenario_type"] == scenario])
        for scenario in sorted({row["scenario_type"] for row in sessions})
    }
    return add_scenario_scores(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.jsonl"))
    parser.add_argument("--cache-dir", type=Path, default=Path("embeddings/minilm-l6-v2-v1"))
    parser.add_argument("--model-cache-dir", type=Path, default=Path("models/huggingface/hub"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("use a new output path; existing evidence must not be overwritten")
    paths = {"catalog": args.catalog, "dataset": Path("data/public_set.jsonl"),
             "split": Path("docs/public_split_v1.json"), "folds": Path("docs/development_folds_v1.json")}
    samples = load_jsonl(paths["dataset"])
    split, folds = load_split_manifest(paths["split"]), load_split_manifest(paths["folds"])
    validate_development_fold_manifest(samples, split, folds)
    development = filter_samples(samples, "development", split)
    if len(development) != 160:
        raise ValueError("expected the fixed Development-160 population")
    source = sorted(Path("starter").rglob("*.py")) + sorted(Path("evaluator").rglob("*.py"))
    source += [Path("experiments/development_folds.py"), Path("experiments/evaluation_reporting.py")]
    provenance = {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
        "runner_sha256": sha256(Path(__file__)),
        "source_sha256": {str(path): sha256(path) for path in source},
        "input_sha256": {name: sha256(path) for name, path in paths.items()},
        "dense_asset_sha256": {name: sha256(args.cache_dir / name)
                               for name in ("metadata.json", "ids.json", "vectors.npy")},
        "scope": "Development-160, unchanged B9 default with explicit local asset paths; synthetic prewarm",
        "fold_method": "fixed partition of independent session outcomes, no fitting or tuning",
        "external_llm_calls": 0,
    }
    started = time.monotonic()
    ids, categories, products = catalog_index(paths["catalog"])
    retriever = ConditionalDenseRetriever.from_catalog(paths["catalog"], dense_config=DenseConfig(
        cache_dir=args.cache_dir, model_cache_dir=args.model_cache_dir))
    try:
        warmup = retriever.retrieve(RetrievalRequest("synthetic_warmup", 1, 10, "shoes", "browsing",
            Strategy("browsing", .6, .2, .2, 120, False, True, "broad_lexical", "synthetic prewarm")))
        observer = AgentObserver(Agent(paths["catalog"], retriever=retriever), catalog_ids=ids)
        report = evaluate(observer, development, ids, categories, products)
        if len(report["sessions"]) != 160:
            raise ValueError("incomplete Development evaluation")
        report.update(score_sessions(report["sessions"]))
        report.update(provenance=provenance, observed_run_counts=observer.counts(),
            timing=observer.timing(), retrieval_diagnostics=observer.retrieval_diagnostics(),
            warmup=warmup.diagnostics.to_dict(), elapsed_seconds=time.monotonic() - started,
            retrieval_configuration=retriever.configuration_snapshot(),
            dense_configuration=retriever.dense_configuration(),
            fixed_folds={name: score_sessions([row for row in report["sessions"] if row["sample_id"] in members])
                         for name, members in folds["folds"].items()})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as handle:
            handle.write(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"output": str(args.output), **score_sessions(report["sessions"]),
                          "counts": observer.counts(), "elapsed_seconds": report["elapsed_seconds"]}))
    finally:
        retriever.close()


if __name__ == "__main__":
    main()
