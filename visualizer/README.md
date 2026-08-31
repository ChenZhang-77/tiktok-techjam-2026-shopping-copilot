# Offline process visualizer

Optional localhost demonstration, separate from the submitted headless Agent and
unmodified official evaluator. It uses simulated customers, not a live-chat backend.

## Start without a new aggregate experiment

From the repository root, in the prepared Python environment described in
[`submission/README.md`](../submission/README.md):

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python visualizer/server.py --port 8765 --split full
```

Open <http://127.0.0.1:8765>. The default bind is localhost. The repository needs
`data/catalog.jsonl`, `data/public_set.jsonl` and prepared local model/vector
assets. Missing assets produce explicit degraded retrieval diagnostics; do not
present a degraded run as a reproduction of the recorded dense result.

1. Select **Current workspace**, then a session from the loaded dataset. The
   default `full` view includes every loaded row; use `--split development` or
   `--split holdout` only when you intentionally want a manifest-defined subset.
   The UI renumbers the visible sessions continuously from `#1` to `#N` while
   retaining the source index internally.
2. Choose a message interval (0–60 seconds); click **Start**.
3. Historical experiments keep their recorded aggregate metrics, but the
   selected session can still be replayed with the current local Agent. This
   replay does not change the recorded score and does not rerun the full set.
4. Expand **Agent-only diagnostics and usage** for state, strategy, query,
   retrieval/fallback details and offline mode. No API key is needed.
4. Click **Stop** to disconnect; the server releases the session when it detects
   the closed connection (after any in-flight local work/message delay).

The visualizer explicitly forces offline delivery configuration and fixed local
asset locations, even if the shell has `SHOPPING_MODE=llm` or an API key. It is
not a switch for real paid execution. Use the documented headless entry for that.

## What the evidence means

- **Recorded Evaluation** is the independent package's Development-160 report,
  not a metric computed from the selected session. Source/module/input/vector
  hashes are checked before linking it to this checkout; missing/stale evidence
  is shown without scores. Timing/environment guarantees still belong to the
  report's recorded environment, not every machine or currently running session.
- **Current workspace** executes a fresh local offline simulated session.
  It is not a replay of the exact recorded aggregate run.
- Historical entries under `experiments/runs/` show saved metrics only. Start is
  disabled; the server rejects attempts to rerun them as current code. Saved
  partial Agent snapshots are insufficient to reproduce an entire old runtime.
- Green **Evaluator HIT**, target rank and scenario/session results are evaluator
  annotations. They are never passed to Agent state, retrieval, prompts or
  configuration. The Agent receives only `reset`/`respond` inputs and the catalog.
- The local API exposes evaluation metadata for inspection. Do not deploy this
  tool as an unreviewed public service or include it in the Agent runtime bundle.

`scripts/start_experiment.sh` passes its selected split and dataset paths to the
visualizer. Each experiment therefore exposes the same visible population as
the run that created it. The script remains an experiment helper, not the final
demo entry, and starting a demo does not require another evaluation.
