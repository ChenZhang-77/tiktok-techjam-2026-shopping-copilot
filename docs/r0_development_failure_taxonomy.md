# R0 Development Failure Taxonomy

This is an offline-only Development analysis. Target ranks were used only
inside the audit and no target identifier is written to this report or any
runtime request/diagnostic.

## Outcome

- Sessions: 160
- Hits: 122
- Misses classified: 38
- Control Plane primary causes: 38
- Retrieval / Ranking primary causes: 0

## Primary causes

| Cause | Misses |
| --- | ---: |
| extraction | 37 |
| state_override | 0 |
| intent_strategy_routing | 1 |
| query_construction | 0 |
| question_policy | 0 |
| retrieval_recall | 0 |
| ranking_filtering | 0 |
| response_contract | 0 |

## Fold consistency

- **fold_1**: samples=40, misses=11; extraction=11
- **fold_2**: samples=40, misses=9; extraction=9
- **fold_3**: samples=40, misses=8; extraction=7, intent_strategy_routing=1
- **fold_4**: samples=40, misses=10; extraction=10

## Scenario breakdown

- **boundary**: extraction=1
- **browsing**: extraction=11, intent_strategy_routing=1
- **buying**: extraction=18
- **intent_override**: extraction=7

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

**A11** — harden extraction and clause scope.

This recommendation is evidence-ranked but still subject to the dependency
order in `docs/optimization_roadmap.md`.

## Example misses

- **extraction**: public_0002 (disclosed_value_not_extracted:100 leather), public_0011 (disclosed_value_not_extracted:100 cotton), public_0016 (disclosed_value_not_extracted:imported), public_0020 (disclosed_value_not_extracted:color grey), public_0022 (disclosed_value_not_extracted:fabric 100 cotton soft comfy breathable and keep you cool)
- **intent_strategy_routing**: public_0037 (buying_to_browsing_without_exploration)

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
