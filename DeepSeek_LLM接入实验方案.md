# DeepSeek LLM 接入实验方案

> 状态：A13-0 已完成；A13-1 已拒绝并回滚；A13-S0 离线基础通过 parity；真实 provider 阶段仍受人工 fixture gate 阻塞。
>
> 当前发布分支：llm（源实验分支：a/a13-llm-semantic-understanding）
>
> 运行时来源基线：0bd33755dcef6db066cf11b5a0a87e0ade554a5e
>
> A13-0 clean comparator：b86a9e788f0388947351d14cedefa8f047367001
>
> 实验代号：A13-S0 影子语义理解；通过审查门后才能进入 A13-C1。

## 1. 一句话定位

DeepSeek 是 A 侧的受控语义解释器，不是第二个 Agent。

现有确定性 Shopping Agent 继续拥有 SessionState、意图转移、约束更新、
Strategy、QueryPlan、检索、澄清和回退。DeepSeek 只在本地规则证明当前
消息存在语义歧义时，返回一个可验证的 UnderstandingDelta 建议。

~~~text
简单明确消息
  -> 当前确定性路径

本地规则观测到歧义
  -> DeepSeek 语义解释
  -> 本地 schema / evidence / state-invariant 验证
  -> SessionState 唯一写入入口

无 key / 超时 / 非法输出 / 验证失败
  -> 调用前的确定性结果
~~~

## 2. 事实基线与审查结论

### 2.1 当前确定性基线

Chen 状态修正后的 Development-160 检查点：

| 指标 | 结果 |
| --- | ---: |
| HitRate@10 | 0.925000 |
| MRR | 0.552760 |
| MTTC | 4.13125 |
| Efficiency | 0.686875 |
| TechnicalScore | 0.765703 |

这是 Development-only 检查点，不是 sealed holdout 结论。A13 正式实验前
必须在新分支重新绑定 commit、catalog/split/evaluator hash 和运行命令。

### 2.2 当前 12 个 miss 的重新分类

2026-08-29 使用基线运行了一次只读 Development-160 离线审查，临时报告
只写入 /private/tmp，尚未绑定为仓库 evidence：

| 主要原因 | miss |
| --- | ---: |
| Question Policy | 10 |
| State / Override | 2 |
| Extraction | 0 |
| Intent / Strategy Routing | 0 |
| Retrieval / Ranking | 0 |

因此：

- 没有证据支持每轮用 LLM 覆盖现有语义解析；
- A13 必须先做 Shadow，不能直接改变用户可见行为；
- 直接得分优先级仍是 State / Override 和 Question Policy；
- 旧 taxonomy 机械推荐 next_experiment=A9 已过期，因为 A9 已测试并回滚；
- 如果 Shadow 不能证明困难语义上的净价值，应作 No-Go 决定。

### 2.3 与现有 B 侧 DeepSeek 的关系

B10b-DS1/DS2 的 opt-in 代码已存在；`/private/tmp` 中的临时远程报告显示 DS1
可能改善排序、DS2 触发可靠性问题，但完整报告尚未 hash-bound，因此两项结论
都只能称为 provisional，且都不是默认路径。证据边界以
[`docs/current_status.md`](docs/current_status.md) 为准。

A13 不替换、不重写 B10b-DS1：

- A13 在检索前理解困难用户表达；
- B10b-DS1 在检索后重排已有 Top-10；
- 同一 turn 默认最多一次远程 LLM 调用；
- A13 和 B10b-DS1 不在同一次指标实验中同时激活。

## 3. 目标与非目标

A13 要回答：

1. DeepSeek 能否在规则输出不完整或冲突时，更准确识别 positive、
   negative、no-preference 和 override 证据？
2. 这些解释能否经过本地验证，转化成不破坏 SessionState 的增量？
3. 严格 gate 下能否改善状态或指标，同时满足延迟、成本和失败率要求？

A13 不做：

- 不直接修改 SessionState；
- 不决定最终 Strategy 或 route weights；
- 不生成、挑选或重排 catalog ASIN；
- 不读取 target ASIN、hit/miss、scenario label、intent card 或未来 turn；
- 不同时重写 Question Policy；
- 不把 A/B 两侧 LLM 改动混成一个无法归因的实验；
- 不把 hosted model alias 描述为完全确定或完全可复现。

## 4. 所有权和 deep Module

A 侧继续拥有 Agent orchestration、SessionState 不变量、intent assessment、
Strategy、QueryPlan、clarification，以及是否接受语义建议。

新 Module 的外部 interface 保持小而稳定：

~~~python
class SemanticInterpreter(Protocol):
    def interpret(
        self,
        request: UnderstandingRequest,
    ) -> UnderstandingOutcome:
        ...
~~~

Module 内部隐藏 prompt、DeepSeek transport、JSON 解析、evidence-span 对齐、
词汇验证、timeout、fallback、token 和延迟诊断。Production 使用 DeepSeek
adapter，tests 使用 fake adapter；callers 和 tests 只穿过这个 interface。

Shadow 阶段不同时抽取 B 侧 DeepSeekSemanticRanker 的通用 transport，避免把
架构重构和指标调优绑定。如果 A13 保留，再以单独的无行为变更提取共享
DeepSeekJsonClient，并证明 B10b-DS1 严格等价。

## 5. 最小输入、输出和验证

UnderstandingRequest 只包含：

- 当前用户消息和 turn；
- 压缩后的 active/rejected/no-preference/override 摘要；
- 本地确定性解析结果；
- 相关 allowed attributes 和最小 CatalogVocabulary 摘要；
- prompt/config version 和 deadline。

不传入完整 catalog、完整 profile、无关历史、候选商品或评测标签。

模型输出：

~~~json
{
  "intent_hint": "buying",
  "positive_constraints": [
    {
      "attribute": "color",
      "value": "white",
      "evidence_span": "white",
      "hard": true
    }
  ],
  "rejected_constraints": [
    {
      "attribute": "color",
      "value": "black",
      "evidence_span": "not black"
    }
  ],
  "no_preference_attributes": [],
  "override_attributes": ["color"],
  "semantic_terms": [],
  "abstain": false
}
~~~

本地验证不变量：

1. 只接受允许字段和类型；
2. evidence_span 必须出现在当前用户消息；
3. 属性限于 category/material/color/size/style/brand/budget/feature/use_case；
4. 可验证值经过 CatalogVocabulary 归一化；
5. 没有当前文本证据的建议不能删除状态；
6. rejected/no-preference 不能被低置信建议恢复为 positive；
7. category override 仍由 SessionState 现有语义执行；
8. 模型数字 confidence 不作为校准概率；
9. 任一验证失败都丢弃完整 delta，不部分应用；
10. fallback 后 state、Strategy、query 和 recommendations 与 no-LLM 一致。

## 6. 触发 gate

Shadow 只在至少一个本地信号存在时请求模型：

- 有 override marker，但未提取替代值；
- 同句包含 positive、negative 或 no-preference 子句；
- 规则只产生 confidence=0.35 的 residual feature；
- 多从句购物表达没有有效结构化约束；
- 同一属性同时成为 positive 和 rejected；
- 存在不能由当前 IntentAssessment 证据解释的转移候选。

前五类是当前 Agent 路径上可复现的语义 Shadow 分层。
`unexplained_intent_transition` 是防御性 invariant signal：当前 `assess_intent`
在任何真实转移上都会携带 evidence，因此它不可从 Agent 运行路径上生成人工
语义样本。它保留在单元级 invariant 测试中，不得伪造空 evidence 来凑人工分层。

Candidate 只开放 Shadow 已证明有效的触发类型。不使用“模型自评低置信”
作为 gate。

全局限制：

- 默认关闭；
- 每 turn 最多一次远程调用；
- A13 激活时当轮不再执行可选 B10b-DS1；
- 无 key 正常走确定性 Agent；
- 不 retry，失败立即回退。

## 7. 实施与实验顺序

### A13-0：基线和当前 R0 绑定

**状态：已完成。** Development-160、四 folds、catalog/split/evaluator/fold
hash、完整测试和刷新后的 12-miss taxonomy 已绑定；Agent 行为未改变，未调用
DeepSeek。证据见
[`docs/a13_0_baseline_evidence.md`](docs/a13_0_baseline_evidence.md)。

- 校验新 worktree、HEAD 和干净状态；
- 只读提供 catalog 并验证 SHA256；
- 重现全量测试和 0.925 基线；
- 重跑当前 12-miss taxonomy；
- 修复或隔离过期 next_experiment=A9 推荐；
- 绑定 commit/data/evaluator/fold hash；
- 不改变 Agent 行为。

### A13-1：先处理 State / Override

**状态：已完成，拒绝并回滚。** 候选清除了两个诊断会话 active state 中的旧值，
但 `public_0002` 的旧值仍从当前 utterance 进入 QueryPlan positive residual；
同时 Development-160 丢失 3 个 hit、四 folds TechnicalScore 全部退化，故恢复
`0.925` comparator。证据见
[`docs/a13_1_state_override_evidence.md`](docs/a13_1_state_override_evidence.md)。
这是独立确定性实验，未调用 LLM：

- 诊断两个 override_old_value_still_active miss；
- 要求旧值从 active state 和 QueryPlan positive roles 同时消失；
- 不改变 Question Policy 或 B 侧排序；
- 单独 keep/revert 后重新冻结 Shadow comparator。

### A13-S0：Shadow 语义理解

**状态：离线基础已完成。** types、fake、validator、六类 local gate、fallback、
safe diagnostics、bounded vocabulary 与 Agent Shadow 注入已实现；disabled、no-key、
fake-abstain 三条 Development-160 均保持 `0.925`，公共行为差异为 0。没有
DeepSeek transport、key 读取或 API 调用。证据见
[`docs/a13_s0_offline_evidence.md`](docs/a13_s0_offline_evidence.md)。下一步必须先完成
不少于 60 条 fixture 的双人独立标注、共同复核和 hash freeze。
已准备可直接分发的 `experiments/fixtures/a13_annotation_pack_v1/`：60 条
无 gold items（五类可达语义 trigger 各 10 条，`low_confidence_residual_feature` 额外 10 条）、
可双击离线标注页、更清晰的双击示例页、兼容模板、schema、validator 和
disagreement compare CLI。60 条表达已经逐条审查并通过 runtime trigger/validator
检查；标注页隐藏内部 trigger 元数据，避免提示独立标注者。该包仅是
`annotation_ready_not_gold_frozen`，不代表双人标注或 fixture freeze 已完成。
协调者允许先用其中 34 条逐条合法的 Zhangchen 子集做 provisional 审查；基于
AI-pending 标签的 clean-commit 离线 deterministic dry-run 为 13/34 exact、
16/34 invalid，其中 9 条为正负约束冲突。该结果只用于定位 parser/contract
失败，不是独立人工 gold 上的准确率，也不能开放真实 API 或选择 Candidate。
下一确定性调查优先处理 polarity conflict 与合法 value projection；完整细节、
hash 和偏差边界见 `docs/a13_annotation_intake_review.md`。

- 先实现 types、fake、validator、gate、fallback 和 diagnostics；
- disabled/no-key 路径逐 turn parity；
- 真实 API 只产生 Shadow delta；
- 不改变 state、query、Strategy、question 或 recommendations；
- 在真实 API 前冻结 `experiments/fixtures/a13_ambiguity_v1.jsonl` 及 SHA256；
- 用冻结的人工歧义集比较规则与模型，不用 target ASIN 调 prompt；
- 报告触发率、有效建议率、schema、fallback、延迟、token 和费用。

人工歧义集及判分协议必须在第一次真实 API 运行前固定：

- 至少 60 条，不少于 10 条/当前 Agent 可达的预定义语义触发类型；
  防御性不可达 invariant signal 只做单元测试。准备进入 Candidate 的单一触发类
  至少 20 条；
- 样本来源可以是去标识化的规则失败表达和独立编写的边界表达，但不含 target
  ASIN、hit/miss、scenario label、未来 turn 或推荐结果；
- 每条保存 prior-state 摘要、当前消息、触发类型和规范化 gold delta；
- 两名成员独立标注，分歧经共同复核后冻结；记录 schema 版本、标注说明和文件 hash；
- 主指标为完整 `UnderstandingDelta` exact-match；另报字段级 precision/recall、
  abstain、invalid 和状态不变量违反数；
- 确定性解析器在同一冻结集上的输出是 comparator，不在看到 LLM 结果后改 gold。

### A13 审查门

全部满足才允许进入 Candidate：

1. schema success >= 99%；
2. fallback exactness = 100%；
3. Shadow 用户可见行为变化 = 0；
4. 至少一个预定义触发类型（样本数 >= 20）的 exact-match 比确定性 comparator
   高 >= 10 个百分点且至少净多 5 条正确；其他触发类型不得回退超过 5 个百分点，
   状态不变量违反数必须为 0；
5. 预计 Candidate 调用率 <= 20% turns；
6. remote p95 目标 <= 2000 ms，硬超时 2500 ms；
7. 平均 prompt 目标 <= 500 tokens；
8. 无 key、prompt/响应原文、用户标识或 evaluator 信息泄漏；
9. focused/full tests 通过；
10. Standards + Spec review 无未解决高优先级 finding。

### A13-C1：受控状态增量

- 只启用通过 Shadow 门的触发类型；
- 只应用通过全部本地不变量的完整 delta；
- Development-160 和四 folds 至少三次无缓存真实 API 运行；
- 报告 gained/lost/tied sessions；
- 不用 Full-200 或已暴露 holdout 调参。

Candidate 保留门：

1. 至少净新增一个 Development 命中，或预定义且可复现地降低 MTTC；
2. TechnicalScore delta 三次运行中位数为正；
3. 三次运行的中位数至少 3/4 folds TechnicalScore delta >= 0；
4. 三次运行的 scenario 中位数满足：Buying/Browsing 各自最多损失 1 个 hit 且
   TechnicalScore delta >= -0.005；Intent Override 和 Boundary 不得损失 hit，
   Intent Override TechnicalScore delta >= -0.005；Boundary 其余指标因 n=8 只作
   披露，不单独据此 keep；
5. 失败时与冻结 comparator 严格等价；
6. 零状态不变量违反、零 invalid response、零 evaluator leakage；
7. 满足调用率、延迟、token、成本和 fallback gate。

### A14：Question Policy，后续独立实验

当前 10/12 miss 指向 Question Policy，所以它是直接得分优先级。但必须在
A13 keep/revert 后单独开始：

- 先复核旧 A9/A10a 失败机制；
- 先定义 ask | stop 和 allowed attribute 的可观察证据；
- 先测确定性策略，再决定是否需要 LLM advisor；
- 不与 A13-C1 同一次实验激活。

## 8. 测试和报告

单元与故障注入至少覆盖：

- disabled/no-key/fake；
- malformed、empty、truncated JSON；
- 多余字段、非法属性和值、evidence span 不匹配；
- positive/rejected/no-preference 冲突；
- 无证据 override/removal；
- prompt injection；
- timeout、DNS、401/403/429/5xx 和 internal exception；
- 失败时完整 delta 丢弃；
- 同 turn 最多一次 backend call。

状态与集成测试至少覆盖：

- 多 session 隔离；
- no-preference/rejected/override 不变量；
- disabled/fallback 的 state、Strategy、QueryPlan、ask 和 recommendations parity；
- diagnostics 不含 prompt/响应/key/evaluator label；
- public response schema 不变；
- RetrievalRequest 和 route-weight 语义不变。

每次真实 API run 至少记录：

~~~text
experiment_id / repeat_index / timestamp_utc
git_commit / baseline_commit
catalog / split / evaluator / prompt / config hashes
requested_model / response_model / request_id
aggregate / fold / scenario metrics
gained / lost / tied sessions
eligible / activated / successful / fallback turns
fallback reasons
prompt / completion / cache tokens
latency p50 / p95 / p99 / max
estimated cost and pricing snapshot date
~~~

未决定 keep 前，真实远程报告写入 /private/tmp，不写 tracked evidence。

## 9. 配置和安全

~~~bash
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
A13_LLM_ENABLED=false
A13_LLM_SHADOW=false
A13_LLM_TIMEOUT_MS=2500
A13_LLM_PROMPT_VERSION=a13-understanding-v1
A13_LLM_TEMPERATURE=0
A13_LLM_MAX_COMPLETION_TOKENS=256
A13_LLM_RESPONSE_FORMAT=json_object
A13_LLM_THINKING_MODE=disabled
A13_LLM_MAX_USER_CHARS=2000
A13_LLM_MAX_STATE_CHARS=2000
A13_LLM_MAX_VOCAB_ITEMS=200
~~~

- key 只放 .env.local 或进程环境，永不进 Git；
- 不在日志、diagnostics、报告或截图显示 key；
- CI 只使用 fake；
- no-key 是支持的正常运行方式；
- config hash 必须包含以上全部有效字段、system/user prompt 模板和 schema 版本；
- 超出输入上限时不调用模型，记录 `input_too_large` 并走确定性路径；
- 模型、价格和 API 行为以实验当日官方信息为准。

## 10. 文件范围和提交纪律

预计文件按阶段限定如下；只有实际诊断需要时才修改列出的 runtime 文件：

| 阶段 | 预计文件 |
| --- | --- |
| A13-0 | 主变更：`experiments/failure_taxonomy.py`、`tests/test_failure_taxonomy.py`；可复现证据：`tests/test_a13_0_baseline_evidence.py`、`docs/a13_0_baseline_evidence.{md,json}`、`docs/a13_0_reports/`；完成后同步 README、current status、roadmap 与 A-side workstream 导航/状态文档 |
| A13-1 | 候选曾修改 `starter/core/state.py`、`starter/core/context_engine.py` 和 endpoint test，随后显式回滚；决定证据为 `docs/a13_1_state_override_evidence.{md,json}`、`docs/a13_1_reports/` 和 `tests/test_a13_1_state_override_evidence.py` |
| A13-S0 | 离线基础已新增 `starter/core/semantic_understanding.py`、`experiments/a13_shadow.py`、`tests/test_semantic_understanding.py`，并仅为注入和 parity 修改 `starter/agent.py`、`tests/test_agent_smoke.py`；`experiments/fixtures/a13_ambiguity_v1.jsonl` 仍是双人标注完成后才能新增的下一 gate 产物 |
| A13-C1 | 只在 S0 文件和必要的 state/integration tests 内激活已通过的单一触发类；决定完成后才新增 `docs/a13_c1_evidence.{md,json}` |

临时真实 API 报告仍写 `/private/tmp`。只有阶段决定完成、provenance/hash 完整且
工作树干净时，才新增上表中的 tracked evidence。

首轮不改：

- evaluator、public labels、catalog；
- RetrievalRequest/RetrievalResult schema；
- Strategy route weights；
- B 侧 retrieval/ranking；
- Question Policy；
- submission package。

每阶段独立 commit、comparator 和 keep/revert。禁止在同一 commit 混合：

- provider 重构与指标调优；
- State/Override 修复与 LLM 激活；
- A13 与 A14；
- A/B 两侧 LLM 激活；
- runtime 变更与 submission 打包。

## 11. 分支和集成顺序

~~~text
chen/chenzhang-77-baseline-setup @ 0bd3375
  -> a/a13-llm-semantic-understanding
      -> A13-0
      -> A13-1
      -> A13-S0
      -> review gate
      -> A13-C1 or No-Go
      -> llm publication branch for the reviewed offline checkpoint
      -> regenerate P0 submission package last
~~~

- 不直接修改 Chen 分支做 A13；
- 不在 p0/submission-readiness 上修改 runtime；
- 未经明确授权不 push、merge 或开 PR；
- P0 在最终 runtime 冻结后重新同步。

## 12. 最终 Go / No-Go

Keep：只有当 DeepSeek 在窄触发类型上带来稳定、可归因的状态或指标改善，
同时满足延迟、成本、安全和回退 gate，才保留 Candidate。

No-Go：若 Shadow 不能证明困难语义的净价值，或 Candidate 没有提升指标，
就保留实验证据并默认关闭。不为了“看起来用了 LLM”扩大模型权限。

最终原则：

> 让模型解释少量规则系统无法确定的当前语义；让确定性 Agent 继续掌握
> 状态、决策、检索和失败回退。
