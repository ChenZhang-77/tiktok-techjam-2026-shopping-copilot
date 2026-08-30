# Project Structure and File Placement

## Verdict

The repository is not structurally chaotic. Runtime code, evaluation code,
experiments, tests, and presentation tooling already have clear top-level
boundaries. The main source of visual complexity is the large body of
hash-bound experiment evidence under `docs/`.

That evidence is intentionally kept rather than compressed or renamed:
machine-readable records, raw reports, tests, and Markdown decisions refer to
one another by stable path and hash. Moving them only for cosmetic symmetry
would create broad churn and make old results harder to reproduce.

## Top-Level Responsibilities

```text
starter/        scored Agent, Control Plane, retrieval, and ranking runtime
evaluator/      official deterministic evaluator; do not tune or modify it
experiments/    Development split, reporting, folds, and offline diagnostics
tests/          behavior, contract, fallback, and evidence verification
scripts/        catalog, cache, experiment, and visualizer entry points
visualizer/     local debugging/demo interface, outside the scored dependency
submission/     minimal independently runnable final-package staging area
data/           official public data plus ignored frozen catalog download
docs/           project state, plans, decisions, and experiment evidence
```

Root Markdown files have distinct roles:

| File | Responsibility |
| --- | --- |
| `README.md` | Public project entry, setup, architecture, and measured results |
| `AGENTS.md` | Stable operating, safety, ownership, and evaluation rules |
| `CONTEXT.md` | Shared domain vocabulary |
| `DATA_ATTRIBUTION.md` | Dataset source and use boundary |
| `DeepSeek_LLM接入实验方案.md` | Authoritative A13 semantic-understanding spec and review gates |
| `A13_annotation_pack_v1.zip` | Deterministic legacy annotation bundle; exposed development diagnostics, not semantic-gate data |

## Documentation Layers

Use the following order instead of reading `docs/` alphabetically:

1. `current_status.md` - authoritative current checkpoint.
2. `human_optimization_recap_zh.md` - plain-language history and metric guide.
3. `optimization_roadmap.md` - dependency order and experiment gates.
4. `question_policy_optimization_plan.md` - authoritative A14 design and
   experiment plan when Question Policy is selected.
5. `a13_ai_silver_protocol.md` - active no-human A13 reference and KPI protocol
   when semantic understanding is selected.
6. `workstreams/` - independently readable A-side and B-side instructions.
7. `*_evidence.md` - one human decision record per recent experiment.
8. `*_evidence.json` and `*_reports/` - machine-readable summaries and raw
   hash-bound evidence.
9. `adr/` - durable architectural/evaluation decisions.
10. `archive/` - completed planning artifacts that are useful for history but
   are not active work.

The root `docs/README.md` is the navigation index for these layers.

## Evidence Naming Convention

Recent experiment artifacts use a stable pattern:

```text
docs/<experiment>_<topic>_evidence.md
docs/<experiment>_<topic>_evidence.json
docs/<experiment>_reports/
```

Historical B0-B7 files predate this exact convention and remain at their
recorded paths. Do not reorganize evidence after the fact unless all references,
hash checks, tests, and reproducibility instructions are updated together.

## Active Work Versus Archive

Local Markdown specs and tickets are created under:

```text
.scratch/<feature>/spec.md
.scratch/<feature>/issues/
```

They are active workflow inputs, not public project documentation. When an
entire ticket set is complete and still useful historically, archive it under:

```text
docs/archive/tickets/<feature>/
```

The completed original B1-B7 Retrieval / Ranking ticket set is archived there.
Its old metrics and next-step wording are historical; current truth always
comes from `docs/current_status.md`.

## Generated and Local-Only Files

The following are intentionally ignored and must not be committed:

- `.venv/`, `__pycache__/`, `.pytest_cache/`;
- `results.json`, `results/`, and ordinary `experiments/runs/*`;
- downloaded catalog files and release staging under `data/`;
- embeddings, indexes, model caches, checkpoints, and secrets;
- `.DS_Store`, logs, and environment files.

Some ignored local caches are required to reproduce optional dense experiments.
Do not delete them during cosmetic cleanup.

`A13_annotation_pack_v1.zip` is a deliberate publication artifact rather than
an ordinary experiment run. Its source remains under
`experiments/fixtures/a13_annotation_pack_v1/`, and it must be regenerated with

```bash
python3 -m experiments.build_a13_annotation_bundle \
  --output A13_annotation_pack_v1.zip
```

before its recorded hash or contents change.

## Where New Work Goes

| Change | Location |
| --- | --- |
| Dialogue state, extraction, planning, clarification | `starter/core/` and A-side tests; retained A14 policy seam is `starter/core/question_policy.py` and later slices follow `docs/question_policy_optimization_plan.md` |
| Retrieval, fusion, ranking, cache behavior | `starter/retrieval/`, `starter/ranking/`, and B-side tests |
| Shared public types | `starter/contracts.py` plus coordinated contract tests |
| Offline analysis or evaluation reporting | `experiments/` |
| Reusable developer command | `scripts/` |
| Current status or next decision | `docs/current_status.md` |
| Experiment decision and bound evidence | `docs/<experiment>_*` and matching report directory |
| Demo or packaging work | `visualizer/`, `submission/`, and `docs/demo_and_submission_plan.md` |

Avoid adding a new top-level directory unless none of these responsibilities
fit. A new file should have one authoritative purpose rather than duplicate
mutable status from another document.
