# Demo and submission checklist

This is the active delivery checklist, not proof of publication. The supplied
competition PDF (Track4, pages33–37), participant kit and actual organizer
instructions govern submission. Our [approved rules](final_delivery_rules.md)
are implementation choices, not extra official requirements.

## What must be delivered

| Requirement | Prepared artifact / current boundary |
| --- | --- |
| Agent implementation and helper files | `submission/agent.py`, allowlisted `submission/src/` |
| Dependencies, setup, evaluator command | `submission/README.md`, pinned requirements, setup/evaluation tools |
| Method/model and runtime-cost report | `submission/REPORT.md`, configuration and bound evidence |
| Public GitHub repository with reproducible README, limitations and credits | Main-only README prepared; main integration/public access and team credits pending |
| Devpost project description, tools/APIs/libraries/data and links | `devpost_draft.md` prepared; actual form submission pending |
| Short public YouTube demo linked from Devpost | Rehearsed `demo_recording_script.md`; actual recording/upload pending |
| Permission-safe assets and attribution | Third-party notices and data attribution; team license/asset decisions pending |

A standalone ZIP/`submission/` is our convenient packaging layout, not a claim
that the PDF requires that exact filename or only one ZIP. No mandatory production
chat backend, real transaction system or extra PPT is inferred. API/result
walkthroughs can demonstrate the text-only Agent. Suggested3–4minutes is an
editing target, not a verified official hard duration.

## One submission, preserved branches

Final Devpost points to existing repository **main**, plus the exact final commit.
Main contains the runnable bundle and evaluator-side evidence; judges need not
switch branches. Keep other branches for history. A public repository exposes
those branches too; main-only submission is not branch-level privacy.

No merge/push, public-visibility change, upload or final submit is implied by
preparing these materials. Inspect remote heads and public access at release time.

## Evidence and claims

Use [current status](current_status.md), [delivery evidence](delivery_reports/README.md)
and the technical report. The independent offline package's Dev160 result is
current; F2 paired results are explicitly historical. New paid verification is
gated. Frozen Full200 public reporting is separate from Dev160 selection and
cannot become a tuning input or unseen-data claim.

The visualizer forces offline simulation. Agent diagnostics are separate from
evaluator HIT/rank/scenario annotations. Historical experiments show saved
metrics only, never silently execute current code as old snapshots.

## Local completion and remaining gates

- [x] Approved scope and one offline-default entry with explicit bounded enhancement.
- [x] Source-only independent package, manifests and Dev160/four-fold parity.
- [x] Synthetic failure/contract tests and explicit local-asset degradation.
- [x] Local browser start/stop/diagnostics and four scenario API walkthroughs.
- [x] README, report, Devpost/credit drafts and recording script prepared.
- [x] Final offline runtime freeze and one Full200 public report (not unseen validation).
- [x] Final archive, provenance checks and last local dual review; see `final_readiness.md`.
- [ ] Independent fresh dependency install / intended evaluator-host validation.
- [ ] New real F2 package verification, only if separately authorized and needed.
- [ ] Team-approved names, roles, source license and asset permissions.
- [ ] Final main integration/public access verified.
- [ ] Actual public YouTube video and all Devpost fields verified/submitted.

Unfinished external gates remain unfinished even if every local test passes.
