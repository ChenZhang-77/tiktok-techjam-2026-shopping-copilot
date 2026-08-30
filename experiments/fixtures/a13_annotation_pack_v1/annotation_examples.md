# A13 标注示例速查

普通标注者请直接双击 `标注示例.html`。HTML 版本包含九个完整示例，每个示例都按
“Prior state → Current message → 为什么这样标 → 不要这样标 → 完整 label”解释。

## 判断顺序

1. 新 evidence 只能来自 `current_message`。
2. `prior_state` 只用于判断 override，不要把旧字段复制到 label。
3. 能得到完整、无矛盾、逐字可举证的变化时，才设置 `abstain=false`。
4. 替换指令没有新值，或同一个 attribute/value 既要又不要时，设置
   `abstain=true`，其余 label 字段全部为空。
5. 标注工具故意隐藏内部 `trigger_type`；触发类型不会显示，也不能作为答案依据。

## 最容易混淆的三种情况

### 明确替换

- Prior：`color=black`
- Current：`Actually, make it blue instead.`
- 标注：positive `color=blue`、`hard=true`、override `color`。
- 不要把旧的 black 自动标成 rejected；当前消息没有逐字排除它。

### 无偏好但仍有排除值

- Current：`Any color is fine, but not black.`
- 标注：no-preference `color`，同时 rejected `color=black`。
- 不要创建 `color=any`。无正向偏好不等于接受全部值。

### 不完整替换

- Prior：`color=black`
- Current：`Use a different color instead.`
- 标注：`abstain=true`，其他字段为空。
- 不要只输出 override，也不要猜一个新颜色。

## evidence、value 和 hard

- `evidence_span` 是当前消息中逐字出现的证据。
- `value` 是小写、去标点的规范值，不能凭空改写成原文没有的概念。
- “must / need / make it”通常是 `hard=true`；“prefer / would like”通常是
  `hard=false`。
- 例如 `Keep it under 80 dollars.` 应使用 value 和 evidence
  `under 80 dollars`，不要猜成 `cheap`，也不要只截取 `80`。

## feature 与 semantic_terms 的边界

- 明确描述商品性质或行为时，优先使用 open `feature`。例如
  `quiet when it moves` 标为 feature，而不是 semantic term。
- feature 的 value 采用最小完整属性短语：去掉 `I need`、`show me`、
  `would be ideal` 等请求框架，但保留否定词和使性质完整的补语。
- `semantic_terms` 只保留不描述商品属性、又无法进入 closed vocabulary 的检索
  上下文。例如 `graduation gift` 可以作为 semantic term。
- 只有活动、对象或场合能脱离商品性质独立检索时才拆出 semantic term；不要把
  `quiet when it moves` 机械拆成 feature `quiet` 加 semantic term `when it moves`。
- 同一短语不得同时出现在 positive/rejected constraint 和 `semantic_terms`。

完整 JSON label 与更多边界示例请打开 `标注示例.html`。
