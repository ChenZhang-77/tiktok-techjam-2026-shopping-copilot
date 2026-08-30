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

By explicit coordinator direction, the 34 individually valid Zhangchen rows
are now retained as a provisional comparison subset rather than discarded.
This lets joint review begin on 18 valid disagreements while the 26 invalid
rows remain excluded. It does not change the gate conclusion below.

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

## The valid-34 subset is usable for provisional adjudication

A coordinator-local artifact was generated without modifying either source
annotation:

`/Users/patryk/Documents/workspace/tiktoktechjam/a13_annotation_pack_v1/provisional_valid34_comparison.json`

Its SHA256 is
`94904faff2f844d0d9727fa52a85a8111b7b57acd0e15fe52cb7eff64490f612`.
It retains the full context and both submitted labels for 16 agreements and 18
disagreements, and separately records every excluded row and validator reason.
It is deliberately stored outside the repository fixture package so provisional
labels cannot be mistaken for frozen gold or become runtime/test hints.

The included subset is highly unbalanced relative to the frozen protocol:

| Trigger stratum | Required for final fixture | Included now |
| --- | ---: | ---: |
| `override_without_value` | 10 | 1 |
| `mixed_polarity_clause` | 10 | 9 |
| `low_confidence_residual_feature` | 20 | 4 |
| `multi_clause_without_structure` | 10 | 10 |
| `positive_rejected_attribute_conflict` | 10 | 10 |

Therefore this artifact may be used to start adjudicating the 18 valid
disagreements and to estimate where label definitions differ. It must not be
used to estimate final trigger-level accuracy, choose a Candidate trigger,
freeze `a13_ambiguity_v1.jsonl`, or authorize a provider.

## AI suggestions reduce review work but do not adjudicate it

Two additional coordinator-local artifacts now prepare the valid-34 subset for
human review:

| Artifact | SHA256 |
| --- | --- |
| `provisional_valid34_ai_adjudication_suggestions.json` | `560f000ada6dfba284c64f4c45f81e8d85ba9cf43662a179a9f44e7fbe8abd5c` |
| `provisional_valid34_ai_labels.jsonl` | `ed802888715962348c30f4f18c260a4bfc683b1336fa55c20ec1b3da7228618d` |

Both live beside the returned annotation files. The labels JSONL carries the 16
exact agreements plus 18 proposed resolutions. The suggestions JSON documents
only those 18 pending decisions: it recommends the `codex` label for 17 and
proposes one synthesized resolution for `LRF-011`, feature `hides dust` with
`hard=false`, preserving the minimal complete property from one submission and
the weak “would be ideal” modality from the other. All 34 proposed labels
individually pass the package's label validator.

Every one of the 18 suggestions remains `human_status=pending`. These artifacts
are an AI-authored review accelerator, not joint adjudication, annotator
provenance, or gold. A human reviewer must accept, edit, or reject each pending
suggestion before any provisional comparator score can be described as
human-reviewed.

## Deterministic dry-run exposes contract failures

The valid-34 AI draft was also used for one explicitly provisional, offline
deterministic-parser dry-run. The report is coordinator-local:

`/Users/patryk/Documents/workspace/tiktoktechjam/a13_annotation_pack_v1/provisional_valid34_deterministic_comparator.json`

Its SHA256 is
`098494e451dc36799d6cea63fb7c6623fb00660c689ea55aed33606ceab1a336`.
It was generated from clean commit `c556231`, binds the items, provisional
annotations, and catalog hashes, validates each prediction without repairing
it, and makes no provider call.

| Diagnostic | Valid-34 result |
| --- | ---: |
| Complete-label exact match | 13 / 34 (38.24%) |
| Invalid deterministic predictions | 16 / 34 (47.06%) |
| Positive-constraint field exact | 15 / 34 (44.12%) |
| Rejected-constraint field exact | 23 / 34 (67.65%) |
| Intent-hint field exact | 19 / 34 (55.88%) |
| Abstain field exact | 24 / 34 (70.59%) |
| No-preference / override / semantic-term field exact | 34 / 34 each |
| Applied runtime-state active/rejected conflicts | 0 / 34 |

The raw request projection's 16 invalid outputs comprise nine
positive/rejected conflicts, six unnormalized proposal values, and one value
outside the closed vocabulary.
Trigger-level exact counts are `OWV` 1/1, `MPC` 2/9, `LRF` 0/4, `MCS` 10/10,
and `PRC` 0/10. However, replaying the same deterministic evidence through the
default `SessionState.apply_user_context` leaves zero items with the same value
in active and rejected state: rejected evidence wins before the final query.
The nine raw PRC conflicts are therefore trigger/request-shape diagnostics, not
nine demonstrated runtime-state invariant failures.

These numbers are not an official accuracy result. The subset is unbalanced,
18 labels are still human-pending, and 17 of those AI recommendations copied
the `codex` draft, so the comparison is not independent of the implementation
being diagnosed. Its permitted use is narrower: locate contract/failure
classes, prepare adjudication, and predeclare the next deterministic test. It
must not select an LLM trigger or satisfy A13-C1.

Before changing the parser, the team must decide and document whether the
official deterministic comparator represents raw pre-state Shadow evidence or
the applied state delta. The former faithfully exposes why A13 is triggered;
the latter better represents default runtime behavior. Optimizing either
projection against these AI-pending labels would be circular, so this decision
must be made before full human adjudication and must not be chosen by whichever
version scores higher on the valid-34 subset.

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

1. The team may immediately review the 18 disagreements in the provisional
   valid-34 artifact, using the AI suggestions only as proposed resolutions;
   any decision remains provisional until human provenance is resolved and the
   complete fixture validates.
2. Zhangchen should reopen the original annotation UI/file and correct the 26
   listed rows using only `current_message` evidence. To preserve independence,
   provide the error class and item ID list, not the `codex` draft answers.
3. Run the standalone `validate` command again and require
   `annotation_count: 60` with exit code 0.
4. Resolve the provenance of `annotations.b.jsonl`. If it is an AI-authored
   draft, a second team member must independently annotate all 60 items. If a
   human actually owns the judgments despite the ID, that person must review
   and explicitly attest the whole file; simply renaming the ID is insufficient.
5. Only after two distinct human-owned files pass validation, run the official
   `compare` command and jointly adjudicate its disagreements.
6. Freeze `experiments/fixtures/a13_ambiguity_v1.jsonl`, its schema/instructions,
   annotator/adjudicator provenance, and SHA256 only after that sign-off.
7. After the full human-owned fixture is frozen, score the deterministic
   comparator using this predeclared projection. The valid-34 dry-run above is
   diagnostic only. The later outcome is A13-C1 for one qualified trigger or
   an explicit No-Go.

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
