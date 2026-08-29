# A13-0 Baseline and Refreshed Taxonomy Evidence

## Decision

Keep A13-0 as an offline-only evidence and taxonomy-tooling change. It binds the
current `0.925` Development-160 comparator to a clean commit and removes the
stale mechanism that translated a dominant Question Policy class directly into
`next_experiment=A9`.

The taxonomy now reports only the dominant failure class, owner, investigation
direction, and `docs/optimization_roadmap.md` as the experiment-selection
authority. Historical R0 and A9 evidence remains unchanged. A9 is still a
rejected and reverted ablation, not the current next step.

## Git and scope

- Starting branch / HEAD: `a/a13-llm-semantic-understanding` / `3a5fbea`.
- Runtime source commit: `0bd3375`.
- Clean comparator commit: `b86a9e7`.
- Comparator change: `experiments/failure_taxonomy.py` and its focused test
  only; no Agent runtime file changed.
- Shared request/result schema, Strategy weights, B-side retrieval/ranking,
  Question Policy, evaluator, catalog, and public labels are unchanged.
- DeepSeek calls: 0. Full-200/Holdout-40 runs: 0.

## Bound inputs

| Input | SHA256 |
| --- | --- |
| `data/catalog.jsonl` | `da979b05a68af864cb0dcf9ee6a81c010c7e66a57978ad286c7a2e005fc69a67` |
| `data/public_set.jsonl` | `857259f7a438e6188ac63e18995b6ff4489bfcfc4a716a798b9a2aa0ee8f7579` |
| `docs/public_split_v1.json` | `98171487d3416ff97989e98aeca145b87df74337c5edbe7c908dd80afc538c50` |
| `docs/development_folds_v1.json` | `d9219a4be4533c4f99156197d03e19e6512ce57b262944a201f8605244ccd78d` |
| `docs/evaluation_config.json` | `8ee0c899ddc68d521754cf9d2f239a8bc09851fb37c5872567160c30d431aa53` |
| `evaluator/local_evaluator.py` | `c21e10a6e772c4824d85f513f0d7d53d23942d20ec9eb3853ff49119317ef96f` |
| `evaluator/splits.py` | `36858b99678befd8e4740b6c31a9e33f429330be38e74d9ca3eb002916fc47a3` |
| `experiments/failure_taxonomy.py` | `2eab725c0a4d58d6f1e50014fab25d7860cfc85f4a1b68b121a04e7408096f60` |

The catalog contains 50,000 rows and 50,000 unique `parent_asin` values. The
200 public samples reproduce the checked-in 160/40 split exactly. The four
Development folds reproduce their deterministic manifest exactly and contain
40 sessions each. The 40 exposed sessions were counted from the manifest but
were not evaluated.

## Development-160 result

| Metric | Result |
| --- | ---: |
| HitRate@10 | 0.925000 |
| MRR | 0.552760 |
| MTTC | 4.13125 |
| Efficiency | 0.686875 |
| TechnicalScore | 0.765703 |

The run produced 649 responses with zero response exceptions, invalid response
payloads, reported fallbacks, prompt tokens, and completion tokens. The clean
run recorded mean response latency `25.06 ms`, p95 `47.82 ms`, initialization
`1.55 s`, and process peak RSS `581,320,704` bytes. These are observations from
this run, not a new behavior comparison.

Scenario results:

| Scenario | Samples | HitRate@10 | MRR | MTTC | TechnicalScore |
| --- | ---: | ---: | ---: | ---: | ---: |
| Boundary | 8 | 1.000000 | 0.601190 | 5.750000 | 0.785357 |
| Browsing | 64 | 0.921875 | 0.518180 | 4.109375 | 0.754204 |
| Buying | 64 | 0.921875 | 0.516828 | 3.625000 | 0.763486 |
| Intent Override | 24 | 0.916667 | 0.724653 | 5.000000 | 0.795729 |

Fixed-fold results:

| Fold | Samples | HitRate@10 | MRR | MTTC | TechnicalScore |
| --- | ---: | ---: | ---: | ---: | ---: |
| fold_1 | 40 | 0.925000 | 0.485724 | 4.075000 | 0.746717 |
| fold_2 | 40 | 0.900000 | 0.624504 | 4.575000 | 0.765851 |
| fold_3 | 40 | 0.950000 | 0.595585 | 3.650000 | 0.800675 |
| fold_4 | 40 | 0.925000 | 0.505228 | 4.225000 | 0.749568 |

## Refreshed failure taxonomy

All 12 misses were behavior-classified with no evaluation-validity flag:

| Primary class | Misses | Scenarios |
| --- | ---: | --- |
| Question Policy | 10 | Browsing 5; Buying 5 |
| State / Override | 2 | Intent Override 2 |

Fold miss counts are `3 / 4 / 2 / 3`. The two State / Override misses are
`public_0002` and `public_0096`, both with
`override_old_value_still_active`. The ten Question Policy misses record four
or five explicitly unproductive replies. The retained-depth lexical pool
contains the target in 158/160 sessions (`0.9875`), and Retrieval / Ranking has
zero primary misses.

This is offline Development evidence. Target rank and hit/miss were used only
inside the audit. The tracked evidence contains sample IDs and causal summaries
but no target ASIN or ground-truth value.

## Stale recommendation disposition

`failure_taxonomy.py` previously encoded a historical map from
`question_policy` to A9. That map drifted after A9 was measured, rejected, and
reverted. Schema `r0-v3` replaces `next_experiment` with
`next_investigation`; it does not assign a stage ID.

The refreshed audit's dominant class is Question Policy, but the reviewed
dependency order remains:

```text
A13-0 -> A13-1 deterministic State / Override -> A13-S0 Shadow
        -> review gate -> A13-C1 or No-Go -> A14 Question Policy
```

Therefore the smallest allowed next stage is A13-1. A13-S0 remains
unauthorized until the user confirms and A13-1 has its own keep/revert decision.

## Verification

Focused protocol, taxonomy, historical-evidence, and complete test suites pass.
The exact commands and run-artifact hashes are recorded in
`docs/a13_0_baseline_evidence.json`.

## Keep / revert recommendation

Keep. The change removes a misleading offline stage-ID claim, preserves all
historical evidence, and binds the current comparator without changing Agent
behavior. Revert only if review finds that a downstream consumer requires the
old generated `next_experiment` field; no such current consumer was found.
