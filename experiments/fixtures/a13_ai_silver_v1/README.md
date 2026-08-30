# A13 AI-Silver V1 Offline Contract

This directory contains A13-AS0 contracts only. It contains no fresh evaluation
items, AI labels, provider responses, secrets, or authorization to make a
network request.

Status:

```text
as0_core_contracts_frozen = true
candidate_config_frozen = true
role_manifest_frozen = false
execution_runner_ready = false
fresh_fixture_frozen = false
reference_builder_provider_authorized = false
candidate_provider_authorized = false
```

The exposed legacy 60-item annotation pack must not be copied here. After the
Candidate config and all role identities are frozen, A13-AS1F may create a new
target-free, trigger-balanced fixture only with explicit reference-builder
authorization.

## Frozen offline seams

- `applied_state_delta_v1.schema.json` defines the canonical comparison unit.
- `fresh_fixture_item.schema.json` defines private fixture rows; `trigger_type`
  is stripped before judging.
- `judge_input.schema.json` defines the only fields visible to blind judges.
- Judge item IDs are salted opaque IDs, never the private trigger-encoded IDs.
- `frozen_fixture_manifest.schema.json` binds the full item/trigger inventory
  and content hash required by the semantic scorer.
- `as0_policy.json` freezes the Candidate trigger, Candidate request config,
  item/accounting thresholds, duplicate policy, consensus rules, and KPI gates.
- `role_manifest.template.json` is intentionally invalid until exact providers,
  model versions, prompt hashes, and config hashes are supplied for the
  Candidate, generator, semantic duplicate auditor, three labelers, and
  adjudicator. Placeholders must never be treated as a frozen manifest.
- The Markdown prompt contracts are frozen inputs whose SHA256 values belong in
  the final role manifest. Preflight compares those values with actual file
  hashes and canonical config hashes from `as0_policy.json`.

This is the AS0T core-contract slice, not the complete AS0 execution toolchain.
AS0R exact role selection and AS0X runner, isolated repair, request/response
provenance, and hash-bound output emission remain pending. No preflight result
from this slice can authorize a request.

## Offline verification

```bash
python3 -m unittest tests.test_a13_ai_silver -v
```

Raw provider requests and responses stay outside Git. Only normalized,
validator-accepted, hash-bound summaries may later become tracked evidence.
