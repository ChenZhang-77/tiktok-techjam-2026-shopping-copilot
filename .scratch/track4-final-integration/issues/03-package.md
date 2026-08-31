# 03 — Reproduce the offline Agent from an independent bundle

**What to build:** A self-contained source bundle with deterministic manifest,
setup instructions and clean-directory evaluation evidence.
**Blocked by:** 02 — Dual-configuration Agent.
**Status:** completed

- [x] Source allowlist, immutable hashes and build/check commands are available.
- [x] Bundle exports Agent and has no sibling checkout dependency or secrets.
- [x] Fixed Development-160/four-fold offline parity and fresh-start tests pass.
- [x] Local model degradation is explicit; package tests and dual review pass.

316 tests; 36-file bundle check and independent metric/hash QA pass. Both reviews
pass against 28694f4..a70b213. Same-machine prepared assets, not a fresh full-dense
dependency installation; separate new stdlib-only venv also returned 10 unique IDs
with explicit dense degradation. Add public evidence links during materials step.
