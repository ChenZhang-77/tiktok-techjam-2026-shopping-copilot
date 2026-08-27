# Dialogue Visualizer

Process visualizer for one public Track 4 session at a time.

This tool is for debugging and understanding agent behavior. It does not replace the official local evaluator and does not modify `evaluator/local_evaluator.py`.

## Recommended Experiment Flow

From the repository root, run one experiment with a name:

```bash
./scripts/start_experiment.sh baseline-bm25 --split development
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
When an experiment was run on `development` or `holdout`, the Session dropdown
shows only sessions from that split.

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

The page contains two different information classes:

- **Agent View**: customer messages, agent message, `ask_attribute`, active
  state, distilled query, route diagnostics, and Top 10 recommendations.
- **Evaluator View**: target product, target highlight/rank, final hit/miss,
  first-hit turn, and aggregate experiment metrics.

Evaluator View exists only for offline analysis. Target ASIN, target rank,
hit/miss labels, and future turns must never flow into agent state, retrieval,
ranking, prompts, or routing. Keep the two views visibly labeled in screenshots
and demo recordings.

The integrated agent may currently ask a non-repeating, priority-biased
clarification while returning recommendations. It does not yet have a retained
candidate-evidence should-ask gate, so do not label the current choice as
expected information gain. After A9 is retained, this page may describe a
`null` `ask_attribute` as a measured no-ask decision.

See `../docs/demo_and_submission_plan.md` for the rehearsed demo flow and
submission safety checklist.
