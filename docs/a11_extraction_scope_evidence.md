# A11 Extraction and Scope Hardening Evidence

## Decision

Retain the bounded A11 candidate at runtime code commit `4ed5560`, with the R0
tracing fix at `b0c953d`. The retained change is deterministic, A-owned, and
keeps the existing `RetrievalRequest.query` contract and clarification policy.

The retained scope is intentionally smaller than the original A11 list:

- derive multi-word category phrases from the frozen catalog;
- prevent `I'm`, model/dimension numbers, and hyphenated phrases such as
  `low-top` from becoming false size/category constraints;
- separate positive, negative, and no-preference clauses before extraction;
- recognize `use_case` and `other` no-preference replies;
- preserve catalog context when the evaluation harness injects a real
  catalog-backed retriever.

Broad catalog feature extraction, catalog brand matching, low-confidence
feature expiry, and QueryPlan residual cleanup are not retained. The broad
candidate at `0589799` regressed Development-160 to HR `0.725`, MRR `0.479085`,
MTTC `5.6125`, and score `0.613976`. Subsequent ablation showed that feature
expiry and broad feature vocabulary were unsafe. The existing A10b residual
renderer remains unchanged.

## Development-160 result

| Metric | A10b baseline | A11 retained | Delta |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.762500 | 0.881250 | +0.118750 |
| MRR | 0.529812 | 0.534308 | +0.004496 |
| MTTC | 5.350000 | 4.381250 | -0.968750 |
| Efficiency | 0.565000 | 0.661875 | +0.096875 |
| Technical score | 0.653194 | 0.733292 | +0.080098 |

There are 22 gained sessions and 3 lost sessions. No response exception,
invalid payload, or fallback was observed. No Full-200 or holdout run was used.

## Fixed-fold gate

| Fold | Baseline score | A11 score | Delta |
| --- | ---: | ---: | ---: |
| fold_1 | 0.608196 | 0.711342 | +0.103146 |
| fold_2 | 0.683092 | 0.749810 | +0.066718 |
| fold_3 | 0.691051 | 0.770167 | +0.079116 |
| fold_4 | 0.630435 | 0.701851 | +0.071416 |

All four fixed folds improve in technical score. This is the decisive keep
gate; the earlier candidate with feature expiry failed fold 4 and was removed.

## Scenario trade-off

Buying and Intent Override improve strongly, Browsing improves modestly, and
Boundary regresses in technical score by `0.039896`. Boundary HitRate remains
`0.875` and MTTC improves by `0.75`, but rank quality falls. This eight-session
slice is a known risk and must not be hidden by the aggregate result.

## Updated offline failure audit

The target-aware audit remains offline-only. It uses Development targets to
classify misses and writes no target ASIN into runtime state, requests,
diagnostics, configuration, or this summary.

- Misses: `38 -> 19`
- Primary Extraction misses: `6 -> 5`
- Remaining primary causes: Extraction `5`, Intent / Strategy Routing `12`,
  State / Override `2`

The small Extraction-count reduction is not inconsistent with the large score
gain: many newly hit sessions previously had downstream causal labels, and the
new category evidence also changes rank and time-to-correct behavior. The five
remaining Extraction misses are dominated by catalog feature phrases such as
material composition, sole/shaft details, and care instructions. Broadly
enabling those phrases failed the clean Development gate, so they remain open.

## Cost and compatibility

- Shared A/B schema: unchanged.
- Question policy: unchanged.
- Model/network/token cost: none.
- Initialization: `1320.31 ms -> 1569.08 ms` in the recorded runs.
- Peak RSS: approximately unchanged (`579,010,560 -> 578,355,200` bytes).
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
