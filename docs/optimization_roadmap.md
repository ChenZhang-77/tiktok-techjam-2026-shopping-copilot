# Shopping Copilot - Project Optimization Roadmap

## Purpose

This is the execution map for the next phase of the project. It is designed for
fresh Codex conversations and for two people working through independent but
coordinated A and B workstreams.

The objective is not to add more components. It is to improve private-set
generalization, align the runtime with Track 4, preserve reliability, and turn
the verified engineering work into a complete submission.

## Non-Negotiable Boundaries

- Optimize only on the fixed Development-160 split and its four fixed folds.
- Do not run or tune from Full-200 or the exposed 40-session holdout.
- Never expose `ground_truth`, target ASIN, scenario labels, intent cards, or
  evaluator behavior to Agent runtime.
- Never mutate the frozen catalog or evaluator to improve a score.
- Keep the current structured runtime as the fallback and comparison baseline.
- Do not retain a feature because it looks more sophisticated.
- One experiment changes one primary behavior and must be independently
  revertible.
- Any shared contract or route-weight semantic change requires A/B agreement.
- Do not push, merge, or open a PR unless the user explicitly asks.

## Outcome Hierarchy

The project must improve six outcomes together:

1. HitRate@10, MRR, and MTTC on development cross-validation.
2. Buying, Browsing, Intent Override, and Boundary robustness.
3. Faithful Track 4 behavior: routing, state evolution, context programming,
   proactive guidance, and measured semantic evidence.
4. Low latency, bounded memory, deterministic fallback, and zero schema drift.
5. A clear product story that maps technical behavior to shopping value.
6. A runnable public repository, submission package, and defensible demo.

## Experiment Discipline

Every experiment record must contain:

```text
ID and owner:
Hypothesis:
Failure class addressed:
Primary behavior changed:
Files expected to change:
Baseline/comparator:
Development folds:
Overall and scenario metrics:
Gained/lost sessions:
Latency/memory/fallback impact:
Keep gate:
Revert gate:
Decision:
```

Prefer a result that wins on at least three of four folds, has an explainable
failure mechanism, and avoids a material scenario regression. A small aggregate
gain with unstable folds or severe Intent Override regression is not enough.

## Dependency Map

```text
R0 failure taxonomy
  -> A8 persistent IntentAssessment
      -> AB0 DecisionEvidence availability
          -> A9 should-ask gate
              -> A10a candidate question value
                  -> A10b internal QueryPlan
                      -> A11 extraction/scope hardening when R0 supports it
                          -> AB1 shared contract and route-semantics freeze
                              -> A12 profile disposition
                                  -> B8 rejected-constraint ranking
                                  -> B9 Browsing-first conditional dense retrieval
                                  -> B10a constraint-preserving CrossEncoder rerank
                                  -> B10b LLM semantic ranking only as a distinct experiment
                                      -> B11/B12 only when diagnosed
                                          -> R4 integrated freeze
                                              -> R5 delivery and rehearsal
```

B9 is blocked by A8 and AB1 because conditional routing cannot be evaluated
reliably when intent flips on ordinary clarification replies or when Strategy
weights describe a route that the selected retriever does not execute.

## R0 - Development Failure Taxonomy

### Goal

Identify why each Development-160 miss occurs before changing behavior.

Classify each miss into one primary cause and optional secondary causes. Use
the earliest causal stage as primary:

| Class | Evidence |
| --- | --- |
| Extraction | a disclosed constraint was missed, misclassified, or given wrong scope |
| State / Override | stale, rejected, or overridden context remained active or valid context was lost |
| Intent / Strategy Routing | extracted state was correct but Buying/Browsing or Strategy was wrong |
| Query Construction | correct active evidence was omitted, duplicated, flattened, or made positive/negative incorrectly |
| Question Policy | clarification was unnecessary, repeated, unavailable, or failed to reveal useful evidence |
| Retrieval Recall | target absent from the retained internal Candidate Pool |
| Ranking / Filtering | target was recalled but filtered, ordered outside Top 10, or ranked poorly |
| Response / Contract | a valid retrieved result was lost, duplicated, invalidated, or serialized incorrectly |

Example: failing to recognize “black” or “leather” is Extraction; recognizing
it correctly but omitting or corrupting it while building the query is Query
Construction.

Record evaluator/timing anomalies separately as `evaluation_validity` flags;
they are not Agent behavior classes.

| Allowed only offline on Development-160 | Forbidden from runtime and tuning |
| --- | --- |
| target ASIN, hit/miss, target rank, pre/post-rank position | Agent, SessionState, RetrievalRequest, Strategy, runtime diagnostics, prompts, rules, or models |
| aggregate and per-scenario failure counts | Full-200/holdout selection, sample-specific exceptions, target-keyed configuration |

The offline target determines whether a failure is Retrieval Recall or Ranking
/ Filtering. It must never become a feature available to the running system.

### Required outputs

- Failure counts overall and by scenario.
- Target recall at the retained retrieval depths.
- Pre/post-rank target positions for offline analysis.
- Examples of the most frequent failure mechanisms.
- A ranked recommendation for the next single experiment.

### Completion gate

The team can state the dominant canonical class, show the primary/secondary
rule, and recommend one smallest next experiment. No runtime code change is
required for the first audit.

## R1 - A-Side Decision Quality

Detailed ownership, files, tests, and handoff requirements are in
`docs/workstreams/DEVELOPER_A_CONTROL_PLANE.md`.

### A8 - Stateful intent persistence

**Status: retained at `83a6bcd`.** The persistent assessment and transition
semantics passed focused/full tests. Development HitRate is unchanged, Buying
improves in three of four folds, Browsing does not regress, and Intent Override
has a small disclosed regression. See `docs/a8_stateful_intent_evidence.md`.
Confidence is an A-owned ordinal stability signal, not a calibrated probability
or an authorized B-side gate.

Problem: intent is derived from the current utterance and can flip from Buying
to Browsing after a normal one-attribute clarification reply.

Hypothesis: intent hysteresis based on previous intent, accumulated active
constraints, explicit exploratory language, and override events will improve
Buying and Intent Override without regressing Browsing.

Keep only if route changes are observable, explainable, and cross-validation
supports the scenario tradeoff.

Before implementation, define persistent `IntentAssessment` semantics:
`intent`, `confidence`, observed `evidence`, `source_turn`, and
`transition_reason`. It must survive later turns directly or be deterministically
derived from persisted evidence. A current-turn-only confidence score does not
solve intent persistence.

### AB0 - Candidate decision evidence availability

This is a design-and-plumbing blocker before A9, not a new ranking experiment.

Start from the full existing `RetrievalResult` and prior returned Candidate IDs.
Define a compact A-side `DecisionEvidence` with only signals whose source and
fallback are known, for example pool size, calibrated top-score margin,
constraint coverage, Top-K stability, attribute partitions, relaxation, route
failure, and turn/exhaustion state.

For each field record:

- producer and owner,
- current source or required new computation,
- current-turn versus cross-turn lifecycle,
- behavior when scores or metadata are unavailable,
- whether it is A-internal or part of the shared contract.

Prefer an A-side adapter first. Coordinate a `RetrievalDiagnostics` extension
only for evidence B must calculate or define. AB0 changes no dialogue policy and
must add contract/leakage tests if the shared schema changes.

### A9 - Should-ask gate

Problem: clarification is usually attempted whenever an attribute is
available, even when recommendations may already be sufficiently concentrated.

Hypothesis: an over-generality gate based on Candidate Pool size, score margin,
constraint coverage, candidate stability, and turn number will reduce wasted
questions and MTTC.

The Agent should continue to return valid recommendations when asking. Do not
start this rule until AB0 proves every retained input exists at the decision
point and has deterministic missing-data behavior.

### A10a - Candidate question value

Problem: `feature` is normally selected before candidate partition evidence.

Hypothesis: ranking questions by expected candidate reduction will improve MTTC
without losing useful preference evidence.

### A10b - Internal QueryPlan

Problem: the distilled query is one string that can retain noisy phrases.

Hypothesis: an A-internal, auditable `QueryPlan` separating
exact/category/semantic/negative evidence will improve private paraphrase
robustness while still building the existing `RetrievalRequest.query` string.

Create A10c only if a measured B experiment requires typed components. A10c is
then an AB1-coordinated contract change with compatibility tests.

### A11 - Extraction and scope hardening

Prioritize catalog-derived category/brand vocabulary, multi-word values,
negation scope, numeric ambiguity, override scope, and bounded low-confidence
feature phrases. A lightweight model parser is optional and must be behind a
timeout plus deterministic fallback.

### A12 - Profile ablation

Only after A8-A11 and AB1 stabilize: test a very small profile prior in vague
Browsing states. Explicit current intent always wins. Keep
`profile_weight=0.0` when the ablation is not stable.

A12 is a required disposition before R4: either run the time-boxed ablation or
record that profile value remains unproven and deferred. A skipped or rejected
ablation leaves the Track 4 long-term-profile gap open.

## R2 - Shared Evidence and Contract Loop

### AB1 - Shared contract and active-route semantics freeze

Preserve the stable interface:

```text
HybridRetriever.retrieve(request: RetrievalRequest) -> RetrievalResult
```

Do not pass SessionState implementation objects into B. Extend the contract
only when AB0/A10c proves a real consumer need. AB1 freezes names, types,
ranges, missing-data behavior, backward compatibility, and leakage tests.

B may compute non-label diagnostics such as:

- route candidate counts and overlap,
- filtered and relaxed pool sizes,
- top-score margin,
- active-constraint coverage,
- candidate attribute partition statistics,
- previous/current candidate stability,
- route/cache failure and latency.

A owns whether to ask, which attribute to ask, and when Strategy changes. B
owns how the requested Strategy executes. Diagnostics must not decide dialogue
policy inside the retrieval plane.

AB1 must also distinguish requested Strategy from executed route. A non-zero
weight cannot be presented as an active route when the selected retriever
ignores it; diagnostics must make execution and fallback observable.

## R3 - B-Side Targeted Retrieval and Ranking

Detailed ownership, files, tests, and handoff requirements are in
`docs/workstreams/DEVELOPER_B_RETRIEVAL_RANKING.md`.

### B8 - Rejected-constraint ranking

Problem: rejected constraints cross the seam but are not a calibrated negative
signal in the retained path.

Test exact, confidence-aware negative scoring without broad exclusion. Missing
metadata remains neutral. Focus on rejection and Intent Override cases.

### B9 - Browsing-first conditional dense route

Track 4 explicitly associates Browsing with diverse dense retrieval. Test a
guarded Browsing route first while preserving the deterministic fallback.
Existing evidence does not justify global enablement.

Candidates:

- broad or low-confidence Browsing as the primary compliance hypothesis,
- stable Buying only as a secondary evidence-supported experiment,
- disable immediately after Intent Override,
- enable only when lexical/structured evidence is ambiguous,
- preserve the deterministic structured fallback.

### B10a - Constraint-preserving CrossEncoder rerank

Candidates:

- anchor the structured Top 3,
- rerank only positions 4-30,
- blend normalized semantic and constraint scores,
- prevent a semantic score from promoting a hard-constraint violation,
- fall back to the exact pre-rerank order.

Retaining a CrossEncoder does not satisfy or close the official LLM Semantic
Ranking pillar. It remains a measured learned reranker with its exact model,
cost, latency, and fallback disclosed.

### B10b - LLM semantic ranking

Treat an actual LLM ranker as a separate experiment with one primary behavior,
a bounded Candidate Pool, token/cost accounting, timeout, deterministic
pre-rank fallback, and the same constraint-preservation rules. Run it only when
time and the competition environment permit a reproducible path. Only a
retained actual LLM route may close the LLM-ranking gap.

If no dense or semantic route survives the gate, record the measured negative
result and the remaining literal Track 4 gap. Do not describe implementation or
reproducibility as retained runtime coverage.

### B11 - Lexical recall refinement

Run only if R0 shows recall is a dominant cause. Test one variable at a time:
exact phrase plus broad OR, field-specific query weights, catalog-derived
synonyms, category normalization, details key/value representation, or removal
of conversational filler.

### B12 - Adaptive depth

Run only after the diagnostics loop exists. Clear Buying can be shallower and
more precise; ambiguous Browsing may go deeper; over-general pools should stop
expanding and return control to A for clarification.

## R4 - Integrated Selection and Freeze

For each retained A or B slice:

1. run focused tests,
2. run the full test suite,
3. run fixed development folds,
4. compare gained/lost sessions,
5. inspect scenario regressions,
6. record latency, memory, fallback, and complexity,
7. keep or revert before starting the next slice.

Do not combine several individually weak changes into a large unreviewable
system. The current structured runtime remains the last-known-good fallback.

The historical Full-200 result must remain explicitly historical after any
behavior change. Do not produce another Full/Holdout tuning loop.

## R5 - Product, Documentation, Demo, and Submission

This track can proceed in parallel once the active architecture is understood.
See `docs/demo_and_submission_plan.md`.

Required outcomes:

- README reflects the real retained runtime and measured negative results.
- AGENTS.md reflects current interfaces and experiment boundaries.
- A/B workstream documents contain current optimization backlogs, not the old
  build-from-scratch plan.
- The debug visualizer clearly separates Agent-visible and evaluator-only data.
- The demo covers Buying, Browsing, Intent Override, and a degraded path.
- `submission/` becomes a minimal independently runnable package.
- Team contributions, limitations, cost, latency, attribution, and reproducible
  commands are complete.

## Time-Based Decision

### If at least two development days remain

Execute R0, A8, AB0, A9, A10a, A10b/A11 as supported, AB1, make the A12
profile disposition, then run the single best R0-supported B experiment. Stop
behavior work early enough to complete R4 and R5.

### If submission is imminent

Do not alter the frozen runtime. Execute only documentation, packaging, clean
start verification, demo preparation, and rehearsal. The project already has a
strong result; an incomplete or misleading submission is a larger risk than a
small unrealized metric gain.

## Explicit Non-Goals

- LangGraph or a multi-agent framework.
- A heavy external vector database.
- Foundation-model fine-tuning.
- Microservices or production deployment.
- A product-scale front end.
- Repeated model sweeps without a diagnosed failure mechanism.
- Claiming optional experiments are the default runtime.
