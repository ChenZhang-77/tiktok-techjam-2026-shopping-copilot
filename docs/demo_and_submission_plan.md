# Demo and submission checklist

This is the team's operating checklist, not text to paste into Devpost and not
proof of publication. It is tracked in Git; "team-only use" is an audience label,
not access control. Do not store private contact details here. The supplied
competition PDF (Track4, pages33–37), participant kit and actual organizer
instructions govern submission. Our [approved rules](final_delivery_rules.md)
are implementation choices, not extra official requirements.

## What must be delivered

| Requirement | Prepared artifact / current boundary |
| --- | --- |
| Agent implementation and helper files | `submission/agent.py`, allowlisted `submission/src/` |
| Dependencies, setup, evaluator command | `submission/README.md`, pinned requirements, setup/evaluation tools |
| Method/model and runtime-cost report | `submission/REPORT.md`, configuration and bound evidence |
| Public GitHub repository with reproducible README, limitations and credits | PUBLIC visibility verified; main synchronization recorded in the execution log |
| Devpost project description, tools/APIs/libraries/data and links | `devpost_draft.md` prepared; actual form submission pending |
| Short public YouTube demo linked from Devpost | Rehearsed `demo_recording_script.md`; actual recording/upload pending |
| Permission-safe assets and attribution | Third-party notices and data attribution; team license/asset decisions pending |

A standalone ZIP/`submission/` is our convenient packaging layout, not a claim
that the PDF requires that exact filename or only one ZIP. No mandatory production
chat backend, real transaction system or extra PPT is inferred. API/result
walkthroughs can demonstrate the text-only Agent. The [live event page](https://tiktoktechjam2026.devpost.com/)
checked on 2026-08-31 specifies a public 3-minute YouTube video and a deadline of
2026-09-01 12:00 SGT, superseding our earlier 3–4-minute suggestion.

## Devpost 填表操作清单（仅供队内操作，不复制提交）

- 项目正文使用 [devpost_story.md](devpost_story.md) 的完整正文；其他已备齐文本使用
  [devpost_draft.md](devpost_draft.md) 中对应字段的文本块。不要复制标题、导航链接或本清单。
- 队名已由用户确认，准确值只维护在字段文档；项目名与队名是不同字段。
- 队长邮箱由用户私下提供，确认填表后只录入指定邮箱字段；不写进仓库、公开正文、图片或 ZIP。
  两位成员已报名；报名确认不等于代成员接受参赛条款。
- 视频、缩略图和图库尚未准备好，不在字段文档中放占位值。视频完成后填写真实公开 YouTube
  链接，并追加至项目说明；图片只能展示真实软件，核对素材权利，不把生成界面冒充实物截图。
- 观察到的表单限制为项目名 60 字符、简介 200 字符、技术标签最多 25 个；Built with
  按平台可用标签选择。DeepSeek 是可选技术，未用于最终离线 Full200 运行。
- Problem Statement 按实际下拉菜单选择对应 Track 4；技术标签和报名复选项不是整段文本粘贴。
- 附件使用 [final_readiness.md](final_readiness.md) 指定的当前 ZIP，观察到的上传上限为 35 MB。
  不上传工作区、catalog、模型缓存、凭据或其他分支 checkout；本操作清单不作为提交附件。
- 正文修订需用户确认后才填表。仓库现已核验公开；远端状态和剩余发布检查
  以 [current_status.md](current_status.md) 与 [final_readiness.md](final_readiness.md) 为准。
  确认退出登录后代码与视频可访问，再使用其链接。
- 保存草稿、接受规则、最终 Submit 是不同动作；遵守各自确认边界，最终核实 Submitted 状态。
  截止时间及视频要求见本文件上方已记录的赛事来源；不能把保存草稿当成提交完成。

## One submission, preserved branches

Final Devpost points to existing repository **main**, plus the exact final commit.
Main contains the runnable bundle and evaluator-side evidence; judges need not
switch branches. Keep other branches for history. A public repository exposes
those branches too; main-only submission is not branch-level privacy.

The separately authorized main-only fast-forward completed on 2026-08-31 at
reviewed checkpoint `bb6b7f3`; all other remote heads and PRIVATE visibility were
verified unchanged. Release-status documentation follows that checkpoint.
The PRIVATE observation above describes that earlier promotion, not current state.
GitHub now reports PUBLIC visibility, verified on 2026-08-31. The user authorized
public-entry cleanup, attachment rebuild/review and main-only synchronization;
see [execution log](final_delivery_execution.md). Revised copy still needs
confirmation before form filling. Uploads and final submission need action-time
confirmation; verify signed-out code/video access before using their links.

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
- [x] Exact registered team name confirmed; see the field values.
- [ ] Source license and asset permissions confirmed.
- [ ] Final video presenter/recorder credits confirmed.
- [x] Reviewed delivery integrated/pushed to private main; other remote branches preserved.
- [x] Public repository visibility verified; no visibility change performed by this cleanup.
- [ ] Actual public YouTube video and all Devpost fields verified/submitted.

Unfinished external gates remain unfinished even if every local test passes.
