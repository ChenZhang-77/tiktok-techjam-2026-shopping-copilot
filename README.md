# TikTok TechJam 2026 - Adaptive Shopping Copilot

An evidence-driven conversational shopping Agent for Track 4: **Shopping
Copilot: AI Conversational Search and Recommendations**.

The Agent maintains current shopping intent across a multi-turn conversation,
distinguishes targeted Buying from open-ended Browsing, retrieves products from
a frozen 50,000-item Amazon catalog, ranks candidates with explicit constraint
evidence, and returns safe recommendations with an optional clarification.

The project is intentionally lightweight: the retained runtime requires no
external API, hosted model, vector database, or token budget. Dense retrieval,
fusion, and semantic reranking were implemented and measured as reproducible
experiments, then disabled by default because their tradeoffs were not robust.

## Current Status

The verified integrated checkout and next optimization decision are documented
in [`docs/current_status.md`](docs/current_status.md). The project-wide route is
[`docs/optimization_roadmap.md`](docs/optimization_roadmap.md).

Verified Development-160 result for the retained structured runtime:

| Metric | Result |
| --- | ---: |
| HitRate@10 | 0.7625 |
| MRR | 0.526989 |
| MTTC | 5.30625 |
| Efficiency | 0.569375 |
| TechnicalScore | 0.653222 |

Historical Full-200 public snapshot:

| Metric | Result |
| --- | ---: |
| HitRate@10 | 0.765000 |
| MRR | 0.517355 |
| MTTC | 5.375000 |
| TechnicalScore | 0.650207 |

The Full-200 result is not a sealed validation result. The public holdout had
already been exposed, so later work must be selected only with fixed
Development-160 cross-validation. The organizer's private 800 sessions remain
the external generalization test.

## Problem Framing

Static keyword search cannot reliably handle a customer who starts vague,
adds constraints over several turns, rejects a suggestion, or changes their
mind. The Track 4 task rewards three outcomes together:

- **Coverage:** is the target product in the Top 10?
- **Precision:** how highly is it ranked?
- **Efficiency:** how many turns are needed to find it?

The system therefore treats each turn as a decision cycle:

```text
What is still true?
  -> Is the customer Buying or Browsing?
  -> How should this turn search and rank?
  -> Are the current recommendations sufficiently focused?
  -> If not, which one question would reduce uncertainty most?
```

## Retained Runtime

```text
user message
  -> SessionState and context update
  -> current Buying/Browsing Strategy
  -> distilled query from active constraints
  -> in-memory SQLite FTS5 field-weighted Candidate Pool
  -> cross-field hard/soft constraint ranking
  -> guarded structured filtering
  -> deterministic relaxation and fill
  -> priority-biased clarification selection
  -> response guard
```

Important behaviors:

- active, overridden, rejected, and no-preference evidence is separated,
- stale values are excluded from the distilled query after Intent Override,
- hard filtering is allowed only with adequate confidence and coverage,
- sparse filters relax rather than emptying the Candidate Pool,
- valid recommendations are normally returned alongside a question,
- invalid/duplicate ASINs and schema errors are guarded,
- optional retrieval/ranking failures degrade to deterministic local behavior.

The stable integration seam is:

```text
HybridRetriever.retrieve(request: RetrievalRequest) -> RetrievalResult
```

Shared types and leakage validation are in `starter/contracts.py`.

## Track 4 Alignment

| Track 4 pillar | Project behavior |
| --- | --- |
| Intent Routing and Hybrid Pipeline | Buying/Browsing currently changes structured Strategy behavior; dense and semantic routes are measured but disabled, so literal Browsing-dense coverage remains open |
| Multi-Turn Scenario Evolution | Session state accumulates constraints, tracks no-preference/rejection, and deactivates stale intent on override |
| Dynamic Context Programming | The Agent rebuilds the query from active state and records Strategy, Candidate, relaxation, and fallback diagnostics |
| Product and Efficiency Metrics | Development evaluation reports HitRate@10, MRR, MTTC, Efficiency, scenario results, latency, memory, and failures |

The next optimization phase makes intent persistence and proactive guidance
more genuinely candidate-aware. A non-zero requested Strategy weight is not
evidence that the retained retriever executed that route. See the roadmap rather
than inferring that each planned behavior is already implemented.

## What the Ablations Showed

Development-160:

| Variant | HitRate@10 | MRR | TechnicalScore | Decision |
| --- | ---: | ---: | ---: | --- |
| Official weak BM25 | 0.12500 | 0.068034 | 0.106710 | Comparison |
| Pure lexical | 0.71875 | 0.485851 | 0.617005 | Reject as default |
| Retained structured path | 0.76250 | 0.526989 | 0.653222 | Retain |
| Dense only | 0.33750 | 0.160501 | 0.272650 | Reject as default |
| Weighted RRF, k=10 | 0.75000 | 0.486620 | 0.637611 | Reject as default |
| Semantic rerank, Top 30 | 0.78125 | 0.484162 | 0.656499 | Reject globally; keep experiment |

Semantic reranking gained recall in some Buying/Browsing sessions but reduced
MRR, regressed Intent Override, split the folds 2/2, and added substantial
latency and memory. The next defensible semantic experiment is conditional and
constraint-preserving, after A-side intent is stabilized.

See [`docs/ablation_summary.md`](docs/ablation_summary.md) for decisions and the
bound JSON reports under `docs/` for numerical provenance.

## Repository Layout

```text
starter/                              Agent, Control Plane, retrieval/ranking
evaluator/                            official deterministic local evaluator
experiments/                          split and reporting infrastructure
tests/                                behavior, contract, fallback, evidence tests
scripts/                              catalog, cache, experiment, visualizer helpers
visualizer/                           local dialogue and metric inspection UI
docs/current_status.md                verified state and next decision
docs/optimization_roadmap.md          project-wide blockers-first route
docs/ablation_summary.md              human-readable keep/reject evidence
docs/workstreams/                     standalone A and B routes
docs/demo_and_submission_plan.md      delivery, demo, packaging, rehearsal
submission/                           final minimal package work area
data/public_set.jsonl                 200 public sessions
```

Generated catalog, model, embedding, cache, and experiment-run files are
ignored by Git.

## Quickstart

Requirements:

- Python 3.10 or newer for the default standard-library runtime.
- The official frozen catalog release.
- Python 3.12 plus `requirements-dense.txt` only for optional semantic
  experiments.

Clone and enter the repository:

```bash
git clone https://github.com/ChenZhang-77/tiktok-techjam-2026-shopping-copilot.git
cd tiktok-techjam-2026-shopping-copilot
python3 --version
```

Download and verify the official catalog:

```bash
./scripts/download_catalog.sh
```

Run the complete test suite:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

If no project virtual environment is present, the default runtime uses only
the Python standard library:

```bash
python3 -m unittest discover -s tests -v
```

Run an ordinary Development-160 evaluation:

```bash
.venv/bin/python -m experiments.evaluation_reporting \
  --split development --structured-filter \
  --output /private/tmp/shopping-copilot-development.json
```

Do not use `--split full` or `--split holdout` for optimization.

## Named Experiments and Visualizer

For an isolated named development run:

```bash
./scripts/start_experiment.sh experiment-name --split development
```

An optional fold can be selected:

```bash
./scripts/start_experiment.sh experiment-name \
  --split development --fold fold_1
```

Generated runs are written under ignored `experiments/runs/` directories and
can be inspected with the local visualizer.

Manual visualizer:

```bash
python3 visualizer/server.py
```

Open `http://127.0.0.1:8765`.

The visualizer may show target and scoring information to a human reviewer.
That information is evaluator-only and is never a valid Agent or retrieval
input. A public demo must clearly separate the Agent-visible view from the
evaluator/debug view.

## Optional Semantic Experiments

Install pinned optional dependencies in a Python 3.12 environment:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dense.txt
```

Dense benchmark cache:

```bash
.venv/bin/python -m scripts.build_dense_index \
  --allow-model-download --batch-size 128
```

Semantic reranker cache and Development-160 experiment:

```bash
.venv/bin/python scripts/cache_reranker.py --allow-model-download
.venv/bin/python -m experiments.evaluation_reporting \
  --split development --semantic-rerank --rerank-limit 30 \
  --output /private/tmp/shopping-copilot-semantic-development.json
```

Model downloads are cache-preparation actions, not ordinary runtime behavior.
After preparation, loading is local-only and failures return the exact
pre-rerank order.

## Current Optimization Route

The current blocker is R0: classify Development-160 failures offline before
changing runtime behavior. `AGENTS.md` owns the taxonomy and leakage boundary;
[`docs/optimization_roadmap.md`](docs/optimization_roadmap.md) owns the complete
dependency order. The A/B workstream documents provide experiment inputs,
tests, and keep/revert gates without overriding that order.

## Reliability and Cost

Historical retained Development-160 evidence:

| Measure | Value |
| --- | ---: |
| Initialization | about 1.25 s |
| Mean retrieval latency | about 36.87 ms |
| p95 retrieval latency | about 82.69 ms |
| Peak RSS | about 574 MB |
| Prompt/completion tokens | 0 / 0 |
| Response exceptions | 0 |
| Invalid response payloads | 0 |

Required fallback behavior includes missing/corrupt dense cache, missing fusion
routes, semantic backend errors, invalid scores, timeout termination, empty
hard filters, duplicate/invalid ASINs, and Candidate Pool shortages.

## Limitations

- The historical public holdout is exposed and cannot support a sealed claim.
- Current intent inference is still too current-utterance-sensitive.
- Clarification remains priority-biased and does not yet have a complete
  should-ask uncertainty gate.
- Rule-based extraction has vocabulary and negation-scope limits.
- Profile ranking is disabled at weight 0.0.
- Dense/fusion/semantic paths are not the default runtime.
- The retained runtime therefore does not yet literally satisfy the
  Browsing-dense/semantic Track 4 pillar; it currently has measured disabled
  alternatives and a guarded follow-up route.
- Long-term profile value has not been demonstrated; profile ranking remains
  disabled at weight 0.0.
- Public sessions are deterministic simulations derived from product metadata,
  not real shopping conversations.
- Private organizer evaluation is the remaining external test of paraphrase and
  user generalization.

## Data, Safety, and Attribution

The competition catalog and sessions are derived from Amazon Reviews 2023 by
McAuley Lab, UCSD. See [`DATA_ATTRIBUTION.md`](DATA_ATTRIBUTION.md).

Do not commit:

- private evaluation data,
- target-linked rules or public-answer hardcoding,
- API keys, tokens, or `.env`,
- downloaded catalogs,
- generated embeddings/model caches/checkpoints,
- unlicensed trademarks or copyrighted demo assets.

## Demo, Submission, and Contributions

The completion route is in
[`docs/demo_and_submission_plan.md`](docs/demo_and_submission_plan.md). The
final deliverables must include an independently runnable Agent package, a
public GitHub repository, Devpost description, public YouTube demo, limitations,
cost/latency, attribution, and named team member contributions.

Do not invent contribution claims. Record each person's actual experiments,
code, documentation, validation, and demo work before submission.

## For Coding Agents

Read [`AGENTS.md`](AGENTS.md), then `docs/current_status.md`, the optimization
roadmap, and exactly one selected workstream document. Work one experiment at a
time and leave a reproducible handoff with tests, development evidence,
gains/regressions, decision, and next smallest step.
