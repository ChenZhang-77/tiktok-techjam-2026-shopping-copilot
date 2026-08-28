# R0 Development Failure Taxonomy

This is an offline-only Development analysis. Target ranks were used only
inside the audit and no target identifier is written to this report or any
runtime request/diagnostic.

## Outcome

- Sessions: 160
- Hits: 122
- Miss sessions: 38
- Behavior-classified misses: 38
- Invalid misses left unclassified: 0
- Control Plane primary causes: 38
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
| extraction | 6 |
| state_override | 7 |
| intent_strategy_routing | 25 |
| query_construction | 0 |
| question_policy | 0 |
| retrieval_recall | 0 |
| ranking_filtering | 0 |
| response_contract | 0 |

## Fold consistency

- **fold_1**: samples=40, misses=11; extraction=1, intent_strategy_routing=8, state_override=2
- **fold_2**: samples=40, misses=9; extraction=2, intent_strategy_routing=6, state_override=1
- **fold_3**: samples=40, misses=8; extraction=2, intent_strategy_routing=5, state_override=1
- **fold_4**: samples=40, misses=10; extraction=1, intent_strategy_routing=6, state_override=3

## Scenario breakdown

- **boundary**: extraction=1
- **browsing**: extraction=4, intent_strategy_routing=8
- **buying**: extraction=1, intent_strategy_routing=17
- **intent_override**: state_override=7

## Target recall from retained lexical pools

| Depth | Hits | Observable sessions | Recall |
| --- | ---: | ---: | ---: |
| retained depth | 145 | 160 | 0.906250 |
| 10 | 111 | 160 | 0.693750 |
| 30 | 131 | 160 | 0.818750 |
| 60 | 141 | 160 | 0.881250 |
| 80 | 140 | 158 | 0.886076 |
| 100 | 106 | 121 | 0.876033 |
| 120 | 1 | 1 | 1.000000 |

## Recommended next experiment

**A8** — stabilize intent assessment before B routing.

This recommendation is evidence-ranked but still subject to the dependency
order in `docs/optimization_roadmap.md`.

## Example misses

- **extraction**: public_0016 (disclosed_value_not_extracted:imported), public_0026 (disclosed_value_not_extracted:100 synthetic), public_0100 (disclosed_value_not_extracted:manmade sole), public_0153 (disclosed_value_not_extracted:rubber sole), public_0170 (disclosed_value_not_extracted:made in the usa or imported)
- **state_override**: public_0002 (override_old_value_still_active), public_0071 (override_old_value_still_active), public_0089 (override_old_value_still_active), public_0096 (override_old_value_still_active), public_0103 (override_old_value_still_active)
- **intent_strategy_routing**: public_0011 (buying_to_browsing_without_exploration), public_0020 (buying_to_browsing_without_exploration), public_0022 (buying_to_browsing_without_exploration), public_0028 (buying_to_browsing_without_exploration), public_0037 (buying_to_browsing_without_exploration)

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
