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

Suggested experiment sequence:

1. `baseline-bm25`: reproduce official score.
2. `stateful-bm25`: use accumulated user messages across turns.
3. `slot-extraction`: extract material/color/size/style/brand/budget/use_case.
4. `metadata-rerank`: combine BM25 with structured field matching.
5. `adaptive-questions`: ask high-value attributes only when the candidate set is broad.
6. `embedding-retrieval`: add local embedding retrieval with an offline index.
7. `hybrid-rerank`: blend BM25, embeddings, metadata, and session state.
