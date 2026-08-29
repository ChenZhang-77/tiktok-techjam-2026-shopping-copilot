# R0 Development Failure Taxonomy

This is an offline-only Development analysis. Target ranks were used only
inside the audit and no target identifier is written to this report or any
runtime request/diagnostic.

## Outcome

- Sessions: 160
- Hits: 148
- Miss sessions: 12
- Behavior-classified misses: 12
- Invalid misses left unclassified: 0
- Control Plane primary causes: 12
- Retrieval / Ranking primary causes: 0

## Experiment record

- **ID / owner:** R0 / shared offline diagnostics
- **Primary behavior change:** none; offline analysis only
- **Hypothesis:** Development-160 misses are dominated by an upstream canonical failure class that can select the next smallest experiment.
- **Comparator:** retained structured Development-160 baseline, same runtime
- **Gained / lost sessions:** 0 / 0; no runtime behavior comparator
- **Latency / memory / fallback impact:** unchanged at runtime
- **Keep gate:** complete fixed-fold Development evidence, canonical causes,
  and no target leakage or runtime behavior change
- **Revert gate:** any target leakage, holdout/full selection, runtime change,
  or non-reproducible fold assignment
- **Decision:** Retain offline audit tooling and evidence; follow the roadmap
  dependency order

## Primary causes

| Cause | Misses |
| --- | ---: |
| extraction | 0 |
| state_override | 2 |
| intent_strategy_routing | 0 |
| query_construction | 0 |
| question_policy | 10 |
| retrieval_recall | 0 |
| ranking_filtering | 0 |
| response_contract | 0 |

## Fold consistency

- **fold_1**: samples=40, misses=3; question_policy=3
- **fold_2**: samples=40, misses=4; question_policy=3, state_override=1
- **fold_3**: samples=40, misses=2; question_policy=2
- **fold_4**: samples=40, misses=3; question_policy=2, state_override=1

## Scenario breakdown

- **browsing**: question_policy=5
- **buying**: question_policy=5
- **intent_override**: state_override=2

## Target recall from retained lexical pools

| Depth | Hits | Observable sessions | Recall |
| --- | ---: | ---: | ---: |
| retained depth | 158 | 160 | 0.987500 |
| 10 | 123 | 160 | 0.768750 |
| 30 | 146 | 160 | 0.912500 |
| 60 | 156 | 160 | 0.975000 |
| 80 | 149 | 152 | 0.980263 |
| 100 | 107 | 109 | 0.981651 |
| 120 | 51 | 51 | 1.000000 |

## Recommended next investigation

- **Dominant failure class:** question_policy
- **Owner:** control_plane
- **Direction:** diagnose the current question-policy mechanism
- **Experiment-selection authority:** `docs/optimization_roadmap.md`

The taxonomy deliberately does not assign a stage ID. The roadmap owns
dependency order and the current experiment selection.

## Example misses

- **state_override**: public_0002 (override_old_value_still_active), public_0096 (override_old_value_still_active)
- **question_policy**: public_0016 (unproductive_replies:5), public_0020 (unproductive_replies:4), public_0054 (unproductive_replies:4), public_0076 (unproductive_replies:4), public_0083 (unproductive_replies:5)

## Interpretation limits

- The taxonomy is deterministic evidence triage, not a learned causal model.
- `question_policy` requires direct evidence such as repeated or explicitly
  unproductive customer replies.
- `extraction` requires disclosed target-card evidence to be absent from active,
  rejected, and overridden structured-state evidence. Query preservation does not
  retroactively make an unrecognized constraint extracted.
- `state_override` is reserved for stale or incorrectly removed state.
- `intent_strategy_routing` covers an explainably wrong intent/Strategy after
  extraction and state have been checked.
- `query_construction` requires extracted active evidence to be omitted or
  inactive evidence to be made positive in the distilled query.
- Remaining misses are separated by whether the target entered the retained
  Candidate Pool (`ranking_filtering`) or did not (`retrieval_recall`).
