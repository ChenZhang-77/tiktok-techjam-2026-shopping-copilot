# Shopping Copilot submission

Exports `Agent` from `agent.py`, with the official reset/respond interface. This
source bundle is independent of the development checkout. It does not include
catalog data, weights, private evaluation, secrets or experiment runners.

## Setup

Tested Python: 3.12.13, SQLite with FTS5. The structured fallback uses the standard
library. For the complete offline B9 route, install the pinned dense dependencies:

```bash
python -m pip install -r requirements-dense.txt
```

Obtain the frozen catalog from the official participant kit, verify its checksum,
and place it at `data/catalog.jsonl`. Prepare the pinned local MiniLM model and
vectors before runtime (setup may need internet):

```bash
python tools/build_dense_index.py --allow-model-download
```

Do not regenerate/download models in ordinary runtime. Optional model/cache
failure produces observable structured fallback, not the full B9 benchmark.

## Configuration

Default `SHOPPING_MODE=offline`. Optional `llm` requires a locally supplied
`DEEPSEEK_API_KEY` and explicit positive `SHOPPING_MAX_CALLS`, `SHOPPING_MAX_USD`,
`SHOPPING_MAX_SECONDS`; all limits default to zero. Never publish credentials.
See `CONFIGURATION.md` for paths, fallback, usage and cost assumptions.

## Reproduce with the official public evaluator

Obtain the unmodified official participant kit separately. From the bundle root:

```bash
SHOPPING_MODE=offline HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python tools/evaluate_offline.py --kit-root /path/to/participant-kit --output /path/to/new-report.json
```

This driver calls the official evaluator, fixed Development-160 only, without
modifying it. It uses the bundled split/folds and requires the kit's public set.
It does not run the exposed holdout, access private data, or call an LLM.
The official final harness may instead import `Agent` directly and supply a
catalog path. Organizer network/resource/packaging policy remains authoritative.

## Delivery status

See `REPORT.md`, `PROVENANCE.json`, `MANIFEST.json` and `THIRD_PARTY_NOTICES.md`.
Local package validation does not mean the public repository/video/Devpost are
submitted. New live F2 verification and final organizer eligibility are pending.
