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
5. `starter/agent.py`
6. `starter/core/state.py`
7. `starter/core/context_engine.py`
8. `starter/core/planner.py`
9. `starter/core/query_builder.py`
10. `starter/core/clarification.py`
11. `starter/core/response_guard.py`
12. `starter/contracts.py`
13. the focused tests named by the selected experiment

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
improved, without a shared schema or question-policy change. The next executable
module is the shared AB1 contract and active-route semantics freeze.
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
- semantic model/cache execution,
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

### 3. `feature` is selected before candidate partition evidence

Candidate-aware scoring exists, but `feature` is normally preferred before the
candidate-value calculation. This can overfit the public simulator's high
feature availability.

### 4. Rule and scope limitations

Extraction uses static vocabulary and regexes. Known example: "I do not care
about color, but I prefer nylon" can incorrectly mark material as no-preference
because the no-preference expression is not scoped to one clause.

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
A8 persistent IntentAssessment
  -> AB0 DecisionEvidence availability
      -> A9 should-ask gate
          -> A10a candidate question value
              -> A10b internal QueryPlan
                  -> A11 extraction/scope hardening when R0 supports it
                      -> AB1 shared contract and route-semantics freeze
```

AB1 passed at `a676855`; its shared diagnostics preserve the A-owned Strategy
request while exposing B-owned execution and fallback. A12 is now explicitly
deferred for time with `profile_weight=0.0` and the Track 4 profile gap open.

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
