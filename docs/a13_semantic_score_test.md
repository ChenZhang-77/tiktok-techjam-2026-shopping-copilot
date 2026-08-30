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
compatible non-abstaining proposal exists. No prompt changes after results.
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

Pending implementation/review/execution. Reuse the existing local key; never
copy or print it. Expected changes: this record, an isolated experiment module,
synthetic tests, eventual bound evidence and the minimal status/navigation set.
