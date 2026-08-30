# A13 Annotation Intake Review

## Technical summary

The A13 human-fixture gate remains closed. The returned `annotations.b.jsonl`
passes the standalone validator with all 60 rows, but its sole `annotator_id`
is `codex`, so it is not evidence of a second team member's independent human
annotation. The returned `annotations.zhangchen (1).jsonl` covers all 60 rows
but fails validation on 26 rows (43.3%). The official comparison command fails
closed until both inputs validate, so there is no official disagreement report,
reconciled gold fixture, provider authorization, A13-C1 decision, or A14-S1
authorization from this intake.

Do not repair Zhangchen's original file in place and do not rename `codex` to a
human annotator. Either action would erase provenance rather than satisfy the
two-member independent-annotation requirement.

## The second submission is not comparison-ready

| Check | `annotations.b.jsonl` | `annotations.zhangchen (1).jsonl` |
| --- | ---: | ---: |
| Rows present, in required order | 60 / 60 | 60 / 60 |
| Validator result | pass | fail |
| Invalid rows | 0 | 26 |
| Abstain labels | 20 | 11 |
| Sole annotator ID | `codex` | `zhangchen` |
| Eligible for official compare now | no, human provenance unresolved | no, validation failed |

The Zhangchen failures are concentrated in three stable validator rules:

| Failure class | Count | Affected items |
| --- | ---: | --- |
| Value is not token-bounded by the current-message evidence span | 9 | `OWV-001`, `OWV-002`, `OWV-004`, `OWV-006`, `OWV-007`, `OWV-008`, `OWV-009`, `OWV-010`, `LRF-019` |
| Proposal value is not normalized | 15 | `OWV-003`, `MPC-003`, `LRF-001`, `LRF-002`, `LRF-003`, `LRF-005`, `LRF-006`, `LRF-007`, `LRF-009`, `LRF-010`, `LRF-014`, `LRF-015`, `LRF-016`, `LRF-017`, `LRF-020` |
| Proposal value is outside the closed attribute vocabulary | 2 | `LRF-004`, `LRF-013` |

The eight `OWV-*` token-bound failures shown above infer a concrete old value
from deictic phrases such as “that color” or “that fabric”. The annotation
contract permits prior state only for understanding an override; a proposed
value still needs token-bounded evidence in the current message. These cases
are semantic corrections, not safe formatting rewrites. Several `LRF-*`
failures likewise require renewed feature-versus-closed-attribute judgment, so
the coordinator must not mechanically normalize the entire file and call it an
independent submission.

## Raw agreement is diagnostic only

Before validity filtering, the two label files are exactly equal on 16 of 60
items (26.7%) and differ on 44. Because one file is invalid, these are intake
diagnostics rather than an official inter-annotator agreement result. Among the
34 Zhangchen rows that individually pass label validation, 16 match the `codex`
draft and 18 differ.

| Trigger stratum | Items | Invalid Zhangchen rows | Raw exact agreements |
| --- | ---: | ---: | ---: |
| `override_without_value` | 10 | 9 | 1 |
| `mixed_polarity_clause` | 10 | 1 | 1 |
| `low_confidence_residual_feature` | 20 | 16 | 1 |
| `multi_clause_without_structure` | 10 | 0 | 3 |
| `positive_rejected_attribute_conflict` | 10 | 0 | 10 |

The valid-but-different rows that will still require adjudication after a valid
second submission are:

`MPC-001`, `MPC-004`, `MPC-005`, `MPC-006`, `MPC-007`, `MPC-008`, `MPC-009`,
`MPC-010`, `LRF-008`, `LRF-011`, `LRF-018`, `MCS-002`, `MCS-004`, `MCS-005`,
`MCS-006`, `MCS-008`, `MCS-009`, and `MCS-010`.

No chart is used because this is a fixed 60-row gate audit with five strata;
the exact counts and repair identifiers are more useful than a distribution
graphic.

## Scope and method

The grain is one current-message annotation per fixed A13 item. Validation used
the exact standalone package received in
`/Users/patryk/Documents/workspace/tiktoktechjam/a13_annotation_pack_v1` and
the package's own `validate_annotations.py`; it did not inspect model output,
deterministic-parser output, product IDs, target labels, recommendations, or
the exposed holdout.

Input hashes:

| Input | SHA256 |
| --- | --- |
| `items.jsonl` | `61a41360490c72178ce083209b68eae643eb5a016570b7e021fd2f1ab31e0cb6` |
| `annotations.b.jsonl` | `17dab8df023a4771b27bab25a77c88865f9d6ee9e3d05c59d5973d33e8054be2` |
| `annotations.zhangchen (1).jsonl` | `dc8ae64d36a218a0b8ae5e385a6e0dac8f60b5d830d9017f85bff4d7b6b9c63e` |
| `README.md` | `a069d1f876da9ceb42ed4242adf1b3b2915eeeb8951b6df85510371d7864e336` |
| `validate_annotations.py` | `240162cbab0f140379dbb5e57a54085ee333e80af83567416ce71383b5736b38` |

The validator was run independently on both complete files. A row-level
diagnostic pass then invoked the same label validator for every Zhangchen row
to enumerate all failing item IDs. Raw exact agreement was calculated only as
a preflight diagnostic and is explicitly not treated as official comparison.

## Required remediation and next gate

1. Zhangchen should reopen the original annotation UI/file and correct the 26
   listed rows using only `current_message` evidence. To preserve independence,
   provide the error class and item ID list, not the `codex` draft answers.
2. Run the standalone `validate` command again and require
   `annotation_count: 60` with exit code 0.
3. Resolve the provenance of `annotations.b.jsonl`. If it is an AI-authored
   draft, a second team member must independently annotate all 60 items. If a
   human actually owns the judgments despite the ID, that person must review
   and explicitly attest the whole file; simply renaming the ID is insufficient.
4. Only after two distinct human-owned files pass validation, run the official
   `compare` command and jointly adjudicate its disagreements.
5. Freeze `experiments/fixtures/a13_ambiguity_v1.jsonl`, its schema/instructions,
   annotator/adjudicator provenance, and SHA256 only after that sign-off.
6. Score the deterministic comparator before viewing any real LLM result. The
   later outcome is A13-C1 for one qualified trigger or an explicit No-Go.

Until these steps are complete:

```text
fixture_frozen = false
real_api_authorized = false
A14-S1_authorized = false
```

## Limitations and open question

This review establishes schema/evidence validity and provenance gaps; it does
not adjudicate which valid-but-different label is semantically correct. The
remaining decision-relevant question is whether `annotations.b.jsonl` represents
a human's independently reviewed judgments or the earlier Codex-generated
draft. Human ownership must be resolved before the file can count toward the
two-member gate.
