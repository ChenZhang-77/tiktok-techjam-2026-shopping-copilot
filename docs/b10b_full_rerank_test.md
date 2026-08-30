# B10b-F1 — Complete DeepSeek ranking comparison

## Frozen experiment, 2026-08-31

The coordinator explicitly requested complete product-reranking testing first,
semantic-understanding testing second, with a report between them. This run
does not activate A13 or the A14 selection pilot. Base commit: `f128f85`.

- Comparator: current Agent, default B9 ConditionalDenseRetriever, existing
  pinned local model/vector cache, normal QuestionPolicy, profile weight zero.
- Candidate: `deepseek-v4-flash`, non-thinking, temperature zero, JSON output,
  256 output tokens, 8-second transport timeout, no retries. One call per
  eligible Browsing turn, at least two existing Top-10 products, no degraded
  upstream retrieval. Do not expand the Candidate set.
- This is a guarded new B10b trial, not an exact repeat of historical DS1:
  use the current Distilled Query, at most 12 bounded active constraints,
  existing Candidate evidence truncated to 700 characters, and turn-local
  aliases `c0`…`c9`. Do not send product IDs, sample IDs, targets, labels,
  profiles, future replies, or evaluator internals to the provider.
- Preserve all original Top-10 members, and every Candidate outside Top-10.
  Reorder only within identical high-confidence hard-match/rejected-match
  profiles from existing B-side diagnostics; profiles retain their original
  positions. Unknown metadata is neutral. No new constraint scorer or A/B
  schema. Apply ordering at the retrieval seam so response/history stay coherent.
- Invalid permutations, timeout, provider errors and no key preserve exact
  original Candidate order. Report fallback truthfully; do not swallow failures
  as successful calls. Upstream fallback remains unchanged.
- Actual provider usage enters response usage and the report. Failed calls with
  unavailable usage reserve a conservative request-size/output-cap cost bound.
  Fixed budgets: at most 1,400 attempted requests and $3 charged-cost estimate/
  conservative unknown-call allowance across this experiment, plus 30 minutes.
  Stop provider calls after three consecutive errors, auth failure, or budget.
- Run the fixed Development-160 baseline and one real-provider Candidate pass.
  If complete and reliability/score gates pass, repeat that exact Candidate once
  with fresh provider requests. No prompt/model/threshold sweep. Partition all
  results by the existing four fixed folds; do not call these unseen tests.
- Retention recommendation needs positive TechnicalScore and non-declining MRR,
  unchanged HitRate and MTTC, at least three non-regressing folds, no scenario
  loss >0.01, <=2% provider failure, p95 provider latency <=5 seconds, zero invalid
  accepted permutations or Top-10 membership changes, and the same direction on
  repeat. Otherwise reject or report inconclusive; do not auto-change defaults.

Official API configuration/pricing references checked on 2026-08-31:
[models/pricing](https://api-docs.deepseek.com/quick_start/pricing/) and
[thinking toggle](https://api-docs.deepseek.com/guides/thinking_mode/).
Conservative peak/cache-miss prices: $0.44/M input and $1.32/M output tokens.
Report advertised model/version separately from the API's response identity.

## Implementation and verification

Reuse the approved Retriever.retrieve, SemanticRanker.rank and Agent.respond
seams. Work is isolated under `experiments/`; production sources, evaluator,
catalog and the default Agent are unchanged. Synthetic tests cover exact
fallback, prefix membership, hard-profile preservation, alias-only requests,
usage reporting, and budgets. Full suite and Standards/Spec review precede the
final report. Credentials are reused from the local project environment file;
never print, copy into the repository, or commit them.

Expected files: `experiments/b10b_full_rerank.py`, focused tests, this record,
hash-bound results and small authoritative status/navigation updates.

## Result

Pending external-data authorization, not a negative result. The 2026-08-31
execution request was rejected by safety review before process creation:
the coordinator must explicitly approve sending runtime shopping queries,
up to 12 active constraints and up to 10 truncated catalog-evidence texts to
`https://api.deepseek.com/chat/completions`, with the above $3 estimate cap.
No provider calls, charges, baseline pass, or Candidate measurement occurred
in this attempt. Do not bypass this approval gate.

The isolated runner and nine synthetic regressions are implemented. Full
offline suite: 428 passed. Standards review found a truncated-HTTP-response
failure-accounting gap; a reproduced RED test now passes after catching
transport exceptions at the paid boundary. Spec review found no other issue.
No production/default changes or publication occurred.

After explicit authorization and a clean source commit, run from repository root:

```bash
../shopping-copilot/.venv/bin/python -m experiments.b10b_full_rerank \
  --execute --output experiments/runs/b10b-f1-20260831
```

Use a fresh empty output directory if this path already contains a previous
attempt. Never repeat an uncertain paid run without checking its provider
journal. Report the first workstream's result before semantic understanding;
the latter remains a separate subsequent experiment.
