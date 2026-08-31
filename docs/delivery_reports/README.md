# Delivery evidence index

These are evaluator-side artifacts intended to remain in final main, not inputs
to the Agent. No other branch is needed to read the retained numerical evidence.

- `offline_package.json`: actual independent-bundle Development-160 core/delivery
  paired run; sessions, four folds, scenarios, latency, routes and source/input hashes.
- `tested_bundle_manifest.json`: exact manifest bytes from that tested bundle.
  Later documentation-only bundle changes may change the current manifest; run
  `python scripts/verify_delivery_evidence.py` to check tested Python runtime
  identity and independently recompute the recorded metrics.
- `f2_historical.json`: unchanged copy of
  `a9e34ae:docs/b10b_paired_verification_result.json`, whose recorded runner is
  `c6b1a45`. It retains per-session outcomes, folds, costs, provider timing and raw
  artifact hashes. It is historical optional-mode evidence, not a fresh live test
  of this delivery. Old full raw provider runs are not copied into the Agent or
  this directory; the bound report records that limitation and their hashes.
- Final Full-200 report: pending the configuration-freeze gate. Once generated,
  retain the frozen configuration/manifest, evaluator/input hashes, all sessions,
  scenarios, latency and zero-call accounting alongside it. Do not use it for
  parameter selection or label it an unseen holdout.

Source-only ZIP users can locate this directory after authorized main publication:
https://github.com/ChenZhang-77/tiktok-techjam-2026-shopping-copilot/tree/main/docs/delivery_reports

That URL is a planned release location until the integration is actually merged,
pushed and made public. It is not evidence that publication has occurred.
