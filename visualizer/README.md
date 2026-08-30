# Dialogue Visualizer

Local process visualizer for one customer session at a time. It is separate
from the official evaluator and does not change `evaluator/local_evaluator.py`.

## Run An Experiment

From the repository root:

```bash
./scripts/start_experiment.sh my-experiment --split development
```

The command evaluates the Agent, creates a new directory under
`experiments/runs/`, saves `results.json`, copies the Agent snapshot, starts
the visualizer, and prints a URL such as:

```text
http://127.0.0.1:8765?experiment=2026-08-31-0646-my-experiment-development
```

The URL is also opened automatically on macOS when possible. If no browser tab
opens, copy the printed URL into a browser. Every run has its own directory and
URL; earlier runs are not overwritten.

## Use The Page

1. Select an experiment from `Experiment`.
2. Select one customer session from `Session`.
3. Enter the delay between messages in `Interval (seconds)`. The default is
   `0.7`; use `0` for immediate playback.
4. Click `Start` to play the selected conversation.
5. Click `Stop` to stop playback.

The page shows the initial customer request, each Agent response, the
recommendations, and the simulated customer follow-up one event at a time.
When the evaluator-valid target is found, the matching recommendation is green,
the left panel reports the first hit turn and rank, and playback stops.

The left panel also shows the five overall metrics from the saved run:
HitRate@10, MRR, MTTC, Efficiency, and TechnicalScore. These are aggregate
experiment metrics, not metrics for only the selected customer.

## Start Only The Visualizer

If a saved experiment already exists, start the page without running another
evaluation:

```bash
python3 visualizer/server.py
```

Then open:

```text
http://127.0.0.1:8765
```

The repository must contain `data/catalog.jsonl` and `data/public_set.jsonl`.
The experiment dropdown discovers saved runs under `experiments/runs/`.

## Scope And Safety

The page is a local demo and debugging tool. It does not affect scoring and
does not send target answers into Agent state, retrieval, ranking, prompts, or
routing. Generated run directories and downloaded data are local artifacts and
are ignored by Git.
