# Project structure

| Location | Responsibility |
| --- | --- |
| `starter/` | Scored Agent, state, control flow, retrieval and ranking |
| `submission/` | Independently runnable Agent bundle and setup/report documents |
| `packaging/` | Sources for the generated bundle entry, tools and documentation |
| `evaluator/` | Unmodified official evaluator |
| `tests/` | Behavior, contract, fallback and evidence verification |
| `scripts/` | Build, setup and verification entry points |
| `visualizer/` | Optional local simulated demo, outside scored runtime |
| `experiments/` | Development evaluation, comparisons and diagnostic tooling |
| `docs/delivery_reports/` | Frozen final public evidence, outside Agent inputs |
| `docs/*_reports/`, `docs/*_evidence.*` | Supporting experiment evidence at stable paths |
| `data/` | Official public data references and ignored catalog assets |

The generated submission is a tested standalone bundle. Its README gives asset
preparation and the official-harness evaluation command. No other branch is
required to run it.

The [documentation index](README.md) separates product/setup documents from
supporting technical evidence. Numerical reports, freeze records and evidence
paths retain their original identity so that reported results remain inspectable.

Catalogs, downloaded models, embeddings, credentials and development working notes
are excluded from the delivery bundle. The root `CONTEXT.md` defines shared
technical vocabulary; `DATA_ATTRIBUTION.md` identifies the dataset-use boundary.
