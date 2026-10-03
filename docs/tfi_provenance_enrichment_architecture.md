# TFI Model Provenance & Enrichment Architecture

## 1. Context

Token Factory Initializr（TFI）当前已经从简单的 Model Catalog 演进为一个统一的 Model Knowledge / Model Selection 数据层。

当前主要数据源包括：

* NVIDIA NIM
* AMD Radeon Cloud
* Hugging Face Inference
* OpenRouter（作为 enrichment / validation source）

不同数据源提供的模型信息并不完整：

* AMD 可能缺少 `description`
* Hugging Face 可能缺少 `description`
* NVIDIA 可能缺少完整的 `capabilities`
* 不同 source 对 capability 的表达方式不同

当前系统已经支持 AMD 和 Hugging Face 的 capabilities normalization。

下一阶段需要引入 OpenRouter API：

```text
GET https://openrouter.ai/api/v1/models
```

作为模型信息 enrichment source。

核心问题：

> 当 canonical model 的某个字段来自另一个 source 时，系统必须能够回答“这个字段来自哪里、来自 source 的哪个字段、什么时候观察到、是原始事实还是 enrichment / inference / normalization”。

不要采用简单的 `reference_map`：

```json
{
  "nvidia.nvidia.deepseek-ai/deepseek-v4.1-flash.description":
    "openrouter.deepseek/deepseek-v4.1-flash.description"
}
```

而采用 **field-level provenance**。

---

# 2. Core Design Principle

采用以下数据模型：

```text
Raw Source
    ↓
Observation
    ↓
Canonical Model
    ↓
Field-level Provenance
```

核心原则：

> Model 是 canonical projection，Provenance 描述 canonical field 的来源和形成方式。

不要把 canonical model 设计成“引用另一个 model 的字段”。

错误方向：

```text
NVIDIA Model
    ↓ reference
OpenRouter Model
```

正确方向：

```text
NVIDIA Canonical Model
    ↓ provenance
OpenRouter Observation
```

---

# 3. Canonical Model

Canonical Model 继续作为 TFI Browse / Initializr 使用的主要数据结构。

示例：

```json
{
  "data_source": "nvidia",
  "provider": "nvidia",
  "model_id": "deepseek-ai/deepseek-v4.1-flash",

  "description": "....",

  "capabilities": {
    "input_modalities": ["text", "image"],
    "output_modalities": ["text"],
    "reasoning": true,
    "tool_calling": true
  }
}
```

Canonical Model 不应该因为 provenance 而变成 source-specific schema。

业务层应该直接使用：

```text
model.description
model.capabilities
```

而不是：

```text
model.description.value
model.description.source
```

除非确实存在需要同时暴露 value + provenance 的场景。

---

# 4. Provenance Schema

为 canonical model 增加：

```text
provenance
```

用于描述字段级数据来源。

推荐结构：

```json
{
  "provenance": {
    "description": {
      "source": "openrouter",
      "source_id": "deepseek/deepseek-v4.1-flash",
      "source_field": "description",
      "method": "enriched",
      "confidence": 0.99,
      "observed_at": "2026-10-03T02:00:00Z"
    },

    "capabilities.input_modalities": {
      "source": "openrouter",
      "source_id": "deepseek/deepseek-v4.1-flash",
      "source_field": "architecture.input_modalities",
      "method": "inferred",
      "confidence": 0.95,
      "observed_at": "2026-10-03T02:00:00Z"
    }
  }
}
```

Provenance key 使用 canonical field path：

```text
description

capabilities.input_modalities

capabilities.output_modalities

capabilities.reasoning

capabilities.tool_calling
```

不要使用：

```text
nvidia.nvidia.xxx.description
```

因为 provenance 描述的是：

> canonical field 的来源

而不是建立两个 source model 之间的静态字段引用。

---

# 5. Provenance Fields

每个 provenance record 至少支持：

```text
source
source_id
source_field
method
confidence
observed_at
```

### source

数据来源：

```text
nvidia
amd
huggingface
openrouter
models_dev
modelparams
provider_api
```

第一阶段至少实现：

```text
nvidia
amd
huggingface
openrouter
```

---

### source_id

source 中对应的数据实体。

例如：

```text
openrouter:
deepseek/deepseek-v4.1-flash
```

NVIDIA：

```text
deepseek-ai/deepseek-v4.1-flash
```

---

### source_field

source 中实际使用的字段路径。

例如：

```text
description

architecture.input_modalities

architecture.output_modalities

supported_parameters
```

支持 nested field path。

---

### method

定义 canonical value 的形成方式。

第一阶段支持：

```text
native
enriched
normalized
inferred
derived
```

含义：

#### native

canonical value 直接来自该模型自己的 primary source。

```json
{
  "source": "nvidia",
  "method": "native"
}
```

#### enriched

canonical value 使用其他 source 的原始信息进行补全。

```json
{
  "source": "openrouter",
  "method": "enriched"
}
```

例如：

```text
NVIDIA.description
← OpenRouter.description
```

#### normalized

source 原始字段经过统一 schema normalization。

例如：

```text
HuggingFace capability representation
→ TFI normalized capability
```

#### inferred

source 数据不能直接作为 canonical fact，而是通过 source 信息推断得到。

例如：

```text
OpenRouter architecture
→ NVIDIA endpoint capability
```

#### derived

根据已有 canonical fields 计算得到。

例如：

```text
input_modalities = ["image"]
+
output_modalities = ["text"]

→ capability.vision = true
```

---

# 6. Confidence

增加：

```text
confidence
```

用于描述：

> 当前 provenance 对 canonical field 的匹配 / 推导置信度。

不要把它解释为 source 本身的“可信度”。

示例：

```text
1.0
```

表示精确匹配。

```text
0.95
```

表示高度可信的 inferred / enrichment。

```text
0.80
```

表示存在一定不确定性的匹配。

第一阶段可以允许：

```text
0.0 <= confidence <= 1.0
```

但不要急于建立复杂的自动 threshold policy。

先保留 metadata 能力。

---

# 7. observed_at

所有 provenance record 应记录：

```text
observed_at
```

表示 source 数据实际被 TFI 观察到的时间。

不要使用：

```text
updated_at
```

来表达 source observation。

因为：

```text
updated_at
```

是 canonical entity 生命周期概念，而：

```text
observed_at
```

是 source observation 概念。

---

# 8. OpenRouter Enrichment

新增 OpenRouter enrichment stage。

数据来源：

```text
GET https://openrouter.ai/api/v1/models
```

OpenRouter 数据主要用于：

```text
description
context_length
architecture
supported_parameters
modalities
pricing
```

第一阶段重点实现：

```text
description
capabilities
```

不要一次性把所有 OpenRouter metadata 都接入 canonical schema。

---

# 9. Model Identity Matching

OpenRouter model ID 与 NVIDIA / AMD / Hugging Face model ID 可能不同。

例如：

```text
NVIDIA:
deepseek-ai/deepseek-v4.1-flash

OpenRouter:
deepseek/deepseek-v4.1-flash
```

因此不能简单：

```python
model_id == source_model_id
```

需要增加一个明确的 identity matching / source mapping 层。

第一阶段可以采用：

```text
exact normalized match
+
known provider/author mapping
+
model family / slug matching
```

但是：

> 不要为了 enrichment 而实现一个复杂的 AI model identity resolution 系统。

先抽象接口：

```python
ModelIdentityMatcher
```

例如：

```python
match(
    canonical_model,
    source_models
) -> MatchResult | None
```

`MatchResult` 至少包含：

```text
source
source_id
confidence
```

未来可以扩展更复杂的 matching strategy。

---

# 10. Enrichment Pipeline

当前 pipeline：

```text
fetch
→ parse
→ normalize
→ validate
→ deduplicate
→ store
→ summarize
→ notify
```

调整为：

```text
fetch
→ parse
→ normalize
→ identity-match
→ enrich
→ validate
→ derive
→ snapshot
→ diff
→ reconcile
→ publish
→ summarize
→ notify
```

如果当前代码结构不适合一次性完整调整，不需要强行重构整个 pipeline。

优先引入：

```text
identity-match
enrich
```

并保持 pipeline stage 的职责清晰。

---

# 11. Enrichment Rules

必须遵守以下规则：

### Rule 1 — 不覆盖已有 native fact

如果：

```text
NVIDIA.description
```

已经存在并且 provenance：

```text
source = nvidia
method = native
```

OpenRouter 不应该默认覆盖它。

---

### Rule 2 — 空字段允许 enrichment

如果：

```text
description = null
```

则：

```text
OpenRouter.description
→ canonical description
```

并写入：

```json
{
  "source": "openrouter",
  "method": "enriched"
}
```

---

### Rule 3 — enrichment 不等于 authoritative fact

例如：

```text
NVIDIA endpoint capabilities
```

由：

```text
OpenRouter model metadata
```

补全时：

```text
method = inferred
```

而不是：

```text
method = native
```

---

### Rule 4 — normalization 必须保留 source provenance

例如：

```text
HF raw capability
→ normalized capability
```

不要丢掉：

```text
source
source_field
observed_at
```

---

### Rule 5 — derived field 不应该伪造 source

例如：

```text
input_modalities=image
→ vision=true
```

这个字段应该：

```json
{
  "method": "derived"
}
```

而不是：

```json
{
  "source": "openrouter"
}
```

除非 `vision=true` 本身确实来自 OpenRouter 的明确字段。

---

# 12. Conflict Resolution

当多个 source 都提供同一个字段时，不应该简单按照“最后写入覆盖”。

例如：

```text
NVIDIA.description
OpenRouter.description
HuggingFace.description
models.dev.description
```

建立明确的 source precedence / resolution strategy。

第一阶段至少实现：

```text
native source
    >
trusted enrichment
    >
inferred
```

但不要把 OpenRouter 永久硬编码成“最高优先级”。

建议抽象：

```python
FieldResolver
```

或者：

```python
EnrichmentPolicy
```

未来可以按 field 配置：

```text
description:
    native > openrouter > huggingface

capabilities:
    native > normalized > openrouter > inferred
```

不要把 resolution policy 散落在各个 source adapter 中。

---

# 13. Provenance Storage

第一阶段不需要建立复杂独立 provenance database。

优先将 provenance 与 canonical model 一起存储：

```json
{
  "model_id": "...",
  "description": "...",
  "capabilities": {},

  "provenance": {}
}
```

例如：

```text
tfi:models:nvidia:nvidia:latest
```

仍然是 Browse 的主要数据入口。

如果未来 provenance 体积明显影响 Browse payload，再拆分：

```text
tfi:models:{data_source}:{provider}:latest
```

和：

```text
tfi:provenance:{data_source}:{provider}:{model_id}:latest
```

当前阶段不要提前复杂化。

---

# 14. Storage Boundary

Provenance 不应该由业务代码自己拼 JSON key。

统一通过 storage / model metadata layer 处理。

例如：

```python
ModelRecord
ModelProvenance
ProvenanceRecord
```

以及：

```python
set_field_provenance(...)
get_field_provenance(...)
```

不要在 pipeline 中出现大量：

```python
model["provenance"]["capabilities.foo"] = ...
```

pipeline 应该表达 semantic operation：

```python
model = enricher.enrich(model, observations)
```

而不是操作底层 storage representation。

---

# 15. API / Browse Considerations

Browse 页面默认只需要 canonical model：

```json
{
  "model_id": "...",
  "description": "...",
  "capabilities": [...]
}
```

不需要默认暴露完整 provenance。

如果需要 debugging / model detail，可以提供：

```text
provenance
```

例如：

```text
GET /models/:id
```

或者内部 debug/admin endpoint。

未来可以展示：

```text
Description
  Source: OpenRouter
  Observed: 2 hours ago

Capabilities
  Source: NVIDIA + OpenRouter
```

但不要在第一阶段为了 provenance 增加复杂 UI。

---

# 16. Tests

必须增加测试。

## Provenance tests

测试：

```text
native field
enriched field
normalized field
inferred field
derived field
```

---

## Enrichment tests

### Case 1

NVIDIA 没有 description：

```text
NVIDIA.description = null
OpenRouter.description = xxx

→ description = xxx
→ provenance.method = enriched
```

### Case 2

NVIDIA 已有 description：

```text
NVIDIA.description = xxx
OpenRouter.description = yyy

→ description = xxx
→ native value preserved
```

### Case 3

NVIDIA capability 缺失：

```text
OpenRouter capability exists

→ capability enriched/inferred
```

### Case 4

HF capability normalized：

```text
HF raw
→ normalized
→ provenance.method = normalized
```

### Case 5

Derived capability：

```text
input/output modalities
→ derived capability
```

---

## Conflict tests

测试：

```text
native + enrichment
enrichment + enrichment
inferred + native
derived + native
```

确保 resolver 行为 deterministic。

---

## Identity matching tests

至少覆盖：

```text
deepseek-ai/deepseek-v4.1-flash
deepseek/deepseek-v4.1-flash
```

以及：

```text
no match
ambiguous match
exact match
```

---

# 17. Backward Compatibility

当前已经存在的 model records 没有 provenance 时：

```text
provenance = {}
```

必须是合法状态。

不要要求一次性迁移所有历史数据。

OpenRouter enrichment 第一次运行后逐步生成 provenance。

不要因为缺少 provenance 导致旧模型不可用。

---

# 18. Do Not Overengineer

当前阶段明确不要实现：

* 独立 provenance database
* event sourcing
* 完整 lineage graph database
* AI-based identity matching
* 自动 source reputation system
* 复杂 confidence scoring framework
* provenance UI dashboard
* 全量 OpenRouter metadata ingestion
* 多层 Observation persistence

当前目标只是建立一个：

```text
简单
可扩展
可追踪
可解释
```

的 field-level provenance foundation。

---

# 19. Expected Architecture

最终目标：

```text
                    ┌─────────────────────┐
                    │    Source APIs      │
                    │                     │
                    │ NVIDIA              │
                    │ AMD                 │
                    │ HuggingFace         │
                    │ OpenRouter          │
                    └──────────┬──────────┘
                               │
                            fetch
                               ↓
                    ┌─────────────────────┐
                    │ Raw / Observation   │
                    └──────────┬──────────┘
                               │
                         normalize
                               ↓
                    ┌─────────────────────┐
                    │ Identity Matching   │
                    └──────────┬──────────┘
                               │
                           enrich
                               ↓
                    ┌─────────────────────┐
                    │ Canonical Model     │
                    │                     │
                    │ description         │
                    │ capabilities        │
                    │ context             │
                    │ ...                 │
                    └──────────┬──────────┘
                               │
                         provenance
                               ↓
                    ┌─────────────────────┐
                    │ Field Provenance    │
                    │                     │
                    │ source              │
                    │ source_id           │
                    │ source_field        │
                    │ method              │
                    │ confidence           │
                    │ observed_at         │
                    └─────────────────────┘
```

---

# 20. Definition of Done

Implementation is complete when:

1. Canonical Model 支持 field-level `provenance`
2. Provenance 至少支持：

   * `source`
   * `source_id`
   * `source_field`
   * `method`
   * `confidence`
   * `observed_at`
3. 支持：

   * `native`
   * `enriched`
   * `normalized`
   * `inferred`
   * `derived`
4. OpenRouter 可以作为 enrichment source
5. NVIDIA / AMD / Hugging Face 的 source facts 不会被 OpenRouter 无条件覆盖
6. 空字段可以被 OpenRouter enrichment
7. Capability normalization 不丢失 provenance
8. Identity matching 与 enrichment 解耦
9. Field conflict resolution 是 deterministic 的
10. 旧 model records 没有 provenance 时仍然合法
11. Browse API 默认仍然以 canonical model 为主，不强制暴露 provenance
12. 有完整 unit tests 覆盖 provenance、enrichment、matching、conflict resolution
13. provenance 不引入独立数据库或复杂 lineage graph
14. 所有 source-specific logic 保持在 source adapter / enrichment layer，而不是污染 Browse / Initializr 业务逻辑

## Final Principle

不要把 Provenance 实现成：

> “Model A 的字段引用 Model B 的字段。”

而应该实现成：

> “Canonical Model 的这个字段，是在什么时间、从哪个 source 的哪个 observation/field，以什么方式形成的。”

最终让 TFI 能够回答：

```text
What is the value?
        ↓
Canonical Model

Where did it come from?
        ↓
Provenance

How was it produced?
        ↓
Method

How confident are we?
        ↓
Confidence

When did we observe it?
        ↓
Observed At
```

这套机制应该成为 TFI 后续接入 OpenRouter、models.dev、ModelParams、provider `/v1/models` 等 enrichment source 的统一基础设施。

