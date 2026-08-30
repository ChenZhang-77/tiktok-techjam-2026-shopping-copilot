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

**Completed first full pass after explicit external-data authorization**, at
clean source `3045691`. The earlier blocked launch created no process or calls;
the coordinator then explicitly authorized the bounded official-API transfer.
No prompt, model, threshold, runtime source or evaluator changed during this run.

| Metric | Default B9 | Flash reranking | Delta |
| --- | ---: | ---: | ---: |
| Development sessions | 160 | 160 | 0 |
| HitRate@10 | 0.925000 | 0.925000 | 0 |
| MRR | 0.554521 | 0.597225 | +0.042704 |
| MTTC | 4.131250 | 4.131250 | 0 |
| TechnicalScore | 0.766231 | 0.779043 | +0.012812 |

Four fixed-fold score deltas: `+0.011241, +0.006804, +0.021355, +0.011846`.
All four scenario scores also improve: Boundary `+0.013750`, Browsing
`+0.017898`, Buying `+0.008973`, Intent Override `+0.009167`. Runtime Browsing
eligibility is inferred from the conversation, not the evaluator scenario label;
that is why a Browsing-only reranker can affect sessions labeled Buying.
There are 25 improved target ranks and one worsened rank, with zero gained or
lost hits. Both arms have 649 response turns; 317 turns were reordered.

### Real API execution and cost

- 412 real requests to the official DeepSeek endpoint; **zero API failures**.
  This means successful calls, not absence of API usage. Every response reported
  `deepseek-v4-flash`; the docs advertise Flash-0731 but the response alias does
  not independently establish that exact model revision.
- 733,782 prompt tokens and 18,128 completion tokens; all usage known and
  reconciled with public response usage. No failed-call unknown usage allowance.
- Conservative peak/cache-miss estimate: **$0.34679304**, not an invoice.
  Cached input/off-peak pricing may reduce the actual charge; the estimate uses
  [official prices](https://api-docs.deepseek.com/quick_start/pricing/).
- Provider latency: mean 0.799 s, median 0.785 s, p95 1.058 s. End-to-end
  response p95: baseline 0.062 s versus Candidate 1.104 s. This is added latency,
  not a speed improvement. No response exceptions or invalid payloads occurred.

### Important comparison caveat and disposition

The predeclared full gate **does not pass**: membership parity and question
parity fail. Each arm had one local `dense_latency_budget_exceeded` fallback
(not a DeepSeek failure). Across arms, ten turns differ in Top-10 membership
within two sessions (`public_0002`, `public_0181`); two questions differ in the
first of those sessions. The saved trace does not retain per-turn upstream
failure diagnostics, so do not assert an exact causal mapping of each timeout
to each difference. Within-call reranker membership preservation holds.

`public_0002` misses in both arms. `public_0181` hits at turn 7 in both arms,
with rank 3 -> 2. As an **ex-post sensitivity diagnostic only**, the other 158
sessions have equal turn keys, candidate membership and visible questions, and
still improve MRR by `+0.042189` / TechnicalScore by `+0.012657`. These matched
sessions contribute about `+0.012499` to the original full-160 score difference.
This supports a promising ranking signal but does not remove the two sessions
from the official comparison or replace the frozen gate with a favorable subset.

Decision: **keep the experiment available; do not promote it to the default**.
The full score and all folds improve, but strict attribution/repeatability is
not complete. The runner correctly stopped before the fresh-provider repeat;
there was no second Candidate pass or parameter sweep. A future promotion
needs a clean paired verification that controls local retrieval timing without
changing the ranking recipe or relaxing the original gate.

This first workstream is now reported. Semantic understanding is the separately
requested next experiment and has not been run. No A13/A14 behavior was added,
no Full/Holdout was evaluated, and no private competition-score gain is claimed.

### Verification and reproduction

[Bound result](b10b_full_rerank_result.json) retains all 160 session outcomes
per arm, four-fold/scenario metrics, source/input/raw-report hashes, token/cost
accounting and the independent audit. Raw full reports and the safe provider
journal are in `experiments/runs/b10b-f1-20260831/` (Git-ignored).
Independent validation recomputed metrics from ranks/hit turns, reconciled usage
and budget, checked unique Development coverage and every bound source hash,
and inspected the mismatched traces. Assessment: **share with caveats**.

Pre-run Standards/Spec review passed after fixing the transport-truncation
fallback. Post-run offline suite: 429 passed, including bound-evidence arithmetic
and source checks. The runtime/default and evaluator remain unchanged.

To reproduce, use a clean source commit and a fresh empty output directory.
This command makes new paid API requests; do not run it merely to inspect results:

```bash
../shopping-copilot/.venv/bin/python -m experiments.b10b_full_rerank \
  --execute --output experiments/runs/b10b-f1-20260831
```

Use a fresh empty output directory if this path already contains a previous
attempt. Never repeat an uncertain paid run without checking its provider
journal. Report the first workstream's result before semantic understanding;
the latter remains a separate subsequent experiment.
