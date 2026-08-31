# 06 — Audit the release and clear external submission gates

**What to build:** A final readiness report separating completed local delivery
from live verification, team approvals and actual public submission.
**Blocked by:** 02 — Dual configuration; 03 — Bundle; 04 — Replay; 05 — Materials.
**Status:** local-audit-complete; external-gates-pending

- [x] Local tests, clean-start, provenance and independent reviews are reconciled (prepared same-machine dependencies; intended-host installation still pending).
- [ ] New real F2 paired passes occur only with explicit transfer/budget authorization.
- [ ] Organizer network/resource policy and the official scoring configuration are confirmed.
- [x] After configuration freeze, one offline Full-200 public report is retained separately from Development evidence; no tuning or unseen-set claim, paid mode separately authorized.
- [x] Separately authorized reviewed delivery pushed to private main; other GitHub branches preserved.
- [ ] Actual Devpost submission references only final main/commit.
- [x] User confirms both members registered and approves existing component credits/publication.
- [ ] Asset/license decisions resolved; public access enabled by owner/admin; video and Devpost submitted with confirmation.
- [x] Incomplete external gates are reported, never marked as submission complete.

Final local Standards/Spec reviews pass at 2f0677c. Full details:
`docs/final_readiness.md`. The later explicit main-only authorization promoted
reviewed `bb6b7f3` to private remote main on 2026-08-31. The unchecked
public/organizer/live-LLM/team/video/Devpost items remain incomplete. No new paid
requests, branch deletion, visibility changes or competition submissions occurred.
