# Shopping Copilot — Current Status

As of 2026-08-31. This is the authoritative current checkpoint, not an experiment
history. Read [final release plan](final_release_plan.md) for decisions,
[branch inventory](branch_inventory.md) for recoverable sources, and
[roadmap](optimization_roadmap.md) for the only active next steps.

## Selected branch

This checkout is `chen/chenzhang-77-baseline-setup`, selected as Plan One and published to remote `yuqing`. It is not the stale local branch also named `yuqing`.

Plan One's runtime is Chen `0bd3375`: state/extraction corrections, scoped
QueryPlan, priority-based clarification, structured retrieval, and conditional
local MiniLM/RRF (B9). B12 and profile scoring remain off. No runtime or shared
contract changes are part of this release organization.

## Current measured default — Development-160 only

| Metric | Original P0 `aaa7e45` | Selected Chen `0bd3375` |
| --- | ---: | ---: |
| HitRate@10 | 0.862500 | 0.925000 |
| MRR | 0.547329 | 0.554521 |
| MTTC | 4.668750 | 4.131250 |
| Efficiency | 0.633125 | 0.686875 |
| TechnicalScore | 0.722074 | 0.766231 |

The release comparison uses the actual B9 route, identical hashed input/model
assets, and synthetic prewarm. No paid call, Full-200 or exposed-holdout run.
See [comparison, folds and caveats](release_comparison.md) and its bound reports.
This is a branch-level comparison, not a causal ablation of one individual fix.
Local warm-run results do not prove other-machine or cold-start reliability.

The earlier Chen `0.765703` / MRR `0.552760` checkpoint used structured-only
injection; it is not this default-route measurement. The old B12
`0.722074` report and Full-200 `0.650207` snapshot remain historical.
The 40 exposed public sessions are not unseen validation; private generalization
is unverified.

## Optional LLM disposition

Only B10b-F2 product reranking is retained as **verified optional Plan Two**:
two paired 160-session passes, scores `0.779043 / 0.779199` versus
`0.766231`, all four folds positive, unchanged HR/MTTC. It used 826 real calls,
estimated total USD 0.69472392; provider p95 1.146/1.609 seconds, max
7.318 seconds, and non-identical ranking orders between rounds.
Evidence stays on the [llm source branch](https://github.com/ChenZhang-77/tiktok-techjam-2026-shopping-copilot/blob/7f0dc6c07b0cc2375a82c50ff47e5ee98652f0b6/docs/b10b_paired_verification.md); do not substitute this checkout's older DS1/DS2 scripts for the F2 recipe.

No new paid tests follow from this release. A13 semantic understanding is
inactive: 60/67 real Shadow responses validated, below the 95% gate; no Candidate
ran, so no Candidate efficacy conclusion is justified.

## Frozen work and preserved data

A13 AI-silver reference construction, annotation repair, A14 selection pilot
and its pending counterfactual audit, profile/depth/recall extensions, and
old P0 packaging are frozen. Their code/evidence remains available; “frozen”
does not mean passed or implemented. Full disposition and reopening conditions
are in [final release plan](final_release_plan.md).

Existing optional DS1/DS2 code remains for history, with no default activation. No llm runtime/interface expansion has been merged into Plan One.

No catalog, cache/model assets, original annotations, raw runs, branches or user
stash were deleted. Chen's missing ignored catalog path was connected locally
to the existing verified catalog for testing; that link is not committed.

## Verification and delivery status

Pre-organization suites: P0 294 tests, Chen 297 tests, llm 443 tests. Final release
checks and test counts are recorded in [release comparison](release_comparison.md).
Default verification command after local data/model preparation:

```bash
.venv/bin/python -m unittest discover -s tests -q
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
  .venv/bin/python -m experiments.release_default_audit \
  --output /private/tmp/release-default-new.json
```

Use a new output filename each time. Missing models/caches mean degraded
structured behavior, not reproduction of the B9 score. Ordinary
`evaluation_reporting --structured-filter` intentionally tests that separate path.

**Source release is not completed competition submission.** Neither selected
checkout contains the new independent package yet. Old P0 packaging is tied
to its older runtime. Next: regenerate from the chosen source, validate a
fresh environment and degradation, then finish evidence-backed contributions,
demo/video and final submission artifacts. Profile remains disabled; B9 is
conditional, not global hybrid retrieval, and Plan One does not claim an active
LLM-ranking pillar. See [delivery plan](demo_and_submission_plan.md).
