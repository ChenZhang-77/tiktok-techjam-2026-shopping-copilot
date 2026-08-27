# AB0 DecisionEvidence Availability — Retained Evidence

## Decision

Retain the A-side `DecisionEvidence` adapter at code commit `a37fd61`. It
summarizes the complete `RetrievalResult` and cross-turn A state before
clarification, without changing the clarification policy or the shared
`RetrievalRequest` / `RetrievalResult` schema.

The full Candidate IDs and evidence text remain internal. Public diagnostics
contain only bounded aggregates and availability statuses. A9 may now use the
signals marked usable below; it must not use the score margin until a separate
coordinated calibration establishes shared semantics.

## Source Audit

| Signal | Producer and lifecycle | Range | Missing/degraded behavior | A9 status |
| --- | --- | --- | --- | --- |
| Pool size | full current `RetrievalResult.candidates`; cross-check existing `candidate_count` | integer >= 0 | zero; inconsistency marks degraded | usable |
| Candidate stability | current Retriever Top-K versus previous returned Top-K from `SessionState`; non-degraded turns only | Top-K Jaccard in [0,1] | null plus explicit status | usable with status guard |
| Score margin | first two finite monotonic `Candidate.score` values | route-local float >= 0 | null plus reason | **not usable: uncalibrated** |
| Constraint coverage | mean fraction of unique active constraints matched across every full-pool Candidate | optional [0,1] | null when evidence is incomplete | usable with status guard |
| Attribute partitions | vocabulary evidence across every Candidate `evidence_text` | map values [0,1] | empty map; evidence count remains visible | usable as bounded heuristic |
| Relaxation/degraded | existing retrieval fallback, route failure, relaxation, and count diagnostics | bool/count | safe false/zero; unavailable retrieval is degraded | usable |
| Turn/exhaustion | current turn plus asked/no-preference A state | bounded turn and sorted attributes | empty attributes | usable |

`current_candidate_depth` is the unique Retriever result prefix up to the
current `top_k`; `previous_candidate_depth` is the previous guarded returned
prefix truncated to the current `top_k`. Stability is unavailable if the
current retrieval or previous response was degraded, so A9 cannot compare
unlike fallback paths as though they were stable.

The complete per-field producer/type/range/lifecycle/fallback/ownership table
is machine-readable in `docs/ab0_decision_evidence.json`.

## Behavior Parity

The clean Development-160 report at `a37fd61` exactly matches the retained A8
report on overall metrics, all scenario metrics, and all 160 session outcomes:
HitRate@10 `0.7625`, MRR `0.529812`, MTTC `5.35`, and technical score
`0.653194`.

An isolated replay compared every turn's `ask_attribute` and recommendation
ASIN sequence between baseline `6811a49` and AB0. Both 160-session, 818-turn
traces hash to:

```text
6ec964221d32812e2a6d40ccc9865f818bbe5bbb8aa7bdab71516031b63bd917
```

Therefore AB0 changes neither should-ask nor what-to-ask behavior. Folds were
not rerun because this module performs no behavior selection and exact dialogue
parity was verified on the complete Development-160 split. Holdout and Full-200
were not run.

## Cost and Rejected Variant

The final clean run observed mean response latency `41.39 ms`, mean retrieval
latency `37.48 ms`, peak RSS `578,813,952` bytes, zero exceptions, zero invalid
payloads, and zero fallbacks. Sequential timing is noisy, so this is not a
claim that AB0 improves latency.

The first full-pool scanner at `5dc1f01` was rejected: it repeatedly compiled
per-term regular expressions and raised mean response latency to `131.74 ms`.
The retained scanner tokenizes each Candidate once and uses bounded phrase
matching.

## Next Step

Proceed to **A9 Should-Ask Over-Generality Gate** as a separate behavioral
experiment. Start with usable, status-guarded fields. Do not gate on
`top_score_margin`, and do not change the shared contract during A9.
