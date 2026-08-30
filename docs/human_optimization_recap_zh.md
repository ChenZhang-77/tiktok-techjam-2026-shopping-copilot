# Shopping Copilot 优化复盘（通俗版）

## 这份文档解决什么问题

这是一份给团队成员和未来自己看的项目流水账。它从最早的 A1/B1
开始，按先后顺序说明：

- 每一步想解决什么问题；
- 实际做了什么；
- 数据有没有变；
- 最后是保留、撤回、跳过，还是仅作为可选实验；
- 下一步为什么这样安排。

详细数值仍以各阶段的 JSON 和 evidence 文档为准。这份中文复盘负责
解释，不替代原始实验记录。

## 先看结论

当前 Chen/A13 基线是在 **A11 的受限抽取增强 + AB1 的真实路由诊断 + B9 的
Browsing 条件式 dense/RRF** 之上，又加入三项 A 侧状态正确性修复。B12 虽然有
更好的旧 Development-160 汇总分，但它没有在看结果前写好保留门槛，而且收益
集中在一个 fold，所以默认关闭。

当前 A13 起点在 Development-160 上的结果：

| 指标 | A13 起点 | 通俗解释 |
| --- | ---: | --- |
| HitRate@10 | 0.925000 | 160 个会话中有 148 个最终在 Top 10 找到目标商品 |
| MRR | 0.552760 | 所有会话的目标商品总体排位；越接近第一名越好，未命中计 0 |
| MTTC | 4.131250 | 平均约 4.13 轮找到目标；越低越好，没找到按第 11 轮计 |
| Efficiency | 0.686875 | 由 MTTC 换算的效率分；越高越好 |
| TechnicalScore | 0.765703 | 50% 命中率 + 30% 排名 + 20% 效率的总分 |

这份结果来自 **Development-160**，不是未见过的最终测试集。当前仓库完整测试为
**353/353 passed**；权威运行状态与最新验证命令以 `docs/current_status.md` 为准。
本轮没有运行 Holdout-40 或 Full-200。

## 编号为什么不是连续的

项目经历过两版路线：

1. 第一版是 A1–A5 和 B1–B7，先把完整系统搭起来。
2. 第二版先做 R0 失败诊断，再从 A8、AB0、A9 继续精细优化。

因此仓库里没有正式的 A6、A7。这不是漏做，而是路线改版后沿用了新的编号。
AB0/AB1 表示 A、B 两侧共同依赖的接口或证据步骤。

## 第一阶段：先把 A 侧对话控制面搭起来

早期 A1–A5 是连续建设过程，当时没有给每一步留下独立、同口径、hash-bound
的 Development-160 对照实验。因此可以确认功能和累计结果，但不能诚实地说
“某一项单独提升了多少分”。

### A1 — 有状态的基础链路

**要解决的问题：** 原始 Agent 不能可靠记住多轮约束，也可能返回重复、无效或
不符合接口的商品。

**做了什么：**

- 增加 Response Guard，检查响应格式、商品 ID、去重和 Top-K；
- 增加按 `session_id` 隔离的 SessionState；
- 从当前有效约束构造查询，而不是把整段历史直接拼接；
- 支持用户改主意、否定旧条件和表示“这个属性无所谓”。

**结果：** 这些能力保留至今，是后续所有实验的基础。没有可单独归因的 A1
指标；其累计行为后来在 B0 基线中被固定。

### A2 — 主动且候选感知的澄清问题

**要解决的问题：** Agent 不能只给商品，还要在需求太宽时问一个有用问题；
同时不能重复询问已经回答或表示无所谓的属性。

**做了什么：**

- 加入主动澄清策略；
- 结合候选商品证据选择问题；
- 记录已询问属性和 no-preference；
- 保留“推荐结果 + 一个问题”的输出方式。

**结果：** 功能保留，但当时没有独立 A2 数值。后来 A9/A10a 专门检验“该不该问”
和“问什么”，并发现简单规则很容易伤害命中率。

### A3 — Buying/Browsing 路由与 Strategy

**要解决的问题：** 明确购买和开放浏览不应该永远走同一种搜索策略。

**做了什么：**

- 增加 Buying/Browsing 判断；
- 增加 Strategy planner；
- 让约束重排、查询深度和路由权重能够随意图变化；
- 加强 Intent Override 和 Boundary 场景处理。

**结果：** 形成了 A 给 B 发“搜索意图”的基础，但早期版本仍存在跨轮意图不稳定，
后来由 A8 专门修正。

### A4 — A/B 接口和诊断

**要解决的问题：** A 侧不应该知道检索内部实现，B 侧也不应该读取 SessionState
内部结构。

**做了什么：**

- 固定 `RetrievalRequest`、`RetrievalResult`、Candidate 和 diagnostics 边界；
- A 只发送当前有效约束、Strategy、query 等运行时信息；
- 禁止 target ASIN、hit/miss、scenario 等评测标签进入运行时；
- 为后续替换检索器准备稳定接口。

**结果：** A/B 可以独立开发。B1 随后验证替换到新检索 seam 后结果完全一致。

### A5 — 评测和加固

**要解决的问题：** 如果没有固定数据、测试和报告，后续任何优化都无法可信比较。

**做了什么：**

- 固定 Development-160 与四个 40 条 fold；
- 补充协议校验、无标签泄漏检查和可重复报告；
- 建立 keep/revert 的实验方式。

**累计检查点（后来由 B0 固定）：**

| HitRate@10 | MRR | MTTC | Efficiency | TechnicalScore |
| ---: | ---: | ---: | ---: | ---: |
| 0.762500 | 0.522693 | 5.318750 | 0.568125 | 0.651683 |

也就是 160 个会话命中 122 个。这个数是 A1–A5 累计系统的检查点，不应归因给
某一个 A 步骤。

## 第二阶段：B 侧检索与排序从 B1 做到 B7

### B1 — 新检索接口的等价迁移

**要解决的问题：** 在继续改检索前，先证明重构没有悄悄改变结果。

**做了什么：** 把 Agent 接到稳定的 HybridRetriever seam，并补充目录、回退和
诊断真实性。

**结果：** 与 B0 的总体指标、四类场景和全部 160 个会话完全一致。**保留**。

### B2 — 更深候选池、结构化约束与安全过滤

**要解决的问题：** 纯关键词只看文本相似度，不够理解颜色、材质、类别等跨字段
约束；硬过滤又可能因为商品字段缺失把候选清空。

**做了什么：**

- 建立更深的 lexical Candidate Pool；
- 加入跨字段 hard/soft 约束打分；
- 加入 guarded filter、自动放宽和不足补齐。

**数据：**

| 版本 | HitRate@10 | MRR | MTTC | TechnicalScore |
| --- | ---: | ---: | ---: | ---: |
| 纯 lexical | 0.718750 | 0.485851 | 5.406250 | 0.617005 |
| 有约束排序、无 guarded filter | 0.762500 | 0.522693 | 5.318750 | 0.651683 |
| B2 structured | 0.762500 | 0.526989 | 5.306250 | 0.653222 |

Guarded filter 没增加命中会话，但让已经命中的商品平均排得更靠前、略微更早找到。
四个 fold 都守住 HitRate，最终 **保留 structured 作为默认**。

### B3 — Dense retrieval 实验

**要解决的问题：** 测试语义向量能否补足关键词召回。

**做了什么：** 使用固定版本的 `all-MiniLM-L6-v2`，为 5 万商品建立可复现缓存，
补齐缺缓存、坏缓存和模型失败回退。

**数据：** Dense-only 的 HitRate 0.337500、MRR 0.160501、MTTC 8.212500、
TechnicalScore 0.272650，远差于 structured。

**结论：** 不能替换默认检索。它在四个 fold 中一共提供 4 个 structured 没找到的
补充命中，因此只保留为后续融合实验能力，**不作为默认**。

### B4 — Weighted RRF 多路融合

**要解决的问题：** Dense 单独很弱，但也许和 structured 合并能补充召回。

**做了什么：** 用 Weighted Reciprocal Rank Fusion 合并 lexical、structured、
dense 的名次，测试 `k=10` 和 `k=60`。

**最佳实验数据（k=10）：** HitRate 0.750000、MRR 0.486620、MTTC 5.168750、
TechnicalScore 0.637611。虽然平均轮数变少，但命中率和排名质量下降，四个 fold
输了三个。

**结论：** 融合代码和诊断保留为实验能力，**默认仍用 structured**。

### B5 — CrossEncoder 语义重排

**要解决的问题：** 在 structured 找出的 Top 30 中，用更强的语义模型重新排序，
看能否把正确商品推到前面。

**数据：**

| 指标 | Structured | CrossEncoder | 变化 |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.762500 | 0.781250 | +0.018750 |
| MRR | 0.526989 | 0.484162 | -0.042827 |
| MTTC | 5.306250 | 4.968750 | -0.337500 |
| TechnicalScore | 0.653222 | 0.656499 | +0.003277 |

它新增 10 个命中，但丢掉 7 个已有命中；四折 2 胜 2 负，Intent Override 明显回退，
每次重排约多 70.59 ms，历史峰值内存约 1.30 GB。

**结论：** 有潜力但不稳定且昂贵，**拒绝作为全局默认**，保留可复现实验。

### B6 — 集成和故障加固

**要解决的问题：** 确保真实 A-side Strategy、缓存、诊断和所有失败回退在一起工作。

**做了什么：** 补充路由诊断、错误/超时/缓存测试和资源记录。

**结果：** 默认 structured 与 B2 完全等价：HitRate 0.762500、MRR 0.526989、
MTTC 5.306250、TechnicalScore 0.653222；0 个响应异常、0 个无效 payload、
0 个已报告回退。**保留集成加固，不改变排序行为**。

### B7 — 冻结、审查和一次公开集评测

**要解决的问题：** 在提交前冻结配置，处理 Standards/Spec 审查问题，并留下最终
公开结果。

**做了什么：** 修复 dense 校验绕过、融合空结果、reranker 真超时终止、证据跨版本
比较等问题；最终 140 个全量测试和 39 个聚焦测试通过（当时测试规模）。

**历史 Full-200：** HitRate 0.765000、MRR 0.517355、MTTC 5.375000、
TechnicalScore 0.650207。

**重要边界：** 这 200 条包含后来已经暴露的 40 条 public holdout，只能作为历史
快照，不能再用于选参数，也不能代表当前 B9 默认版本。

## 第三阶段：先诊断，再继续精细优化

### R0 — Development-160 失败分类

**要解决的问题：** 先判断失败来自对话状态、抽取、策略、查询、召回还是排序，
避免盲目换模型。

**结果（当时 38 个 miss）：** Intent/Strategy 25、State/Override 7、Extraction 6。
目标商品进入 lexical pool 的会话是 145/160，所以当时最大问题在 A 侧而不是 B 侧。

**结论：** 先做 A8。Target 信息只用于 Development 离线分析，不进入 Agent、
RetrievalRequest、运行时 diagnostics、规则或模型。

### A8 — 跨轮保存意图判断

**要解决的问题：** 用户只回答一个澄清问题时，不能让之前已经明确的 Buying 意图
突然退回 Browsing。

**做了什么：** 在 SessionState 保存 A-owned `IntentAssessment`，包含 ordinal
confidence（low/medium/high）、证据、来源轮次和转移原因。

**数据：** HitRate 0.762500 不变；MRR 0.526989 → 0.529812；MTTC
5.306250 → 5.350000；TechnicalScore 0.653222 → 0.653194，整体近似持平。

**结论：** Buying 的稳定性更好，Browsing 不回退，但 Intent Override 略有损失。
因为状态语义和后续决策价值明确，受限版本 **保留**。Confidence 是等级信号，
不是概率，也不直接交给 B。

### AB0 — 为澄清决策准备完整候选证据

**要解决的问题：** A9 想判断“该不该问”，但旧代码只看到 Top-K 文本，看不到完整
Candidate Pool、稳定性、约束覆盖和过滤放宽情况。

**做了什么：** 在 A 侧 clarification 前构建 DecisionEvidence，包括完整池大小、
Top-K stability、constraint coverage、attribute partition、relaxation/degradation、
turn/exhaustion 等摘要。Raw Candidate ID/文本不跨接口。

**结果：** Development 指标和 160 个会话与 A8 完全一致；818-turn replay 的
问答/推荐 trace 也完全一致。**保留证据能力，不改变策略**。

### A9 — Should-Ask gate

**要解决的问题：** 候选已经足够集中时，Agent 是否应该停止追问、直接推荐。

**实验结果：** HitRate 0.762500 → 0.750000，MTTC 5.350000 → 5.431250，
TechnicalScore 0.653194 → 0.644556；丢失 2 个会话，没有新增命中。

**结论：** 规则过早停止或改变了对话路径，**已撤回**。AB0 的证据仍保留。

### A10a — 选择“最值钱”的问题

**要解决的问题：** 如果确实要问，应该问哪个属性才能最好地切分完整候选池。

**实验结果：** HitRate 0.756250、MRR 0.520012、MTTC 5.362500、
TechnicalScore 0.646879，主指标均回退。

**原因：** 当前 partition 只覆盖 category/material/color/style/use_case，其他允许
询问的属性被不公平地当成低价值，比较口径不完整。

**结论：** **已撤回**。以后只有补齐可比属性证据和 fallback 后才值得重试。

### A10b — A 内部可审计 QueryPlan

**要解决的问题：** 一条 query 字符串把类别、硬条件、软偏好、语义短语和排除项
混在一起，难以解释也容易把否定条件重新变成正向词。

**做了什么：** A 内部先拆成 category/hard/soft/semantic/residual/excluded，
再保守地渲染回原来的单一 `RetrievalRequest.query`。没有单方面改 A/B 公共接口。

**结果：** Development、场景和全部 160 个会话完全一致。**保留结构和可观测性，
不宣称质量提升**。

### A11 — 受限的抽取增强

**要解决的问题：** Agent 没识别出用户说的类别、材质、否定和 no-preference，
后面的查询与排序再强也无济于事。

**最终保留范围：**

- 从冻结 catalog 派生多词类别；
- clause/list 范围内的正向、负向和 no-preference 抽取；
- 数字与连字符消歧；
- 保持已有 QueryPlan renderer 和 A/B schema 不变。

**数据：**

| 指标 | A10b/A8 基线 | A11 | 变化 |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.762500 | 0.862500 | +0.100000 |
| MRR | 0.529812 | 0.545568 | +0.015756 |
| MTTC | 5.350000 | 4.675000 | -0.675000 |
| TechnicalScore | 0.653194 | 0.721420 | +0.068226 |

新增 19 个命中、丢失 3 个，净增 16 个，四个 fold 都提高。Boundary 的
TechnicalScore 下降 0.057083，是明确风险。原先更宽的 feature、brand、expiry、
residual cleanup 组合候选被拒绝；只有上述受限范围 **保留**。

### AB1 — “想运行”与“实际运行”分开记录

**要解决的问题：** Strategy 中 dense 权重大于 0，不代表 dense 真的执行过。旧诊断
会让人误以为系统已经使用混合检索。

**做了什么：** 诊断分别记录 requested routes、executed routes 和 fallback，
并校验它们必须互相一致。

**结果：** 所有 Development 指标、场景、会话和 folds 与 A11 完全一致。在 726 次
检索中 lexical/structured 各执行 726 次；dense 被请求 475 次，但实际执行 0 次。

**结论：** **保留**。它不涨分，但让架构声明真实，也为 B9 提供可靠入口。

### A12 — Profile ablation

**计划：** 检验长期用户画像作为弱 prior 是否有价值。

**当前状态：** 因时间原因明确延期，`profile_weight=0.0`。没有数据支持就不能宣称
系统已利用长期画像优化排序。

## 第四阶段：B8–B12 针对剩余检索问题做小步实验

### B8 — 被拒绝约束的软惩罚

**要解决的问题：** 用户说“不要皮革”后，包含皮革的候选应该适度降权。

**做了什么：** 使用 exact catalog evidence、0.80 confidence threshold 和最大
0.18 的软惩罚，并保证正向新条件覆盖旧拒绝、缺字段保持中性。

**结果：** 代码测试通过，但 Development-160 的 726 次检索里
`rejected_constraints` 实际出现 0 次，所以全部数据与 AB1 完全一致。

**结论：** 变量根本没被数据触发，无法证明有效，**已撤回**。

### B9 — 只给宽泛 Browsing 开启 dense + RRF

**要解决的问题：** 全局 dense 很差，但开放浏览可能比精确购买更需要语义补充。

**门槛：** Browsing、Strategy 要求 dense、最多一个 active constraint、structured
池至少 30 个。其他情况维持原 structured 顺序；dense 失败也回到完全相同的顺序。

**数据（相对 AB1）：**

| 指标 | AB1 | B9 | 变化 |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.862500 | 0.862500 | 0 |
| MRR | 0.545568 | 0.547329 | +0.001761 |
| MTTC | 4.675000 | 4.668750 | -0.006250 |
| TechnicalScore | 0.721420 | 0.722074 | +0.000654 |

725 次检索中 dense/fusion 实际执行 102 次；只有 4 个 Browsing 会话改变，3 个改善、
1 个回退，没有新增或丢失命中。四折没有回退。

**代价：** 初始化约 2.12 s → 3.58 s；峰值 RSS 约 563 MB → 1.109 GB；
dense p95 约 5.03 ms，总 retrieval p95 约 40.44 ms。

**结论：** 提升很小而内存代价明显，但它只影响合适的 Browsing、四折安全、失败
精确回退，并让 Track 4 的 dense route 真正运行，因此 **条件式保留为当前默认**。

### B10a — 保护头部结果的 CrossEncoder

**要解决的问题：** B5 全局重排破坏了强约束结果，所以这次固定 structured Top 3
或 Top 5，只重排后面的候选。

**数据：**

| 版本 | HitRate@10 | MRR | MTTC | TechnicalScore | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| B9 默认 | 0.862500 | 0.547329 | 4.668750 | 0.722074 | 基线 |
| 固定 Top 3 | 0.875000 | 0.515952 | 4.543750 | 0.721411 | 总分和 MRR 回退 |
| 固定 Top 5 | 0.868750 | 0.524025 | 4.543750 | 0.720708 | 总分和 MRR 回退 |

Top 3 四折 2 胜 2 负；每次实际重排平均约增加 68.82 ms，冷启动最大约 2.03 s。

**结论：** 两种都 **拒绝作为默认**，B9 默认完全不变。

### B10b — 真正的 LLM ranker

**当前状态：** 已实现 DeepSeek DS1：仅在 opt-in 的 Browsing Top-10 路径中受控
重排；DS2 把候选扩大到 Top-20。远程运行显示了可能的排序收益和 DS2 可靠性问题，
但完整报告仍在 `/private/tmp`，尚未形成 hash-bound tracked evidence。精确临时结果
只存在该临时目录，`docs/current_status.md` 只维护证据边界和 provisional 状态；
两者都不是默认路径。由此可以诚实地说
“已有受控 LLM 排序实验代码和临时测量”，不能说“默认 Agent 每轮都调用 LLM”。

### A13 — A 侧受控语义理解

下一项被选中的 LLM 工作不是扩大 B 侧重排，而是让 DeepSeek 在确定性解析之后生成
可验证的 `UnderstandingDelta`，帮助理解少量歧义、修正和否定表达。第一阶段只做
Shadow 记录，不得改变状态、策略、问题或推荐；通过触发覆盖、准确性、延迟、费用、
fallback 和固定折门槛后，才允许对单一触发类做候选激活。完整规范见仓库根目录
`DeepSeek_LLM接入实验方案.md`，当前尚未实现，不能提前声明效果。

### B11 — Lexical recall refinement

**进入条件：** 必须先证明目标商品经常没进入 lexical candidate pool。

**B11 当时的离线诊断：** 旧 B9 检查点的 22 个 miss 中，主要原因是
Intent/Strategy 16、Extraction 4、State/Override 2、Retrieval/Ranking 0；
在保留深度中目标商品覆盖 157/160。

**结论：** 在该检查点，召回不是主要瓶颈，贸然改 product text/field weight 风险大，
所以 **没有启动行为实验**。

### B12 — 自适应候选深度

**要解决的问题：** 高置信、约束充分的 Buying 不一定需要和宽泛请求一样深的候选池。

**可选规则：** 只有 Buying + high ordinal confidence + 至少两个 active constraints
才选择较小但不低于 60 的 depth；B 只接收合法 `Strategy.retrieval_depth`，不读取
原始 confidence。

**数据：**

| 指标 | B9 默认 | B12 可选 | 变化 |
| --- | ---: | ---: | ---: |
| HitRate@10 | 0.862500 | 0.868750 | +0.006250 |
| MRR | 0.547329 | 0.549735 | +0.002406 |
| MTTC | 4.668750 | 4.606250 | -0.062500 |
| TechnicalScore | 0.722074 | 0.727170 | +0.005096 |

它让 160 个会话中的命中从 138 增加到 139，只改变 3 个会话。但 fold 1 小幅下降，
fold 2/3 不变，主要增益全部集中在 fold 4；Buying MRR 还下降 0.001799。

**结论：** 汇总结果有希望，但当时没有在看结果前写好 keep/revert 门槛，事后再定
标准会构成 post-hoc selection。因此只作为 `--adaptive-depth` **可复现实验，默认关闭**。

## 历史 B9 检查点的数据应该怎么理解

### 1. HitRate@10：先看能不能找到

每个会话最多进行 10 轮。只要任意一轮返回的 Top 10 中出现目标商品，这个会话就是
一次 hit。该检查点 `0.8625 = 138 / 160`，有 22 个会话没找到。

它不关心目标排第 1 还是第 10，所以必须和 MRR 一起看。

### 2. MRR：找到以后排得够不够靠前

目标排第 1，贡献 1；第 2，贡献 1/2；第 10，贡献 1/10；没找到，贡献 0。
该检查点 0.547329 说明整体排名尚可，但它是所有会话的平均值，不等于“平均排第
1.83 名”，不能直接取倒数解释。

### 3. MTTC：需要聊多少轮

命中的会话使用第一次命中的轮数；10 轮仍未命中就按 11 计。该检查点为 4.66875，越低越好。
因此改善 MTTC 既可能来自更早命中，也可能来自把一个 miss 变成 hit。

### 4. Efficiency：MTTC 的换算分

公式是 `Efficiency = (11 - MTTC) / 10`，并截断到 0–1。它不是独立的新信息，
只是让“轮数越低越好”变成“分数越高越好”。该检查点 MTTC 4.66875 对应 0.633125。

### 5. TechnicalScore：官方技术总分口径

公式是：

```text
0.50 × HitRate@10 + 0.30 × MRR + 0.20 × Efficiency
```

命中率权重最大，所以不能为了让少数会话更早结束而牺牲很多 hit；这正是 A9、
B4、B10a 被拒绝的重要原因。

### 6. Fold：看提升是否只碰巧发生在一小块数据

Development-160 被固定分成四组，每组 40 条。理想改动应该多数 fold 不回退，
而不是总分全靠一个 fold 拉高。四个 fold 仍属于 Development-160，**不是另外的
Holdout-40**。

### 7. 场景数据

| 场景 | 样本 | 命中数 | HitRate@10 | MRR | MTTC | TechnicalScore |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Buying | 64 | 54 | 0.843750 | 0.517591 | 4.328125 | 0.710590 |
| Browsing | 64 | 56 | 0.875000 | 0.540272 | 4.546875 | 0.728644 |
| Intent Override | 24 | 21 | 0.875000 | 0.635764 | 5.458333 | 0.739063 |
| Boundary | 8 | 7 | 0.875000 | 0.576389 | 6.000000 | 0.710417 |

在该检查点，最弱的命中率是 Buying；Intent Override 排名最好但对话轮数偏多；Boundary
只有 8 条，一条会话就会让 HitRate 波动 12.5 个百分点，所以不能过度解读。

### 8. 从几个基线看累计进展

| 检查点 | HitRate@10 | MRR | MTTC | TechnicalScore | 说明 |
| --- | ---: | ---: | ---: | ---: | --- |
| 官方 weak BM25 | 0.125000 | 0.068034 | 9.810000 | 0.106710 | 最初参考线 |
| A1–A5 / B0 累计系统 | 0.762500 | 0.522693 | 5.318750 | 0.651683 | 对话控制面完成 |
| B2 retained structured | 0.762500 | 0.526989 | 5.306250 | 0.653222 | 检索结构化增强 |
| A11 + AB1 | 0.862500 | 0.545568 | 4.675000 | 0.721420 | 抽取大幅改善 |
| 历史 B9 检查点 | 0.862500 | 0.547329 | 4.668750 | 0.722074 | 小幅排名改善 |
| 可选 B12 | 0.868750 | 0.549735 | 4.606250 | 0.727170 | 实验性，默认关闭 |

从 B0 到历史 B9 检查点，净增 16 个命中，MRR 增加 0.024636，MTTC 降低 0.65 轮，
TechnicalScore 增加 0.070391。其中证据最强、贡献最大的单步是受限 A11；B9
只是小幅锦上添花。

## 现在项目处于什么状态

**已经做好的：**

- 多轮状态、覆盖/否定/no-preference、Buying/Browsing 和安全响应；
- 结构化 lexical retrieval、约束排序、guarded filter 和确定性回退；
- 在窄 Browsing 桶中实际运行的 dense + RRF；
- Development-160、四折、场景、会话级差异、延迟/内存和故障证据；
- A13-0 已绑定 Development-160、四 folds 和输入/evaluator hash；A13-1
  确定性候选已实测、拒绝并回滚；精确计数见 `docs/current_status.md`。

**仍然薄弱的：**

- 当前 hash-bound `0.925` 审计中的 12 个 miss 为 Question Policy 10、
  State / Override 2；A13-1 只清除了 active-state 半轴，`public_0002` 的旧值仍
  进入 QueryPlan positive residual，且四 folds 全部退化，因此未保留该候选；
- 完整 should-ask gate 尚未有可保留版本；
- 长期 profile 仍为 0 权重；
- B10b-DS1 仅是 opt-in LLM ranker，默认仍关闭；A13 只有离线 fake Shadow
  基础，尚无 provider transport 或真实语义质量证据；
- B9 的增益很小，内存成本明显；
- 当前好结果仍是 Development 数据，私有 800 条才是真正的外部泛化检验。

**建议下一步：** A13-S0 离线 types、fake、validator、gate、fallback、diagnostics
和 disabled/no-key/fake parity 已完成。现在由两名成员独立标注不少于 60 条人工
歧义集、共同复核并冻结 hash；完成此前不运行真实 API。通过 Shadow review gate
后才做 A13-C1 单一触发类候选激活。10 个 Question Policy miss 属于独立的 A14，
不与 A13 同时调参；B11、B12 和新的 reranker 同期冻结。

A14 已完成重新设计，但尚未改变运行时。关键结论不是“再调一个少问问题的阈值”：
本地 evaluator 会先给当前推荐打分，再根据 `ask_attribute` 生成下一轮回复；没问具体
属性只会得到无信息回复。因此 A14 首先优化“问哪个”，保留现有 ask opportunity，
等属性选择稳定后才单独测试“是否提前停止”。

推荐顺序是：先做逐轮 audit 和深 Question Policy Module 的行为等价封装；再为全部
允许属性建立 available/partial/unavailable/degraded 等显式证据状态；然后做确定性
selection Shadow，最后才开启只改变属性选择的 Candidate。缺失证据绝不当作零分。
LLM 不拥有策略：离线 teacher 只能聚类冻结且 hash-bound 的 catalog feature 短语，
并通过确定性验证；在线 advisor 不接收原始 feature 短语，只能基于有界汇总证据重排
已合格的问题短名单。两者都不能决定 stop、修改状态或绕过确定性回退。完整总纲见
`docs/question_policy_optimization_plan.md`。

## 证据入口

- 当前唯一状态源：`docs/current_status.md`
- 早期 B1–B7 决策：`docs/ablation_summary.md` 和 `docs/b7_review_resolution.md`
- R0：`docs/r0_development_failure_taxonomy.md`
- A8：`docs/a8_stateful_intent_evidence.md`
- AB0：`docs/ab0_decision_evidence.md`
- A9：`docs/a9_should_ask_evidence.md`
- A10a：`docs/a10a_question_value_evidence.md`
- A10b：`docs/a10b_query_plan_evidence.md`
- A11：`docs/a11_extraction_scope_evidence.md`
- A13-0：`docs/a13_0_baseline_evidence.md`
- A13-1：`docs/a13_1_state_override_evidence.md`
- A13-S0 离线基础：`docs/a13_s0_offline_evidence.md`
- AB1：`docs/ab1_route_semantics_evidence.md`
- B8：`docs/b8_rejected_constraint_evidence.md`
- B9：`docs/b9_conditional_dense_evidence.md`
- B10b：`experiments/deepseek_ds1.py`、`experiments/deepseek_ds2.py` 和 README
  的复现命令；完整远程运行报告目前只在 `/private/tmp`，尚未形成 tracked evidence
- A13：`DeepSeek_LLM接入实验方案.md`
- A14：`docs/question_policy_optimization_plan.md`
- B10a：`docs/b10a_constraint_rerank_evidence.md`
- B11：`docs/b11_prerequisite_evidence.md`
- B12：`docs/b12_adaptive_depth_evidence.md`

最后更新：2026-08-30。任何运行时代码变化后，都应重新跑 Development-160 和
四个固定 fold，再更新本文；文档提交本身不会改变指标。
