# A13 标注示例速查

普通标注者请直接双击 `标注示例.html`。HTML 版本包含九个完整示例，每个示例都按
“Prior state → Current message → 为什么这样标 → 不要这样标 → 完整 label”解释。

## 判断顺序

1. 新 evidence 只能来自 `current_message`。
2. `prior_state` 只用于判断 override，不要把旧字段复制到 label。
3. 能得到完整、无矛盾、逐字可举证的变化时，才设置 `abstain=false`。
4. 替换指令没有新值，或同一个 attribute/value 既要又不要时，设置
   `abstain=true`，其余 label 字段全部为空。

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

完整 JSON label 与更多边界示例请打开 `标注示例.html`。
