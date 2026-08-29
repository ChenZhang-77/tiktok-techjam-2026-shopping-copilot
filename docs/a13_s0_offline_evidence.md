# A13-S0 Offline Shadow Foundation Evidence

## Decision

**Keep the offline Shadow foundation. Do not start a real DeepSeek run yet.**

The retained code adds the A-owned `SemanticInterpreter` seam, typed request and
delta objects, a deterministic fake backend, six-signal local trigger gate,
all-or-nothing validator, bounded input vocabulary, no-retry fallback, safe
diagnostics, and Shadow-only Agent injection. No semantic proposal is applied
to SessionState, Strategy, QueryPlan, clarification, retrieval, recommendations,
or the public response.

This is not a claim that DeepSeek semantic understanding is working. There is
no provider transport, no key read, no remote call, no pricing/model claim, and
no frozen human gold fixture in this stage.

## Development-160 parity

All three offline modes were run from clean commit `837214f` against the fixed
Development-160 split and the A13-0 input hashes:

| Mode | Backend calls | Valid fake deltas | Behavior mismatches | HitRate@10 | MRR | MTTC | TechnicalScore |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| disabled | 0 | 0 | 0 / 649 | 0.925000 | 0.552760 | 4.13125 | 0.765703 |
| no-key | 0 | 0 | 0 / 649 | 0.925000 | 0.552760 | 4.13125 | 0.765703 |
| fake abstain | 67 | 67 | 0 / 649 | 0.925000 | 0.552760 | 4.13125 | 0.765703 |

The local gate marked 67 of 649 turns eligible (`10.32%`), below the `20%`
candidate call-rate ceiling. On this evaluator dialogue distribution all 67
were `low_confidence_residual_feature`; the other five predefined trigger
classes therefore still require independent ambiguity fixtures and cannot be
judged from Development traffic alone.

Raw paired response dictionaries differ on all 649 turns because the comparator
and Shadow Agent each measure their own retrieval latency. The parity projection
removes only `latency_ms` and `stage_latencies_ms`; message, ask attribute,
recommendations, usage, state, Strategy, QueryPlan, retrieval route/candidates,
and fallback diagnostics are exact. Both raw and projected mismatch counts are
retained rather than hiding the timing difference.

## Validation and safety coverage

Tests cover:

- disabled, ineligible, no-key, fake, timeout, arbitrary exception, and input
  bound fallbacks;
- malformed types, missing/extra fields, illegal attributes and values,
  evidence-span mismatch, duplicate/conflicting fields, unsupported override,
  abstain conflict, and rejected/no-preference restoration;
- all six local trigger signals;
- one backend call at most per eligible turn and no retry;
- error-text, prompt, response, request-id, key, profile, session, and user-text
  exclusion from diagnostics;
- multi-session isolation and exact state/response/retrieval-request parity;
- catalog vocabulary capped at 200 items.

The final suite is 330/330, including four hash/metric evidence tests. Reports
and hashes are machine-checked by
[`test_a13_s0_offline_evidence.py`](../tests/test_a13_s0_offline_evidence.py).
Raw reports are in [`a13_s0_reports/`](a13_s0_reports/), and structured
provenance is in
[`a13_s0_offline_evidence.json`](a13_s0_offline_evidence.json).

## Scope boundary

- No Full-200 or exposed Holdout-40 run.
- No evaluator, catalog, Question Policy, B-side retrieval/ranking, shared
  contract, or route-weight semantic change.
- No DeepSeek transport or API call.
- No environment key read or logged secret.
- No LLM usage or cost claim.

## Next gate

Before any real API run, `experiments/fixtures/a13_ambiguity_v1.jsonl` must be
created under the reviewed protocol: at least 60 examples, at least 10 per
predefined trigger, at least 20 for any Candidate trigger, two members'
independent annotations, reconciliation, frozen schema/instructions, and a
recorded SHA256. The deterministic comparator must be scored before viewing LLM
results.

That two-member annotation/reconciliation requirement is not satisfiable by
silently generating labels in this coding session. Until the team completes and
signs off that fixture, `fixture_frozen=false`, `real_api_authorized=false`, and
DeepSeek must remain uncalled.
