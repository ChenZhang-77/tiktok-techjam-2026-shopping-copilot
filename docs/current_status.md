# Shopping Copilot — Current Status

As of 2026-08-31. This is the authoritative current checkpoint, not an experiment
history. Read [final release plan](final_release_plan.md) for decisions,
[branch inventory](branch_inventory.md) for recoverable sources, and
[roadmap](optimization_roadmap.md) for the only active next steps.

## Selected branch

The delivery was assembled on `release/track4-final-integration`, based on fetched main
`3b01416` (Chen offline runtime plus teammate visualizer updates). Chen's earlier
source publication to `yuqing` remains historical. The user has now authorized
stepwise local implementation and automatic per-step review; see the
[execution log](final_delivery_execution.md). On 2026-08-31 the user separately
authorized integrating/pushing the reviewed version to existing main while
preserving all other branches and repository visibility. Remote main was safely
fast-forwarded from `3b01416` to reviewed checkpoint `bb6b7f3`; subsequent release
status edits are documentation-only. Main was directly verified at `9d83674`.
The user subsequently approved publication and the existing component credits,
confirmed both participants registered, and requested a fresh project/copy review
before any form filling. Revised copy is pending approval. The repository remains
PRIVATE; available CLI permission is WRITE, so visibility requires an owner/admin.
No public change, upload, new paid call or Devpost submission has occurred.

Plan One's runtime is Chen `0bd3375`: state/extraction corrections, scoped
QueryPlan, priority-based clarification, structured retrieval, and conditional
local MiniLM/RRF (B9). B12 and profile scoring remain off. The new delivery entry
and independent package now integrate explicit optional F2 reranking while
preserving offline behavior and the shared contract.

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

## Frozen final public report — separate Full200 population

One offline Full200 run completed on frozen package/runtime source `951d03e` after
the reporting tool's independent review. No ranking/state/configuration was tuned
using the result. [Full report](delivery_reports/final_public_full200.json),
[freeze](delivery_reports/final_public_freeze.json) and the started marker retain
200 session outcomes, scenario metrics, timing and code/input/model hashes.

HR@10 **0.930000** (186/200), MRR **0.527544**, MTTC **4.105000**, Efficiency
**0.689500**, TechnicalScore **0.761163**. 807 turns, 127 dense/fusion executions,
zero observed fallback/invalid payloads/response exceptions, zero external calls
and tokens. Response p95 **46.863 ms**, max **113.374 ms**, initialization with
synthetic prewarm **4.342 s**, measured run **25.986 s**, peak process RSS
**1,101,496,320 bytes**. These are prepared same-machine observations, not every
cold-start/other-host guarantee. Setup downloads are outside measured runtime.

This is the exposed **public** population, not unseen validation or private800.
Do not interpret its difference from Development160 as an algorithm change.
Independent arithmetic/source/input verification is available through
`python scripts/verify_delivery_evidence.py` without running the Agent again.

## Optional LLM disposition

Only B10b-F2 product reranking is retained as **verified optional Plan Two**:
two paired 160-session passes, scores `0.779043 / 0.779199` versus
`0.766231`, all four folds positive, unchanged HR/MTTC. It used 826 real calls,
estimated total USD 0.69472392; provider p95 1.146/1.609 seconds, max
7.318 seconds, and non-identical ranking orders between rounds.
The unchanged [historical F2 evidence](delivery_reports/f2_historical.json) is
retained here, so judges do not need another branch. Do not substitute older
DS1/DS2 scripts or call historical F2 a live test of this new integrated package.

No new paid tests follow from this release. A13 semantic understanding is
inactive: 60/67 real Shadow responses validated, below the 95% gate; no Candidate
ran, so no Candidate efficacy conclusion is justified.

## Frozen work and preserved data

A13 AI-silver reference construction, annotation repair, A14 selection pilot
and its pending counterfactual audit, profile/depth/recall extensions, and
old P0 packaging are frozen. Their code/evidence remains available; “frozen”
does not mean passed or implemented. Full disposition and reopening conditions
are in [final release plan](final_release_plan.md).

Existing optional DS1/DS2 code remains for history, with no default activation.
Step 02 adds `starter.delivery.Agent` and the frozen F2 reranking wrapper without
changing the retained Control Plane or shared contracts. The offline default is
unchanged; live enhancement of this new entry is not yet verified. See
[configuration and explicit limits](delivery_configuration.md) and the execution log.

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

**Source release is not completed competition submission.** The integration
checkout now contains the newly generated independent package; old P0 packaging
was not copied as runtime. Package-source hashes, clean-directory synthetic
startup and an actual Development-160/four-fold paired run pass: score .766231,
649 turns, zero observed fallback, exact core/delivery traces. See
[bound package evidence](delivery_reports/offline_package.json).
Validation used separately copied local assets and the prepared same-machine
Python environment; no other-machine/fresh dependency-install claim is made.
The visualizer now forces offline mode, binds recorded metrics to matching source
and inputs, separates evaluator annotations, and rejects historical/out-of-split
reruns. Seven API/behavior regressions and the browser walkthrough pass; the full
suite was 323 tests at step 04. Step 05 prepared a main-only Devpost draft, a
commit-supported contribution draft and a rehearsed recording script.
Actual video recording/upload, new live LLM verification
and public submission remain incomplete. Profile remains disabled; B9 is
conditional, not global hybrid retrieval, and Plan One does not claim an active
LLM-ranking pillar. See [delivery plan](demo_and_submission_plan.md).

Final local audit: 330 tests pass, including a clean source snapshot with an
independently copied catalog; 37-file bundle and45-entry combined ZIP hashes
verify. Standards/Spec final reviews pass. [Final readiness](final_readiness.md)
records the exact limits of this local completion and the uncompleted external gates.

Judge-facing revision: [story](devpost_story.md) and [field preview](devpost_draft.md)
are locally revised, not yet approved/filled or pushed. Existing component credits
are now user-approved. The live event page's public 3-minute YouTube requirement
and 2026-09-01 12:00 SGT deadline supersede the earlier video editing suggestion.
The user confirmed the registered team name; its exact value is in the
[field values](devpost_draft.md#team-name). Leader contact data stays out of Git.
Following the audience-boundary re-review, field values and public story are
separated from the [team-only operating checklist](demo_and_submission_plan.md#devpost-填表操作清单仅供队内操作不复制提交).
The earlier zero-finding copy review missed this distinction; see the
[correction record](judge_readiness_review.md#audience-boundary-correction).
