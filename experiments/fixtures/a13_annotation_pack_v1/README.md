# A13 歧义语义独立标注包 v1

你将标注 60 条购物对话边界表达。目标是为每条当前消息给出一个结构化
`UnderstandingDelta`，作为后续比较确定性解析器和 DeepSeek Shadow 的人工标准。

这不是推荐质量标注。你不需要挑商品，也不会看到商品 ID、命中结果或模型输出。

## 最简单的操作方法

1. 双击 `开始标注.html`，不需要安装软件，也不需要直接编辑 JSONL。
2. 填写你的标注者代号；需要参考时，点击页面右上角的“查看清晰示例”。
3. 逐条填写。页面会在当前浏览器自动保存草稿，也可以导入之前下载的 JSONL 继续。
4. 完成 60 条后点击“验证并下载 JSONL”。页面会生成
   `annotations.<你的代号>.jsonl`；把这个文件发回即可。

标注者不需要打开终端。协调者收到文件后，为确保 evidence 和 runtime vocabulary
也正确，在本目录运行最终校验：

```bash
python3 validate_annotations.py validate \
  --items items.jsonl \
  --annotations annotations.<你的代号>.jsonl
```

看到 `annotation_count: 60` 才算正式验收完成。
如果不方便使用浏览器，`annotations.template.jsonl` 仍可作为高级/兼容入口，
但普通标注者无需直接打开它。
`annotation_schema.json` 只描述 JSON 形状；交叉字段不变量、evidence 和 runtime
vocabulary 以 `validate_annotations.py` 的结果为准。

## 独立性规则

- 可以查看 `开始标注.html`、`标注示例.html`、`items.jsonl` 和本 README。
- 不得查看另一名标注者的答案、规则解析器输出、DeepSeek 输出或分歧报告。
- 不得搜索商品或推测最终推荐。
- 不确定时不要猜：使用 `abstain=true`，并在 `notes` 简述原因。
- 全部独立提交后，才由协调者运行 `compare` 并共同复核分歧。

## 标注对象

每个 item 包含：

- `prior_state`：本轮之前已经确认的意图与约束；
- `current_message`：本轮唯一可以提供新 evidence span 的文本；
- `trigger_type`：为什么规则系统认为这条值得进入 Shadow 检查；它不是答案。
  每条已用固定 catalog 和当前 runtime gate 复算，构建器在任何分层不匹配时会直接失败；
- `source`：这些条目都是独立编写的边界表达。

你标的是“本轮可以安全提出的变化”，不是把 prior state 完整复制到 label。

## Label 字段

每个 `label` 必须恰好包含：

```json
{
  "intent_hint": null,
  "positive_constraints": [],
  "rejected_constraints": [],
  "no_preference_attributes": [],
  "override_attributes": [],
  "semantic_terms": [],
  "abstain": true
}
```

### `intent_hint`

- 只允许 `"buying"`、`"browsing"` 或 `null`。
- 仅当当前消息本身足以支持意图时填写；不要仅凭 prior state 复制。

### `positive_constraints`

当前消息明确想要或接受的属性值：

```json
{
  "attribute": "material",
  "value": "leather",
  "evidence_span": "leather",
  "hard": true
}
```

- `attribute` 只能是：`category`、`material`、`color`、`size`、`style`、
  `brand`、`budget`、`feature`、`use_case`。
- `value` 使用小写、去标点后的规范化短语。
- `category/material/color/size/style/use_case` 还必须属于包内 validator
  与 runtime parity test 绑定的 closed vocabulary；`brand/budget/feature` 依赖
  当前消息的逐字 evidence。
- `evidence_span` 必须逐字出现在 `current_message` 中，并包含完整 value token。
- 明确要求、明确选择或替代值用 `hard=true`；偏好、愿望或弱推断用
  `hard=false`。

### `rejected_constraints`

当前消息明确排除的值。字段只有 `attribute`、`value`、`evidence_span`，没有
`hard`。

### `no_preference_attributes`

只有当前消息明确表示“该属性随便、无偏好、不重要”时填写属性名。

`no preference` 表示没有正向偏好，不代表接受所有值。因此“颜色随便，但不要黑色”
可以同时标记 `no_preference_attributes=["color"]` 和 rejected `color=black`。

### `override_attributes`

当前消息明确替换、清除或改变 prior state 中的某个属性，并且本轮 label 对该属性有
新的 positive、rejected 或 no-preference evidence 时填写。仅说“换一个”，但没有安全
的新值或清除语义时应 abstain，不要凭空创造替代值。

### `semantic_terms`

仅用于当前消息中明确、对购物检索有用、但不描述商品属性且无法安全归入上述属性的
上下文短语。必须逐字出现在当前消息中。明确的商品性质或行为（如
`quiet when it moves`）优先标为 open `feature`；活动背景等无法进入 closed
`use_case` vocabulary 的上下文（如 `graduation gift`）才进入 `semantic_terms`。
不要重复已经写入 positive/rejected 的 value。

### `abstain`

- 无法形成安全、无矛盾的完整 delta 时使用 `true`。
- `abstain=true` 时，其余六个 label 字段必须为空或 `null`。
- 只要输出任何有效字段，`abstain` 就必须是 `false`。

## 冲突与取舍

- 同一 attribute/value 不得同时 positive 和 rejected。
- positive attribute 不得同时 no-preference。
- rejected value 可以与同属性 no-preference 共存。
- 后一句是否覆盖前一句，只在语言明确表达纠正或替代时采用；否则 abstain。
- evidence 只能来自当前消息，prior state 只用于理解 override 和连续语境。

## 完成后的协调步骤

两份文件都通过 `validate` 后，协调者运行：

```bash
python3 validate_annotations.py compare \
  --items items.jsonl \
  --left annotations.member_a.jsonl \
  --right annotations.member_b.jsonl \
  --output disagreements.json
```

共同复核仅处理 `disagreements.json` 中的条目。最终 reconciled gold 是下一阶段产物，
不要在独立标注期间创建或修改。
