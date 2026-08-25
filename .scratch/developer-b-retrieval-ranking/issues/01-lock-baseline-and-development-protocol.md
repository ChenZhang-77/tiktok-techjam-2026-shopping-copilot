# 01 — Lock the A-side baseline and Development Set protocol

**What to build:** Establish a reproducible B-stage starting point that proves
the latest Control Plane is green, records its exact Development Set behavior,
and provides deterministic development-only folds without treating the Exposed
Holdout as confirmatory evidence.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] The latest A-side main code passes its complete standard-library test suite.
- [ ] The 160-session baseline is reproduced with overall and per-scenario metrics recorded.
- [ ] A deterministic, scenario-stratified, sample-ID-only Development Set fold manifest is checked in and validated for completeness, disjointness, and reproducibility.
- [ ] Experiment guidance explicitly prohibits B-stage holdout/full inspection before freeze and links the exposure decision.
- [ ] Shared Retrieval Request, Candidate, Strategy, Retrieval Diagnostics, and Retrieval Result contracts are reviewed without evaluator-only fields.
- [ ] The working branch contains the latest A-side main before B1 begins.

## Comments

