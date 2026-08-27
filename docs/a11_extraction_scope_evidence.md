# A11 Extraction and Scope Hardening Evidence

## Decision

Retain the reviewed bounded A11 candidate at clean runtime code commit
`c50e69f`; the earlier R0 tracing fix remains in its history at `b0c953d`. The
retained change is deterministic, A-owned, and
keeps the existing `RetrievalRequest.query` contract and clarification policy.

The retained scope is intentionally smaller than the original A11 list:

- derive multi-word category phrases from the frozen catalog;
- prevent `I'm`, model/dimension numbers, and hyphenated phrases such as
  `low-top` from becoming false size/category constraints;
- separate positive, negative, and no-preference clauses before extraction;
- keep comma-delimited negative and no-preference lists inside their clause,
  while preventing catalog phrases from crossing punctuation or masked spans;
- preserve a category head as positive context when a same-attribute modifier
  list is rejected, and support controlled ASCII/Unicode possessive boundaries;
- use the same supported attribute inventory for positive and rejected
  constraints, including explicit brand and budget evidence;
- recognize `use_case` and `other` no-preference replies;
- derive catalog context from the actual injected catalog-backed retriever and
  reject an explicitly conflicting catalog path.

Broad catalog feature extraction, catalog brand matching, low-confidence
feature expiry, and QueryPlan residual cleanup are not retained. The combined
broad candidate at `0589799` regressed Development-160 to HR `0.725`, MRR
`0.479085`, MTTC `5.6125`, and score `0.613976`. That report supports rejecting
the combination only; no independent hash-bound report isolates the effect of
each component. Their individual effects therefore remain unproven. The
existing A10b residual renderer remains unchanged.

## Development-160 result

| Metric | A10b baseline | A11 retained | Delta |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.762500 | 0.862500 | +0.100000 |
| MRR | 0.529812 | 0.545568 | +0.015756 |
| MTTC | 5.350000 | 4.675000 | -0.675000 |
| Efficiency | 0.565000 | 0.632500 | +0.067500 |
| Technical score | 0.653194 | 0.721420 | +0.068226 |

There are 19 gained sessions and 3 lost sessions. No response exception,
invalid payload, or fallback was observed. No Full-200 or holdout run was used.

## Fixed-fold gate

| Fold | Baseline score | A11 score | Delta |
| --- | ---: | ---: | ---: |
| fold_1 | 0.608196 | 0.714592 | +0.106396 |
| fold_2 | 0.683092 | 0.729780 | +0.046688 |
| fold_3 | 0.691051 | 0.761646 | +0.070595 |
| fold_4 | 0.630435 | 0.679664 | +0.049229 |

All four fixed folds improve in technical score. This is the decisive keep
gate. Earlier exploratory components were removed before this clean retained
run; their individual effects were not preserved as independent hash-bound
evidence.

## Scenario trade-off

Buying and Intent Override improve strongly, Browsing improves modestly, and
Boundary regresses in technical score by `0.057083`. Boundary HitRate remains
`0.875`, while MRR falls and MTTC is `0.625` turns worse. This eight-session
slice is a known risk and must not be hidden by the aggregate result.

## Updated offline failure audit

The target-aware audit remains offline-only. It uses Development targets to
classify misses and writes no target ASIN into runtime state, requests,
diagnostics, configuration, or this summary.

- Misses: `38 -> 22`
- Primary Extraction misses: `6 -> 4`
- Remaining primary causes: Extraction `4`, Intent / Strategy Routing `16`,
  State / Override `2`

The Extraction-count reduction is not inconsistent with the aggregate score
gain: newly hit sessions can previously have downstream causal labels, and the
new category evidence also changes rank and time-to-correct behavior. Four
primary Extraction misses remain. Broader extraction alternatives lack
independent hash-bound evidence, so they remain open rather than being assigned
an isolated causal conclusion.

## Cost and compatibility

- Shared A/B schema: unchanged.
- Question policy: unchanged.
- Model/network/token cost: none.
- Initialization: `1320.31 ms -> 1569.28 ms` in the recorded runs.
- Peak RSS: approximately unchanged (`579,010,560 -> 578,469,888` bytes).
- Response latency is not directly comparable because A11 reaches correct
  products in fewer turns; no latency regression was observed in the report.

## Reproducible artifacts

- `docs/a11_extraction_scope_evidence.json`
- `docs/a11_reports/development_scoped_extraction.json`
- `docs/a11_reports/fold_1_scoped_extraction.json`
- `docs/a11_reports/fold_2_scoped_extraction.json`
- `docs/a11_reports/fold_3_scoped_extraction.json`
- `docs/a11_reports/fold_4_scoped_extraction.json`
- `docs/a11_reports/development_failure_audit.json`
- `docs/a11_reports/development_broad_extraction_rejected.json`

The next dependency-ordered module is AB1 Shared Contract and Active-Route
Semantics Freeze. B9 must not begin before AB1 closes that seam.
