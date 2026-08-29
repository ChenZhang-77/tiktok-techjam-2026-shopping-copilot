# R0 Development Failure Taxonomy

This is an offline-only Development analysis. Target ranks were used only
inside the audit and no target identifier is written to this report or any
runtime request/diagnostic.

## Outcome

- Sessions: 160
- Hits: 145
- Miss sessions: 15
- Behavior-classified misses: 15
- Invalid misses left unclassified: 0
- Control Plane primary causes: 15
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
| state_override | 0 |
| intent_strategy_routing | 1 |
| query_construction | 3 |
| question_policy | 11 |
| retrieval_recall | 0 |
| ranking_filtering | 0 |
| response_contract | 0 |

## Fold consistency

- **fold_1**: samples=40, misses=3; question_policy=3
- **fold_2**: samples=40, misses=4; question_policy=4
- **fold_3**: samples=40, misses=3; query_construction=1, question_policy=2
- **fold_4**: samples=40, misses=5; intent_strategy_routing=1, query_construction=2, question_policy=2

## Scenario breakdown

- **browsing**: question_policy=5
- **buying**: question_policy=5
- **intent_override**: intent_strategy_routing=1, query_construction=3, question_policy=1

## Target recall from retained lexical pools

| Depth | Hits | Observable sessions | Recall |
| --- | ---: | ---: | ---: |
| retained depth | 154 | 160 | 0.962500 |
| 10 | 117 | 160 | 0.731250 |
| 30 | 141 | 160 | 0.881250 |
| 60 | 152 | 160 | 0.950000 |
| 80 | 145 | 152 | 0.953947 |
| 100 | 109 | 115 | 0.947826 |
| 120 | 53 | 53 | 1.000000 |

## Recommended next investigation

- **Dominant failure class:** question_policy
- **Owner:** control_plane
- **Direction:** diagnose the current question-policy mechanism
- **Experiment-selection authority:** `docs/optimization_roadmap.md`

The taxonomy deliberately does not assign a stage ID. The roadmap owns
dependency order and the current experiment selection.

## Example misses

- **intent_strategy_routing**: public_0080 (buying_to_browsing_without_exploration)
- **query_construction**: public_0002 (inactive_value_present_in_query:leather), public_0103 (inactive_value_present_in_query:cotton), public_0183 (inactive_value_present_in_query:polyester)
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
