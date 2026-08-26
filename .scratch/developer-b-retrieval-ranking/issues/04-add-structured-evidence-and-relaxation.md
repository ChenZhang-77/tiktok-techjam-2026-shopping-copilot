# 04 — Add structured evidence and safe relaxation

**What to build:** Improve precise Buying and Intent Override recommendations by
using cross-field structured evidence, guarded filtering, and observable
relaxation while preserving broad Browsing recall.

**Blocked by:** 03 — Integrate the Retrieval / Ranking Plane with exact parity.

**Status:** in-progress

- [ ] Evidence covers title, categories, features, details, store, description, and parseable price where appropriate.
- [ ] Sparse price or details fields cannot broadly eliminate the Candidate Pool.
- [ ] A zero-result hard filter relaxes the lowest-confidence eligible constraint and fills from the unfiltered order.
- [ ] Relaxed constraints and filtered pool sizes are present in Retrieval Diagnostics.
- [ ] Fixed Development Set cross-validation and an unfused lexical ablation support any retained behavior.

## Comments
