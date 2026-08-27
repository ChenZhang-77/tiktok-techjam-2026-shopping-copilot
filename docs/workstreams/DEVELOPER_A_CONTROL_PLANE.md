# Developer A Optimization Route - Control Plane

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
HybridRetriever.retrieve(request: RetrievalRequest) -> RetrievalResult
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

## Blocking Order

```text
R0 failure taxonomy
  -> A8 stateful intent
      -> A9 should-ask gate
          -> A10 question value and query components
              -> A11 extraction/scope hardening
                  -> A12 profile ablation
```

Do not start A12 before the explicit-intent path is stable.

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

An implementation may add intent confidence/evidence, but do not enlarge State
until tests require a real field.

### Expected files

- `starter/core/context_engine.py`
- `starter/core/state.py` only if persistent evidence is required
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

## A9 - Should-Ask Over-Generality Gate

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
- possibly `starter/contracts.py` only after A/B coordination
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

## A10 - Question Value and Query Components

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

For query distillation, preserve conceptual components:

```text
category/exact terms
active hard terms
active soft terms
semantic feature/use-case phrase
rejected/overridden terms
```

Do not blindly append the full current utterance after its evidence has been
captured in state. Negative terms must not become positive FTS terms.

### Keep gate

- Candidate questions are explainable from current evidence.
- MTTC improves without recall loss.
- Query traces exclude stale, rejected, duplicated, and excessive low-confidence
  phrases.

## A11 - Extraction and Scope Hardening

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

The profile is a weak anonymized prior, not a user identity or hard constraint.

Rules:

- run only after A8-A11,
- use a small soft signal only in vague/low-constraint Browsing,
- explicit current intent always wins,
- override never resurrects a profile preference as active intent,
- report a direct `profile_weight=0.0` comparison,
- retain zero when fold evidence is weak.

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
- query component examples,
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
