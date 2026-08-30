# Branch Inventory — 2026-08-31

Snapshot taken before release-document commits; short SHAs below identify recoverable source points, not the eventual remote publication tips.

| Local branch | Source HEAD | Disposition |
| --- | --- | --- |
| `a/a10a-question-value` | `9b140bd` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `a/a10b-query-plan` | `76bc533` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `a/a11-extraction-scope` | `8213065` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `a/a13-llm-semantic-understanding` | `bbb0075` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `a/a8-intent-assessment` | `6811a49` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `a/a9-should-ask` | `0049e7b` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `ab/ab0-decision-evidence` | `58dd70c` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `ab/ab1-route-semantics` | `7719fe4` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `b/b10a-constraint-preserving-crossencoder` | `6cf3948` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `b/b11-prerequisite-audit` | `3b90c54` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `b/b12-adaptive-depth` | `ebf3c21` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `b/b8-rejected-constraint-ranking` | `fca2279` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `b/b9-browsing-conditional-dense` | `8416f6a` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `b/r0-failure-taxonomy` | `df641ca` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `chen/chenzhang-77-baseline-setup` | `0bd3375` | Selected Plan One source; publish to remote yuqing |
| `llm` | `7f0dc6c` | Publish to remote llm; optional Plan Two |
| `main` | `b5d97ea` | Preserve; do not publish main |
| `p0/submission-readiness` | `aaa7e45` | Frozen packaging/demo draft; old runtime, do not submit as new source |
| `patryk/track4-experiments` | `bddf7d7` | Frozen historical checkpoint; preserve code/evidence, no automatic resumption |
| `yuqing` | `9530e94` | Stale local pointer; preserve, not the new remote release |

## Remote snapshot before publication

Origin: `ChenZhang-77/tiktok-techjam-2026-shopping-copilot`.

| Remote | Verified SHA before this publication |
| --- | --- |
| llm | `ccbb2fbb3a01212cacd66e6224e4db534a779e41` |
| yuqing | `ebf3c2102b071df1ddeafb7ab21b7cb6ec19b8bc` |
| main | `0bd33755dcef6db066cf11b5a0a87e0ade554a5e` |
| Zhang-Chen | `129018573fccb27643b5c3769b4519ae46ccc788` |

These are pre-push facts, not live aliases. Use `git ls-remote --heads origin`
to inspect current publication tips. Only llm and yuqing are authorized targets.

P0 and some historical checkpoints are local-only. A fresh remote clone may
not contain those commits; the recovery commands below require this preserved
shared local repository. Publishing llm/yuqing does not publish an archival P0 ref.

## What is preserved

No branch, catalog, embedding/model cache, annotation file or raw run is deleted.
The existing stash named `backup: pre-A13 cleanup of p0 worktree 2026-08-29`
is untouched; it is user work, not something to apply or drop during cleanup.

The three existing worktrees remain on their original local branch names.
P0's build/package/verification scripts and report/demo drafts remain recoverable
at `aaa7e45`; cherry-picking or regenerating them into a newer runtime is a
separate delivery step with synchronization and fresh-directory tests.

Old long-form guidance can be read without changing the checkout:

```bash
git show 7f0dc6c:docs/current_status.md
git show 7f0dc6c:docs/optimization_roadmap.md
git show 0bd3375:docs/current_status.md
git show aaa7e45:submission/PROVENANCE.md
```

Do not restore those files over current guidance merely to resume an obsolete
next-step instruction. See [final release plan](final_release_plan.md).
