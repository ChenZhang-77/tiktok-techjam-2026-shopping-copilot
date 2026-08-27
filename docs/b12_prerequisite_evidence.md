# B12 Adaptive Candidate Depth Prerequisite Evidence

## Decision

Do not start a confidence-adaptive depth experiment yet. B12's prerequisite is
not satisfied, so this module changes no runtime behavior and runs neither a
Development-160 candidate comparison nor fixed-fold selection.

The current system already varies `Strategy.retrieval_depth` by A-owned intent
and active-constraint count: Buying uses 60 or 80 candidates, while Browsing
uses 120 or 100. B then consumes that bounded typed value. This is legitimate
intent/constraint-aware depth, but it is not the B12 confidence-adaptive policy
described in the roadmap.

## Why the gate fails

A8 persists an `IntentAssessment` and exposes low, medium, and high ordinal
stability bands. Its retained evidence explicitly says the signal is not a
calibrated probability and `B_side_gate` is false. The current planner reads
the assessment only to explain the intent transition; it does not use
`confidence` or `confidence_band` when selecting depth.

AB1 retained truthful requested/executed/fallback Route diagnostics. It did not
change the request schema or Strategy weight semantics, and it did not define a
confidence-to-depth mapping. B must therefore not import A's state, parse a
free-form reason, or invent thresholds for A's ordinal signal.

## Current seam

```text
A SessionState
  -> plan_strategy(intent, active constraints)
  -> Strategy.retrieval_depth = 60 / 80 / 100 / 120
  -> RetrievalRequest
  -> B limits lexical retrieval to the requested depth
```

The seam itself is sufficient for a future B12 implementation: A can own the
mapping and continue to send only `Strategy.retrieval_depth`; B does not need
raw confidence or a `SessionState` object. What is missing is the coordinated,
tested meaning of that mapping.

## Required next action

An A/B-coordinated slice should define how A's ordinal confidence bands affect
the existing depth field, including unavailable-assessment fallback and exact
bounds. A should own and test this decision. B should continue to validate and
execute only the typed bounded depth.

Only after that slice exists should B12 compare it on Development-160 and all
four fixed folds, reporting ranking quality, chosen-depth distribution,
latency, memory, and gained/lost sessions. The current intent/constraint mapping
must remain the fixed fallback.

## Evaluation boundary

- Development-160 behavior run: not run; no authorized candidate behavior.
- Fixed-fold behavior runs: not run for the same reason.
- Full-200 and exposed Holdout-40: not run.
- Evaluator target ASIN, target rank, hit/miss, and scenario labels: not used.
- Runtime code changed: none.

Machine-checkable evidence and source hashes are in
`docs/b12_prerequisite_evidence.json`.
