# B11 Lexical Recall Prerequisite Evidence

## Decision

Do not start a B11 behavior experiment. The current Development-160 R0 refresh
does not show lexical recall as a dominant primary failure cause, which is the
explicit prerequisite in the B-side roadmap.

This is a prerequisite disposition, not a claim that recall is perfect. Three
of 160 targets never entered the retained lexical pool, but all 22 current miss
sessions were classified first as upstream control-plane failures.

## Current Development-160 audit

The audit ran at clean commit `6cf3948` using current A-side behavior and the
retained structured retriever so evaluator-only target ranks could be compared
with the lexical Candidate Pool. It did not change runtime behavior.

| Measure | Value |
| --- | ---: |
| Sessions | 160 |
| Hit sessions | 138 |
| Miss sessions | 22 |
| Retrieval/ranking primary causes | 0 |
| Control-plane primary causes | 22 |
| Retained-depth target recall | 157/160 = 0.98125 |
| Targets absent from retained pool | 3 |

Primary causes were intent/strategy routing `16`, extraction `4`, and state
override `2`. Fold miss counts were 5, 6, 4, and 7; no fold produced a
retrieval/ranking primary-cause bucket.

## Why B11 is skipped

B11 would change a single lexical-recall variable such as product-text fields,
query normalization, synonyms, internal depth, or multi-query union. The
roadmap permits that only when R0 shows candidate-pool misses are the dominant
cause. Here, recall is high and the three absent targets are secondary to
earlier diagnosed failures. Widening retrieval now would add cost and noise
without addressing the primary bucket.

No B11 candidate was created, no runtime route changed, and no folds were spent
on behavior selection because the entry gate failed.

## Data boundary

Only Development-160 and its fixed fold assignment were used. Target ASIN and
target rank were evaluator-side offline inputs only; the report contains no
target ASIN values, and no target field entered Agent state, `RetrievalRequest`,
Strategy, runtime diagnostics, rules, or models. Full-200 and the exposed
40-session holdout were not run.
