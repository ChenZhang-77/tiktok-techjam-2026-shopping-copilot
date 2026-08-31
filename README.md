# TikTok TechJam 2026 - Adaptive Shopping Copilot

Active final delivery integration: [configuration](docs/delivery_configuration.md),
[approved rules](docs/final_delivery_rules.md), and [step/review log](docs/final_delivery_execution.md).
The offline default is preserved; the new optional LLM entry has no new live verification yet.

An evidence-driven conversational shopping Agent for Track 4: **Shopping
Copilot: AI Conversational Search and Recommendations**.

The Agent maintains current shopping intent across a multi-turn conversation,
distinguishes targeted Buying from open-ended Browsing, retrieves products from
a frozen 50,000-item Amazon catalog, ranks candidates with explicit constraint
evidence, and returns safe recommendations with an optional clarification.

The retained default runtime requires no external API, hosted model, vector
database, or token budget. B9 conditionally executes a pinned local MiniLM dense
route for broad Browsing and otherwise preserves the structured order. B12's
bounded adaptive depth is reproducible but disabled by default. Global dense,
CrossEncoder, and LLM reranking are not enabled by default. DeepSeek DS1 is
available as an explicit, isolated performance experiment.

## Current Status

Plan One is the Chen local/no-external-LLM runtime, published to `yuqing`.
Plan Two is the explicit optional F2 product reranker on `llm`; both branches
still default to local behavior. A13 semantic understanding and A14 selector
experiments are frozen, not enabled.

The [final release plan](docs/final_release_plan.md) defines the two paths,
[branch inventory](docs/branch_inventory.md) identifies frozen work, and
[current status](docs/current_status.md) owns all current metrics and caveats.
The new same-protocol [Development-160 comparison](docs/release_comparison.md)
selects Chen: score `0.766231` versus original P0 `0.722074`, HR `0.925`
versus `0.8625`. This is the default B9 route, not the older structured-only
`0.765703` checkpoint. It is not a private/holdout result.

The stronger LLM evidence and exact F2 runner belong to the llm branch, not this checkout's older DS1/DS2 scripts.
The independent submission package, cold-start portability and final video
remain delivery work; old P0 packaging must be regenerated for the selected source.

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
  -> scoped extraction with frozen-catalog multi-word categories
  -> SessionState and context update
  -> current Buying/Browsing Strategy
  -> distilled query from active constraints
  -> in-memory SQLite FTS5 field-weighted Candidate Pool
  -> cross-field hard/soft constraint ranking
  -> guarded structured filtering
  -> deterministic relaxation and fill
  -> broad-Browsing gate -> local dense retrieval + weighted RRF
     (otherwise exact structured order)
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
Retriever.retrieve(request: RetrievalRequest) -> RetrievalResult
```

Shared types and leakage validation are in `starter/contracts.py`.

## Track 4 Alignment

| Track 4 pillar | Project behavior |
| --- | --- |
| Intent Routing and Hybrid Pipeline | Buying/Browsing changes Strategy and execution; B9 conditionally runs local dense retrieval plus weighted RRF for broad Browsing, with exact structured fallback |
| Multi-Turn Scenario Evolution | Session state accumulates constraints, tracks no-preference/rejection, and deactivates stale intent on override |
| Dynamic Context Programming | The Agent rebuilds the query from active state and records Strategy, Candidate, relaxation, and fallback diagnostics |
| Product and Efficiency Metrics | Development evaluation reports HitRate@10, MRR, MTTC, Efficiency, scenario results, latency, memory, and failures |

AB1 freezes requested, executed, and fallback Route semantics. B8's bounded
rejected-constraint candidate was reverted because Development-160 supplied
zero rejection turns. B9 is retained at `7f520ba`: dense and fusion actually
executed on 102 of 725 retrieval turns, only Browsing outcomes changed, and all
four fixed folds were non-regressing. B10a then tested Top-3 and Top-5 anchored
CrossEncoder tails; both reduced MRR and TechnicalScore, so the B9 default is
unchanged and an actual LLM reranker is not justified by this evidence. B12's
optional bounded depth candidate has favorable aggregate metrics but remains
disabled because it lacks a contemporaneous keep/revert gate and gains are
concentrated in fold 4.

## What the Ablations Showed

Historical Development-160 ablations on their recorded comparators (not the current Chen default):

| Variant | HitRate@10 | MRR | TechnicalScore | Decision |
| --- | ---: | ---: | ---: | --- |
| Official weak BM25 | 0.12500 | 0.068034 | 0.106710 | Comparison |
| Pure lexical | 0.71875 | 0.485851 | 0.617005 | Reject as default |
| Retained structured path | 0.76250 | 0.526989 | 0.653222 | Retain |
| A11 broad extraction candidate | 0.72500 | 0.479085 | 0.613976 | Reject |
| A11 bounded extraction scope | 0.86250 | 0.545568 | 0.721420 | Retain |
| B9 broad-Browsing conditional dense | 0.86250 | 0.547329 | 0.722074 | Retain conditionally |
| B12 bounded adaptive depth | 0.86875 | 0.549735 | 0.727170 | Exploratory; default off |
| B10a CrossEncoder, Top 3 anchored | 0.87500 | 0.515952 | 0.721411 | Reject as default |
| B10a CrossEncoder, Top 5 anchored | 0.86875 | 0.524025 | 0.720708 | Reject as default |
| Dense only | 0.33750 | 0.160501 | 0.272650 | Reject as default |
| Weighted RRF, k=10 | 0.75000 | 0.486620 | 0.637611 | Reject as default |
| Semantic rerank, Top 30 | 0.78125 | 0.484162 | 0.656499 | Reject globally; keep experiment |

Global semantic reranking gained recall in some Buying/Browsing sessions but
reduced MRR, regressed Intent Override, split the folds 2/2, and added
substantial latency and memory. B9 instead retained a narrow Browsing-only
dense route. B10a's safer anchored variants also failed: Top 3 split the folds
2/2 and reduced MRR by `0.031377`; Top 5 still reduced MRR by `0.023304`.

See [`docs/ablation_summary.md`](docs/ablation_summary.md) for decisions and the
bound JSON reports under `docs/` for numerical provenance.

## Repository Layout

```text
starter/                    Agent, Control Plane, retrieval, and ranking runtime
evaluator/                  official deterministic local evaluator
experiments/                Development split, reporting, and offline analysis
tests/                      behavior, contract, fallback, and evidence tests
scripts/                    catalog, cache, experiment, and visualizer helpers
visualizer/                 local dialogue and metric inspection UI
submission/                 final minimal package staging area
data/                       public sessions and ignored frozen catalog download
docs/README.md              documentation navigation index
docs/project_structure.md   detailed ownership and file-placement rules
docs/workstreams/           standalone A-side and B-side routes
docs/*_reports/             raw hash-bound experiment reports
docs/archive/               completed planning artifacts, not active backlog
```

The evidence-heavy `docs/` layout is intentional: summary JSON, raw reports,
tests, and decision documents are hash-bound by stable paths. Generated
catalog, model, embedding, cache, and ordinary experiment-run files are ignored
by Git. See [`docs/project_structure.md`](docs/project_structure.md) before
adding or moving directories.

## Quickstart

Requirements:

- Python 3.10 or newer for deterministic structured fallback behavior.
- The official frozen catalog release.
- Python 3.12 plus `requirements-dense.txt`, the pinned model, and a compatible
  embedding cache to activate the retained B9 dense route.

Clone and enter the repository:

```bash
git clone --branch yuqing https://github.com/ChenZhang-77/tiktok-techjam-2026-shopping-copilot.git
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

If no project virtual environment or dense cache is present, the Agent degrades
to its deterministic standard-library structured path:

```bash
python3 -m unittest discover -s tests -v
```

Run the actual default B9 Development-160 audit after preparing local dense assets:

```bash
.venv/bin/python -m experiments.release_default_audit \
  --output /private/tmp/shopping-copilot-development-new.json
```

Do not use `--split full` or `--split holdout` for optimization.

### Optional LLM Plan Two

The default Agent does not read a key or call a hosted model. Plan Two uses only
the exact verified B10b-F2 Top-10 recipe on the llm branch, with explicit
activation, budget/token accounting and deterministic pre-rerank fallback.
See the llm branch's [F2 protocol/evidence](https://github.com/ChenZhang-77/tiktok-techjam-2026-shopping-copilot/blob/7f0dc6c07b0cc2375a82c50ff47e5ee98652f0b6/docs/b10b_paired_verification.md). Do not substitute this checkout's old DS1/DS2 scripts or provisional results for F2.

No additional paid calls are part of the release task. Keep keys in ignored
local configuration, never in source, reports or logs. The exposed 40-session
public subset must not be used for tuning or described as a fresh generalization check.

Semantic understanding is inactive. All incomplete experiments and their reopening conditions are listed in [final plan](docs/final_release_plan.md).

## Named Experiments and Visualizer

Historical experiment commands below are reference-only. The active release
route and frozen experiment list are in [final release plan](docs/final_release_plan.md).


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

Each run gets a new directory and a new URL. The runner starts the visualizer
automatically after evaluation and opens the URL on macOS when possible. The
terminal always prints the URL, so automatic browser opening is not required.
The page is a single Demo view: select a saved run and customer, enter the
message interval in seconds (default `0.7`), then click `Start`. Customer and
Agent messages appear one at a time, recommendations marked `HIT` stop the
dialogue immediately, and the left panel reports the current customer's hit
turn. The five overall metrics are shown on the left: HitRate@10, MRR, MTTC,
Efficiency, and TechnicalScore.

Manual visualizer:

```bash
python3 visualizer/server.py
```

Open `http://127.0.0.1:8765`.

The visualizer is for local process inspection and demo recording. It does not
change the official evaluator or send target information into the Agent. Target
product details and evaluator-only internals are not exposed in the page.

## Local Dense and Optional Semantic Setup

Install pinned optional dependencies in a Python 3.12 environment:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dense.txt
```

Retained B9 dense cache:

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
After preparation, loading is local-only. Missing/incompatible cache or model
failures return the exact structured order.

## Current Optimization Route

New behavior work is frozen. Follow [release roadmap](docs/optimization_roadmap.md):
source verification, documentation/review, authorized branch publication, then
fresh-source packaging and demo. Historical experiment “next steps” do not
reopen work. All freeze/recovery decisions are in [final release plan](docs/final_release_plan.md).

## Reliability and Cost

Historical B9 checkpoint cost evidence (not a new Chen/llm latency benchmark):

| Measure | Value |
| --- | ---: |
| Initialization | about 3.58 s |
| Mean retrieval latency | about 21.73 ms |
| p95 retrieval latency | about 40.44 ms |
| Peak RSS | about 1.109 GB |
| Dense route mean / p95 | about 4.70 / 5.03 ms |
| Prompt/completion tokens | 0 / 0 |
| Response exceptions | 0 |
| Invalid response payloads | 0 |

Required fallback behavior includes missing/corrupt dense cache, missing fusion
routes, semantic backend errors, invalid scores, timeout termination, empty
hard filters, duplicate/invalid ASINs, and Candidate Pool shortages.

## Limitations

- The historical public holdout is exposed and cannot support a sealed claim.
- Stateful intent is retained, but confidence remains an ordinal A-side signal,
  not a calibrated probability. B12's A-owned bounded-depth experiment is
  disabled by default; two primary State / Override misses remain.
- Clarification remains priority-biased and does not yet have a complete
  should-ask uncertainty gate.
- Four primary Development Extraction misses remain. Broader extraction
  alternatives remain unproven without independent hash-bound evidence.
- Profile ranking is disabled at weight 0.0.
- B9 closes the literal Browsing-dense route only for its narrow gate; global
  dense remains rejected. Only the llm branch's B10b-F2 has the newer paired verification; neither it nor older DS1/DS2 is active in the default.
- B9 adds about 1.5 seconds of initialization and about 546 MB of observed peak
  RSS for a small rank/turn gain with no additional hits.
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
