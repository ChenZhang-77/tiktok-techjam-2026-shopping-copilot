# 01 — Lock the A-side baseline and Development Set protocol

**What to build:** Establish a reproducible B-stage starting point that proves
the latest Control Plane is green, records its exact Development Set behavior,
and provides deterministic development-only folds without treating the Exposed
Holdout as confirmatory evidence.

**Blocked by:** None — can start immediately.

**Status:** completed

- [x] The latest A-side main code passes its complete standard-library test suite.
- [x] The 160-session baseline is reproduced with overall and per-scenario metrics recorded.
- [x] A deterministic, scenario-stratified, sample-ID-only Development Set fold manifest is checked in and validated for completeness, disjointness, and reproducibility.
- [x] Experiment guidance explicitly prohibits B-stage holdout/full inspection before freeze and links the exposure decision.
- [x] Shared Retrieval Request, Candidate, Strategy, Retrieval Diagnostics, and Retrieval Result contracts are reviewed without evaluator-only fields.
- [x] The working branch contains the latest A-side main before B1 begins.

## Comments

- Merged A-side `origin/main` at `2280bf7` into the B feature branch.
- Verified 58 standard-library tests after adding the fold and reporting protocol.
- Reproduced Development Set metrics exactly: HitRate@10 0.7625, MRR
  0.522693, MTTC 5.31875, Efficiency 0.568125, TechnicalScore 0.651683.
- Generated four deterministic 40-session folds; each contains 16 Buying,
  16 Browsing, 6 Intent Override, and 2 Boundary sessions.
- Kept the official evaluator byte-for-byte unchanged; fold selection and
  per-scenario derived scores run through an external experiment wrapper.
- Recorded zero public respond exceptions, zero invalid response payloads, and
  zero explicitly reported fallbacks. A-side internal fallbacks are not
  observable until B1 supplies Retrieval Diagnostics.
