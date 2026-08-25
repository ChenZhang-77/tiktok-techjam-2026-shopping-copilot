# TikTok TechJam 2026 - Track 4 Shopping Copilot

Private team workspace for Track 4, **Shopping Copilot: AI Conversational Search and Recommendations**.

This repository is based on the official participant kit:

- Official repo: https://github.com/TechJam2026/techjam-conversational-search
- Release: https://github.com/TechJam2026/techjam-conversational-search/releases/tag/participant-kit
- Competition spec: `docs/competition_specification.md`
- Submission rules: `docs/submission_rules.md`

## Goal

Build a multi-turn shopping agent that finds a hidden target product from a frozen 50,000-item Amazon catalog within at most 10 turns.

The local score is measured on 200 public development sessions:

- `HitRate@10`
- `MRR`
- `MTTC`
- `TechnicalScore = 0.50 * HitRate@10 + 0.30 * MRR + 0.20 * Efficiency`

The official weak BM25 starter baseline is:

| Metric | Value |
| --- | ---: |
| HitRate@10 | 0.125 |
| MRR | 0.068034 |
| MTTC | 9.81 |
| TechnicalScore | 0.10671 |

## Repository Contents

```text
data/public_set.jsonl             200 public development sessions
docs/                             official participant docs and scoring config
evaluator/local_evaluator.py      official local evaluator
starter/agent.py                  editable weak BM25 baseline
scripts/download_catalog.sh       downloads official catalog release asset
scripts/run_baseline.sh           runs the local evaluator
experiments/                      team experiment notes
submission/                       final packaging notes
```

Large data files are intentionally not committed:

- `data/catalog.jsonl.gz`
- `data/catalog.jsonl`
- generated embeddings, indexes, checkpoints, and result files

## Quickstart

Use Python 3.10 or newer.

```bash
git clone https://github.com/ChenZhang-77/tiktok-techjam-2026-shopping-copilot.git
cd tiktok-techjam-2026-shopping-copilot
python3 --version
```

Download the official catalog:

```bash
./scripts/download_catalog.sh
```

Run the official weak starter baseline:

```bash
./scripts/run_baseline.sh
```

The command writes `results.json`. The first target is to reproduce the official baseline in `docs/baseline_results.json`.

## Development Plan

Step 1: reproduce the official baseline.

- Clone this repo.
- Download `catalog.jsonl.gz` from the official GitHub release.
- Decompress it into `data/catalog.jsonl`.
- Run `python3 -m evaluator.local_evaluator`.
- Confirm the score matches `docs/baseline_results.json`.

Step 2: improve the agent.

Start by editing `starter/agent.py`. Recommended upgrade order:

1. Add conversation state per `session_id`.
2. Extract structured slots from each user message: category, material, color, size, style, brand, budget, feature, use case.
3. Detect scenario behavior: buying, browsing, intent override, boundary/no-preference.
4. Add metadata-aware retrieval and reranking on top of BM25.
5. Add adaptive clarification: ask useful questions only when they can reduce the candidate set.
6. Optional: add embeddings or a lightweight reranker, with an offline fallback.

Do not modify `evaluator/` when reporting scores.

## Submission Interface

The submitted agent must export:

```python
class Agent:
    def reset(self, session_id: str, user_profile: dict) -> None:
        ...

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        return {
            "message": "Do you have a material preference?",
            "ask_attribute": "material",
            "recommendations": [{"parent_asin": "B000..."}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }
```

`ask_attribute` must be one of:

```text
category, material, color, size, style, brand, budget, feature, use_case, other, null
```

Only the first 10 valid unique `parent_asin` values are scored.

## Data Policy

The catalog and sessions are derived from Amazon Reviews 2023 by McAuley Lab, UCSD. Keep the official attribution in `DATA_ATTRIBUTION.md`.

Do not commit:

- private evaluation data
- API keys or `.env`
- downloaded catalog files
- generated embeddings or model checkpoints unless they are small and license-safe
- output files that contain secrets or private test artifacts

## Remote GPU

The official BM25 baseline does not need GPU. A remote GPU can be useful later for:

- generating product embeddings
- running local sentence-transformer / E5 / BGE models
- running a local reranker
- experimenting with a small local LLM for slot extraction

Any GPU-dependent path must document setup, dependencies, expected memory, and CPU/offline fallback behavior.
