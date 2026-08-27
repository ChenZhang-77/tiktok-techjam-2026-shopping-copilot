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

The one Full-200 Final Public Run has already occurred. Do not run
`--split full` again during optimization and do not use it to select behavior. See
`docs/adr/0001-treat-public-holdout-as-exposed.md`.

Offline Development-160 analysis may use target ASIN, hit/miss, and target rank
to distinguish Retrieval Recall from Ranking / Filtering. Those fields must
never enter Agent state, requests, Strategy, runtime diagnostics, prompts,
rules, or models. Do not use Full-200 or the exposed holdout for diagnosis-led
tuning.

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

## Development Result

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
implemented experimental routes should be enabled. Use the canonical R0
taxonomy from `../AGENTS.md`, with the earliest causal stage as primary. Record
evaluator/timing anomalies separately as `evaluation_validity` flags.
The current experiment is `r0-failure-taxonomy`; it changes no runtime behavior.
The authoritative dependency order is maintained only in
`../docs/optimization_roadmap.md`. Use the selected A/B workstream for its
hypothesis, inputs, tests, and keep/revert gate. Do not copy the full sequence
into an experiment note.
