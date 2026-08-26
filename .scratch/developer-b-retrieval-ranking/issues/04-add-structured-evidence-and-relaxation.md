# 04 — Add structured evidence and safe relaxation

**What to build:** Improve precise Buying and Intent Override recommendations by
using cross-field structured evidence, guarded filtering, and observable
relaxation while preserving broad Browsing recall.

**Blocked by:** 03 — Integrate the Retrieval / Ranking Plane with exact parity.

Status: complete

- [x] Evidence covers title, categories, features, details, store, description, and parseable price where appropriate.
- [x] Sparse price or details fields cannot broadly eliminate the Candidate Pool.
- [x] A zero-result hard filter relaxes the lowest-confidence eligible constraint and fills from the unfiltered order.
- [x] Relaxed constraints and filtered pool sizes are present in Retrieval Diagnostics.
- [x] Fixed Development Set cross-validation and an unfused lexical ablation support any retained behavior.

## Comments

- Retained guarded structured filtering as the runtime default after four fixed Development folds preserved HitRate@10 and improved mean MRR by 0.0042955 and mean TechnicalScore by 0.00153875 over the B1 no-filter control.
- Pure BM25, the B1 constraint-rerank control, and B2 structured modes are independently reproducible; 15 raw reports, scenario metrics, timings, peak RSS, hashes, and the decision are recorded in `docs/b2_structured_cv.json` and `docs/b2_reports/`.
- Final implementation evidence was generated from clean commit `eab7e61`; 92 tests and compile checks pass. Holdout and full were not run.
- Final review point `44934d7`: Standards and Spec reviewers both reported `No actionable findings.`
