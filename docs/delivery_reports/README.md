# Delivery evidence index

These are evaluator-side artifacts retained in final main, not inputs
to the Agent. No other branch is needed to read the retained numerical evidence.

- `offline_package.json`: actual independent-bundle Development-160 core/delivery
  paired run; sessions, four folds, scenarios, latency, routes and source/input hashes.
- `tested_bundle_manifest.json`: exact manifest bytes from that tested bundle.
  Later documentation-only bundle changes may change the current manifest; run
  `python scripts/verify_delivery_evidence.py` from the full repository root
  (this script is not included in the standalone ZIP) to check tested Python runtime
  identity and independently recompute the recorded metrics.
- `f2_historical.json`: unchanged copy of
  `a9e34ae:docs/b10b_paired_verification_result.json`, whose recorded runner is
  `c6b1a45`. It retains per-session outcomes, folds, costs, provider timing and raw
  artifact hashes. It is historical optional-mode evidence, not a fresh live test
  of this delivery. Old full raw provider runs are not copied into the Agent or
  this directory; the bound report records that limitation and their hashes.
- `final_public_full200.json`: one actual frozen offline Full200 pass at runtime
  `951d03e`; 200 outcomes, scenarios, timing and zero-call/failure accounting.
- `final_public_freeze.json` and `.started`: exact source/configuration/manifest,
  evaluator/input/vector/local-model hashes and the one-shot start record. These
  are copied unchanged from the independent bundle run, not regenerated to hide
  a mismatch. Later documentation-only package changes leave tested Python bytes
  unchanged. Independent verification recomputes results without another run.
  Do not use this public/exposed report for tuning or label it an unseen holdout.

Source-only ZIP users can read the reports in the
[public repository evidence directory](https://github.com/ChenZhang-77/tiktok-techjam-2026-shopping-copilot/tree/main/docs/delivery_reports).
Combined ZIP users can read the included `evidence/` directory without GitHub
access. Numerical evidence and frozen runtime bytes are retained unchanged.
