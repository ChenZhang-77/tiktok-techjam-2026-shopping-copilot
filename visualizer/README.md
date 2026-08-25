# Dialogue Visualizer

Process visualizer for one public Track 4 session at a time.

This tool is for debugging and understanding agent behavior. It does not replace the official local evaluator and does not modify `evaluator/local_evaluator.py`.

## Recommended Experiment Flow

From the repository root, run one experiment with a name:

```bash
./scripts/start_experiment.sh baseline-bm25
```

The script will:

- create a new folder under `experiments/runs/`;
- save this run's `results.json`;
- copy the current `starter/agent.py` to `agent_snapshot.py`;
- create `metadata.json` and `notes.md`;
- open a visualizer URL for that run, such as:

```text
http://127.0.0.1:8765?experiment=2026-08-25-2105-baseline-bm25
```

Each experiment gets its own directory and URL. Old experiment outputs are not overwritten.

## Manual Visualizer

You can also start only the visualizer:

```bash
python3 visualizer/server.py
```

Open:

```text
http://127.0.0.1:8765
```

Use the Experiment dropdown to switch between the current workspace and saved experiment runs.

## What It Shows

- One selected public session at a time.
- Overall metrics for the selected experiment.
- Current customer's target product and session result.
- Customer message for each turn.
- Agent message and `ask_attribute`.
- Top 10 recommendations with product title, price, categories, and target hit highlight.
- Final hit/miss, first hit turn, and target rank.

The baseline agent currently does not ask clarifying questions, so `ask_attribute` will usually be `null`. After improving `starter/agent.py`, the same visualizer will show the new multi-turn behavior.
