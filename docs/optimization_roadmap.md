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
  -> A8 stateful intent
      -> A9 should-ask gate
          -> A10 question value and query distillation
              -> AB1 diagnostics contract
                  -> B8 rejected-constraint ranking
                  -> B9 conditional semantic route
                  -> B10 constraint-preserving rerank
                      -> R4 integrated freeze
                          -> R5 delivery and rehearsal
```

B9 is blocked by A8 because conditional semantic routing cannot be evaluated
reliably when the intent signal flips on ordinary clarification replies.

## R0 - Development Failure Taxonomy

### Goal

Identify why each Development-160 miss occurs before changing behavior.

Classify each miss into one primary cause and optional secondary causes:

| Class | Evidence |
| --- | --- |
| Recall | target absent from lexical/structured/dense Top-N |
| Ranking | target in the Candidate Pool but outside final Top 10 or ranked poorly |
| State | stale, rejected, or overridden context affected the active query |
| Dialogue | clarification was unnecessary, repeated, or failed to reveal useful evidence |
| Extraction | a disclosed constraint was missed, misclassified, or given wrong scope |

Record target rank only in offline development analysis. It must never enter a
runtime request, diagnostic, or learned rule keyed by sample/target.

### Required outputs

- Failure counts overall and by scenario.
- Target recall at the retained retrieval depths.
- Pre/post-rank target positions for offline analysis.
- Examples of the most frequent failure mechanisms.
- A ranked recommendation for the next single experiment.

### Completion gate

The team can state whether the dominant bottleneck is A-side state/dialogue,
B-side recall, B-side ranking, or mixed. No runtime code change is required for
the first audit.

## R1 - A-Side Decision Quality

Detailed ownership, files, tests, and handoff requirements are in
`docs/workstreams/DEVELOPER_A_CONTROL_PLANE.md`.

### A8 - Stateful intent persistence

Problem: intent is derived from the current utterance and can flip from Buying
to Browsing after a normal one-attribute clarification reply.

Hypothesis: intent hysteresis based on previous intent, accumulated active
constraints, explicit exploratory language, and override events will improve
Buying and Intent Override without regressing Browsing.

Keep only if route changes are observable, explainable, and cross-validation
supports the scenario tradeoff.

### A9 - Should-ask gate

Problem: clarification is usually attempted whenever an attribute is
available, even when recommendations may already be sufficiently concentrated.

Hypothesis: an over-generality gate based on Candidate Pool size, score margin,
constraint coverage, candidate stability, and turn number will reduce wasted
questions and MTTC.

The Agent should continue to return valid recommendations when asking.

### A10 - Candidate question value and query components

Problem: `feature` is normally selected before candidate partition evidence,
and the distilled query is one string that can retain noisy phrases.

Hypothesis: ranking questions by expected candidate reduction and separating
exact/category/semantic/negative query evidence will improve private paraphrase
robustness and MTTC.

### A11 - Extraction and scope hardening

Prioritize catalog-derived category/brand vocabulary, multi-word values,
negation scope, numeric ambiguity, override scope, and bounded low-confidence
feature phrases. A lightweight model parser is optional and must be behind a
timeout plus deterministic fallback.

### A12 - Profile ablation

Only after A8-A11 stabilize: test a very small profile prior in vague Browsing
states. Explicit current intent always wins. Keep `profile_weight=0.0` when the
ablation is not stable.

## R2 - Shared Diagnostics Loop

### AB1 - Retrieval evidence for A-side decisions

Preserve the stable interface:

```text
HybridRetriever.retrieve(request: RetrievalRequest) -> RetrievalResult
```

Do not pass SessionState implementation objects into B. Extend the contract
only when a real experiment requires it.

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

## R3 - B-Side Targeted Retrieval and Ranking

Detailed ownership, files, tests, and handoff requirements are in
`docs/workstreams/DEVELOPER_B_RETRIEVAL_RANKING.md`.

### B8 - Rejected-constraint ranking

Problem: rejected constraints cross the seam but are not a calibrated negative
signal in the retained path.

Test exact, confidence-aware negative scoring without broad exclusion. Missing
metadata remains neutral. Focus on rejection and Intent Override cases.

### B9 - Conditional semantic route

Do not enable semantic work globally. Existing evidence shows modest Buying and
Browsing potential but severe Intent Override and MRR regression.

Candidates:

- stable Buying only,
- low-confidence Browsing only,
- disable immediately after Intent Override,
- enable only when lexical/structured evidence is ambiguous,
- preserve the deterministic structured fallback.

### B10 - Constraint-preserving semantic rerank

Candidates:

- anchor the structured Top 3,
- rerank only positions 4-30,
- blend normalized semantic and constraint scores,
- prevent a semantic score from promoting a hard-constraint violation,
- fall back to the exact pre-rerank order.

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

Execute R0, A8, A9, AB1, then the single best R0-supported B experiment. Stop
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
