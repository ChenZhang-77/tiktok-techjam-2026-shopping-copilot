# Experiments

Use this folder for team experiment notes. Do not commit large generated artifacts.

Run ordinary experiments on the fixed development split:

```bash
./scripts/start_experiment.sh experiment-name --split development
```

The 40-session public holdout is already exposed because the A-side baseline was
run on all 200 sessions before B-stage development. Do not use `--split holdout`
for B-stage selection. Use the four deterministic folds in
`docs/development_folds_v1.json` for cross-validation within the 160-session
Development Set.

Use `--split full` exactly once after the complete B configuration is frozen.
That Final Public Run is for non-confirmatory reporting and must not trigger
further tuning. See `docs/adr/0001-treat-public-holdout-as-exposed.md`.

Rebuild and validate the fold manifest with:

```bash
python3 -m experiments.development_folds
```

Run one validation fold without touching the Exposed Holdout:

```bash
./scripts/start_experiment.sh b1-parity-fold-1 --split development --fold fold_1
```

Repeat with `fold_2`, `fold_3`, and `fold_4`. A retained experiment must report
all four results; the ordinary unsuffixed development run remains the 160-session
aggregate comparison against `docs/b0_development_baseline.json`.

Recommended note format:

```markdown
# YYYY-MM-DD Experiment Name

## Hypothesis

## Change

## Command

## Public Score

- HitRate@10:
- MRR:
- MTTC:
- TechnicalScore:

## Scenario Breakdown

- Buying:
- Browsing:
- Intent Override:
- Boundary:

## Notes
```

The original B1-B7 build sequence is complete. Do not restart it or assume that
implemented experimental routes should be enabled. The current optimization
sequence is:

1. `r0-failure-taxonomy`: classify misses as state, question, query, recall,
   ranking, or timing failures without changing behavior.
2. `a8-state-confidence`: repair state/scope errors and expose stable confidence.
3. `a9-question-value`: improve the ask-or-retrieve decision.
4. `a10-query-builder`: make query construction state-aware and auditable.
5. `ab1-contract-freeze`: freeze shared diagnostics and route semantics.
6. `b8-rejected-constraints`: test confidence-gated negative evidence.
7. `b9-conditional-semantic`: route semantic help only to justified buckets.
8. `b10-protected-rerank`: protect strong structured matches while reranking a
   bounded tail.

Run lexical recall or adaptive-depth work only if the R0 taxonomy supports it.
See `../docs/optimization_roadmap.md` and the A/B workstream documents for
hypotheses, dependencies, and keep/revert gates.
