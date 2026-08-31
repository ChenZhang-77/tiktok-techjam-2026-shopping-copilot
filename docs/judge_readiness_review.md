# Judge-facing material and public-release review

Date: 2026-08-31. Review base: `9d83674`, the directly verified private main.
Scope: improve the judge-facing story, recheck the submitted product/evidence,
and inspect public-release risks. No algorithm changes, new paid calls, Full200
rerun, remote push, form filling or visibility change are part of this revision.

## Verdict and boundaries

The offline product and retained evidence pass the checks below. The revised
English story leads with the shopping problem, explains design decisions, and
reports the measured result without turning it into unseen accuracy, real-user
conversion or a prize claim. User approval of the rewritten copy is still needed.

This is not a declaration of complete Track 4 fulfillment or completed submission.
Public visibility, video, final form confirmation,
intended-host installation and source/asset rights decisions remain open.
Known architectural gaps are listed explicitly below and in the public story.

## Product and evidence checks

- Full suite: 330 tests pass with offline flags, including synthetic standalone
  package startup, optional-provider failures, contracts and replay boundaries.
- Generated bundle: 37 files match the allowlisted source and manifest.
- `scripts/verify_delivery_evidence.py` passes: tested Python hashes, Dev160
  arithmetic/four folds/core-delivery parity, Full200 freeze/input hashes,
  200 recorded outcomes, failure counters and Dev160 subset parity reconcile.
- Every Python file and frozen numerical report/manifest is unchanged from
  `9d83674`. No new Agent evaluation of Full200 was performed.
- Full200 remains the exposed public population: 186/200 sessions hit Top-10,
  not 93% real-user conversion or a measured improvement over Development-160.
- Optional F2 is still a pre-run choice limited to eligible existing Top-10
  reranking. Historical paid evidence is not a new live integrated-package test.
- Validation uses the prepared same-machine environment. Synthetic independent
  startup is not a fresh full dense dependency installation on another machine.

## Archive

Earlier reviewed-copy candidate: `Track4_judge_review_with_evidence_2026-08-31.zip`.
SHA-256: `4a8ededc688b9d2f38bb6a97c324ac1ea85637e19341d6dfcc56592221e620ad`.

At that checkpoint all 45 entries matched both manifests and the checkout's
source/evidence bytes. It contains 37 submission files, seven evaluator-side evidence files and
one evidence manifest; no catalog, model weights, credentials or alternate branch
checkout. The earlier two ZIPs remain preserved. This ZIP is local and not uploaded.
The human-facing Devpost story is a repository document/form text, not Agent input.

## Public-release risk check

Direct remote heads match the local remote-tracking snapshot:

| Remote branch | Verified commit |
| --- | --- |
| main | `9d83674a1101ca86f29c6e430dbcaf45b2daa707` |
| llm | `a9e34ae4b125c8103b4f740134d7f1752a97c476` |
| yuqing | `9e1b1d4d1eedbd6cc777c2697f8844472b574016` |
| Zhang-Chen | `3b0141633f2df8044fcbde4e9f99794f30778e93` |

A read-only pattern scan covered 278 reachable commits and 2,131 commit/blob
objects, 55,456,353 bytes, with no oversized objects skipped. Patterns checked
provider token formats, private-key headers, quoted credential assignments and
credential-like filenames; no candidates were found. The current llm annotation
ZIP's ten files were separately checked for provider-token/private-key patterns,
also with no matches. No secret values were printed or saved in this report.

This is **not exhaustive security/privacy/license certification**. Pattern checks
can miss unfamiliar, encoded or split secrets. Server-only refs, Actions logs,
artifacts, issues and PRs were not audited. An owner must consider those before
making the repository public. The public dataset and historical annotation/
experiment assets remain in the repository's branches/history; the minimal
submission ZIP excludes the catalog, public input sessions and annotation pack.
Do not equate the ZIP's small allowlist with the entire repository's public scope.

Repository visibility is PRIVATE. The current CLI identity has WRITE, not ADMIN,
permission; an owner/admin must perform the visibility change. Publication
approval does not remove this permission requirement. All other remote branches
remain intact; making the existing repository public exposes them and history.
The new leader email is not copied to any public file or archive.

## Requirements and current confirmations

- Original PDF section 4.5 requires a public repository, written description,
  public YouTube demo and team contributions. Backend/API walkthroughs are valid.
- The [live event page](https://tiktoktechjam2026.devpost.com/) specifies a public
  3-minute YouTube video and deadline 2026-09-01 12:00 SGT. The recording script
  now targets 2:55–3:00, replacing our former internal 3–4-minute suggestion.
- The [event rules](https://tiktoktechjam2026.devpost.com/rules) require original
  work or significant updates during the submission period. The Git history
  retains both earlier development and changes after the period began; the team
  must describe that history honestly, not claim everything began on August 29.
- User confirms both members registered and approves the existing component
  credits/publication. Their public handles remain unchanged. This does not
  substitute for accepting terms for everyone. The exact team name was subsequently
  confirmed and is maintained in [field values](devpost_draft.md#team-name).
- Source-license and third-party asset decisions are not inferred from approval
  to publish. No new source license or ownership assertion was invented.
- Coverage gaps remain: complete over-generality retrieval cutoff, long-term
  profile updating/ranking and self-refining workflow orchestration. The offline
  run does not execute an LLM ranking stage. These must not be hidden by stronger
  marketing language or described as complete pillar fulfillment.

## Independent review

Independent Standards and Spec reviews of `9d83674...e8d7519` both pass with
zero actionable findings. Standards independently reproduced the 330-test suite;
both reviewers verified the 37-file bundle, frozen evidence and all 45 ZIP entries.
Neither review found runtime or numerical-evidence changes. The remote permission
and history-scan observations above were assessed as supplied, bounded evidence,
not repeated independently or treated as security certification.

This completion note changes review metadata only, not the reviewed submission
payload or ZIP. A pass of document consistency cannot clear the external gates
above. No push, publication, form filling or submission has been performed.

## Audience-boundary correction

The subsequent user/teammate review found that the zero-finding conclusion above
missed an important audience boundary. Both review axes identified two P2 issues
and one P3 issue: operational notes mixed into field values, a newly supplied team
name still marked missing, and internal approval language in the public story.
The earlier product/evidence checks remain historical evidence, not proof that
the copy was ready for direct submission.

The user authorized fixing those findings. The revision based on `318e948` keeps
only actual field values plus a clearly separated story link in the field document,
moves operating guidance to the existing team checklist, and replaces approval
language with product-focused wording. Private contact details remain outside Git.
Public-data, same-machine, live-LLM and architectural limitations are preserved.
Runtime and numerical evidence are unchanged. Independent re-review is pending.

The current attachment and its hash are recorded in [final readiness](final_readiness.md).
It only updates the package report's obsolete team-name gate and generated
document hashes; the three prior archives are preserved.
