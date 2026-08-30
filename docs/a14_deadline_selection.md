# A14 deadline selection pilot

Predeclared 2026-08-31, before viewing Candidate outcomes. LR0 found two
synthetic editor corrections, but no competition gain; retain only the cheap
offline diagnostic and defer A13 runtime/multi-family work for the deadline.
The coordinator's score-first request opens this separate deterministic pilot.

This is a small A14-S1/C1 investigation, not a claim that the full all-legal-
question counterfactual audit or formal S1 gate is complete. One Candidate,
one paired Development run; no parameter sweep. Runtime defaults stay unchanged
unless all keep conditions and a follow-up review pass.

Hypothesis: within already comparable evidence, rank-weighted separation with
no reduction in evidence coverage chooses a more useful question than raw
vocabulary diversity. Reuse QuestionPolicy.decide and existing A14-1 records.
No new catalog interpretation, state/query/retrieval change, LLM, or stop rule.

Frozen selector:

1. Preserve stop, feature-first, degraded/error, and the existing concrete-
   Buying material anchor (active category + color).
2. Examine only the contiguous legacy-eligible priority prefix with available
   bounded-vocabulary evidence, canonical questions and bounded extraction.
   Stop the prefix at the first unsupported attribute; never demote it by
   treating missing evidence as zero. If the baseline is outside the prefix,
   keep it.
3. Among that prefix, require coverage at least the baseline's. Choose maximum
   rank-weighted split, then coverage, with baseline on equal split. Only a
   strictly larger split may replace baseline.

First run legacy-returning Shadow, retaining same-snapshot proposed actions;
then run the opt-in Candidate through the unchanged official evaluator on the
same fixed Development-160. Partition both results using the fixed four folds
(not four independently fitted models). Compare scenario scores, gained/lost
sessions, productive-answer diagnostics, legality, fallback, and timing.

Keep gate: aggregate TechnicalScore strictly improves, HitRate does not fall,
at least three folds do not regress, no scenario loses >0.01 TechnicalScore,
zero response/schema/eligibility violations, and a coherent changed-question
mechanism. If any fails, preserve default and stop this Candidate. A passing
pilot still needs the full S1 counterfactual/productive-answer audit and review
before default activation. No Full/Holdout, evaluator changes or target rules.

## Result

Review correction before interpreting the pilot: the first run at `eb5214f`
used the earlier A14 audit's explicit HybridRetriever (structured-only), not
the current default B9 ConditionalDenseRetriever. It also exposed a missing
aggregate-fold score in the reporting helper. Both paired evaluations finished
and their raw session results were saved, but final fold summary failed.
Those results are exploratory only and cannot authorize default retention.
The corrected run uses default B9 configuration with the existing pinned local
model/vector cache, plus a plain-policy baseline to prove visible Shadow
parity. No selector parameters change. Record real route executions/fallbacks
and next-answer active-attribute/no-preference proxies; these are not calibrated
answerability or full counterfactual regret.

Corrected default-route run at `b77d835`, repeated at repaired source `5a6b65b`:

| Metric | Default / Shadow | Selection Candidate |
| --- | ---: | ---: |
| HitRate@10 | 0.925000 | 0.925000 |
| MRR | 0.554521 | 0.554869 |
| MTTC | 4.131250 | 4.087500 |
| Efficiency | 0.686875 | 0.691250 |
| TechnicalScore | 0.766231 | 0.767211 |

Score delta is **+0.000980**, not the larger structured-only exploratory gain.
Fixed-fold score deltas are `+0.001500, -0.000500, +0.002000, +0.000917`.
No session hit was gained or lost. Scenario score deltas are Boundary
`+0.005000`, Browsing `+0.000885`, Buying `+0.000312`, and Intent Override
`+0.001667`. The aggregate is positive but small, and fold 2 regresses.

Baseline and Shadow match visible responses exactly. Baseline, Shadow and
Candidate reproduce their complete session outcomes, scenario/fold metrics,
and visible trace hashes in the second run. Dense/fusion actually execute;
the pinned model is `all-MiniLM-L6-v2` revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, with compatible existing vectors.
Both arms use the same default B9 gate and weights. Cache paths are supplied
explicitly because this checkout lacks its own generated model/vector files.

The Candidate changes 24 of 642 question decisions (Shadow proposes changes
on 23 of 649 baseline turns). It has zero observed response exceptions,
invalid payloads, fallbacks, and question-eligibility/final-turn violations.
Observed next replies fall from 458 to 451; new-active-attribute replies remain
156, while new-no-preference replies fall from 236 to 229. This supports fewer
unproductive questions, but is a proxy, not calibrated answerability or a
complete counterfactual causal audit. Same-snapshot evidence and subsequent
attribute/no-preference state are retained for all 24 changed decisions.

Second-run response p95 is 59.26 ms baseline versus 58.94 ms Candidate. This
single-host timing does not establish a latency improvement; no extra model
or retrieval call is introduced. Peak process-tree memory was not measured.

Decision: **retain the opt-in pilot for follow-up, keep production default
unchanged**. The numeric pilot gate passes, but the full S1 all-legal-question
counterfactual/regret check is not complete. No online LLM, shared-contract,
evaluator, ranking, state, or question-template change was retained. No
Full/Holdout or private-set result is claimed.

Next smallest score-first step: audit the changed-question sessions and fold-2
regression with the existing offline counterfactual seam, then decide whether
the small benefit warrants promoting this exact selector. Do not tune a new
threshold or restart AI-silver infrastructure. If that audit cannot justify
promotion within the deadline, preserve default and move to remaining delivery
work. This is an explicit review boundary, not an assertion of default gains.

Bound evidence: [a14_deadline_selection_result.json](a14_deadline_selection_result.json)
contains all baseline/Candidate session outcomes, fixed folds, same-snapshot
changed-question audit, source/input/evaluator hashes, route configuration,
cost/timing boundaries, and repeatability checks. Full temporary reports are
not required to recompute the published session/fold metrics.

Reproduce from repository root using the project's Python environment and
existing pinned cache locations (no downloads or provider key required):

```bash
python -m experiments.a14_deadline_selection \
  --dense-cache PATH_TO_EXISTING_MINILM_VECTORS \
  --model-cache PATH_TO_EXISTING_HUGGINGFACE_HUB \
  --output PATH_TO_NEW_EMPTY_REPORT_DIRECTORY
python -m unittest discover -s tests -q
```

Automatic review: Standards and Spec findings were fixed and re-reviewed with
no open findings. The malformed-state guard and aggregate fold score have
synthetic regression tests. Final full suite: 419 tests passed; updated Markdown
links and `git diff --check` pass. Production source files remain unchanged.
