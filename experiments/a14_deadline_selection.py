"""Opt-in Development-only selection pilot; production defaults are untouched."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import time

from starter.core.clarification import QUESTION_TEXT
from starter.core.question_policy import QuestionPolicy


class SelectionPolicy:
    """Decorate the approved policy seam, returning legacy or one bounded choice."""

    def __init__(self, *, candidate=False):
        self.legacy = QuestionPolicy()
        self.candidate = candidate
        self.records = []
        self.last_latency_ms = None

    def decide(self, *, state, result, turn, top_k, response_fallback_used=False):
        started = time.perf_counter()
        outcome = self.legacy.decide(state=state, result=result, turn=turn,
            top_k=top_k, response_fallback_used=response_fallback_used)
        baseline = outcome.decision.attribute
        proposed = baseline
        raw_constraints = getattr(state, "active_constraints", None)
        active = {c["attribute"] for c in raw_constraints
                  if isinstance(c, dict) and isinstance(c.get("attribute"), str) and c.get("active", True)
                  } if isinstance(raw_constraints, list) else set()
        raw_no_preference = getattr(state, "no_preference_attributes", None)
        no_preference = sorted(a for a in raw_no_preference if isinstance(a, str)) if isinstance(raw_no_preference, set) else []
        protected = getattr(state, "intent", None) == "buying" and {"category", "color"} <= active and baseline == "material"
        diagnostics = outcome.diagnostics
        if baseline and not protected and not diagnostics.get("fallback_used") and diagnostics["evidence_status"] == "available":
            evidence = diagnostics["attribute_evidence"]
            prefix = []
            for attribute in diagnostics["eligible_attributes"]:
                row = evidence[attribute]
                numeric = (row["candidate_coverage"], row["rank_weighted_split"])
                if (row["status"] != "available" or not row["eligible"]
                    or row["comparability_family"] != "bounded_candidate_vocabulary_v1"
                    or row["answerability_status"] != "canonical_question"
                    or row["actionability_status"] != "bounded_extractor"
                    or not all(isinstance(v, (float, int)) and not isinstance(v, bool)
                               and math.isfinite(v) and 0 <= v <= 1 for v in numeric)):
                    break
                prefix.append(attribute)
            if baseline in prefix:
                reference = evidence[baseline]
                alternatives = [a for a in prefix if evidence[a]["candidate_coverage"] >= reference["candidate_coverage"]
                                and evidence[a]["rank_weighted_split"] > reference["rank_weighted_split"]]
                if alternatives:
                    proposed = max(alternatives, key=lambda a: (evidence[a]["rank_weighted_split"], evidence[a]["candidate_coverage"]))
        self.last_latency_ms = round((time.perf_counter() - started) * 1000, 6)
        self.records.append({"session_id": str(getattr(state, "session_id", "invalid")), "turn": turn,
            "baseline": baseline, "proposed": proposed,
            "selected": proposed if self.candidate else baseline,
            "eligible": diagnostics["eligible_attributes"],
            "active_attributes": sorted(active),
            "no_preference_attributes": no_preference,
            "evidence": {a: {k: r[k] for k in ("status", "candidate_coverage", "rank_weighted_split")}
                         for a, r in diagnostics["attribute_evidence"].items()},
            "changed": proposed != baseline, "latency_ms": self.last_latency_ms})
        if not self.candidate or proposed == baseline:
            return outcome
        decision = replace(outcome.decision, attribute=proposed,
            question=QUESTION_TEXT[proposed], reason_code="rank_weighted_prefix")
        return replace(outcome, decision=decision, diagnostics=dict(diagnostics,
            mode="deadline_selection_candidate", reason_code="rank_weighted_prefix"))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def score_sessions(sessions):
    from evaluator.local_evaluator import metric_summary
    from experiments.evaluation_reporting import add_scenario_scores
    result = metric_summary(sessions)
    efficiency = max(0.0, min(1.0, (11.0 - result["mttc"]) / 10.0)) if result["mttc"] is not None else 0.0
    result["efficiency"] = round(efficiency, 6)
    result["recommended_technical_score"] = round(0.5 * result["hit_rate_at_10"] + 0.3 * result["mrr"] + 0.2 * efficiency, 6)
    result["scenario_metrics"] = {s: metric_summary([r for r in sessions if r["scenario_type"] == s])
                                  for s in sorted({r["scenario_type"] for r in sessions})}
    return add_scenario_scores(result)


def main():
    from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
    from evaluator.splits import filter_samples, load_split_manifest
    from experiments.development_folds import validate_development_fold_manifest
    from experiments.evaluation_reporting import AgentObserver, code_provenance
    from starter.agent import Agent
    from starter.retrieval import ConditionalDenseRetriever, DenseConfig

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dense-cache", type=Path, default=DenseConfig().cache_dir)
    parser.add_argument("--model-cache", type=Path, default=DenseConfig().model_cache_dir)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        parser.error("use an empty output directory")
    paths = {"catalog": "data/catalog.jsonl", "dataset": "data/public_set.jsonl",
             "split": "docs/public_split_v1.json", "folds": "docs/development_folds_v1.json"}
    samples = load_jsonl(paths["dataset"])
    split = load_split_manifest(paths["split"])
    folds = load_split_manifest(paths["folds"])
    validate_development_fold_manifest(samples, split, folds)
    development = filter_samples(samples, "development", split)
    if len(development) != 160:
        raise ValueError("fixed Development-160 required")
    provenance = {"code": code_provenance(), "input_sha256": {k: _sha(v) for k, v in paths.items()},
                  "source_sha256": _sha(__file__), "scope": "fixed Development-160 only",
                  "fold_method": "fixed partition of independent session results; no fitted models"}
    ids, categories, products = catalog_index(paths["catalog"])
    reports = {}
    class TracedAgent(Agent):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.trace = []
            self.session_order = []

        def reset(self, session_id, user_profile):
            self.session_order.append(session_id)
            super().reset(session_id, user_profile)

        def respond(self, session_id, user_message, turn, top_k):
            response = super().respond(session_id, user_message, turn, top_k)
            visible = {k: response.get(k) for k in ("message", "ask_attribute", "recommendations")}
            self.trace.append(hashlib.sha256(json.dumps(visible, sort_keys=True).encode()).hexdigest())
            return response

    for mode in ("baseline", "shadow", "candidate"):
        started = time.perf_counter()
        retriever = ConditionalDenseRetriever.from_catalog(paths["catalog"],
            dense_config=DenseConfig(cache_dir=args.dense_cache, model_cache_dir=args.model_cache))
        policy = SelectionPolicy(candidate=mode == "candidate")
        agent = TracedAgent(paths["catalog"], retriever=retriever)
        if mode != "baseline":
            agent.question_policy = policy
        observer = AgentObserver(agent, catalog_ids=ids)
        try:
            report = evaluate(observer, development, ids, categories, products)
        finally:
            retriever.close()
        report.update(score_sessions(report["sessions"]))
        if len(agent.session_order) != len(development):
            raise ValueError("session trace does not cover fixed Development")
        # Offline report join only: sample identifiers never enter SelectionPolicy.
        report["offline_session_sample_map"] = dict(zip(agent.session_order,
            (s["sample_id"] for s in development)))
        next_answers = {"observed_replies": 0, "new_active_attribute": 0, "no_preference": 0}
        violations = 0
        previous = {}
        for record in policy.records:
            attribute = record["selected"]
            if attribute is not None and (attribute not in record["eligible"] or record["turn"] >= 10):
                violations += 1
            prior = previous.get(record["session_id"])
            if prior and prior["selected"] is not None:
                next_answers["observed_replies"] += 1
                next_answers["new_active_attribute"] += int(prior["selected"] in set(record["active_attributes"]) - set(prior["active_attributes"]))
                next_answers["no_preference"] += int(prior["selected"] in set(record["no_preference_attributes"]) - set(prior["no_preference_attributes"]))
            previous[record["session_id"]] = record
        report.update(provenance=provenance, observed_run_counts=observer.counts(),
                      timing=observer.timing(), elapsed_seconds=time.perf_counter() - started,
                      retrieval_diagnostics=observer.retrieval_diagnostics(),
                      retrieval_configuration=retriever.configuration_snapshot(),
                      dense_configuration=retriever.dense_configuration(),
                      visible_trace_sha256=hashlib.sha256(json.dumps(agent.trace).encode()).hexdigest(),
                      question_legality_violations=violations, answer_proxy=next_answers,
                      policy_records=policy.records,
                      changed_questions=sum(r["changed"] for r in policy.records),
                      fixed_folds={name: score_sessions([r for r in report["sessions"] if r["sample_id"] in set(members)])
                                   for name, members in folds["folds"].items()})
        reports[mode] = report
        (args.output / (mode + ".json")).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"mode": mode, **score_sessions(report["sessions"]), "changed_questions": report["changed_questions"],
                          "observed": observer.counts()}), flush=True)
    before, after = reports["shadow"], reports["candidate"]
    baseline_by_id = {r["sample_id"]: r for r in before["sessions"]}
    summary = {"provenance": provenance, "score_delta": round(after["recommended_technical_score"] - before["recommended_technical_score"], 6),
        "fold_deltas": {f: round(after["fixed_folds"][f]["recommended_technical_score"] - before["fixed_folds"][f]["recommended_technical_score"], 6) for f in folds["folds"]},
        "gained": [r["sample_id"] for r in after["sessions"] if r["hit"] and not baseline_by_id[r["sample_id"]]["hit"]],
        "lost": [r["sample_id"] for r in after["sessions"] if not r["hit"] and baseline_by_id[r["sample_id"]]["hit"]],
        "runtime_default_changed": False,
        "shadow_visible_parity": reports["baseline"]["visible_trace_sha256"] == before["visible_trace_sha256"]}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
