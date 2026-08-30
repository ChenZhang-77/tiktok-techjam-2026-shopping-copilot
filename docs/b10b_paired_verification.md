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

Result: pending. No new provider request has been sent at declaration.
