# A13-1 State / Override Decision Evidence

## Decision

**Reject and revert.** The bounded deterministic candidate removed the two
diagnosed stale preferences from active state and QueryPlan positive roles, but
it reduced Development-160 quality and regressed TechnicalScore on every fixed
fold. The Shadow comparator therefore remains the no-candidate `0.925` runtime.

This was an A-side state experiment only. It did not change Question Policy,
B-side retrieval/ranking, route-weight semantics, the shared contract, catalog,
evaluator, or public output through an LLM. It made zero DeepSeek calls and did
not run Full-200 or the exposed Holdout-40.

## Bound hypothesis and diagnosis

The two A13-0 State / Override misses were `public_0002` and `public_0096`.
Each asks to reset an earlier preference, but the earlier value and replacement
can be represented under different runtime attributes. Existing same-attribute
replacement therefore left the earlier value active.

The candidate added a narrow explicit-prior-preference reset. It preserved the
category and unrelated later evidence, removed the initial stale preference,
and prevented that value from silently reactivating without a new explicit
override. Focused endpoint tests exercised the public `Agent.respond` seam.

The candidate reached zero eligible-turn State / Override flags for both
diagnosed sessions. That proves the local mechanism, but not a keep decision:
the removed values also contributed useful retrieval evidence elsewhere.

## Development-160 result

| Metric | A13-0 comparator | Candidate | Delta |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.925000 | 0.906250 | -0.018750 |
| MRR | 0.552760 | 0.520590 | -0.032170 |
| MTTC | 4.131250 | 4.431250 | +0.300000 (worse) |
| Efficiency | 0.686875 | 0.656875 | -0.030000 |
| TechnicalScore | 0.765703 | 0.740677 | -0.025026 |

The candidate gained no sessions and lost `public_0080`, `public_0103`, and
`public_0183`. Boundary, Browsing, and Buying aggregates were unchanged, while
Intent Override fell from HitRate `0.916667` to `0.791667` and TechnicalScore
from `0.795729` to `0.628889`.

All four fixed folds regressed in TechnicalScore:

| Fold | HitRate delta | TechnicalScore delta |
| --- | ---: | ---: |
| fold_1 | 0.000000 | -0.020125 |
| fold_2 | 0.000000 | -0.017375 |
| fold_3 | -0.025000 | -0.020999 |
| fold_4 | -0.050000 | -0.041604 |

Operationally, the candidate produced 694 responses with zero response
exceptions, invalid payloads, reported fallbacks, or token usage. Its failure
is a quality-gate failure, not a reliability failure.

## Revert verification

The candidate commit is `1cd1f05`; the explicit revert is `19657e0`. After the
revert, the runtime tree matches the A13-1 starting runtime and Development-160
returned exactly to HitRate `0.925000`, MRR `0.552760`, MTTC `4.131250`,
Efficiency `0.686875`, and TechnicalScore `0.765703`.

Tests run during the decision:

- candidate focused A-side suite: 82 passed;
- candidate full suite: 305 passed;
- reverted runtime full suite: 304 passed;
- hash/metric decision-evidence suite: 5 passed.
- final full suite including evidence tests: 309 passed.

The exact commands, input hashes, full commit identifiers, report hashes,
scenario data, fold deltas, and operational counters are machine-checked in
[`a13_1_state_override_evidence.json`](a13_1_state_override_evidence.json) and
[`test_a13_1_state_override_evidence.py`](../tests/test_a13_1_state_override_evidence.py).
Raw reports are in [`a13_1_reports/`](a13_1_reports/).

## Taxonomy caveat

The offline taxonomy can still report `inactive_value_present_in_query` when an
old overridden instance and a newly reasserted active instance normalize to the
same text. This audit ambiguity did not determine the decision: evaluator
metrics, fold consistency, and gained/lost sessions already require rejection.
It is isolated as an evidence limitation rather than another runtime change.

## Keep / revert recommendation and next gate

- Keep the candidate and revert commits plus this evidence, so the failed
  mechanism is reproducible and is not retried blindly.
- Keep the reverted `0.925` runtime as the A13 Shadow comparator.
- Do not activate this state-reset candidate in A13-S0 or A13-C1.
- A13-S0 may now begin with offline types, fake backend, validator, local gate,
  fallback, diagnostics, and disabled/no-key parity. A real API run remains
  gated by a frozen ambiguity fixture and its review protocol.
