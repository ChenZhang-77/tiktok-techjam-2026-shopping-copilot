# Process Visualizer

Realtime process visualizer for one public Track 4 session at a time.

This tool is for debugging and understanding agent behavior. It does not replace the official local evaluator and does not modify `evaluator/local_evaluator.py`.

## Run

From the repository root:

```bash
python3 visualizer/server.py
```

Open:

```text
http://127.0.0.1:8765
```

## What It Shows

- One selected public session at a time.
- Customer message for each turn.
- Agent message and `ask_attribute`.
- Top 10 recommendations with product title, price, categories, and target hit highlight.
- Final hit/miss, first hit turn, and target rank.

The baseline agent currently does not ask clarifying questions, so `ask_attribute` will usually be `null`. After improving `starter/agent.py`, the same visualizer will show the new multi-turn behavior.
