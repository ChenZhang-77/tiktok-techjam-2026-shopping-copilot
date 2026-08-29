# 标注示例

以下示例不属于 `items.jsonl`，只用于说明格式。

## 1. 明确替换

Prior state：`material=cotton`  
Current message：`Actually, make it leather instead.`

```json
{
  "intent_hint": null,
  "positive_constraints": [
    {
      "attribute": "material",
      "value": "leather",
      "evidence_span": "leather",
      "hard": true
    }
  ],
  "rejected_constraints": [],
  "no_preference_attributes": [],
  "override_attributes": ["material"],
  "semantic_terms": [],
  "abstain": false
}
```

## 2. 无正向偏好，但保留排除条件

Current message：`Any color is fine, but not black.`

```json
{
  "intent_hint": null,
  "positive_constraints": [],
  "rejected_constraints": [
    {
      "attribute": "color",
      "value": "black",
      "evidence_span": "black"
    }
  ],
  "no_preference_attributes": ["color"],
  "override_attributes": [],
  "semantic_terms": [],
  "abstain": false
}
```

## 3. 弱偏好

Current message：`I would prefer something packable.`

```json
{
  "intent_hint": "buying",
  "positive_constraints": [
    {
      "attribute": "feature",
      "value": "packable",
      "evidence_span": "packable",
      "hard": false
    }
  ],
  "rejected_constraints": [],
  "no_preference_attributes": [],
  "override_attributes": [],
  "semantic_terms": [],
  "abstain": false
}
```

## 4. 无法消解的自相矛盾

Current message：`I want red, but no red.`

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

Notes 可写：`Same value is explicitly both required and rejected.`

## 5. 只有不完整的 override 指令

Prior state：`color=black`  
Current message：`Use a different color instead.`

没有提供新颜色，也没有明确变成 color no-preference，因此不要创造值：

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
