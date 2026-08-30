# A14-1 Complete Attribute Evidence Coverage

## Decision

Keep A14-1. Every Question Policy decision now carries one explicit evidence
record for each of the ten allowed attributes while returning the exact legacy
question, message, and recommendations. Missing, partial, uncalibrated,
degraded, and not-applicable evidence are no longer represented by an absent
map key or interpreted as zero Question Value.

This completes the behavior-neutral A14 preparation that is permitted before
the A13 review gate. Stop here: A14-S1, A14-C1, LLM teacher/advisor work, and
ask/stop behavior remain blocked until the A13 human-fixture review has a
recorded disposition.

## Retained contract

`AttributeQuestionEvidence` records:

- attribute and evidence status;
- evidence source, current-turn/full-pool lifecycle, and numeric range;
- Candidate coverage, bounded value count, and rank-weighted split when the
  evidence family is comparable;
- answerability and actionability status;
- comparability family;
- eligibility plus its explicit reason;
- missing-data behavior.

Status vocabulary is closed:

```text
available | partial | unavailable | uncalibrated | degraded | not_applicable
```

Eligibility is separate from evidence health. An attribute may have available
Candidate evidence but be satisfied, already asked, excluded by the legacy
intent priority, or blocked on the final turn. This prevents “not eligible”
from being confused with “no evidence.”

The Module computes the existing full-pool partition score and the new bounded
coverage/split record in one pass, then passes the unchanged score into
`DecisionEvidence`. `choose_clarification` still returns the legacy action.

## Source and coverage decision

| Attribute | Development status | Source / interpretation |
| --- | --- | --- |
| category | available on 649/649 turns | bounded Candidate vocabulary; comparable only within `bounded_candidate_vocabulary_v1` |
| material | available on 649/649 turns | same bounded family |
| color | available on 649/649 turns | same bounded family |
| style | available on 649/649 turns | same bounded family |
| use_case | available on 649/649 turns | same bounded family |
| feature | uncalibrated on 649/649 turns | Candidate evidence is unstructured; generic text diversity is not treated as a value partition |
| size | unavailable on 649/649 turns | no field-tagged Candidate evidence at the A-side seam |
| brand | unavailable on 649/649 turns | no field-tagged Candidate evidence at the A-side seam |
| budget | unavailable on 649/649 turns | no field-tagged Candidate evidence at the A-side seam |
| other | not applicable on 649/649 turns | controlled legacy fallback; no comparable partition by definition |

“Available” here proves that the declared bounded source and measurement are
present. It does not prove that the attribute produces a useful answer or that
values from different evidence families may be compared. `partial` and
`degraded` are covered by focused fixtures even though neither occurred in the
clean Development run.

The existing extractor can consume answers for size, brand, and budget, but
that does not manufacture Candidate-side separation evidence. Those attributes
therefore remain eligible under the legacy policy while their evidence record
correctly says `unavailable` and `preserve_legacy_action`.

## Exact behavior and metrics

The clean final A14-1 runtime/audit source commit is `c6fb8e5`. The standard
Development/fold reports were captured at clean behavior commit `4f615f4`;
the final clean 649-turn audit at `c6fb8e5` independently reproduces their
metrics and exact visible trace. Against the independent
legacy visible trace captured at `2e4108a`:

| Check | Result |
| --- | ---: |
| Sessions | 160 |
| Compared turns | 649 |
| Session/turn-shape mismatches | 0 / 0 |
| Message mismatches | 0 |
| Recommendation-list mismatches | 0 |
| `ask_attribute` mismatches | 0 |
| Policy violations | 0 |

The visible-response trace remains
`098afbdf9b1ce3c0813ccb311b90432837e8b3ac7f36ed78248fe2fef3a75146`.
The A14-1 semantic Question Policy trace digest is
`032d4c897f29b06efda53977341a1867cf562d621692039e97dedd2bdaa586ed`.
It excludes only operational latency and reproduced exactly in four independent
clean runs whose latency summaries differed. The complete bounded 649-turn,
ten-attribute trace is retained at `docs/a14_1_reports/turn_audit.json`; the
evidence test validates every field and derives the published status and
eligibility counts from it.

| Scope | HitRate@10 | MRR | MTTC | Efficiency | TechnicalScore |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development-160 | 0.925000 | 0.552760 | 4.13125 | 0.686875 | 0.765703 |
| fold_1 | 0.925000 | 0.485724 | 4.075 | 0.692500 | 0.746717 |
| fold_2 | 0.900000 | 0.624504 | 4.575 | 0.642500 | 0.765851 |
| fold_3 | 0.950000 | 0.595585 | 3.650 | 0.735000 | 0.800675 |
| fold_4 | 0.925000 | 0.505228 | 4.225 | 0.677500 | 0.749568 |

The Development report records 649 responses and zero response exceptions,
invalid payloads, reported fallbacks, internal fallbacks, or token usage. No
Full-200 or exposed-Holdout run was performed.

## Cost

Question Policy compilation observed mean `9.647 ms`, p95 `15.546 ms`, and max
`21.164 ms`. A14-0's separate local run observed mean `2.987 ms` and p95
`4.653 ms`; the non-paired differences are about `+6.660 ms` mean and
`+10.893 ms` p95. The A14-1 standard Development report observed overall
response mean `33.797 ms` and p95 `58.919 ms`.

These local sequential timings are noisy and are not a paired causal estimate.
The absolute policy cost is retained as acceptable for this evidence-only
slice, but later selection work should reuse these compiled records rather
than rescan Candidate text.

## Safety and missing-data behavior

- no raw Candidate ID/text, target, ground truth, user profile, scenario rule,
  or evaluator reply rule enters policy diagnostics;
- the complete Question Policy diagnostics and each attribute record reject
  unknown fields before projection; source/status/family, lifecycle/range,
  answerability/actionability, and eligibility use closed vocabularies and relations;
- coverage/split values are either null or bounded to `[0, 1]`; value count is
  null or a non-negative integer;
- bounded `available` requires at least two covered Candidates and at least two
  values;
- partial/unavailable/uncalibrated/degraded evidence always preserves the
  exact legacy action;
- retrieval or attribute-compiler failure returns a complete ten-record safe
  fallback rather than failing `Agent.respond`;
- no shared contract, B-side route meaning, state mutation order, parser,
  retriever, or model was added;
- LLM calls: 0; Full/Holdout runs: 0.

## Evidence and verification

`docs/a14_1_attribute_evidence.json` records the decision, inputs, source
snapshot, raw-report hashes, coverage, parity, metrics, folds, latency, and
gate. `docs/a14_1_reports/turn_audit.json` is the complete bounded per-turn
evidence; `coverage_audit.json` is its retained summary; the adjacent
Development/fold reports are standard evaluator outputs. The evidence test
validates every per-turn field/range/semantic and derives all published values
from those files. Historical source hashes are checked against their pinned Git
blobs rather than the later live files.

```bash
../shopping-copilot/.venv/bin/python -m experiments.a14_turn_audit \
  --baseline docs/a14_0_reports/legacy_visible_trace.json \
  --output /private/tmp/a14-1-turn-audit.json
../shopping-copilot/.venv/bin/python -m experiments.evaluation_reporting \
  --split development --structured-filter \
  --output /private/tmp/a14-1-development.json
../shopping-copilot/.venv/bin/python -m unittest \
  tests.test_a14_1_attribute_evidence tests.test_question_policy \
  tests.test_a14_turn_audit tests.test_agent_smoke -v
../shopping-copilot/.venv/bin/python -m unittest discover -s tests -v
```

The focused A14-1 evidence/policy/audit/Agent run passed 39 tests. The complete
repository suite passed 375 tests after evidence and navigation synchronization.

## Next gate

Do not auto-open A14-S1 merely because evidence coverage is complete. A13's
human fixture still has to be independently annotated, reconciled, and given a
recorded provider/Candidate or No-Go disposition. After that gate, A14-S1 may
compute a deterministic proposed attribute in Shadow while returning this
unchanged legacy action. A14-C1 remains a separate later decision.
