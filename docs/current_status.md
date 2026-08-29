# Shopping Copilot - Current Status

This file is the single source of truth for the current project state. It is
written for a fresh Codex conversation and for the two-person team. Re-check
the Git checkout before relying on any checkout-specific value below.

## Start Here in a New Conversation

Read, in order:

1. `AGENTS.md` for non-negotiable operating rules.
2. This file for the verified current state and next decision.
3. `docs/human_optimization_recap_zh.md` when a human-readable Chinese history
   and metric explanation is needed.
4. `docs/optimization_roadmap.md` for the project-wide execution order.
5. One workstream document:
   - A: `docs/workstreams/DEVELOPER_A_CONTROL_PLANE.md`
   - B: `docs/workstreams/DEVELOPER_B_RETRIEVAL_RANKING.md`
6. The files named by the selected experiment.

At the beginning of the conversation, report:

```text
Branch:
HEAD:
Working tree clean/dirty:
Selected workstream and experiment:
Files expected to change:
Development-only verification command:
```

Do not implement a backlog item merely because it appears in a roadmap. The
user must still ask for implementation. A planning or review request is
read-only.

## Verified Behavior Checkpoint

The retained B12 checkpoint was verified on 2026-08-28. The A13 planning
branch test and baseline reproduction were verified on 2026-08-29:

| Item | Value |
| --- | --- |
| Branch at B12 verification | `b/b12-adaptive-depth` |
| Retained default behavior commit | `7f520ba` |
| Optional B12 code/default-parity commit | `82891c8` |
| B10a experiment branch | `b/b10a-constraint-preserving-crossencoder` |
| Latest local full test suite (2026-08-29) | 297 passed on the A13 planning branch |
| Catalog | 50,000 unique products, local generated file ignored by Git |
| Default runtime | B9 gated dense/RRF; B12 adaptive depth is explicit opt-in only |

Branch and remote facts can drift. Re-check them before reporting or changing
the repository. Do not fetch, push, merge, or open a PR unless the user asks.
Documentation-only commits after this checkpoint do not invalidate the metrics;
any runtime behavior change does.

## Verified Development Result

The retained default after bounded A11 extraction and B9 conditional dense was
reproduced exactly at B12's disabled-by-default code commit `82891c8` on the
fixed Development-160 split:

| Metric | Development-160 |
| --- | ---: |
| HitRate@10 | 0.86250 |
| MRR | 0.547329 |
| MTTC | 4.66875 |
| Efficiency | 0.633125 |
| TechnicalScore | 0.722074 |

Scenario diagnostics:

| Scenario | Samples | HitRate@10 | MRR | MTTC | TechnicalScore |
| --- | ---: | ---: | ---: | ---: | ---: |
| Boundary | 8 | 0.875000 | 0.576389 | 6.000000 | 0.710417 |
| Browsing | 64 | 0.875000 | 0.540272 | 4.546875 | 0.728644 |
| Buying | 64 | 0.843750 | 0.517591 | 4.328125 | 0.710590 |
| Intent Override | 24 | 0.875000 | 0.635764 | 5.458333 | 0.739063 |

Observed default reliability was zero response exceptions, invalid payloads,
reported fallbacks, and route failures. Dense and fusion executed 102 times.
The bound default-parity artifact is
`docs/b12_reports/development_default_parity.json`. Optional B12 improves the
aggregate but regresses Buying MRR and fold 1, with its positive fold result
concentrated in fold 4. It remains disabled; see
`docs/b12_adaptive_depth_evidence.md`.

## Latest A-Side State-Correction Checkpoint

After the checkpoint above, the local `Zhang-Chen` working tree was corrected
for three known A-side correctness issues: negated feature-list clauses are no
longer promoted into positive constraints, low-confidence fallback text cannot
revoke `no-preference`, and offline taxonomy uses the shared no-preference
detector. The correction adds no LLM and does not change the B-side retrieval
interface.

Development-160 was rerun after the correction:

| Metric | Result |
| --- | ---: |
| HitRate@10 | 0.925000 |
| MRR | 0.552760 |
| MTTC | 4.13125 |
| Efficiency | 0.686875 |
| TechnicalScore | 0.765703 |

The run produced 649 responses with zero response exceptions, invalid payloads,
and fallbacks. This is a Development-only correctness checkpoint, not a sealed
holdout validation and not an ablation proving the contribution of each fix.
The exact output was retained outside the repository and is intentionally not
part of the shared checkout.

## Historical Final Public Result

The one Full-200 Final Public Run was executed from frozen commit `98d3325`:

| Metric | Full-200 |
| --- | ---: |
| HitRate@10 | 0.765000 |
| MRR | 0.517355 |
| MTTC | 5.375000 |
| Efficiency | 0.562500 |
| TechnicalScore | 0.650207 |

This is a historical, non-confirmatory public snapshot. The 40-session public
holdout had already been exposed by earlier full-set work. Do not tune against,
repeat, or present this result as a sealed validation result. The organizer's
private 800 sessions remain the external generalization test. See:

- `docs/adr/0001-treat-public-holdout-as-exposed.md`
- `docs/b7_final_public_summary.json`
- `docs/b7_final_public_run.json`

Any later behavior change means the Full-200 result no longer describes the new
runtime. Report it as historical and select new work only with Development-160
cross-validation.

## Current Retained Runtime

```text
user message
  -> scoped extraction with frozen-catalog multi-word categories
  -> state/context update
  -> current-turn Buying/Browsing inference
  -> Strategy planning
  -> distilled active-state query
  -> in-memory SQLite FTS5 field-weighted candidate pool
  -> hard/soft cross-field constraint ranking
  -> guarded structured filtering with deterministic relaxation/fill
  -> broad-Browsing gate -> pinned local dense retrieval + weighted RRF
     (otherwise exact structured order)
  -> candidate-aware but still priority-biased clarification
  -> response guard
```

The public seam is:

```text
Agent.respond(session_id, user_message, turn, top_k) -> response dict
Retriever.retrieve(request: RetrievalRequest) -> RetrievalResult
```

The shared contract lives in `starter/contracts.py`. Developer A must not send
evaluator labels. Developer B must not import Agent state implementation
internals.

AB1 distinguishes requested from executed Routes. B9 consumes the existing
typed request without changing the shared schema and executes dense only behind
its Browsing/constraint/pool-size gate. It never parses `Strategy.reason` and
does not use an unavailable intent-confidence field.

## Retained Conditional and Disabled Paths

| Path | Decision |
| --- | --- |
| B9 broad-Browsing MiniLM + weighted RRF | Retained conditionally; exact structured fallback |
| Dense-only MiniLM retrieval | Reject as default; weak recall/ranking |
| Global weighted RRF fusion | Reject as default; cross-validation regression |
| Top-30 CrossEncoder semantic rerank | Reject globally; small aggregate gain but MRR and Intent Override regression, high cost |
| B10a anchored CrossEncoder | Reject as default; Top 3 and Top 5 both reduce MRR and TechnicalScore |
| B10b-DS1 DeepSeek Browsing Top-10 | Opt-in code and provisional remote measurement; default remains off |
| B10b-DS2 DeepSeek Browsing Top-20 | Provisional remote rejection; complete report is not yet tracked |
| Profile ranking | Disabled at weight 0.0; no evidence-backed gain |

Do not claim that every request combines lexical, dense, and semantic routes.
The default Agent conditionally combines structured and dense evidence for a
narrow Browsing bucket; Buying remains unchanged. The DeepSeek B10b-DS1 ranker
exists only as an opt-in experiment and is not part of the retained default.

## Current Bottlenecks

The current `0.925` planning audit assigns the 12 Development misses to:

1. Question Policy: 10;
2. State / Override: 2;
3. Extraction, Intent / Routing, and Retrieval / Ranking: 0 primary misses.

This audit was generated read-only into `/private/tmp` and still needs
clean-commit/hash binding before it supersedes the older tracked R0 artifact.
The old taxonomy's automatic `next_experiment=A9` recommendation is stale
because A9 was already measured, rejected, and reverted.

The next work is therefore A-owned and ordered:

1. bind the current baseline and refreshed taxonomy;
2. diagnose the two State / Override misses as a deterministic slice;
3. run A13 DeepSeek semantic understanding in Shadow mode only;
4. activate only a trigger class that passes the reviewed Shadow gate;
5. address Question Policy later as a separate A14 experiment.

The authoritative A13 plan is
[`DeepSeek_LLM接入实验方案.md`](../DeepSeek_LLM接入实验方案.md). It does not claim
that A13 is implemented.

## Current A13 Decision

`a/a13-llm-semantic-understanding` starts from Chen baseline `0bd3375`.
DeepSeek is planned as an A-owned, evidence-gated semantic interpreter before
state mutation, not as a second Agent and not as a replacement for the existing
deterministic parser.

The first runtime-capable stage is Shadow: it may call the provider and record a
validated `UnderstandingDelta`, but it must not change SessionState, Strategy,
QueryPlan, clarification, recommendations, or public output. Candidate
activation requires exact fallback, bounded call rate/latency/cost, focused and
full tests, and fixed Development-fold evidence.

A13 does not replace B10b-DS1. A13 interprets difficult user language before
retrieval; B10b-DS1 reranks an existing Browsing Top-10 after retrieval. They
must not be activated together in one metric experiment, and the default
runtime remains no-LLM.

## R0 Result

R0 is complete at clean code commit `0b9bc74`. The Development-160 baseline
remained HitRate@10 `0.7625`, MRR `0.526989`, MTTC `5.30625`, and recommended
technical score `0.653222`; R0 changed no runtime behavior.

Of 38 missed sessions, the earliest observed cause was Intent / Strategy
Routing in 25, State / Override in seven, and Extraction in six. Intent /
Strategy Routing was the largest class in every fixed fold. The target entered
the retained lexical pool in 145 of 160 sessions, so the next optimization
should stay on the A-side control plane.
This is deterministic evidence triage, not proof that every downstream failure
would disappear after one upstream behavior change. The durable report is
`docs/r0_development_failure_taxonomy.md`, with turn-level offline evidence in
the adjacent JSON artifact.

## A8 Result

A8 is retained at clean code commit `83a6bcd`. `IntentAssessment` is now a
persistent `SessionState` value with intent, A-owned ordinal confidence,
evidence, source turn, and an explicit transition reason. A diagnostics expose
the complete decision while `Strategy.reason` exposes only the transition;
the A/B request contract is unchanged.

On Development-160, HitRate@10 remains `0.7625`, MRR increases from `0.526989`
to `0.529812`, MTTC changes from `5.30625` to `5.35`, and technical score is
effectively neutral (`0.653222` to `0.653194`). Buying improves in three of four
folds and Browsing does not regress; Intent Override regresses slightly. The
bounded decision and rejected variants are recorded in
`docs/a8_stateful_intent_evidence.md`.

## AB0 Result

AB0 is retained at clean code commit `3988b8b`. The A-side adapter computes
bounded full-pool size, Top-K stability, constraint coverage, attribute
partition, relaxation/degradation, and turn/exhaustion summaries before
clarification. Raw Candidate IDs/text are not serialized, and the shared A/B
contracts are unchanged. Route-local score margin is observable but explicitly
uncalibrated and unusable for A9.

The clean Development-160 metrics and all 160 session outcomes exactly match
A8. A separate 818-turn replay also produced an identical ask/recommendation
trace hash. The original slow scanner was rejected; the retained implementation
observed `41.18 ms` mean response latency and zero failures. Full evidence is in
`docs/ab0_decision_evidence.md`.

## A9 Result

A9 is rejected and reverted. The tested stability/no-partition gate regressed
the technical keep metrics: HitRate fell from `0.7625` to `0.7500`, MTTC
rose from `5.35` to `5.43125`, and technical score fell from `0.653194` to
`0.644556`. Two sessions were lost and none gained. The hash-bound reports do
not include turn-level question counts, so those are not used as a retained
claim. The final runtime preserves the pre-A9 question policy. See
`docs/a9_should_ask_evidence.md`.

## A10a Result

A10a is rejected and reverted. The candidate used full-pool partition
scores only after feature was unavailable, but HitRate fell to `0.75625`, MRR
to `0.520012`, MTTC rose to `5.3625`, and technical score fell to `0.646879`.
The current partition vocabulary covers only category/material/color/style/
use_case; uncovered attributes were implicitly treated as low value, so the
evidence is not comparable across all allowed question attributes. See
`docs/a10a_question_value_evidence.md`.

## A10b Result

A10b is retained at clean code commit `9560344`. The A-owned `QueryPlan`
separates category, hard, soft, semantic, residual, and excluded evidence while
still emitting the existing single `RetrievalRequest.query`. Rejected and
overridden values never render positive. Broader residual cleanup was not
retained and its isolated effect remains unproven, so the conservative renderer
remains retained. All Development-160 metrics, scenario
metrics, and 160 session outcomes exactly match the baseline. See
`docs/a10b_query_plan_evidence.md`.

## A11 Result

A11 is retained as a bounded deterministic slice at reviewed runtime code
commit `350cce2`, with the earlier R0 tracing fix at `b0c953d`. It adds
catalog-derived multi-word categories, clause-scoped positive/negative/
no-preference extraction, and numeric/hyphen disambiguation. It does not change
the shared A/B schema, QueryPlan residual renderer, or clarification policy.

Development-160 improved from HR `0.7625`, MRR `0.529812`, MTTC `5.35`, and
score `0.653194` to HR `0.8625`, MRR `0.545568`, MTTC `4.675`, and score
`0.721420`. All four fixed folds improved; 19 sessions were gained and three
lost. Boundary score fell by `0.057083`, while its HitRate stayed flat and MTTC
worsened by `0.625`, so Boundary quality remains a disclosed risk. The updated
offline audit has 22 misses and four primary Extraction misses.

The combined broad candidate was rejected. Feature-vocabulary, feature-expiry,
brand, and residual-cleanup components remain individually unproven because no
independent hash-bound reports were retained. See
`docs/a11_extraction_scope_evidence.md`.

## Historical AB1 through B12 Decisions

AB1 Shared Contract and Active-Route Semantics Freeze is retained at clean code
commit `a676855`. It appends truthful requested, executed, and fallback Route
fields to `RetrievalDiagnostics`; the request/query schema, Strategy weights,
ranking, and question policy remain unchanged. Development metrics, scenario
metrics, all 160 session outcomes, and all four folds exactly match A11.

The retained contract rejects unknown Route names and out-of-range requested
weights. When AB1 fields are reported, `fallback_used`, `fallback_route`, and
`executed_routes` must agree; downstream reranking preserves upstream fallback
evidence. A reranker wrapping a legacy producer keeps all appended AB1 fields
unreported on both success and fallback paths.
The contract rejects partial requested-only or executed-only reports.

Across 726 Development retrievals, lexical and structured were each requested
and executed 726 times. Dense was requested 475 times by Strategy but executed
zero times by the retained Hybrid path. All responses reported AB1 semantics,
with zero fallback Routes. See `docs/ab1_route_semantics_evidence.md`.

B8 Rejected-Constraint Ranking was implemented and measured at `f53a7ee`, then
reverted at `3952788`. Its exact, confidence-aware, capped soft penalty passed
targeted tests, but Development-160 contained zero rejected constraints across
726 retrieval turns. Metrics, scenarios, sessions, and four folds therefore
matched AB1 without exercising the variable. This failed the keep gate; see
`docs/b8_rejected_constraint_evidence.md`.

B9 Browsing-First Conditional Dense Route is retained at `7f520ba`. Relative to
AB1, HitRate@10 is unchanged, MRR improves by `0.001761`, MTTC by `0.00625`, and
TechnicalScore by `0.000654`. Only Browsing changed; three sessions improved,
one regressed, and no hit was gained or lost. Fold TechnicalScore deltas were
`+0.000238`, `0`, `0`, and `+0.002375`.

The default run observed 102 dense/fusion executions out of 725 retrieval
turns, zero fallbacks/failures, dense p95 about `5.03 ms`, and overall retrieval
p95 about `40.44 ms`. Startup rose from about `2.12 s` to `3.58 s`, and peak
RSS from about `563 MB` to `1.109 GB`. This cost is part of the keep decision,
not hidden overhead. See `docs/b9_conditional_dense_evidence.md`.

B10a Top-3 and Top-5 anchored CrossEncoder candidates are rejected. Top 3
raised HitRate by `0.0125` but lowered MRR by `0.031377` and TechnicalScore by
`0.000663`; its four folds split 2/2. Top 5 still lowered MRR by `0.023304` and
TechnicalScore by `0.001366`. The optional learned-reranker path averaged about
`68.82 ms` per executed retrieval and had a roughly `2.03 s` cold-start maximum.
Its reported `1.100 GB` RSS is parent-process-only; spawned worker and total
process-tree peak memory remain unavailable.
At `93b5b19`, the B9 default exactly reproduced all aggregate, scenario, and
session outcomes. See `docs/b10a_constraint_rerank_evidence.md`.

B10b-DS1 was later implemented as an opt-in DeepSeek Browsing Top-10 experiment.
It improved MRR and median TechnicalScore while HitRate@10, MTTC, and
Efficiency remained unchanged. It is not the retained default. B10b-DS2
Top-20 was rejected because 9 of 371 calls fell back (`2.43%`), above its
predeclared `2%` reliability gate. The commands and implementations are tracked;
the complete remote-run reports currently remain outside Git under
`/private/tmp`, so these measurements are not yet hash-bound tracked evidence.

The earlier refreshed R0 audit rejected B11's entry condition: all 22 misses
had upstream primary causes, retrieval/ranking had zero, and retained lexical
depth covered 157/160 targets. See `docs/b11_prerequisite_evidence.md`. A12
is explicitly deferred for time: `profile_weight=0.0`, profile value remains
unproven, and the Track 4 long-term-profile gap stays open. B12 is an explicit
exploratory option at `82891c8`, not a retained default: its aggregate is
favorable but no contemporaneous keep/revert gate exists and the gain is
concentrated in fold 4.
See `docs/b12_adaptive_depth_evidence.md`. Score margin remains forbidden as a
gate. The complete dependency order lives only in
`docs/optimization_roadmap.md`.

If submission is imminent, skip new behavior work and execute the delivery
track in `docs/demo_and_submission_plan.md`.

## Ownership

| Area | Owner | Non-owner |
| --- | --- | --- |
| Session state, extraction, intent, Strategy timing, clarification, response guard, `starter/agent.py` | Developer A | Developer B |
| Catalog, lexical/structured/dense retrieval, fusion, ranking, cache, retrieval diagnostics | Developer B | Developer A |
| `RetrievalRequest`, `RetrievalResult`, Strategy weight semantics | Shared and coordinated | Neither changes alone |
| Evaluator, public labels, frozen catalog | Official/read-only | Neither modifies |

## Documentation Map

| Document | Purpose |
| --- | --- |
| `README.md` | Public project entry, setup, architecture, results, limitations |
| `AGENTS.md` | Operational contract for coding agents |
| `docs/current_status.md` | Current verified state and next decision |
| `docs/project_structure.md` | Directory responsibilities, evidence layout, and archive policy |
| `docs/optimization_roadmap.md` | Project-wide optimization sequence and gates |
| `DeepSeek_LLM接入实验方案.md` | Reviewed A13 semantic-understanding plan, gates, and branch boundary |
| `docs/r0_development_failure_taxonomy.md` | Clean Development-160 failure audit and next-experiment evidence |
| `docs/a8_stateful_intent_evidence.md` | Stateful intent keep/reject evidence and tradeoff boundary |
| `docs/ab0_decision_evidence.md` | DecisionEvidence sources, fallbacks, parity, and A9 input boundary |
| `docs/a9_should_ask_evidence.md` | Rejected should-ask gate, evaluator mechanism, and A10a route consequence |
| `docs/a10a_question_value_evidence.md` | Rejected full-pool question-value candidate and incomplete partition coverage |
| `docs/a10b_query_plan_evidence.md` | Retained A-internal QueryPlan roles, parity, and A11 boundary |
| `docs/a11_extraction_scope_evidence.md` | Retained bounded extraction scope, rejected expansions, folds, and remaining risks |
| `docs/b9_conditional_dense_evidence.md` | Retained Browsing-only dense gate, quality, route truth, cost, and folds |
| `docs/b10a_constraint_rerank_evidence.md` | Rejected constraint-preserving CrossEncoder variants |
| `docs/b11_prerequisite_evidence.md` | B11 prerequisite failure and no-start decision |
| `docs/b12_adaptive_depth_evidence.md` | Exploratory adaptive depth result and default-off boundary |
| `docs/ablation_summary.md` | Human-readable keep/reject evidence |
| `docs/human_optimization_recap_zh.md` | Plain-language Chinese A1/B1-to-current recap and metric guide |
| `docs/workstreams/DEVELOPER_A_CONTROL_PLANE.md` | Standalone A-side route |
| `docs/workstreams/DEVELOPER_B_RETRIEVAL_RANKING.md` | Standalone B-side route |
| `docs/demo_and_submission_plan.md` | Demo, README, Devpost, packaging, rehearsal |
| `CONTEXT.md` | Stable shared vocabulary only |

## Remaining Track 4 Coverage Gaps

- Browsing-specific diverse dense retrieval is retained only behind the B9
  broad-Browsing gate; it is not a global route.
- CrossEncoder reranking is reproducible but rejected both globally and in the
  tested Top-3/Top-5 constraint-preserving variants.
- B10b-DS1/DS2 are implemented opt-in LLM semantic-ranker experiments with
  provisional remote measurements; neither is retained in the default runtime.
- A13 A-side semantic understanding is planned and reviewed, not implemented.
- Profile ranking remains disabled at weight `0.0`; long-term profile value has
  not been demonstrated.
- Candidate-aware clarification exists, but a complete should-ask gate has not
  yet been retained.

These are explicit gaps, not implied capabilities. If an experiment is rejected
again, preserve the measured result and disclose the literal coverage gap.

## Safe Verification Commands

Default runtime tests:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Ordinary Development-160 evaluation:

```bash
.venv/bin/python -m experiments.evaluation_reporting \
  --split development --structured-filter \
  --output /private/tmp/shopping-copilot-development.json
```

Do not run `--split full` or `--split holdout` during optimization.

## End-of-Session Handoff

Every implementation session should leave this concise status in its final
response or an updated workstream section:

```text
Branch and commit:
Experiment ID:
Hypothesis:
Files changed:
Tests:
Development folds/results:
Scenario gains/regressions:
Latency/memory/fallback impact:
Keep/revert decision:
Shared-contract changes:
Known risks:
Next smallest step:
```
