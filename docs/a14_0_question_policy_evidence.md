# A14-0 Question Policy Parity Evidence

## Decision

Keep A14-0. The existing clarification decision now sits behind one total,
read-only `QuestionPolicy.decide(...)` entry point, and a target-free offline
turn audit binds the policy's Development-160 behavior. This slice changes no
recommendation, question, metric, shared retrieval contract, or state mutation
order.

A14-1 is the next allowed behavior-neutral slice. A14-S1 and every A14
Candidate remain blocked until the A13 human-fixture review has a recorded
disposition.

## Scope and interface

`Agent.respond` calls the Module after retrieval and before `response_guard`.
The Module owns same-snapshot `DecisionEvidence`, eligibility, the legacy
decision, canonical question rendering, bounded diagnostics, and complete
fallback. `record_agent_response` remains the only mutation that commits an
asked attribute to session state.

The retained implementation adds:

- `starter/core/question_policy.py` — total `QuestionPolicy`, decision/outcome
  types, legacy-parity decision, validation, and deterministic fallback;
- `starter/core/clarification.py::available_attributes` — one reusable
  eligibility source while preserving `choose_clarification` compatibility;
- `starter/agent.py` — one post-retrieval Question Policy call and bounded
  diagnostics;
- `experiments/a14_turn_audit.py` — fixed Development-160 trace capture,
  input binding, safe visible-response hashes, policy audit, and exact legacy
  comparator;
- focused policy, Agent, audit, and hash-bound evidence tests.

The public response never contains raw Candidate IDs/text, target data, or
model inputs. Policy latency is retained as offline tracer telemetry rather
than added to the response, because nondeterministic timing would break exact
response parity.

## Independent visible-response comparator

The legacy trace was captured from a clean detached worktree at `2e4108a`.
Only safe hashes of the public message, `ask_attribute`, and recommendation
list were retained. The current trace was captured at clean runtime commit
`f594601` with the same catalog, public dataset, split/fold manifests,
evaluation config, and evaluator sources.

| Check | Result |
| --- | ---: |
| Development sessions | 160 |
| Compared turns | 649 |
| Session-shape mismatches | 0 |
| Turn-shape mismatches | 0 |
| `ask_attribute` mismatches | 0 |
| Message mismatches | 0 |
| Recommendation-list mismatches | 0 |
| Input hashes match | yes |
| Metric parity | exact |

Both traces have visible-response SHA256
`098afbdf9b1ce3c0813ccb311b90432837e8b3ac7f36ed78248fe2fef3a75146`.
The richer target-free Question Policy trace has SHA256
`7bb6c838ccfd9e2820ce26cb1c5b852610c4413a381b51752cc911fc857584de`.

## Turn audit

| Observation | Count |
| --- | ---: |
| Ask decisions | 587 |
| Stop decisions | 62 |
| Unproductive replies | 226 |
| New-active-evidence outcomes | 155 |
| No-preference outcomes | 234 |
| Other responses after a question | 69 |
| Repeated/ineligible/known/final-turn/output violations | 0 |

All 649 decisions had valid retrieval evidence in this run. Question Policy
latency was mean `2.987 ms`, p95 `4.653 ms`, and max `5.876 ms`. These timings
are local observations, not a performance guarantee.

The current legacy policy selected eight attributes in this fixed trace:
brand 21, color 78, feature 132, material 65, other 48, size 57, style 102,
and use case 84. This does **not** establish complete comparable evidence for
all allowed attributes; proving explicit source/status/missing-data behavior
for all ten belongs to A14-1.

## Development and fixed-fold parity

| Scope | HitRate@10 | MRR | MTTC | Efficiency | TechnicalScore |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development-160 | 0.925000 | 0.552760 | 4.13125 | 0.686875 | 0.765703 |
| fold_1 | 0.925000 | 0.485724 | 4.075 | 0.692500 | 0.746717 |
| fold_2 | 0.900000 | 0.624504 | 4.575 | 0.642500 | 0.765851 |
| fold_3 | 0.950000 | 0.595585 | 3.650 | 0.735000 | 0.800675 |
| fold_4 | 0.925000 | 0.505228 | 4.225 | 0.677500 | 0.749568 |

The standard Development report records 649 responses with zero response
exceptions, invalid response payloads, reported fallbacks, internal fallbacks,
or token usage. No Full-200 or exposed-Holdout evaluation was run.

## Safety and fallback review

- malformed policy state returns a coherent guarded stop instead of failing
  `Agent.respond`;
- invalid retrieval evidence rebuilds safe empty evidence and preserves the
  legacy selection path;
- selector/rendering errors are caught at the Module boundary;
- duplicate recommendation IDs retain the legacy text projection exactly;
- an ask must be eligible, non-final-turn, and have canonical non-empty text;
- response diagnostics expose closed statuses/reasons only;
- A13 no-key/disabled semantic-interpreter parity remains intact;
- no LLM or provider call was made.

## Reproduction and evidence binding

The machine-readable record is `docs/a14_0_question_policy_evidence.json`.
It SHA-binds all inputs, four runtime/audit sources, the clean legacy trace,
current turn audit, Development report, and four fixed-fold reports. The
matching evidence test derives parity, metrics, reliability, scope, trace
completeness, and leakage checks from those files.

Core commands:

```bash
../shopping-copilot/.venv/bin/python -m experiments.a14_turn_audit \
  --baseline docs/a14_0_reports/legacy_visible_trace.json \
  --output /private/tmp/a14-0-turn-audit.json
../shopping-copilot/.venv/bin/python -m experiments.evaluation_reporting \
  --split development --structured-filter \
  --output /private/tmp/a14-0-development.json
../shopping-copilot/.venv/bin/python -m unittest \
  tests.test_a14_0_question_policy_evidence \
  tests.test_question_policy tests.test_a14_turn_audit tests.test_agent_smoke -v
../shopping-copilot/.venv/bin/python -m unittest discover -s tests -v
```

The focused evidence/policy/audit/Agent run passed 34 tests. The complete
repository suite passed 365 tests after the evidence and navigation updates.

## Next decision

Proceed only to A14-1 complete attribute-evidence coverage while keeping the
returned action, question, recommendations, and metrics unchanged. Do not
start A14-S1, A14-C1, an LLM teacher/advisor, or an ask/stop change before the
A13 review gate is closed and the new slice has its own reviewed evidence.
