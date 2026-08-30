# A13 AI-Silver Evaluation Protocol

## Decision

A13 may proceed without human annotation, but the resulting reference is
`AI-silver`, never human gold. AI-silver may open a bounded Shadow/Candidate
experiment; it cannot by itself justify retention. Runtime retention still
depends on the fixed Development-160 folds, exact fallback, safety invariants,
cost, and an explicit keep/revert decision.

This protocol replaces the earlier two-person annotation requirement as the
active A13 route. It does not retroactively turn either returned annotation
file or the valid-34 AI draft into reference truth.

Current state:

```text
protocol_status = planned_not_executed
ai_silver_frozen = false
reference_builder_provider_authorized = false
candidate_provider_authorized = false
A13_C1_authorized = false
```

## What Decision the Evidence Supports

The protocol must answer two different questions without conflating them:

1. **Semantic screening:** on a frozen ambiguity fixture, does the candidate
   produce an applied state transition that agrees with an independently built
   multi-model AI-silver reference more often than the deterministic path?
2. **Runtime retention:** when enabled for one predeclared trigger, does the
   candidate improve Development-160 robustly without breaking fallback,
   state, latency, cost, privacy, or scenario guardrails?

AI-silver answers only the first question. Fixed-fold Development evidence owns
the second.

## Evidence Levels and Claim Language

| Level | Evidence | Permitted claim |
| --- | --- | --- |
| `L0` | Exposed legacy 60-item fixture | Development diagnostic only; no semantic-quality claim |
| `L1` | Single-source or exposed provisional labels, including valid-34 | Diagnostic only; not independent reference evidence |
| `L2` | Frozen multi-model AI-silver under this protocol | Agreement with AI-silver; not accuracy against truth |
| `L3` | L2 plus fixed Development-160/fold Candidate evidence | Evidence-backed keep/revert decision for this runtime |
| `L4` | Independently adjudicated human gold | Not produced by the no-human route and must not be claimed |

Reports and submission text must use `agreement`, not `accuracy`, for L2.

## Frozen Comparison Unit

The primary comparison unit is `applied_state_delta_v1`, not the raw parser or
model proposal. For the same isolated prior state:

```text
deterministic evidence -> production SessionState.apply_user_context
candidate delta        -> validator -> same isolated state transition
AI-silver delta         -> validator -> same isolated state transition
```

The resulting normalized transition records:

- intent before/after;
- active constraints added and deactivated;
- rejected constraints added;
- no-preference attributes added or removed;
- override attributes and stale values deactivated.

Raw `UnderstandingDelta` exact agreement remains a diagnostic because it
explains trigger/request-shape differences. It is not the primary comparator.
The serializer, ordering, normalization, schema, and hashes must be frozen in
AS0 before any reference or candidate output is inspected. The comparator seam
must not be selected according to whichever scores better on the exposed
valid-34 draft.

## Fixture and Contamination Boundary

The existing 60 target-free items are permanently development diagnostics. The
item text, trigger mix, 34 provisional labels, and comparator behavior have
already been inspected while selecting failure classes and the applied-state
seam. They must not be reused in an eligible semantic gate, even if their labels
are withheld from the judges.

AS0 must freeze the Candidate prompt/config, comparator, fixture-generation
rubric, source policy, and duplicate-audit method/threshold before any new
evaluation item is generated or inspected. AS1F then creates a fresh target-free,
trigger-balanced fixture that:

- contains at least 60 new items overall;
- contains at least 10 new items for every runtime-reachable trigger;
- contains at least 20 new items for the one proposed Candidate trigger;
- keeps `unexplained_intent_transition` unit-test-only because it is not
  runtime-reachable with empty evidence;
- uses an independent non-Candidate generator and/or frozen deterministic
  transformations of newly generated seed expressions; the Candidate
  model/version may not author any item;
- has no normalized-message exact duplicate or predeclared-threshold
  lexical/semantic near-duplicate of the legacy 60; rejected generated items
  remain accounted for in a pre-score duplicate audit;
- freezes item order, item SHA256, schema, instructions, validator, comparator,
  trigger counts, generator prompt/config, and Candidate config before judging;
- keeps target ASIN, hit/miss, scenario label, future turns, recommendations,
  comparator output, candidate output, and internal trigger names out of judge
  inputs.

The following artifacts are excluded from reference generation and prompt
tuning:

- `experiments/fixtures/a13_annotation_pack_v1/items.jsonl` and its ZIP copy;
- `annotations.b.jsonl`;
- `annotations.zhangchen (1).jsonl`;
- `provisional_valid34_ai_labels.jsonl`;
- the valid-34 comparison, suggestions, and comparator report.

The legacy item text remains L0; returned and provisional labels remain L1.
All are historical diagnostics. Their existence and prior exposure must be
disclosed in the final evidence record.

## Independent Automated Reference Roles

Use three blind labeler roles, `J1`/`J2`/`J3`, plus a bounded adjudicator only
when needed.

Required independence:

- the candidate model/version may not be the fixture generator, J1, J2, J3, or
  adjudicator;
- J1/J2/J3 must use three distinct model/version identities and three distinct
  model families, none belonging to the Candidate family; no family receives
  two votes;
- the adjudicator must use a model/version distinct from every labeler and a
  family outside the two labelers that formed the majority;
- labelers receive identical evidence and rubric but cannot see other labels;
- model ID, provider, prompt hash, config, request/response hashes, latency,
  tokens, cost, retry status, and validator result are recorded;
- the runner verifies these identity/family constraints before any request and
  fails closed if they are not met;
- a hosted alias is recorded honestly and is not called deterministic.

If the required independent families are unavailable, the run is
`insufficient_independence_diagnostic` and cannot open A13-C1. The correct
disposition is No-Go or acquiring independent judges, not weakening the vote
or calling self-evaluation gold.

### Bounded validation repair

Every first-pass label goes through the standalone schema/evidence validator.
One repair call is allowed using only the same item, the labeler's own invalid
output, and machine-readable validation errors. It may not see another label,
the deterministic output, or the candidate output. A second invalid result is
retained as invalid; it is not manually or mechanically rewritten.

## Consensus and Adjudication

Consensus operates on the validated `applied_state_delta_v1` projection:

1. `3/3` exact agreement becomes `silver_unanimous`.
2. `2/3` exact agreement becomes `silver_majority`; a blind adjudicator must
   independently validate the majority or return a different valid delta.
3. Three-way disagreement, adjudicator disagreement, or invalid adjudication
   becomes `silver_unresolved`.
4. Unresolved items stay in coverage and disagreement denominators. They may
   not be silently dropped to raise agreement.

The adjudicator sees the item, rubric, and anonymized J1/J2/J3 labels. It does
not see model identities, vote counts, deterministic/candidate outputs, or
Development targets.

One independent repeat build is required for the proposed Candidate trigger.
Its canonical applied-state labels must be at least 90% exact-stable under the
fixed-denominator rule below. A changed, invalid, or unresolved repeat label is
retained in the stability report and counts as non-stable rather than being
overwritten or excluded.

## KPI Framework

### Primary retention KPI

`Development-160 TechnicalScore delta`, evaluated overall and on the four
frozen folds, remains the primary keep/revert outcome. This directly represents
the competition decision and is harder to game than AI agreement alone.

### Semantic screening KPI

For one predeclared trigger with at least 20 frozen items:

```text
AI-silver applied-state exact-agreement delta
  = candidate exact-agreement rate
  - deterministic comparator exact-agreement rate
```

The Candidate must improve by at least 10 percentage points and at least five
net exact items. Other evaluated triggers may not regress by more than five
percentage points. This is an opening gate, not the final keep decision.

### Frozen denominators

For each trigger `T`, freeze `N_T` as the number of all fixture items assigned
to that trigger. No formula may replace it with a canonical-only or valid-only
denominator:

```text
reference_coverage(T) = canonical_reference_items(T) / N_T
model_exact(T) = canonical items where model applied-state == reference / N_T
semantic_delta(T) = candidate_exact_count(T) / N_T
                    - deterministic_exact_count(T) / N_T
net_exact_items(T) = candidate_exact_count(T) - deterministic_exact_count(T)
repeat_stability(T) = items canonical in both builds with identical state / N_T
```

An invalid or unresolved reference contributes zero to the exact and stability
numerators while remaining in `N_T`. An invalid Candidate/comparator projection
also contributes zero to that model's exact numerator. Overall rates use the
sum of all frozen trigger denominators. Reports must show numerator, denominator,
percentage, and invalid/unresolved counts; the `>=10pp`, `>=5 net items`,
`<=5pp` regression, coverage, and stability gates all use these formulas.

### Reference drivers

Report, but do not substitute for the primary outcomes:

- first-pass and post-repair schema-valid rates;
- unanimous, majority, adjudicated, and unresolved rates;
- canonical reference coverage overall and by trigger;
- repeat-build applied-state exact stability;
- per-field agreement and abstain rate;
- labeler/adjudicator calls, latency, tokens, and cost.

### Hard guardrails

An eligible AI-silver/reference run requires:

- 100% item accounting and trigger accounting;
- 100% accepted-label schema/evidence validity;
- at least 95% canonical reference coverage overall;
- 100% canonical coverage and at least 90% repeat-build stability in the
  proposed Candidate trigger;
- zero target/evaluator/recommendation leakage;
- zero use of candidate output in reference generation;
- hash-bound prompts, configs, inputs, normalized outputs, and summaries.

An eligible Candidate additionally requires:

- candidate schema success at least 99%;
- exact deterministic fallback on no-key, timeout, malformed/invalid output,
  validator failure, and provider failure;
- Shadow visible-response/state/Strategy/QueryPlan/recommendation change of
  zero before Candidate activation;
- zero state-invariant and evaluator-leakage violations;
- estimated Candidate call rate at most 20% of turns;
- remote p95 at most 2000 ms with a 2500 ms hard timeout;
- average prompt at most 500 tokens;
- focused/full tests and unresolved-free Standards/Spec review.

## Phase Order and Authority Boundaries

```text
A13-S0 offline foundation complete
  -> A13-AS0 protocol/comparator/candidate/generator freeze    no provider
      -> explicit authorization for reference-builder provider calls
          -> A13-AS1F fresh blind fixture generation and hash freeze
              -> A13-AS1J blind AI-silver judging and adjudication
                  -> A13-AS2 audit, repeat-build check, and hash freeze
                      -> semantic review gate
                          -> explicit authorization for candidate provider Shadow
                              -> A13-S1 real-provider Shadow
                                  -> A13-C1 or No-Go
```

AS0 is documentation/tooling work only. AS1F/AS1J/AS2 may call the independent
fixture generator, judges, and adjudicator only after explicit
reference-builder authorization and never through Agent runtime. Candidate
provider access is a separate authorization after the frozen silver review.
No phase authorizes A14-S1, B10b, a shared-contract change, or Full/Holdout use.

## One-Shot Selection and Regeneration Rule

Candidate prompt/config and the comparator must be frozen before AS1 outputs or
summaries are viewed. Score the frozen candidate once. If a developer changes
prompt, gate, schema, normalization, trigger, or state application after seeing
AI-silver results, the current silver set becomes selection-exposed for that
candidate version. The new version must either:

- generate a newly frozen, independently built silver fixture; or
- be treated as Development-only and receive no semantic-gate claim.

Repeated prompt sweeps against one AI-silver set are prohibited.

## Candidate Keep/Revert Gate

After the semantic gate, retain A13-C1 only when all existing runtime gates also
pass:

1. at least one net Development hit or a predeclared reproducible MTTC gain;
2. median aggregate TechnicalScore delta across three uncached runs is positive;
3. the run median has nonnegative TechnicalScore delta on at least three of four
   frozen folds;
4. Buying/Browsing each lose at most one hit and have TechnicalScore delta at
   least `-0.005`; Intent Override and Boundary lose no hits, and Intent Override
   TechnicalScore delta is at least `-0.005`;
5. failure paths are exactly comparator-equivalent;
6. invalid response, invariant violation, and evaluator leakage counts are zero;
7. call-rate, latency, token, cost, and fallback gates pass.

Failure of the silver gate or Development gate is a recorded No-Go. Do not
weaken thresholds merely to demonstrate LLM usage.

## Required Artifacts Before Execution

AS0 must define, but this planning change does not yet create:

- `experiments/fixtures/a13_ai_silver_v1/` with target-free judge inputs;
- a versioned `applied_state_delta_v1` schema and serializer;
- a fresh-fixture generator/source config and legacy duplicate audit;
- three blind labeler configs, an adjudicator config, and identity/family
  enforcement;
- a manifest binding model/prompt/config/input/validator/comparator hashes;
- a runner that keeps raw provider material out of Git and emits normalized,
  hash-bound summaries;
- synthetic tests for validation, consensus, disagreement retention,
  contamination rejection, comparator symmetry, and fallback;
- `docs/a13_ai_silver_evidence.{md,json}` only after AS1F/AS1J/AS2 complete.

## Stop Conditions

Stop and record No-Go when any of the following holds:

- the fresh fixture or required independent non-Candidate families are
  unavailable;
- canonical coverage or repeat-build stability misses its gate;
- reference generation sees candidate/comparator/evaluator output;
- the Candidate misses the semantic advantage gate;
- fixed Development folds or scenario guardrails fail;
- cost, latency, fallback, schema, invariant, or leakage gates fail;
- submission timing no longer allows independent review and clean freeze.

This is intentionally stricter than using one model as both teacher and judge.
The purpose is not to manufacture a score; it is to make a no-human decision
auditable and difficult to improve by circular evaluation.
