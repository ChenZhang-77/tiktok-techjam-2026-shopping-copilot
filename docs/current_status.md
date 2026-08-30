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
6. `docs/question_policy_optimization_plan.md` when the selected work is A14.
7. `docs/a13_ai_silver_protocol.md` when the selected work is
   A13-AS0/AS1F/AS1J/AS2.
8. The files named by the selected experiment.

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

The retained B12 checkpoint was verified on 2026-08-28. A13-0 bound the current
baseline and refreshed taxonomy on 2026-08-29. A13-1 then tested and rejected a
deterministic State / Override candidate. A14-0 was retained on 2026-08-30 as a
behavior-identical Question Policy Module and turn-audit slice:

| Item | Value |
| --- | --- |
| Branch at B12 verification | `b/b12-adaptive-depth` |
| Retained default behavior commit | `7f520ba` |
| Optional B12 code/default-parity commit | `82891c8` |
| B10a experiment branch | `b/b10a-constraint-preserving-crossencoder` |
| Current A13 publication branch | `llm`, cut from reviewed A13 HEAD `bbb0075` |
| A14-0 runtime source commit | `f594601`; exact visible-response parity to legacy `2e4108a` across 649 Development turns |
| A14-1 runtime/audit source commit | `b238c68`; closed Question Policy diagnostics, retained fallback semantics, and ten closed-schema attribute-evidence records per turn with the same visible response |
| Latest local full test suite (2026-08-30) | 407 passed after reviewed A13-AS0 core contracts; default runtime remains no-LLM |
| Committed annotation bundle | `A13_annotation_pack_v1.zip`, SHA256 `8eb3379c730df8ee1a536b1ccfcb198bc456198ee280dea82c2100fc9cd0658b` |
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
The A13-0 rerun is retained as hash-bound tracked evidence in
`docs/a13_0_reports/development.json`.

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

The current hash-bound `0.925` audit assigns the 12 Development misses to:

1. Question Policy: 10;
2. State / Override: 2;
3. Extraction, Intent / Routing, and Retrieval / Ranking: 0 primary misses.

The audit is bound to clean comparator `b86a9e7`, the verified catalog/split/
evaluator/fold hashes, four rerun folds, and a target-free miss summary in
`docs/a13_0_baseline_evidence.md`. The generator no longer emits a stage ID:
schema `r0-v3` reports the dominant investigation class and delegates current
experiment selection to `docs/optimization_roadmap.md`. Historical R0/A9
artifacts remain unchanged; A9 is already measured, rejected, and reverted.

The remaining work is A-owned and ordered:

1. preserve the rejected-and-reverted A13-1 State / Override result;
2. run A13-S0 Shadow only against the restored `0.925` comparator;
3. activate only a trigger class that passes the reviewed Shadow gate;
4. address Question Policy later as a separate A14 experiment.

The authoritative A13 plan is
[`DeepSeek_LLM接入实验方案.md`](../DeepSeek_LLM接入实验方案.md). It does not claim
provider activation, real-model evidence, or retained LLM runtime behavior.

A14 planning is now reviewed and documented in
[`docs/question_policy_optimization_plan.md`](question_policy_optimization_plan.md).
Evidence-only audit, Interface, and parity preparation may proceed while A13 is
gated, but an A14 behavior Candidate must remain separate from A13/B10b metric
activation. The first recommended Candidate changes attribute selection only;
it does not revive a broad should-stop rule or let an LLM control the policy.

## Current A13 Decision

`a/a13-llm-semantic-understanding` starts from Chen baseline `0bd3375`.
DeepSeek is planned as an A-owned, evidence-gated semantic interpreter before
state mutation, not as a second Agent and not as a replacement for the existing
deterministic parser.

A13-0 is complete at clean comparator `b86a9e7`; it reproduced Development-160
and all four folds, bound the input/evaluator hashes, refreshed the 12-miss
taxonomy, and changed no Agent behavior. See
`docs/a13_0_baseline_evidence.md`. A13-1 cleared the active-state half of the
stale-value issue but failed the QueryPlan-positive-role half on `public_0002`;
it also lost three Development hits and regressed TechnicalScore on all four
folds, so it was rejected and explicitly reverted. See
`docs/a13_1_state_override_evidence.md`. The A13-S0 offline foundation now has
types, fake, validator, six-signal gate, safe diagnostics, bounded vocabulary,
and disabled/no-key/fake Development parity. See
`docs/a13_s0_offline_evidence.md`. It has no DeepSeek transport; no API call or
key read has been made for A13.

The offline Shadow foundation records a validated fake `UnderstandingDelta`
without changing SessionState, Strategy, QueryPlan, clarification,
recommendations, or public output. The coordinator has selected a no-human
AI-silver route. Its authoritative protocol is
[`docs/a13_ai_silver_protocol.md`](a13_ai_silver_protocol.md). A13-AS0T core
contract tests now pass: the source-neutral applied-state comparator, Candidate
request config, schemas/prompts, contamination checks, role-independence
preflight, consensus, and fixed-denominator KPI calculator are hash-bound in
[`docs/a13_as0_offline_tooling_evidence.md`](a13_as0_offline_tooling_evidence.md).
The exact independent role manifest remains intentionally invalid/pending;
AS0X execution, isolated repair, and request/response provenance are not yet
implemented. This is not a completed execution toolchain, so
AI-silver is not frozen, reference-builder/Candidate provider calls are not
authorized, and A13-C1 is not open. Candidate activation still
requires exact fallback, bounded call rate/latency/cost, focused/full tests,
and fixed Development-fold evidence.

A teammate-ready but unlabeled 60-item package now lives at
`experiments/fixtures/a13_annotation_pack_v1/`; it includes the shared items,
generated double-click offline annotation UI, a clearer double-click example
guide, blank per-annotator template, schema, standalone validator, and a
post-submission disagreement comparison command. Its status is annotation-ready,
not gold or AI-silver-frozen, so it grants no provider authorization. All five
runtime-reachable semantic strata are replayed against the bound catalog during
the build; the defensive but Agent-unreachable intent-transition invariant stays
unit-test-only rather than being represented by fabricated empty evidence.
The exact teammate-facing build is committed at repository root as
[`A13_annotation_pack_v1.zip`](../A13_annotation_pack_v1.zip), with the bound
SHA256 recorded in the checkpoint table above.

Two returned annotation files were preflighted on 2026-08-30. The `codex`
file passes 60/60 validation but does not establish a second member's human
provenance. The Zhangchen file covers 60/60 rows but has 26 validation failures,
so the official comparison cannot yet run. No source annotation was rewritten;
the exact failure classes, hashes, raw preflight agreement, and repair sequence
are recorded in `docs/a13_annotation_intake_review.md`. Under the selected
no-human route, the legacy 60 items and both returned files remain L0/L1
historical diagnostics and are excluded from the AI-silver semantic gate.
Reference-builder provider work remains unauthorized, and A14-S1 remains
blocked on the A13 disposition.

The coordinator subsequently authorized provisional use of the 34 individually
valid Zhangchen rows while ignoring the 26 invalid rows. A local, untracked
`provisional_valid34_comparison.json` now records 16 agreements, 18
disagreements, the 26 exclusions, source hashes, and an explicit `not_gold`
boundary. It has only 1/10 valid
`override_without_value` and 4/20 valid `low_confidence_residual_feature` rows;
it cannot satisfy reference coverage, semantic selection, provider, A13-C1, or
A14-S1 gates. It may remain a diagnostic but cannot be copied into or used to
tune the new AI-silver reference. See `docs/a13_annotation_intake_review.md`
for the artifact hash and exact permitted uses.

An AI-only adjudication draft now accompanies that local subset: 16 exact
agreements were carried forward, 17 disagreements received a `codex`-label
recommendation, and `LRF-011` received one synthesized recommendation. All 34
draft labels pass row-level validation, but all 18 disagreements remain marked
human-pending. The draft is only a review accelerator; it does not resolve
semantic truth, create gold/AI-silver, or authorize comparator/LLM selection
claims. The no-human route supersedes further human adjudication as the active
next step without upgrading these old labels.

A clean-commit (`c556231`) deterministic dry-run against those 34 AI-provisional
labels is now hash-bound in the same coordinator-local directory. It records
13/34 complete-label exact matches and 16/34 invalid predictions: nine
positive/rejected conflicts, six unnormalized values, and one closed-vocabulary
violation. `MCS` is 10/10 exact while `PRC` is 0/10 with ten invalid outputs;
positive-constraint field exact is only 15/34. These are failure-localization
diagnostics, not accuracy evidence: the subset is unbalanced and its pending AI
labels are not independent human gold. Applied-state replay leaves zero
active/rejected same-value conflicts, so the nine raw PRC conflicts do not prove
that final runtime state is invalid. This historical check exposed the raw
Shadow versus applied-state seam; the AS0 protocol now predeclares the latter
without selecting it by valid-34 score. Exact hashes and boundaries are in
`docs/a13_annotation_intake_review.md`.

A13-AS0T now freezes `applied_state_delta_v1` as the primary semantic
comparison unit: deterministic, Candidate, and AI-silver deltas are applied to
the same isolated prior state. Raw `UnderstandingDelta` exact remains a trigger
diagnostic. The Candidate config and fresh-fixture rules are frozen; AS0R must
still bind exact identities and hashes for the independent generator, semantic
duplicate auditor, three blind judges, and adjudicator; AS0X must then validate
the execution/repair/provenance runner before any new evaluation item or
reference output is viewed. The exposed legacy 60 items
cannot score the semantic gate. AS1F/AS1J/AS2 require separate explicit
authorization for reference-builder provider calls; the Candidate model/version
cannot generate, label, or adjudicate. AI-silver agreement uses fixed all-item
denominators and may open Candidate Shadow, but only fixed Development-160/fold
evidence may retain runtime behavior.

A13 does not replace B10b-DS1. A13 interprets difficult user language before
retrieval; B10b-DS1 reranks an existing Browsing Top-10 after retrieval. They
must not be activated together in one metric experiment, and the default
runtime remains no-LLM.

## Current A14 Decision

The reviewed Question Policy direction is not another hand-tuned should-ask
threshold. The evaluator scores recommendations before generating its next
reply, and a no-ask miss yields no new product preference; A9 therefore gives
no basis for making broad early stopping the first A14 hypothesis. A10a also
showed that partial Candidate partition evidence cannot be compared globally
when feature, size, brand, budget, and other are uncovered.

A14 will deepen clarification into one A-owned `Question Policy` Module called
once after retrieval and before `response_guard`. The Module owns the same-
snapshot Decision Evidence, eligibility, per-attribute evidence status,
selection cascade, fallback, rendering, diagnostics, and optional advisor
handling. It does not change `RetrievalRequest`, `RetrievalResult`, Strategy
weights, B route semantics, or state mutation ordering.

The reviewed order is:

```text
A14-0 turn audit and deep-Module parity
  -> A14-1 complete attribute-evidence status
      -> A14-S1 deterministic selection Shadow
          -> A14-C1 selection-only Candidate
              -> optional catalog-only policy
              -> optional offline LLM teacher Shadow/No-Go
              -> optional online LLM advisor and stop slices
```

The first behavior Candidate preserves the current ask opportunity and changes
only which legal attribute is selected. Unsupported evidence uses an explicit
legacy fallback; missing evidence is never converted to zero Question Value.
An optional offline LLM teacher may later cluster a frozen, hash-bound catalog
phrase fixture, but it has no direct runtime path. A separate online advisor
may only rerank an eligible shortlist from bounded aggregate evidence in one
reviewed bucket. Neither can stop, create an attribute, mutate state, or bypass
deterministic fallback. Full design, diagnostics, experiment gates, and
alternatives are in `docs/question_policy_optimization_plan.md`.

A14-0 is now retained at runtime source commit `f594601`. The clean legacy
comparator at `2e4108a` and current implementation produced exactly the same
649 Development-turn public messages, `ask_attribute` values, and
recommendation lists; their common visible-response trace SHA256 is
`098afbdf9b1ce3c0813ccb311b90432837e8b3ac7f36ed78248fe2fef3a75146`.
Development and all four fixed folds reproduce the existing metrics, with zero
response exceptions, invalid payloads, or fallbacks. The policy trace records
587 asks, 62 stops, zero policy violations, and p95 local policy latency
`4.653 ms`. See `docs/a14_0_question_policy_evidence.md`.

A14-1 is now retained at final runtime/audit source commit `b238c68`. All ten allowed
attributes have explicit evidence source, lifecycle, range, status,
comparability, answerability/actionability, eligibility, and missing-data
behavior. The fixed Development audit finds bounded comparable evidence for
category/material/color/style/use_case, uncalibrated feature text, unavailable
field-tagged size/brand/budget evidence, and a not-applicable `other`
partition. The 649-turn visible trace and all Development/fold metrics remain
exactly unchanged; see `docs/a14_1_attribute_evidence.md`.

This reaches the farthest safe automatic boundary while A13 remains open.
A14-S1, A14-C1, LLM teacher/advisor work, and ask/stop changes remain blocked
until A13's AI-silver review has a recorded disposition.

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
| `docs/question_policy_optimization_plan.md` | Authoritative A14 Question Policy Module, evidence, LLM role, and experiment slices |
| `DeepSeek_LLM接入实验方案.md` | Reviewed A13 semantic-understanding plan, gates, and branch boundary |
| `docs/r0_development_failure_taxonomy.md` | Clean Development-160 failure audit and next-experiment evidence |
| `docs/a8_stateful_intent_evidence.md` | Stateful intent keep/reject evidence and tradeoff boundary |
| `docs/ab0_decision_evidence.md` | DecisionEvidence sources, fallbacks, parity, and A9 input boundary |
| `docs/a9_should_ask_evidence.md` | Rejected should-ask gate, evaluator mechanism, and A10a route consequence |
| `docs/a10a_question_value_evidence.md` | Rejected full-pool question-value candidate and incomplete partition coverage |
| `docs/a10b_query_plan_evidence.md` | Retained A-internal QueryPlan roles, parity, and A11 boundary |
| `docs/a11_extraction_scope_evidence.md` | Retained bounded extraction scope, rejected expansions, folds, and remaining risks |
| `docs/a13_0_baseline_evidence.md` | Current 0.925 comparator, hashes, folds, and refreshed target-free taxonomy |
| `docs/a13_1_state_override_evidence.md` | Rejected-and-reverted deterministic state-reset candidate, folds, and restored comparator |
| `docs/a13_s0_offline_evidence.md` | Retained offline Shadow foundation, Development parity, and the historical pre-provider gate at that checkpoint |
| `docs/a13_ai_silver_protocol.md` | Active no-human A13 reference protocol, comparator seam, KPI hierarchy, contamination controls, and provider boundaries |
| `docs/a13_as0_offline_tooling_evidence.md` | Hash-bound AS0 core contracts and pending exact-role/execution-runner blockers |
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
- A13-0 is complete, A13-1 is rejected/reverted, and the A13-S0 offline Shadow
  foundation passes parity. AS0 core contracts are hash-bound, but exact
  independent roles and the execution/repair/provenance runner are pending;
  no frozen AI-silver or real
  semantic-quality evidence exists, and
  reference-builder/Candidate provider calls remain unauthorized. The exposed
  legacy 60 items cannot score the semantic gate.
- Profile ranking remains disabled at weight `0.0`; long-term profile value has
  not been demonstrated.
- Candidate-aware clarification runs through the retained A14-0 deep Interface,
  and A14-1 retains complete explicit ten-attribute evidence with exact legacy
  behavior. Deterministic selection Shadow and a should-ask gate have not yet
  been retained and are blocked on the A13 disposition.

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
