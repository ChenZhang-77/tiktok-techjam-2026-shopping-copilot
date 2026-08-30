# B10b-F2 — bounded paired verification for Plan Two

Predeclared 2026-08-31 from `5475b2b`. The user asks whether the ranking
benefit can be verified now. LLM remains Plan Two; this is a bounded close-out
test, not a return to LLM-led optimization or authorization to change defaults.

## Diagnosis and frozen intervention

The original F1 trace deterministically reproduces 10 membership differences
in two sessions. Baseline took 29.20 s and Candidate 368.14 s. The old evidence
cannot map the individual dense timeout events to exact changed turns.

Ranked hypotheses, with observable predictions:

1. First eligible-query initialization affects the acceptance budget: warming
   one synthetic query before both arms should remove first-turn differences.
2. Steady-state scheduling still breaches the unchanged dense budget: new
   per-turn diagnostics would show fallback even after prewarm.
3. Ranking changes subsequent dialogue inputs: request fingerprints would
   diverge despite equal upstream results up to the first changed request.

Only execution setup/measurement changes: construct the real default B9
retriever once, warm one synthetic browsing query, reuse it for all arms.
No cached/replayed answers, acceptance-budget relaxation, retries, parameter
sweep, target-conditioned rule, production edits or evaluator edits.
Each arm still executes actual retrieval for every current Agent request.

Keep F1 ProductReranker, prompt/model/temperature/token cap, eligibility,
constraint protection and score/reliability gates byte-for-byte unchanged.
The existing public seams are Retriever.retrieve and Agent.respond. Add an
identity observation wrapper before reranking: hash the whole request excluding
random session ID, and whole ordered result excluding measured latency fields;
retain actual route/fallback/latency telemetry per turn. Do not send these
additional observations to DeepSeek.

## Sequence, gates, stop conditions

1. Fixed Development-160 baseline and placebo, both no-LLM. Require exact
   input/upstream-result fingerprints, visible traces and session outcomes,
   full coverage, zero upstream failure and zero invalid responses/exceptions.
2. Only if step 1 passes and external transfer is authorized, run one real
   Candidate. Besides every original F1 gate, require input/upstream-result
   fingerprint parity and zero upstream fallback.
3. If Candidate passes, repeat with fresh API requests. Each paid arm must
   separately pass against the same baseline. Otherwise stop, with no retuning.

Bounds across paid arms: 900 attempted requests, $1 conservative allowance,
20 minutes from first paid call; original 8-second transport timeout, no retry,
three-consecutive-error/auth stop. Expected paid cost about $0.35 per pass from
F1, not a guarantee or invoice. Existing local key stays local. Only bounded
distilled query/active constraints and aliased candidate text reach the official
DeepSeek endpoint, exactly as authorized for F1; no profiles, targets, labels,
sample/product IDs or future turns. Do not launch a second validation recipe
if this one fails. Infrastructure/preflight failure is inconclusive, not a
negative ranking-effect estimate. Missing approval permits offline work only.

Retention means verified opt-in Plan Two only, never automatic default activation.
No hidden-set generalization claim. Keep full 160-session denominators/four
fixed folds, report each pass, gained/lost hits/ranks, latency/cost/fallback,
source/input/raw hashes. One-time synthetic prewarm is not proof of robust cold
startup on other machines; report that limitation. Hypotheses are not proven
causes merely because the new prewarmed run succeeds.

## Scope and verification

Expected changes: isolated `experiments/b10b_paired_rerank.py`, synthetic tests,
this record, eventual bound evidence and minimal current-status/navigation
updates reflecting main offline Plan One and optional LLM Plan Two.
Use existing sibling Python/model/vector caches. Offline tests:

```bash
../shopping-copilot/.venv/bin/python -m unittest tests.test_b10b_paired_rerank -q
../shopping-copilot/.venv/bin/python -m unittest discover -s tests -q
```

## Result — verified optional Plan Two

Completed at clean runner source `c6b1a45` on 2026-08-31. The separate offline
preflight passed with zero paid calls. After authorized external transfer, the
execution run again passed baseline/placebo, then completed Candidate and a
fresh-provider repeat. No prompt, model, threshold or acceptance budget changed.
[Bound evidence and independent QA](b10b_paired_verification_result.json).

| Metric | Baseline / placebo | Candidate | Fresh repeat |
| --- | ---: | ---: | ---: |
| Sessions / turns | 160 / 649 | 160 / 649 | 160 / 649 |
| HitRate@10 | 0.925000 | 0.925000 | 0.925000 |
| MRR | 0.554521 | 0.597225 | 0.597746 |
| MTTC | 4.131250 | 4.131250 | 4.131250 |
| TechnicalScore | 0.766231 | 0.779043 | 0.779199 |
| Score delta | — | +0.012812 | +0.012968 |
| API calls | 0 | 413 | 413 |
| Estimated cost USD | 0 | 0.34736196 | 0.34736196 |

Both paid arms pass all original F1 gates and additional full-input/upstream
pairing gates. Every arm has identical request and entire pre-rerank ordered
pool/evidence/diagnostic fingerprints, excluding measured latency only. Questions,
Top-10 membership and turn coverage match; there are zero upstream/API failures,
response exceptions, invalid payloads, or budget stops. Each paid arm improves
25 session target ranks and worsens one; gained/lost hits are 0/0.

Four-fold score deltas:

- Candidate: `+0.011241, +0.006804, +0.021355, +0.011846`.
- Repeat: `+0.011866, +0.006804, +0.021355, +0.011846`.

All four scenario scores improve in both passes. They are repeated development
measurements, not independent unseen folds or a hidden-test guarantee. Between
the two paid passes, 62 turns have different recommendation order; only one
session outcome differs (`public_0125`, best rank 6 -> 4, same hit turn 4).
Temperature zero therefore does not imply identical output. The predeclared
repeat condition was repeated gate passage, not exact ranking determinism.

Total: **826 calls, $0.69472392 conservative estimate**, all usage known.
Each pass reports 734,943 input and 18,172 output tokens. Requested and returned
model is `deepseek-v4-flash`; no stronger immutable-version claim is made.
Price assumptions are inherited unchanged from F1, not a provider invoice.

Provider-path p95 is **1.146 s / 1.609 s**, maximum **2.014 s / 7.318 s**.
End-to-end response p95 is **0.068 s baseline, 1.195 s Candidate, 1.544 s repeat**.
The 7.3-second tail is a real deployment tradeoff, not hidden by a good p95.
Actual evaluation durations: baseline 25.0 s, placebo 24.8 s, Candidate
400.4 s (6m40s), repeat 454.4 s (7m34s): about **15m05s** for the four arms,
excluding model setup, the separate 48-second preflight, preparation and review.

Decision: retain as **verified optional Plan Two**, not the default. The score
gain is about 1.7% relative and improves ordering, not HitRate/MTTC. Plan One
remains the local/no-external-LLM main delivery route; A13 stays inactive.
No more paid rounds or tuning are authorized by this result. Future packaging
would still need declared opt-in configuration, fallback and environment tests.
This run does not establish cold-start reliability on other machines or prove
the unique cause of the original F1 timing differences.

## Audit and reproduction

Source, input and every raw artifact hash were independently checked. Overall,
fold and scenario metrics were recomputed from per-session ranks/hit turns;
the 826 journal rows match both arms' provider ledgers and cost totals. Raw
artifacts remain in ignored `experiments/runs/b10b-f2-20260831/`; the zero-call
preflight is in `experiments/runs/b10b-f2-preflight-20260831/`. Bound evidence
retains sessions, folds, source/input/raw hashes and QA without credentials.

Historical commands (the second incurs new charges; do not rerun automatically):

```bash
../shopping-copilot/.venv/bin/python -m experiments.b10b_paired_rerank \
  --offline --output experiments/runs/b10b-f2-preflight-20260831
../shopping-copilot/.venv/bin/python -m experiments.b10b_paired_rerank \
  --execute --output experiments/runs/b10b-f2-20260831
```

Reproduction requires a new empty output directory and the pinned existing
model/vector cache. Synthetic observer tests preserve actual results, retain
failures and ignore only measured latency in fingerprints. Bound-evidence
regression independently checks arithmetic, frozen source and decision logic.
Full suite: **443 passed**. Standards/Spec reviews pass with no open findings.
Production Agent, F1 implementation, evaluator, catalog, shared contracts and
submission packaging remain unchanged. No Git push was performed.
