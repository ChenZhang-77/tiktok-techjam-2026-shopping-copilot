# Submission Packaging Workspace

> Release freeze: this checkout has staging instructions only, not a completed
> independent package. The old P0 package at `aaa7e45` uses the older runtime;
> regenerate it from the selected source before submission. See
> [final release plan](../docs/final_release_plan.md).

This directory is a staging area, not proof that the final competition package
is complete. Follow `../docs/demo_and_submission_plan.md` for the full delivery
route and `../docs/current_status.md` for verified claims.

## Target package

```text
submission/
  README.md
  agent.py
  requirements.txt
  src/                 # only when required by imports
```

## Package only after the runtime is frozen

1. Copy the retained implementation and only its required local modules.
2. Pin or document every required dependency.
3. Document model/cache setup, latency, memory, cost, and deterministic fallback.
4. Add the exact clean-start command and response-schema smoke test.
5. Verify the final archive from a fresh temporary directory.

## Required checks

- `Agent` imports and instantiates without developer-machine state.
- Responses contain valid `message`, `ask_attribute`, `recommendations`, and
  `usage` fields.
- Recommendations are unique, catalog-valid `parent_asin` values.
- No evaluator modification, target leakage, future-turn access, or private
  evaluation data is present.
- No secrets, `.env`, tokens, credentials, absolute local paths, generated run
  output, or unnecessary caches are packaged.
- External models, APIs, licenses, and offline behavior are disclosed.
- Metrics use the same dataset labels and caveats as the root README.
- Team contributions are factual and evidence-backed.

Do not call the public 40-session slice sealed or unseen. Do not claim dense,
RRF, or semantic reranking as part of the default runtime unless a later frozen
configuration actually retains them.

Likewise, do not claim a candidate-evidence should-ask gate, persistent intent
confidence, or profile personalization until the corresponding retained
implementation and Development-160 evidence exist. Disclose literal Track 4
dense/semantic/profile gaps when they remain disabled.
