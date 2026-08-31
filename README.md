# Adaptive Shopping Copilot — TikTok TechJam 2026, Track 4

**Shopping intent moves. Search should keep up.**

A shopper can add a requirement, reject an earlier preference or change direction
mid-conversation. Adaptive Shopping Copilot turns current session context into
catalog-grounded recommendations: stateful intent handling, structured retrieval
and conditional local semantic search over 50,000 products.

**One delivery, two explicit configurations:** offline by default; optional,
bounded LLM product reranking. No live-chat service is required to run the Agent.

In one frozen offline public evaluation, the target product appeared in the
Top-10 in **186 of 200 simulated sessions**, with zero external API calls.
This is public benchmark evidence, not real-user conversion or unseen validation.
See [measured results and limits](#measured-evidence) and the
[judge-facing project story](docs/devpost_story.md).

## Start here

- [Independent submission setup and evaluator command](submission/README.md)
- [Configuration, limits and fallback](submission/CONFIGURATION.md)
- [Technical report](submission/REPORT.md)
- [Local simulated demo](visualizer/README.md)
- [Current evidence and remaining gates](docs/current_status.md)
- [Devpost draft](docs/devpost_draft.md) · [Demo script](docs/demo_recording_script.md)

The final Devpost code link will point only to this repository's **main** and an
identified final commit. No other branch is required to run the submission.
Historical branches are preserved. On 2026-08-31 the reviewed integration
checkpoint `bb6b7f3` was fast-forwarded to remote main with user authorization.
The repository remains private; public GitHub/video/Devpost submission is not
complete. See the [release record](docs/final_delivery_execution.md).

## Run the independent Agent

Use Python 3.12.13 with SQLite FTS5. From a checkout of the final published main:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r submission/requirements-dense.txt
cd submission
# Place the official frozen catalog at data/catalog.jsonl first.
../.venv/bin/python tools/build_dense_index.py --allow-model-download
SHOPPING_MODE=offline HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  ../.venv/bin/python tools/evaluate_offline.py \
  --kit-root /path/to/unmodified-participant-kit --output /path/to/new-report.json
```

Setup may download the pinned local model; ordinary runtime must not download.
The detailed [setup guide](submission/README.md) lists the catalog checksum,
paths and degradation rules. This command runs fixed Development-160 with the
unmodified official evaluator and compares the bundled delivery entry against its
retained core. Use a new output path.

The evaluator imports `Agent` from `submission/agent.py` and calls:

```python
agent.reset(session_id, user_profile)
response = agent.respond(session_id, user_message, turn, top_k)
```

The response contains `message`, `ask_attribute`, catalog-valid
`recommendations=[{"parent_asin": "..."}]`, usage and inspectable diagnostics.
The headless entry does not depend on the visualizer or experiment runners.

## Architecture and Track 4 coverage

```text
reset/respond inputs + frozen catalog
  -> scoped extraction, active preferences and override state
  -> Buying/Browsing strategy and distilled query
  -> SQLite FTS5 + constraint ranking + guarded filtering
  -> gated local MiniLM/RRF for broad Browsing
  -> optional explicit F2 Top-10 product reranking
  -> priority-biased clarification + response guard
```

| Official Track 4 pillar | Implemented / conditional / missing boundary |
| --- | --- |
| I. Core Architecture: Intent Routing & Hybrid Pipeline | Buying/Browsing routing and structured retrieval implemented; local dense/RRF conditional; LLM semantic ranking is F2 opt-in only, absent from offline execution |
| II. Dialog Strategy: Multi-Turn Scenario Evolution | Scoped state/override/no-preference tracking and structured clarification implemented; priority-biased questions are not a complete proactive over-generality retrieval-cutoff policy |
| III. Self-Evolution: Dynamic Context Programming | Current dialogue state distills the query and selects a bounded fixed strategy; long-term profile ranking/update and self-refining workflow orchestration are not implemented |
| IV. Evaluation Matrix: Product & Efficiency Metrics | HR@10, MRR, MTTC, Efficiency and TechnicalScore plus folds/scenarios/runtime evidence are reported below; private-set performance remains unknown |

This is a coverage assessment, not a claim of complete pillar fulfillment. The
kit permits rule-based/local methods and says a paid LLM is not required, but that
does not waive other architecture expectations. Confirm any eligibility-critical
gap with the organizer before final submission; do not resolve it by wording alone.

LLM mode is selected **before a run**, not hot-switched mid-conversation. It only
reorders eligible existing Top-10 products with constraint protection: no recall
expansion, dialogue-understanding model or profile-ranking claim. Keys alone never
enable it. Calls need explicit budgets; no-key, timeout, malformed output and
budget exhaustion preserve the pre-rerank order with visible reasons. See
[configuration](docs/delivery_configuration.md).

## Measured evidence

| Population / configuration | HitRate@10 | MRR | MTTC | TechnicalScore |
| --- | ---: | ---: | ---: | ---: |
| Independent offline package, Development-160 | 0.925000 | 0.554521 | 4.131250 | 0.766231 |
| Frozen offline package, Full-200 public report | 0.930000 | 0.527544 | 4.105000 | 0.761163 |

The [package report](docs/delivery_reports/offline_package.json) contains sessions,
four fixed folds, scenarios, source/input hashes and latency/resource evidence.
The paired core/delivery traces match exactly: 649 turns, 101 dense/fusion
executions and zero observed fallback. Offline API calls/tokens are zero;
local compute and setup costs are not zero.

This is a same-machine prepared environment with synthetic prewarm, not a fresh
dependency install on another machine or a hidden-test guarantee. Response p95
was 47.702 ms and max 119.827 ms in the delivery arm; see the report for timing
boundaries and shared-process initialization caveats.

Historical F2 paired Development-160 scores were 0.779043 / 0.779199, with unchanged
HitRate/MTTC. These are **not new live measurements of the integrated package**.
The [historical evidence retained in main](docs/delivery_reports/f2_historical.json)
records 826 calls and an inherited USD 0.69472392 allowance estimate, not a current
price or invoice. New real F2 verification remains separately gated.

Recent selection used fixed Development-160/four folds. The remaining 40 public
sessions were exposed earlier. The [final Full-200 report](docs/delivery_reports/final_public_full200.json)
was run once after offline configuration freeze: 186/200 hits, 807 turns, zero
observed fallback/invalid responses/exceptions and no external calls. Frozen
source/configuration/evaluator/data/model hashes are retained in the same directory.
It is public reporting, not unseen validation or a tuning input. Do not compare
a 160-row score with a 200-row score as an improvement or regression.
Historical [ablations](docs/ablation_summary.md) and
[source comparison](docs/release_comparison.md) remain available separately.

## Limitations and safety

- Public sessions are deterministic simulations, not measured real-user outcomes.
  Private-800 performance is unknown.
- Clarification is priority-biased, not a proven optimal stopping policy.
  Complex overrides/extraction can still fail; profile ranking is disabled.
- Missing local model/vector assets cause observable structured degradation,
  which is not reproduction of the full B9 benchmark.
- Remote LLM orders can vary even at temperature zero. The inherited 8-second
  request timeout is not a guarantee of whole-turn latency or organizer limits.
- The Agent must not read targets, labels, scenario IDs, future turns or private
  evaluation data. Demo hit/rank annotations are evaluator-only.
- A13/A14, profile/depth/recall extensions and model/prompt tuning remain frozen.

## Rebuild and verify

From the repository root:

The full repository test suite also expects the official catalog at repository
`data/catalog.jsonl` (distinct from a standalone bundle's data directory). Prepare
that file first; two catalog-integrity tests intentionally fail when it is absent.

```bash
python scripts/build_submission.py
python scripts/build_submission.py --check
python scripts/verify_delivery_evidence.py
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python -m unittest discover -s tests -q
```

For a combined source-and-evidence delivery ZIP, after evidence verification:

```bash
python scripts/build_submission.py --check --archive /path/to/new-delivery.zip --include-evidence
```

The archive keeps `submission/` and `evidence/` separate with their own manifests;
the latter retains Dev160, historical F2 and frozen Full200 reporting, not catalog
data, labels for runtime, model weights or another branch's code.

The source-only bundle includes an allowlisted runtime, setup tools, dependency
versions, split/folds, report and SHA-256 manifest. Evaluation reports live under
`docs/delivery_reports/`, outside Agent runtime. Catalogs, model weights,
embeddings, credentials and private data are not shipped in the bundle.

## Team, attribution and submission

[Team-approved contributions](docs/team_contributions.md) distinguish verified
component work from unassigned/shared or future work. See
[third-party notices](submission/THIRD_PARTY_NOTICES.md) and
[data attribution](DATA_ATTRIBUTION.md). Public visibility does not itself grant
a source-code license; maintainers must confirm their license/asset decisions.

The remaining external gates include repository public visibility,
source/asset rights decisions, an actual public YouTube demo and final Devpost fields.
Prepared text or local tests do not mean those actions have happened.

Repository navigation: [docs map](docs/README.md). Coding agents must read
[AGENTS.md](AGENTS.md), current status and the release roadmap before changes.
