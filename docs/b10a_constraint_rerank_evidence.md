# B10a Constraint-Preserving CrossEncoder Evidence

## Decision

Do not enable B10a in the default runtime. The corrected Top-3 candidate, a
single-variable Top-5 follow-up, all four Top-3 folds, and a B9-default parity
run were evaluated at clean commit `93b5b19`. Both candidates failed the
predeclared MRR and TechnicalScore gate. The current default remains B9.

The local CrossEncoder adapter and `--constraint-preserving-rerank` evaluation
mode remain only to reproduce the ablation. This is a learned reranker, not an
LLM ranker, and does not close Track 4's LLM Semantic Ranking gap.

## Tested behavior

- base route: retained B9 conditional dense;
- pinned model: `cross-encoder/ms-marco-MiniLM-L2-v2` at revision
  `1b5cd67b15209f24824c50370e0397743aa9b787`;
- initial protected prefix: Top 3;
- reranked tail: ranks 4-30;
- follow-up protected prefix: Top 5, with every other variable unchanged;
- blend: `0.35` retained base score plus `0.65` normalized semantic-rank signal;
- base score uses `fusion_score` or structured `ranking_score` when available;
- an exact high-confidence persisted rejection match cannot move ahead of a
  non-contradicted candidate, including A's real `active=false` record shape;
- an explicit hard match stays ahead of neutral unknown evidence, while missing
  evidence remains neutral and is never labeled a contradiction;
- `no_preference` and a current positive preference suppress stale rejection
  influence;
- model failure returns the exact pre-rerank order;
- runtime model access is local-only.

## Development-160 result

| Metric | B9 baseline | Top 3 | Delta | Top 5 | Delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| HitRate@10 | 0.862500 | 0.875000 | +0.012500 | 0.868750 | +0.006250 |
| MRR | 0.547329 | 0.515952 | -0.031377 | 0.524025 | -0.023304 |
| MTTC | 4.668750 | 4.543750 | -0.125000 | 4.543750 | -0.125000 |
| Efficiency | 0.633125 | 0.645625 | +0.012500 | 0.645625 | +0.012500 |
| TechnicalScore | 0.722074 | 0.721411 | -0.000663 | 0.720708 | -0.001366 |

Top 3 changed 74 of 160 session outcomes, gained seven hits, and lost five.
Its fold TechnicalScore deltas were `-0.008925`, `+0.020312`, `-0.028262`,
and `+0.014223`: two wins and two losses. Because Top 5 already failed the
aggregate gate, it was not eligible for fold selection and no additional folds
were spent on it.

## Operational cost

The Top-3 run executed semantic reranking on all 707 retrieval turns, always
with a 27-candidate tail. Mean semantic-rerank latency was `68.82 ms`, p95 was
`72.41 ms`, and the cold-start maximum was `2032.46 ms`. Overall retrieval mean
and p95 were `93.05 ms` and `114.99 ms`. The reported `1.100 GB` peak RSS is
the evaluator parent process only; it excludes the spawned CrossEncoder worker,
so worker and total process-tree peak memory are unavailable. There were zero
route failures, response exceptions, invalid payloads, or tokens.

## Default parity and data boundary

At `93b5b19`, the default `--conditional-dense` route exactly reproduced the B9
aggregate metrics, scenario metrics, and all 160 session outcomes. The shared
request contract and Agent policy were not changed.

Only Development-160 and its four fixed folds were used. Target information
was used only by the offline evaluator for comparisons; no target ASIN, target
rank, hit/miss, scenario label, or future utterance entered Agent state,
`RetrievalRequest`, routing, ranking, or runtime diagnostics. The exposed
40-session holdout and Full-200 were not run.

## Consequence for B10b

Do not escalate to a more expensive actual LLM ranker without new R0 evidence.
The cheaper bounded learned reranker already failed its ranking-quality gate
and added material latency. B10b should therefore be recorded as not justified,
not silently presented as completed LLM Semantic Ranking.
