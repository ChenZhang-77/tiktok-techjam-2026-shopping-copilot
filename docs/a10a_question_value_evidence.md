# A10a Candidate Question Value — Rejected Experiment

## Decision

Reject and revert candidate `304a3d6`. Runtime commit `7a63ef2` restores the
pre-A10a question policy. The candidate preserved whether the Agent asks and
preserved feature-first behavior; only after feature was unavailable did it use
the full Candidate-pool partition score before the existing Top-K fallback.

No query construction or shared A/B contract changed. The rule used no target,
scenario, hit/miss, or evaluator label at runtime.

## Development-160 Result

| Metric | AB0 baseline | A10a candidate | Delta |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.7625 | 0.75625 | -0.00625 |
| MRR | 0.529812 | 0.520012 | -0.009800 |
| MTTC | 5.3500 | 5.3625 | +0.0125 |
| Efficiency | 0.56500 | 0.56375 | -0.00125 |
| Technical score | 0.653194 | 0.646879 | -0.006315 |

No session was gained and `public_0064` was lost. Intent Override scenario
score fell `0.026473`; Browsing fell `0.005859`; Buying fell `0.000312`.
Boundary improved `0.0025`, which does not offset the overall regression. The
candidate failed the overall gate, so folds were not run.

## Evidence Coverage Audit

The current A-side Candidate vocabulary has comparable partition evidence only
for `category`, `material`, `color`, `style`, and `use_case`. It has no
equivalent value for `feature`, `size`, `brand`, `budget`, or `other`.
Consequently a global ranking would compare supported attributes with missing
attributes as if missing meant low value. The tested candidate avoided that
largest error by keeping feature first, but even its narrower full-pool change
regressed the retained baseline.

Do not add B-owned product-field semantics to `Candidate.diagnostics`
unilaterally. A10a can be reconsidered only after A11 provides comparable
A-owned extraction evidence or AB1 coordinates a typed/ranged/fallback B
diagnostic for the missing attributes.

## Evidence Boundary and Next Step

The hash-bound evaluator reports do not include per-turn selection diagnostics,
so no exact selection-count claim is retained. The clean metric regression is
sufficient for rejection. Holdout and Full-200 were not run.

Proceed to **A10b Internal QueryPlan**. It remains A-owned, must emit the
existing single `RetrievalRequest.query`, and must not change the question
policy. Machine-readable evidence is in `docs/a10a_question_value_evidence.json`.
