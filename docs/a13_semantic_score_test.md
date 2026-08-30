# A13-F1 — isolated semantic-understanding score test

Predeclared 2026-08-31 from `6a6ee51`, after reporting B10b-F1. The user asks
to proceed to semantic testing, prioritizing competition score under the
deadline. This is a separate opt-in experimental test, not passage of the
deferred formal AI-silver / A13-C1 gates. No packaging work is authorized here.

## Frozen recipe

- Current default B9, normal QuestionPolicy, zero profile weight, unchanged
  catalog/evaluator/runtime source. No B10b reranking or A14 selection.
- Only the existing `low_confidence_residual_feature` trigger is eligible.
  One Flash call per eligible turn, no retries; never call from evaluator labels.
- Use existing UnderstandingRequest/Delta validation. Send only bounded current
  message, minimal active/rejected/no-preference state, relevant allowed values
  and deterministic override flag. No profiles, IDs, target, scenario, future
  reply, Candidate products or evaluator data. Current message <=2000 chars,
  state <=2000 chars, vocabulary <=200 items, encoded payload <=16000 bytes.
- `deepseek-v4-flash`, non-thinking, temperature 0, JSON, max512 output tokens.
  Transport in an isolated child process with a 2.4-second wait cap and the
  existing Agent request's 2.5-second deadline; no late
  proposal can enter the Agent. Response <=65536 bytes. Reject redirects.
- Locally validate the entire delta before use. Intent hint must be null and
  semantic_terms empty. Preserve parser rows with confidence >0.35. A proposed
  conflicting value/rejection/no-preference against those rows rejects the full
  delta. Protect prior rejected/no-preference values from positive resurrection.
  On a useful compatible delta, replace only low-confidence residual feature
  rows, merge evidence-backed proposals (confidence .85 is a fixed ordinal,
  not a model probability), and leave the existing state writer/override rule
  in charge. Abstain/error/invalid/no-key changes no parsed fields.
- Use an isolated Agent subclass at the existing pre-state Shadow hook; only
  parsed input lists change in Candidate mode, never direct SessionState writes.
  Public test seams: Agent.respond and SemanticInterpreter.interpret.
- Total test budget <=300 attempted calls, $1 conservative cost estimate,
  20 minutes; stop after three consecutive provider failures or auth failure.
  Invalid semantic proposals are separately counted and never called success.

## Measurement and decision

Run default baseline, real-provider Shadow, then Candidate on fixed
Development-160/four folds. Warm the same default local retriever once using
a synthetic query before evaluation to reduce cold-start timing noise; retain
all per-turn upstream fallback diagnostics. Shadow must preserve visible,
state/query/strategy behavior (usage/latency excluded). Candidate may change
state, query and questions as downstream consequences of understanding; do not
require Candidate parity, which would prohibit the intended treatment.

Candidate starts only if Shadow parity holds, no upstream retrieval failures,
>=95% eligible proposals validate, provider failure <=2%, and at least one
compatible non-abstaining proposal changes the counterfactual state. The state
comparison includes provenance/confidence metadata; it is not semantic accuracy.
No prompt changes after results.
Repeat Candidate with fresh API calls only if it passes: positive overall
TechnicalScore, nondecreasing HR/MRR, at least 3/4 nonregressing folds, no
scenario loss >.01, <=2% provider errors, >=95% valid proposals, provider p95
<=2 seconds, no upstream failures, schema/state-invariant violations or budget
stop. Retention requires the same direction on repeat; defaults never auto-switch.

Report fixed denominators, gained/lost sessions, actual state changes, safe
token/cost/latency/fallback telemetry and source/input hashes. Semantic validity
is not semantic accuracy; no independent-gold claim. If no useful effect or
negative score, stop this recipe and report, without widening its permissions.

## Result

Completed on 2026-08-31 at clean source `29bef26`. The user authorized the
separate semantic test after B10b-F1; the existing local credential was reused,
never copied or printed. No prompt/model/threshold change occurred during the run.
See [bound result and independent QA](a13_semantic_score_result.json).

**Decision: stop this recipe before Candidate; no default promotion.** The
Shadow safety/utility gate fails because only 60/67 proposals validate (89.55%,
required >=95%). This is not evidence that a Candidate lowered or failed to
raise the score: no Candidate or repeat was executed. Shadow is deliberately
behavior-inert, so equal scores establish parity, not semantic efficacy.

| Measurement | Default B9 | Real-provider Shadow |
| --- | ---: | ---: |
| Development sessions / turns | 160 / 649 | 160 / 649 |
| HitRate@10 | 0.925000 | 0.925000 |
| MRR | 0.554521 | 0.554521 |
| MTTC | 4.131250 | 4.131250 |
| TechnicalScore | 0.766231 | 0.766231 |
| API attempts / provider failures | 0 / 0 | 67 / 0 |

- 60 valid returns: 56 abstentions and 4 compatible non-abstaining proposals.
  Four counterfactual state differences, **zero applied turns** in Shadow.
- Seven invalid returns: four `value_evidence_mismatch`, three `bad_value`.
  These are successful API responses rejected locally, not API outages.
- Exact whole-behavior parity on all 649 turns, identical 160 session outcomes,
  and all four fold/scenario results identical. Gained/lost sessions: 0/0.
- No upstream retrieval fallback, state/question invariant violations,
  response exceptions, invalid response payloads, or budget stop.
- Provider-path latency: mean 1.155 s, p95 1.816 s, maximum 2.050 s.
  Token usage: 67,326 input + 3,550 output; no unknown-usage calls.
- Conservative peak/cache-miss estimate: **$0.03430944**, not an invoice.
  Same official [pricing](https://api-docs.deepseek.com/quick_start/pricing/)
  and [non-thinking setting](https://api-docs.deepseek.com/guides/thinking_mode/)
  checked for B10b-F1 on 2026-08-31: $0.44/M input, $1.32/M output.
  Requested and returned identity: `deepseek-v4-flash`.

Scope matters: this tests only low-confidence residual-feature interpretation
with conservative evidence/allowed-value checks. It neither measures general
semantic accuracy nor rules out other LLM approaches. Under the deadline,
leave this recipe inactive; the stronger next score opportunity is resolving
B10b-F1's paired-retrieval parity issue before any further paid reranking run.
Do not loosen these semantic gates after seeing results or restart AI-silver.

## Reproduction and audit

At the frozen source and with the existing pinned local assets:

```bash
../shopping-copilot/.venv/bin/python -m experiments.a13_semantic_score \
  --execute --output experiments/runs/a13-f1-20260831
```

This is the historical paid command, not permission to rerun. Raw baseline,
Shadow, provenance, final provider journal and summary remain in the ignored
run directory. The tracked result binds their hashes and source/input hashes,
plus all sessions/folds needed to recompute the reported metrics. Journal
`final_disposition` events, if present, replace the indicated `record_index`;
they must not be counted as additional API calls or token usage.

Independent QA recomputed overall, fold and scenario metrics from session
outcomes, matched the journal to the final semantic ledger, verified all raw,
source and input hashes, and confirmed exact trace parity. No holdout was run.
Standards/Spec review found deadline acceptance and journal-error/late-disposition
edge cases before paid execution; all were fixed and re-reviewed with synthetic
regressions. Final suite: **440 passed**, including bound-evidence validation.
Production Agent, evaluator, catalog, shared contracts, defaults and submission
packaging remain unchanged.
