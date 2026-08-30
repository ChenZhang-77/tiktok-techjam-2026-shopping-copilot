# Developer A Optimization Route - Control Plane

> Release freeze (2026-08-31): [final plan](../final_release_plan.md) and
> [current status](../current_status.md) supersede historical “next steps” below.
> No automatic A13/A14/model/parameter work. This branch's only current track is
> source validation, documentation/publication, then separately verified packaging.

## Purpose

This is the standalone route for a fresh Codex conversation working on the
Agent / Control Plane. It describes current responsibilities and blockers, not
permission to implement every item.

Developer A's question is:

```text
What is still true about the customer's intent?
  -> Should the current route change?
  -> What evidence should retrieval receive?
  -> Are recommendations focused enough?
  -> If not, which one question is worth another turn?
```

## New-Conversation Startup

Read, in order:

1. `AGENTS.md`
2. `docs/current_status.md`
3. `docs/optimization_roadmap.md`
4. this document
5. [`DeepSeek_LLM接入实验方案.md`](../../DeepSeek_LLM接入实验方案.md) when the
   selected experiment is A13
6. [`docs/a13_ai_silver_protocol.md`](../a13_ai_silver_protocol.md) when the
   selected experiment is A13-AS0/AS1F/AS1J/AS2
7. [`docs/question_policy_optimization_plan.md`](../question_policy_optimization_plan.md)
   when the selected experiment is A14
8. `starter/agent.py`
9. `starter/core/state.py`
10. `starter/core/context_engine.py`
11. `starter/core/planner.py`
12. `starter/core/query_builder.py`
13. `starter/core/clarification.py`
14. `starter/core/decision_evidence.py` when the selected experiment is A14
15. `starter/core/response_guard.py`
16. `starter/contracts.py`
17. the focused tests named by the selected experiment

Then report:

```text
Branch and HEAD:
Working tree:
Selected A experiment:
Diagnosed failure class:
Expected files:
B-side dependency or contract impact:
Focused tests:
Development-only evaluation:
```

Do not edit code when the user asks only for a review, diagnosis, or plan.

## Current Integrated State

Latest coordinator decision: local/no-external-LLM Plan One is primary; all
hosted LLM work is optional Plan Two. The single bounded
[B10b-F2 follow-up](../b10b_paired_verification.md) does not activate A13 or
change A-side state/question semantics. Return to low-risk Plan One review
and delivery after its disposition; do not start another LLM tuning cycle.

Latest separate test (2026-08-31): [A13-F1](../a13_semantic_score_test.md)
completed the user's post-reranking semantic comparison. Real Shadow has exact
160-session/649-turn parity, 67 calls and no API failures, but its 60 valid
returns (89.55%) fail the 95% gate. No Candidate was run; stop this recipe and
leave defaults unchanged. This deadline authorization does not pass the formal
AI-silver gates below. Its then-recommended B10b-F1 follow-up is now the bounded
F2 check above, not an extension of annotation/reference infrastructure.

Deadline update (2026-08-31): [A13-LR0](../a13_light_review.md) is complete;
only the cheap offline editor is retained. A13 runtime and multi-family
reference building are deferred, satisfying the disposition needed to start
the separate [A14 deadline pilot](../a14_deadline_selection.md). Read its
current result before the older pending-A13 flow below. The pilot must compare
the real B9 default, not confuse the previous structured-only A-side audit
with default-route evidence. No default activation is implied.

The integrated checkout and verified metrics are in `docs/current_status.md`.
The current Control Plane already provides:

- isolated SessionState objects,
- raw/audited conversation history,
- active, overridden, rejected, and no-preference state,
- common category/material/color/size/style/brand/budget/feature/use-case
  extraction,
- Intent Override and category-level context reset,
- Buying/Browsing Strategy generation,
- active-state query distillation,
- non-repeating clarification with Candidate evidence,
- public response guard,
- Control Plane diagnostics,
- the stable `RetrievalRequest`/`RetrievalResult` seam.

The next phase does not rebuild these capabilities. It targets decision quality
and private-set robustness.

A8 Stateful Intent Persistence is retained at `83a6bcd`. AB0 DecisionEvidence
Availability is retained at `3988b8b`; it defines every proposed signal and
fallback without changing ask behavior or the shared contract. A9 Should-Ask
Over-Generality Gate was tested, rejected, and reverted because it worsened
HitRate/MTTC. A10a Candidate Question Value was subsequently tested, rejected,
and reverted because its partial-evidence post-feature ranking regressed every
main metric. A10b was then retained at `9560344` with exact Development session
parity and no shared schema change. A11 was retained as a bounded deterministic
slice at `350cce2`: Development score rose to `0.721420` and all four folds
improved, without a shared schema or question-policy change. AB1 and B9 are now
complete. Chen's later A-side corrections define the selected A13 comparator;
read `../current_status.md` for its current metrics and audit caveats.

The planning-only refresh assigns the remaining misses to Question Policy and
State / Override, not Extraction or Intent / Routing. A13 remains gated before
provider activation. A14 planning and evidence-only preparation are now
reviewed and may proceed without changing behavior; A14 Candidate behavior must
remain separate from an active A13/B10b metric experiment. The authoritative
A14 total plan is `docs/question_policy_optimization_plan.md`.
The retained A8 confidence is an A-owned ordinal stability signal with
`low`/`medium`/`high` diagnostic bands, not a calibrated probability or B-side
gate.

## Ownership

Developer A owns:

- `starter/agent.py` orchestration,
- `starter/core/state.py`,
- `starter/core/context_engine.py`,
- `starter/core/planner.py`,
- `starter/core/query_builder.py`,
- `starter/core/clarification.py`,
- `starter/core/response_guard.py`,
- `starter/core/diagnostics.py`,
- Control Plane tests,
- when and why per-turn Strategy values change.

Developer A does not own:

- catalog loading or indexing,
- BM25/FTS internals,
- structured/dense/fusion mechanics,
- ranking score implementation,
- B-owned retrieval/ranking semantic model or cache execution,
- retrieval latency/cache optimization.

Developer A may use Retriever fixtures. Do not build a second retrieval stack
inside Control Plane files.

## Shared Contract

Current public seam:

```text
Retriever.retrieve(request: RetrievalRequest) -> RetrievalResult
```

Developer A constructs `RetrievalRequest` with:

- `session_id`, `turn`, `top_k`,
- distilled query,
- current intent,
- Strategy,
- active constraints,
- no-preference attributes,
- rejected constraints,
- asked attributes.

Do not send SessionState itself or any evaluator-only label. Consume Candidate
and RetrievalDiagnostics without importing B implementation internals.

Before changing the contract or Strategy semantics:

1. state why the existing fields cannot support the experiment,
2. notify Developer B,
3. add contract tests,
4. keep changes backward-compatible when possible,
5. update the B workstream and `docs/current_status.md`,
6. never change route-weight meaning unilaterally.

## Diagnosed A-Side Bottlenecks

### 1. Current-utterance intent instability

`Agent.respond` replaces `state.intent` with an inference based on the current
message and current extraction. A normal clarification reply with one soft
constraint can move a previously specific Buying session back to Browsing.

### 2. Clarification has no complete should-ask gate

The current policy normally asks whenever an attribute is available. It does
not first decide whether recommendations are sufficiently concentrated.

The rejected A9 result shows that a broad concentration/stability stop gate is
not the right first follow-up under the current evaluator. A14 first audits
turns and improves attribute selection while preserving the ask opportunity;
product-oriented stopping is a later, separately measured slice.

### 3. `feature` is selected before candidate partition evidence

Candidate-aware scoring exists, but `feature` is normally preferred before the
candidate-value calculation. This can overfit the public simulator's high
feature availability.

The earlier A10a candidate also proved that partial partition maps cannot rank
all allowed attributes: unavailable feature/size/brand/budget/other evidence
must not be interpreted as zero Question Value.

### 4. Rule and scope limitations

Extraction still uses bounded vocabulary and regexes, but the current planning
audit reports no primary Extraction miss. Broader parser work therefore
requires new evidence and must not globally replace the deterministic path.

### 5. Query evidence is flattened into one string

Exact constraints, semantic phrases, current wording, and negative evidence are
not represented as separate conceptual components.

### 6. Previous diagnostics are recorded more than used

Candidate stability, filter relaxation, route failure, and repeated uncertainty
do not yet drive a complete next-turn policy.

The full `RetrievalResult` exists immediately after retrieval, but
`starter/agent.py` currently reduces it to public recommendations and Top-K
text evidence before clarification. Therefore A9 does not yet have the complete
decision input named below.

## Blocking Order

The authoritative whole-project order is `../optimization_roadmap.md`. Within
the A workstream, the current local blockers are:

```text
Historical A8 -> AB0 -> A9 -> A10a -> A10b -> A11 -> AB1

Current 0bd3375 baseline
  -> A13-0 current baseline and R0 binding complete
      -> A13-1 deterministic State / Override slice rejected and reverted
          -> A13-S0 offline Shadow foundation complete
              -> A13-AS0T/AS0R/AS0X core-contract/role/runner gates
                  -> A13-AS1F fresh fixture build and hash freeze
                      -> A13-AS1J/AS2 blind AI-silver build and review
                          -> A13-S1 Candidate provider Shadow
                              -> A13-C1 guarded activation or No-Go

A13 disposition
  -> A14-0 turn audit and deep-Module parity
      -> A14-1 complete attribute-evidence status
          -> A14-S1 deterministic selection Shadow
              -> A14-C1 selection-only Candidate
                  -> optional synthetic/LLM/stop slices
```

AB1 passed at `a676855`; its shared diagnostics preserve the A-owned Strategy
request while exposing B-owned execution and fallback. A12 remains deferred
with `profile_weight=0.0`. A13 does not change the shared RetrievalRequest or
route-weight semantics in its first stages.

A14 design and zero-behavior audit preparation do not require provider access
or a shared contract change. Do not activate an A14 Candidate before the active
A13 review decision, and do not combine A14 selection, stop, LLM, profile,
query, or retrieval changes in one experiment.

## A8 - Stateful Intent Persistence

### Hypothesis

Intent hysteresis based on previous intent, accumulated constraints, explicit
exploration language, and override events will improve Buying and Intent
Override without damaging Browsing.

### Desired behavior

- A clarification reply does not flip intent by default.
- Browsing becomes Buying only when concrete evidence accumulates.
- Buying becomes Browsing only on explicit relaxation/exploration evidence.
- Override triggers re-evaluation and an explainable reason.
- `Strategy.reason` records why intent was kept or changed.

Freeze an `IntentAssessment` before changing inference:

```text
intent: buying | browsing
confidence: calibrated bounded value or declared ordinal band
evidence: conversation-derived reasons only
source_turn: last turn that materially changed the assessment
transition_reason: retained | accumulated | relaxed | explicit override
```

Because the result affects later turns, persist the assessment or the complete
evidence needed to derive it deterministically. A current-turn-only confidence
value is not acceptable. Keep raw confidence A-owned; expose only a coordinated
Strategy/gate to B unless a measured consumer requires a shared field.

### Expected files

- `starter/core/context_engine.py`
- `starter/core/state.py`
- `starter/core/planner.py` only if Strategy consumes confidence
- `starter/agent.py` orchestration wiring
- `tests/test_context_engine.py`
- `tests/test_state.py`
- `tests/test_planner.py`
- `tests/test_agent_smoke.py`

### Required tests

- Buying remains Buying after one soft clarification answer.
- Browsing becomes Buying after sufficient specific constraints.
- Explicit exploration can keep/restore Browsing.
- Override removes stale context and re-evaluates intent.
- State and diagnostics contain no evaluator labels.
- Buying/Browsing still execute observably different Strategies.

### Keep gate

- Route behavior is more stable and explainable.
- Development folds support the overall/scenario tradeoff.
- Buying or Intent Override improves without a material Browsing regression.
- No public-simulator sample or target-specific logic is introduced.

### Revert gate

- Intent becomes sticky and ignores real customer changes.
- Fold evidence is unstable.
- Browsing recall/efficiency materially regresses.
- The solution requires sample-specific exceptions.

## AB0 - DecisionEvidence Availability

### Goal

Make A9 executable without inventing inputs or prematurely changing the shared
contract. AB0 changes evidence plumbing only; it does not change whether the
Agent asks.

### Source audit

| Candidate signal | First source to test | Ownership |
| --- | --- | --- |
| pool size | full `RetrievalResult.candidates` / existing `candidate_count` | B meaning, A adapter |
| top-score margin | Candidate scores only after range and missing-score behavior are verified | shared definition if retained |
| constraint coverage | existing Candidate evidence/diagnostics when comparable across products | B-produced, A-consumed |
| Candidate stability | current versus `SessionState.previous_candidate_ids` Top-K overlap | A |
| attribute partitions | full Candidate evidence, not only recommendation text | B evidence, A question policy |
| relaxation/degraded mode | existing `RetrievalDiagnostics` | B |
| turn and exhausted attributes | `SessionState` | A |

Prefer an A-side `DecisionEvidence` adapter built from the existing
`RetrievalResult` and state. Extend `RetrievalDiagnostics` only when B must
compute a missing value or own its semantics. Never add target rank, hit/miss,
scenario label, or evaluator timing.

### Completion gate

- every proposed A9 field has a producer, type, range, lifecycle, and fallback;
- the full Candidate evidence reaches the decision point without leaking into
  the public response unnecessarily;
- current versus previous Candidate IDs have an explicit Top-K/depth meaning;
- contract and leakage tests pass when any shared field changes;
- ask/no-ask behavior is unchanged.

## A9 - Should-Ask Over-Generality Gate

**Disposition: rejected and reverted.** Candidate `30765cd` failed the overall
Development gate. The current runtime retains the pre-A9 question policy. Any
future variant must retain a hash-bound turn audit before making question-count
claims. Full evidence: `docs/a9_should_ask_evidence.md`.

### Hypothesis

Separating "should ask" from "what to ask" will reduce wasted turns and MTTC
while preserving early-hit opportunity.

### Candidate evidence

Use only non-label information such as:

- Candidate Pool size,
- top-score/rank margin when calibrated,
- active-constraint coverage,
- Candidate stability across turns,
- attribute partition availability,
- turn number,
- no-preference/exhausted attributes,
- filter relaxation or degraded mode.

Use only the AB0 fields that pass their availability and calibration checks.
Do not turn every possible signal into a required input.

### Desired behavior

- Return recommendations even when asking.
- Ask only when the pool is genuinely broad/low-confidence and a useful
  attribute exists.
- Allow `ask_attribute=None` before turn 10 when another question has low value.
- Never repeat an asked or no-preference attribute.
- Record a short reason for ask/no-ask.

### Expected files

- `starter/core/clarification.py`
- `starter/agent.py`
- `starter/core/diagnostics.py`
- an A-owned decision-evidence module or adapter
- `starter/contracts.py` only if AB0 proves B must add a shared field
- `tests/test_clarification.py`
- `tests/test_agent_smoke.py`

### Required tests

- concentrated candidates produce no question,
- broad candidates with useful partitions produce one question,
- no useful partition produces no question or safe `other`,
- final turn never asks,
- recommendation output remains valid,
- no-preference and previously asked attributes stay unavailable.

### Keep gate

- MTTC/Efficiency improves on stable development folds,
- HitRate does not materially fall from lost clarification information,
- question count and repeated/no-value questions fall,
- behavior is based on Candidate evidence, not public sample availability.

## A10a - Candidate Question Value

**Disposition: rejected and reverted.** Candidate `304a3d6` preserved
feature-first behavior and only replaced the later Top-K partition ranking with
full-pool scores. Uncovered size/brand/budget/other attributes could not compete
with any positively scored supported attribute, so the candidate retained a
missing-as-low confound and regressed HitRate, MRR, MTTC, Efficiency, and score.
Bounded A11 did not supply comparable partition evidence. Revisit only if AB1
supplies it and defines how an uncovered attribute preserves legacy priority. Full record:
`docs/a10a_question_value_evidence.md`.

### Hypothesis

Ranking attributes by candidate coverage, value diversity, and expected pool
reduction will generalize better than unconditional `feature` priority.

Conceptual score:

```text
QuestionValue(attribute)
  = candidate coverage
  * value diversity
  * expected pool reduction
  * answer usefulness prior
  - asked/no-preference/exhaustion penalty
```

The answer-usefulness prior must not be a hardcoded public-sample table.

### Keep gate

- Candidate questions are explainable from current evidence.
- MTTC improves without recall loss.
- Question selection changes without also changing query construction.

## A10b - Internal QueryPlan

**Disposition: retained at `9560344`.** Category, hard, soft, semantic,
residual, and excluded evidence are explicit A-side roles. The plan still
renders one `RetrievalRequest.query`; all 160 Development outcomes match the
baseline. Residual text stays intact unless exact active/excluded phrases can be
removed, because broader cleanup belongs to A11. Full record:
`docs/a10b_query_plan_evidence.md`.

### Hypothesis

Separating query evidence by role will make query construction auditable and
reduce stale, duplicated, or incorrectly positive terms without changing the
shared request schema.

For query distillation, preserve conceptual components:

```text
category/exact terms
active hard terms
active soft terms
semantic feature/use-case phrase
rejected/overridden terms
```

In A10b these components are an A-owned, auditable `QueryPlan` that produces the
existing single `RetrievalRequest.query` string. No shared schema change is
expected.

Create A10c only if a measured B experiment must consume components separately.
A10c still requires a separate A/B agreement even though AB1 now freezes Route
diagnostics and fallback semantics. Developer A must not add typed components to
`RetrievalRequest` unilaterally.

Broader residual cleanup was not retained, and its isolated effect remains
unproven because no independent hash-bound report exists. Preserve the A10b
conservative residual renderer; exact rejected/overridden values must still
never become positive FTS terms.

### Keep gate

- Query traces exclude stale, rejected, duplicated, and excessive low-confidence
  phrases.
- Retrieval quality improves or remains stable without changing question policy.

## A11 - Extraction and Scope Hardening

**Status: retained as a bounded slice at `350cce2`.** The retained behavior is
catalog-derived multi-word category extraction, clause/list-scoped positive/
negative/no-preference evidence, numeric/hyphen disambiguation, and injected
catalog-path consistency. It gained 19 Development sessions, lost three,
improved all four fixed-fold technical scores, and raised overall score from
`0.653194` to `0.721420`.

The combined broad candidate was rejected during ablation. Catalog feature,
feature-expiry, brand, and QueryPlan residual-cleanup components lack
independent hash-bound reports, so their individual effects remain unproven.
Do not resurrect those behaviors without a new isolated experiment. Boundary
technical score fell by `0.057083`; preserve this risk in handoffs. Full
evidence: `docs/a11_extraction_scope_evidence.md`.

Prioritize R0-supported failures:

- catalog-derived category and brand vocabulary,
- multi-word values and normalized synonyms,
- clause-scoped no-preference and negation,
- `avoid`, `without`, `anything but`, and mixed positive/negative clauses,
- budget/size/model-number ambiguity,
- override scope and replacement attributes,
- bounded lifetime/length for low-confidence feature phrases.

Use deterministic changes first. A lightweight model parser is optional only
for low-confidence input and must have token/cost accounting, timeout, and the
existing deterministic fallback. It must win development cross-validation.

## A12 - Profile Ablation

**Status: deferred for time.** Further A-side optimization was paused before an
ablation was run. Keep `profile_weight=0.0`; profile value remains unproven and
the Track 4 long-term-profile gap remains open. This is a disposition, not a
positive or negative experiment result.

The profile is a weak anonymized prior, not a user identity or hard constraint.

Rules:

- run only after A8-AB1,
- use a small soft signal only in vague/low-constraint Browsing,
- explicit current intent always wins,
- override never resurrects a profile preference as active intent,
- report a direct `profile_weight=0.0` comparison,
- retain zero when fold evidence is weak.

Before R4, record one explicit A12 disposition: retained, rejected with evidence,
or deferred for time with the profile gap still open.

Do not claim cross-session long-term memory; the evaluator supplies isolated
sessions without stable identity.

## Required Invariants Across All A Work

- one isolated state per `session_id`,
- provenance/source turn preserved,
- inactive/rejected values excluded from positive query,
- category override clears conflicting product context,
- no-preference attributes are not asked again,
- valid recommendations can accompany clarification,
- Agent output stays schema-valid under B failure,
- no target/ground-truth/scenario/evaluator data crosses the seam,
- current explicit intent outranks profile evidence,
- all behavior is deterministic unless stochasticity is explicitly measured.

## Evaluation

Focused tests depend on the experiment. Before keeping a slice:

```bash
.venv/bin/python -m unittest \
  tests.test_state \
  tests.test_context_engine \
  tests.test_planner \
  tests.test_query_builder \
  tests.test_clarification \
  tests.test_response_guard \
  tests.test_agent_smoke -v

.venv/bin/python -m unittest discover -s tests -v
```

Evaluate only Development-160 and its fixed folds. Report:

- overall score,
- four scenario scores,
- intent switch count/reasons,
- question count and useful-question proxy,
- repeated/no-preference violations,
- gained/lost sessions,
- latency/fallback impact.

Do not run Full/Holdout.

## A13 - Guarded LLM Semantic Understanding

**Status: A13-0 complete; A13-1 rejected and reverted; A13-S0 offline foundation passes parity; A13-AS0T core contracts pass; exact roles, execution runner and provider work remain gated.** The authoritative spec,
phase order, interface, trigger conditions, safety invariants, latency/cost
targets, and keep/revert gates are in
[`DeepSeek_LLM接入实验方案.md`](../../DeepSeek_LLM接入实验方案.md).
The reference-building protocol, comparator seam, KPI hierarchy, contamination
controls, and separate reference-builder/Candidate authorizations are in
[`docs/a13_ai_silver_protocol.md`](../a13_ai_silver_protocol.md).

A13 is not permission to replace the deterministic parser. The required order
is:

```text
A13-0 complete at clean comparator b86a9e7
  -> A13-1 deterministic State / Override slice rejected and reverted
      -> A13-S0 offline Shadow foundation complete
          -> A13-AS0T core comparator/config/schema tests pass
              -> A13-AS0R exact independent role manifest pending
                  -> A13-AS0X execution/repair/provenance runner pending
                      -> explicit reference-builder authorization
                          -> A13-AS1F fresh fixture generation and hash freeze
                              -> A13-AS1J/AS2 blind judging, audit, and freeze
                                  -> A13-S1 Candidate provider Shadow
                                      -> A13-C1 guarded activation or No-Go
```

The LLM proposes a validated `UnderstandingDelta`; it never mutates
`SessionState` directly. Disabled, no-key, timeout, invalid-output, and
validator-failure paths must preserve exact no-LLM behavior. A13 does not
change the shared retrieval contract, and the same turn must not activate both
A13 and the optional B10b-DS1 reranker during metric attribution.

Question Policy remains a separate A14 experiment because it dominates the
current hash-bound audit. The A13-0 record is
[`docs/a13_0_baseline_evidence.md`](../a13_0_baseline_evidence.md). The A13-1
decision record is
[`docs/a13_1_state_override_evidence.md`](../a13_1_state_override_evidence.md).
The A13-S0 offline foundation record is
[`docs/a13_s0_offline_evidence.md`](../a13_s0_offline_evidence.md).
The A13-AS0T core-contract record (not a complete execution runner) is
[`docs/a13_as0_offline_tooling_evidence.md`](../a13_as0_offline_tooling_evidence.md).
The teammate-facing legacy annotation package is
[`experiments/fixtures/a13_annotation_pack_v1/README.md`](../../experiments/fixtures/a13_annotation_pack_v1/README.md).
The reproducible teammate-facing ZIP committed on the `llm` publication branch
is [`A13_annotation_pack_v1.zip`](../../A13_annotation_pack_v1.zip).
It remains useful for development diagnosis but is exposed and cannot score the
new semantic gate; it is not reconciled gold and does not authorize provider
work.
The first returned-file intake is audited in
[`docs/a13_annotation_intake_review.md`](../a13_annotation_intake_review.md):
the `codex` draft validates but lacks confirmed human-member provenance, while
the Zhangchen submission has 26 invalid rows. These files are now L1 historical
diagnostics under the selected no-human route; neither may seed, tune, or judge
the AI-silver reference.
The legacy 60 item texts are also selection-exposed. A13-AS0T has frozen the
Candidate and independent generation rules; AS0R must still bind exact
independent model identities before AS1F builds and
hash-freezes a fresh target-free fixture before blind judging.
The 34 individually valid Zhangchen rows remain available only through the
coordinator-local provisional comparison described there. They may explain
historical failure classes but may not seed, tune, or score AI-silver work.
The adjacent AI adjudication suggestions remain exposed, non-independent L1
diagnostics. They must not be copied into the committed fixture or shown to
blind labelers/adjudicators.
The clean offline valid-34 deterministic dry-run is diagnostic only: 13/34
complete-label exact and 16/34 invalid predictions, dominated by nine
positive/rejected conflicts in the raw request projection. Applied-state replay
has zero surviving active/rejected same-value conflicts, so do not treat those
nine as final-state bugs. A13-AS0 now predeclares `applied_state_delta_v1` as
the primary comparator and raw Shadow request exact as diagnostic only,
independent of which scores better on the AI-pending subset. This does not
satisfy the AI-silver or A13-C1 gate. See the same intake review for the report
hash, field breakdown, and circularity warning.
Do not combine A13 semantic understanding with an ask/stop policy change.

## A14 - Question Policy Deepening

**Status: A14-0 and A14-1 retained with exact legacy-visible parity; wait for
the A13 review disposition before A14-S1.**
The authoritative plan is
[`docs/question_policy_optimization_plan.md`](../question_policy_optimization_plan.md).

The retained A14-0 runtime source is `f594601`. Its independent clean legacy
trace, 649-turn current audit, unchanged Development/fold metrics, zero policy
violations, source/input hashes, and local policy latency are bound in
[`docs/a14_0_question_policy_evidence.md`](../a14_0_question_policy_evidence.md).
A14-1 is retained at `b238c68`; its complete per-turn closed-schema evidence, exact
parity, fixed folds, latency, and missing-data disposition are in
[`docs/a14_1_attribute_evidence.md`](../a14_1_attribute_evidence.md). Do not
open A14-S1 or a Candidate while A13 remains undecided.

The recommended Module has one runtime Interface:

```text
QuestionPolicy.decide(
  state,
  current RetrievalResult,
  turn/top_k,
  response fallback status,
) -> QuestionPolicyOutcome
```

It is called after retrieval and before `response_guard`. It is read-only and
hides same-snapshot Decision Evidence construction, eligible attributes,
per-attribute availability/comparability, guarded selection, legacy fallback,
question rendering, diagnostics, and optional advisor handling. `Agent` remains
responsible only for attaching the returned question; guarded response
recording remains responsible for adding the attribute to state.

The first behavior Candidate must change only attribute selection. It preserves
the baseline ask opportunity because the local evaluator scores current
recommendations before generating a reply and no-ask produces no new product
preference after a miss. Initial stop remains limited to final turn, no eligible
attribute, or explicitly non-actionable legal choices.

The deterministic policy begins with a lexicographic cascade:

```text
eligibility
  -> evidence health/comparability
  -> likely answerability
  -> actionability in the current extraction/state/query pipeline
  -> rank-weighted Candidate split
  -> intent fit
  -> legacy priority fallback
```

Do not reduce this to a single globally comparable score until calibration is
proven. Missing, partial, uncalibrated, and degraded evidence are different
states. Numeric evidence from one attribute family cannot automatically defeat
an uncovered legacy attribute.

Required order:

1. A14-0: retained turn audit plus deep-Module parity, no behavior change;
2. A14-1: retained explicit evidence status for all ten allowed attributes, no
   behavior change;
3. wait for A13 review disposition;
4. A14-S1: deterministic selection Shadow and offline counterfactual audit;
5. A14-C1: selection-only Candidate with legacy fallback;
6. optional catalog-only safe-policy Shadow/Candidate if a learnable bucket is
   diagnosed;
7. optional A14-S3T offline LLM teacher Shadow or No-Go, with no direct runtime
   path;
8. optional online LLM advisor Shadow/Candidate or No-Go in one ambiguity
   bucket;
9. broader ask/stop Candidate only after selection is stable.

Optional LLM work uses separate internal adapters. An offline teacher may
cluster only a frozen, hash-bound set of grounded catalog feature phrases and
must pass deterministic validation. The online advisor receives no raw feature
phrases and may only rerank an already eligible shortlist from bounded
aggregate evidence. Neither may decide stop in its first Candidate, create an
attribute, mutate state, see Candidate IDs or evaluator data, or bypass
deterministic fallback. Question wording may improve real UX and the demo, but
the local evaluator responds to `ask_attribute`, not prose quality.

A14-S3T owns the teacher's frozen input, deterministic validation,
reliability/cost gate, and offline-only disposition. It cannot open A14-C3;
only the separate online A14-S3 advisor Shadow can do that. A teacher artifact
needs a new deterministic Shadow/Candidate review before it can affect runtime.

Development-only target data may score counterfactual legal actions offline;
it must not enter runtime or training features. A later learned policy must use
catalog-derived synthetic trajectories, ship only a small validated artifact,
and fall back to the legacy action on missing, corrupt, or out-of-distribution
inputs. Development remains selection-only and Full/Holdout remain untouched.

### Likely implementation files after approval

- `starter/core/question_policy.py`;
- `starter/core/clarification.py` as a compatibility wrapper or legacy adapter;
- `starter/core/decision_evidence.py` deepened into or consumed by the Module;
- `starter/agent.py` wiring;
- focused Question Policy, Agent, response-guard, leakage, and turn-audit tests;
- `experiments/` and `docs/a14_*` evidence only for the selected slice.

Do not change `starter/contracts.py`, B retrieval/ranking implementation, the
evaluator, catalog, public labels, or submission package in A14-0/C1 without a
separately approved blocker.

## Handoff to Developer B

For a retained A change, provide:

- exact `RetrievalRequest` examples for stable Buying, Browsing, and Override,
- Strategy and reason examples,
- final query examples and the A-internal QueryPlan trace,
- typed query component examples only if coordinated A10c was retained,
- active/rejected/no-preference fixtures,
- required new diagnostics, if any,
- contract test results,
- branch/commit and development evidence,
- explicit statement of unchanged route-weight semantics or a coordinated
  contract decision.

## End-of-Session Template

```text
Branch and commit:
A experiment:
Failure class:
Behavior changed:
Files changed:
Focused/full tests:
Development folds and scenarios:
Question/intent diagnostics:
Keep/revert decision:
B dependency or shared-contract impact:
Known risks:
Next smallest step:
```
