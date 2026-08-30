# Release Comparison and Validation — 2026-08-31

## Decision: Chen is the stronger main source

Share with caveats. Publish Chen `0bd3375` descendants to `yuqing`, keep
`llm` for optional Plan Two, and freeze P0 packaging at `aaa7e45`.
[Final plan](final_release_plan.md) defines the release scope and pending package work.

| Source | HR@10 | MRR | MTTC | TechnicalScore | Dense executions |
| --- | ---: | ---: | ---: | ---: | ---: |
| P0 original `aaa7e45` | 0.862500 | 0.547329 | 4.668750 | 0.722074 | 102 |
| Chen `0bd3375` | 0.925000 | 0.554521 | 4.131250 | 0.766231 | 101 |
| llm default `7f0dc6c` | 0.925000 | 0.554521 | 4.131250 | 0.766231 | 101 |

Chen improves score by **0.044157**, gains **10 hits and loses none**, and lowers
MTTC by **0.5375 turns**. llm's default has exact parity with Chen's 160 session
outcomes; that is not a claim that every intermediate diagnostic is identical.
This review changes no runtime behavior, so the measured source hashes remain
valid after the documentation commits.

## Protocol and source binding

Runner: [release_default_audit.py](../experiments/release_default_audit.py).
All arms use the same official catalog/public-set/split/four-fold hashes, same
local embedding asset hashes and pinned MiniLM revision, actual
`ConditionalDenseRetriever` defaults and one synthetic `shoes` prewarm.
Only asset paths are explicitly injected. B12/profile/LLM/experimental question
selection are off. This is not `evaluation_reporting --structured-filter`.

The official evaluator is unchanged. Every session is included. Fixed folds
are partitions of the 160 independent session outcomes, not fitted models or
new samples. No exposed-holdout/Full-200 runs and **zero external LLM calls**.
Both candidate branches received the same audit runner without changing
`starter/` or `evaluator/`.

Bound full reports:

- [P0 default](release_reports/p0_default.json)
- [Chen default](release_reports/chen_default.json)
- [llm default](release_reports/llm_default.json)
- [SHA256 manifest](release_reports/manifest.json)

The reports include all 160 session outcomes, scenario/fold metrics, counts,
source/input/asset hashes, warmup, route execution and latency. Source commits
refer to pre-organization runtime snapshots; the runner SHA binds the new
audit file independently. They do not assert that the documentation worktree
was clean during measurement.

## All four folds, Chen minus original

| Fixed fold | HR delta | MRR delta | MTTC delta | Score delta |
| --- | ---: | ---: | ---: | ---: |
| fold_1 | +0.050000 | +0.005417 | -0.275000 | +0.032125 |
| fold_2 | +0.050000 | +0.021905 | -0.200000 | +0.035571 |
| fold_3 | +0.050000 | +0.006766 | -0.600000 | +0.039029 |
| fold_4 | +0.100000 | -0.005318 | -1.075000 | +0.069904 |

All fold TechnicalScores and hit rates improve. Do not claim every component
improves: fold_4 MRR falls; scenario MRR also falls in Browsing
(`0.540272 -> 0.522582`) and Buying (`0.517591 -> 0.516828`).
All four scenario TechnicalScores nevertheless improve.

Gained Development sessions: `public_0037`, `public_0093`, `public_0111`,
`public_0130`, `public_0171`, `public_0175`, `public_0179`, `public_0180`,
`public_0194`, `public_0195`. Lost: none. Session IDs are offline evidence,
never runtime feature/configuration inputs.

## Reliability and uncertainty

All three arms have zero response exceptions, invalid payloads, reported
fallbacks or route failures. They emit 725 / 649 / 649 scored turns.
Observed audit elapsed times (including startup): 83.31 / 76.37 / 89.59 seconds.
Do not infer a runtime-speed ranking: same-machine measurements and warmup do
not prove cold-start or other-machine reliability. Retained B9's acceptance
budget remains 250 ms after execution, not a preemptive timeout.

This selects between integrated branches, not individual fixes. Development
is repeatedly exposed; no private-test gain or statistical significance is
claimed. The old structured-only Chen score `0.765703` is a different comparator.

## Reproduce

From each source checkout, after placing the official catalog at
`data/catalog.jsonl` and preparing the pinned local model/cache:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
  .venv/bin/python -m experiments.release_default_audit \
  --output /private/tmp/release-default-new.json
```

For shared local assets, use `--cache-dir`, `--model-cache-dir` and
`--catalog` explicitly. They must resolve to the same hashed inputs across arms.
The original P0 checkpoint lacks this new runner: run the same audit script
through `runpy.run_path` from P0's working directory so its own Agent/evaluator
are imported. The report hashes record the runner actually used.

## Verification and review

Before organization: P0 **294**, Chen **297**, llm **443** tests passed.
After organization: P0 **294**, Chen **302**, llm **448** tests pass.
Tests recompute metrics/folds, verify active-source and artifact hashes,
and cover synthetic score/miss accounting. Local Markdown links: P0 28,
Chen 53, llm 112 checked, zero missing targets. Independent Standards/Spec
review is pending before push; it is not inferred from passing tests.

Source publication is independent of competition-package readiness. The P0
package's tests pass for P0 only; selected branch `submission/` is still staging.
See [delivery plan](demo_and_submission_plan.md).
