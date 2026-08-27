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
taxonomy from `../AGENTS.md`, with the earliest causal stage as primary:

```text
Extraction -> State / Override -> Intent / Strategy Routing
-> Query Construction -> Question Policy -> Retrieval Recall
-> Ranking / Filtering -> Response / Contract
```

Record evaluator/timing anomalies separately as `evaluation_validity` flags.
The current optimization sequence is:

1. `r0-failure-taxonomy`: classify Development-160 failures offline without
   changing runtime behavior.
2. `a8-intent-assessment`: persist intent evidence, confidence, and transition
   reasons without mixing in extraction/scope work.
3. `ab0-decision-evidence`: prove the source, owner, lifecycle, and fallback of
   every proposed A9 input; keep ask behavior unchanged.
4. `a9-should-ask`: improve the ask-or-retrieve decision using only retained
   AB0 signals.
5. `a10a-question-value`: rank candidate questions without changing query
   construction.
6. `a10b-query-plan`: make A-side query construction state-aware and auditable
   while preserving the existing single query contract.
7. `a11-extraction-scope`: address only extraction failures demonstrated by R0.
8. `ab1-contract-freeze`: freeze any required shared fields and actual route
   semantics before B work.
9. `b8-rejected-constraints`: test confidence-gated negative evidence.
10. `b9-browsing-dense`: test a guarded Browsing-first dense route.
11. `b10-protected-rerank`: protect strong structured matches while reranking a
   bounded tail.

Run lexical recall or adaptive-depth work only if the R0 taxonomy supports it.
See `../docs/optimization_roadmap.md` and the A/B workstream documents for
hypotheses, dependencies, and keep/revert gates.
