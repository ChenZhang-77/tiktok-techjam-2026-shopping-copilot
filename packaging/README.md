# Shopping Copilot submission

Exports `Agent` from `agent.py`, with the official reset/respond interface. This
source bundle is independent of the development checkout. It does not include
catalog data, weights, private evaluation, secrets or experiment runners.
The combined delivery ZIP also has a sibling `evidence/` directory with public
evaluation reports and a separate evidence manifest. That directory is not on
the Agent import/input path; no public labels or catalog are required from it.

## Setup

Tested Python: 3.12.13, SQLite with FTS5. The structured fallback uses the standard
library. For the complete offline B9 route, install the pinned dense dependencies:

```bash
python -m pip install -r requirements-dense.txt
```

Obtain the frozen catalog from the official participant kit, verify its checksum,
and place it at `data/catalog.jsonl`. Expected SHA-256:
`da979b05a68af864cb0dcf9ee6a81c010c7e66a57978ad286c7a2e005fc69a67`.
For example, check it with `shasum -a 256 data/catalog.jsonl` on macOS.
Prepare the pinned local MiniLM model and
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

## Frozen final Full200 public report

This is separate from development selection. The remaining40 were exposed earlier:
Full200 is not unseen validation and must not be used to tune the frozen Agent.
To reproduce the frozen offline configuration independently, record a new freeze
outside the bundle, then run once with the same inputs:

```bash
python tools/evaluate_final_public.py --kit-root /path/to/participant-kit \
  --freeze-file /path/to/new-freeze.json --freeze-only
python tools/evaluate_final_public.py --kit-root /path/to/participant-kit \
  --freeze-file /path/to/new-freeze.json --output /path/to/new-full200-report.json
```

Both commands default to this bundle's prepared catalog/model/vector paths; use
identical explicit path options for nondefault assets. Freeze records runtime,
evaluator, data, vector and local-model hashes. A `.started` marker prevents an
automatic second run from the same freeze; preserve it, including on failure.
The marker is retained after successful completion too: it is not an unfinished
run indicator. In the combined ZIP, `evidence/final_public_full200.json` contains
200 outcomes and records `acceptance_passed: true` with unchanged source/input
hashes; source-only bundle users can read it in the public repository evidence directory.
The runner uses only offline configuration, verifies each response contract and
retains all200 outcomes/scenarios/timing. No private set or external LLM is used.

## Package reference

See `REPORT.md`, `PROVENANCE.json`, `MANIFEST.json` and `THIRD_PARTY_NOTICES.md`.
The report distinguishes measured offline results, historical LLM evidence and
implementation limits. The manifests identify the packaged source files.
