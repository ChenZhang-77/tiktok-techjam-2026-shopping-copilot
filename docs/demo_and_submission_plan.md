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
| Public GitHub repository with reproducible README, limitations and credits | Private main published; component credits approved; public access still pending |
| Devpost project description, tools/APIs/libraries/data and links | `devpost_draft.md` prepared; actual form submission pending |
| Short public YouTube demo linked from Devpost | Rehearsed `demo_recording_script.md`; actual recording/upload pending |
| Permission-safe assets and attribution | Third-party notices and data attribution; team license/asset decisions pending |

A standalone ZIP/`submission/` is our convenient packaging layout, not a claim
that the PDF requires that exact filename or only one ZIP. No mandatory production
chat backend, real transaction system or extra PPT is inferred. API/result
walkthroughs can demonstrate the text-only Agent. The [live event page](https://tiktoktechjam2026.devpost.com/)
checked on 2026-08-31 specifies a public 3-minute YouTube video and a deadline of
2026-09-01 12:00 SGT, superseding our earlier 3–4-minute suggestion.

## One submission, preserved branches

Final Devpost points to existing repository **main**, plus the exact final commit.
Main contains the runnable bundle and evaluator-side evidence; judges need not
switch branches. Keep other branches for history. A public repository exposes
those branches too; main-only submission is not branch-level privacy.

The separately authorized main-only fast-forward completed on 2026-08-31 at
reviewed checkpoint `bb6b7f3`; all other remote heads and PRIVATE visibility were
verified unchanged. Release-status documentation follows that checkpoint.
The user subsequently approved public visibility and the current component
credits, and requested another project/copy review before filling. Revised copy
awaits approval; public access has not been enabled. The available CLI identity
has WRITE, not ADMIN, permission, so an owner/admin is needed for visibility.
Uploads and final submission still need action-time confirmation. Inspect remote
heads, public-history risks and signed-out access before public release.

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
- [x] User confirms both members registered and approves current component credits.
- [ ] Exact registered team name, source license and asset permissions confirmed.
- [x] Reviewed delivery integrated/pushed to private main; other remote branches preserved.
- [ ] Authorized public repository access enabled by owner/admin and verified.
- [ ] Actual public YouTube video and all Devpost fields verified/submitted.

Unfinished external gates remain unfinished even if every local test passes.
