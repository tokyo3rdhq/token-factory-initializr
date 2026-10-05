# TFI Agent-Friendly Model Catalog API

## 1. Objective

为 Token Factory Initializr（TFI）增加一套 **Agent-friendly、OpenAI-compatible 的公开 Model Catalog API**。

目标不是创建新的 Model 数据源，而是：

> 将 TFI 当前已经 canonicalized / normalized 的 Model Catalog，以稳定、标准、易于 Agent 消费的 HTTP API 形式公开。

API 应支持：

* OpenAI-compatible `/api/v1/models`
* Model list
* Model detail
* `data_source` filter
* `provider` filter
* `capabilities` filter
* `llms.txt`
* `agents.md`

所有接口均为公开、无鉴权的 GET API。

---

# 2. Product Interface

最终提供：

```text
GET https://start.magi.website/api/v1/models

GET https://start.magi.website/api/v1/models/{id}

GET https://start.magi.website/llms.txt

GET https://start.magi.website/agents.md
```

Model list 支持：

```text
GET /api/v1/models?data_source=nvidia

GET /api/v1/models?provider=groq

GET /api/v1/models?capabilities=chat,vision

GET /api/v1/models?data_source=huggingface&capabilities=vision,reasoning
```

---

# 3. Design Principles

## 3.1 Canonical Model Catalog

API 只读取 TFI 当前 canonical Model Catalog。

不要在 API layer：

* 重新抓取 NVIDIA
* 重新抓取 AMD
* 重新抓取 Hugging Face
* 重新抓取 OpenRouter
* 执行 enrichment
* 执行 normalization
* 执行 deduplication

这些属于已有 data pipeline。

API layer 的职责：

```text
KV / Canonical Catalog
        ↓
API projection
        ↓
HTTP response
```

---

## 3.2 No Provenance

公开 API **不返回 provenance**。

不要返回：

```json
{
  "provenance": {}
}
```

也不要返回：

```json
{
  "source_field": "...",
  "observed_at": "...",
  "confidence": 0.95
}
```

Provenance 是 TFI 内部 data quality / lineage 能力，不属于 public Model Catalog API。

API 返回的是：

> 当前 TFI 认为正确的 canonical model representation。

---

# 4. OpenAI-Compatible Model List

实现：

```text
GET /api/v1/models
```

返回 OpenAI-compatible list response。

推荐结构：

```json
{
  "object": "list",
  "data": [
    {
      "id": "openai/gpt-oss-120b",
      "object": "model",
      "created": 0,
      "owned_by": "groq",

      "data_source": "groq",
      "provider": "groq",

      "capabilities": [
        "chat",
        "reasoning",
        "tool_calling"
      ]
    }
  ]
}
```

---

# 5. OpenAI Compatibility

兼容 OpenAI `/v1/models` 的基本 response shape：

```text
object
data[]
```

每个 model 至少包含：

```text
id
object
created
owned_by
```

其中：

```text
object = "model"
```

如果 TFI 没有可靠的 model creation timestamp：

```json
{
  "created": 0
}
```

不要伪造模型创建时间。

---

# 6. TFI Extension Fields

在 OpenAI-compatible model object 上增加 TFI-specific fields：

```text
data_source
provider
capabilities
```

例如：

```json
{
  "id": "openai/gpt-oss-120b",
  "object": "model",
  "created": 0,
  "owned_by": "groq",

  "data_source": "groq",
  "provider": "groq",

  "capabilities": [
    "chat",
    "reasoning",
    "tool_calling"
  ]
}
```

不要把 TFI 内部 schema 全量暴露。

尤其不要暴露：

```text
provenance
raw_source_data
internal storage keys
pipeline metadata
confidence
observed_at
```

---

# 7. Model ID

API 的 `{id}` 使用 canonical `model_id`。

例如：

```text
GET /api/v1/models/openai/gpt-oss-120b
```

其中：

```text
model_id = openai/gpt-oss-120b
```

API router 必须正确处理 model IDs 中的 `/`。

不要假设：

```text
{id}
```

一定是单个 path segment。

实现时使用 catch-all / wildcard route 或等价机制。

例如：

```text
/api/v1/models/:id{.+}
```

具体语法根据当前 framework/router 实现。

---

# 8. Model Detail API

实现：

```text
GET /api/v1/models/{id}
```

例如：

```text
GET /api/v1/models/openai/gpt-oss-120b
```

返回单个 canonical model 的 public representation。

推荐：

```json
{
  "id": "openai/gpt-oss-120b",
  "object": "model",
  "created": 0,
  "owned_by": "groq",

  "data_source": "groq",
  "provider": "groq",

  "name": "GPT OSS 120B",

  "description": "...",

  "capabilities": [
    "chat",
    "reasoning",
    "tool_calling"
  ],

  "context_length": 131072
}
```

具体字段以当前 canonical Model schema 中已经存在的数据为准。

**不要为了 API 添加大量新的 Model fields。**

API 是 canonical model 的 projection。

---

# 9. Filter API

`GET /api/v1/models` 支持：

```text
data_source
provider
capabilities
```

---

## 9.1 data_source

例如：

```text
GET /api/v1/models?data_source=nvidia
```

只返回：

```text
data_source == "nvidia"
```

多个 data sources 可以支持：

```text
GET /api/v1/models?data_source=nvidia,amd
```

语义：

```text
data_source IN ["nvidia", "amd"]
```

如果当前实现不需要多值 data_source，可以第一阶段只支持单值，但 API schema 应尽量保持可扩展。

---

# 10. provider Filter

例如：

```text
GET /api/v1/models?provider=groq
```

多个 provider：

```text
GET /api/v1/models?provider=groq,together
```

语义：

```text
provider IN ["groq", "together"]
```

注意：

```text
data_source != provider
```

不要混淆两者。

例如：

```text
data_source = huggingface
provider = together
```

是合法的数据。

---

# 11. Capabilities Filter

核心接口：

```text
GET /api/v1/models?capabilities=chat,vision
```

这是 Agent-friendly API 的重点能力。

---

## 11.1 Capability Semantics

多个 capability 默认采用：

```text
AND
```

也就是说：

```text
?capabilities=chat,vision
```

表示：

> 返回同时具备 `chat` AND `vision` 的模型。

例如：

```text
Model A:
chat
vision

Model B:
chat

Model C:
vision

→ only Model A
```

---

## 11.2 Capability normalization

API filter 只能针对 canonical normalized capabilities。

不要在 API layer 判断：

```text
architecture.input_modalities contains image
```

也不要在 API layer重新解释：

```text
supports_vision
multimodal
image_input
```

这些应该在已有 normalization pipeline 完成。

API 只做：

```text
canonicalModel.capabilities.includes(capability)
```

---

# 12. Capability Naming

第一阶段使用当前 TFI 已经定义的 normalized capability vocabulary。

不要因为 API 实现而重新设计 capability taxonomy。

例如可能包括：

```text
chat
vision
audio
video
image_generation
reasoning
tool_calling
structured_output
embedding
```

实际可用值必须来自当前 canonical schema / normalization implementation。

如果某个 capability 尚未被 canonical pipeline 支持：

> API 不应该自行增加这个 capability。

---

# 13. Filter Combination

支持：

```text
GET /api/v1/models?data_source=nvidia&provider=nvidia&capabilities=chat,vision
```

语义：

```text
data_source = nvidia
AND provider = nvidia
AND capabilities contains chat
AND capabilities contains vision
```

整体 filter：

```text
AND
```

单个 query parameter 的多个值：

```text
OR
```

因此：

```text
provider=groq,together
```

表示：

```text
provider == groq OR provider == together
```

而：

```text
capabilities=chat,vision
```

表示：

```text
chat AND vision
```

---

# 14. Search

第一阶段不要额外实现：

```text
?q=
```

全文搜索。

当前 API 的核心目标是：

```text
catalog discovery
+
structured filtering
+
model detail
```

如果未来需要 search，再设计独立 semantics。

不要在本次任务中扩大 scope。

---

# 15. Pagination

第一阶段如果当前 Model Catalog 数量仍然较小，可以：

```text
GET /api/v1/models
```

直接返回全部 models。

但是 API implementation 应保持未来增加 pagination 的空间。

不要设计：

```text
page
offset
cursor
```

除非当前 catalog 数据量已经证明需要。

如果暂时不分页，应在 API documentation 中明确：

> 当前 endpoint 返回全部匹配 models。

未来可以增加：

```text
limit
cursor
```

而不破坏现有 response shape。

---

# 16. Empty Result

例如：

```text
GET /api/v1/models?capabilities=nonexistent
```

应该返回：

```http
200 OK
```

```json
{
  "object": "list",
  "data": []
}
```

不要把“没有匹配模型”当作 HTTP 404。

---

# 17. Invalid Filter

对于未知 capability：

```text
GET /api/v1/models?capabilities=foo_bar
```

建议返回：

```http
400 Bad Request
```

并提供 machine-readable error：

```json
{
  "error": {
    "message": "Unknown capability: foo_bar",
    "type": "invalid_request_error",
    "param": "capabilities",
    "code": "invalid_capability"
  }
}
```

对于未知 provider / data_source，可以根据当前产品策略选择：

### Option A

返回空：

```text
200 + data=[]
```

### Option B

400 invalid filter。

优先选择一种并保持一致。

推荐：

```text
unknown capability → 400
unknown data_source/provider → 200 empty
```

因为 capability 是固定 vocabulary，而 provider/data_source 是动态 catalog data。

---

# 18. Content Type

所有 JSON API：

```http
Content-Type: application/json
```

字符编码：

```text
UTF-8
```

---

# 19. Caching

这是一个公开、无鉴权、读多写少的 Catalog API。

必须充分利用 Cloudflare caching。

推荐：

```http
Cache-Control: public, max-age=300
```

或者根据当前数据更新周期选择合理 TTL。

对于：

```text
/api/v1/models
/api/v1/models/{id}
```

应该尽可能 cache-friendly。

不要每次 API request 都直接访问 KV 并重新构建完整 catalog。

优先：

```text
Cloudflare Cache
    ↓
Worker
    ↓
KV
```

或者根据现有架构采用等价的 caching strategy。

---

# 20. CORS

因为 API 的主要目标之一是 Agent / Web tooling consumption，可以允许跨域读取：

```http
Access-Control-Allow-Origin: *
```

这是 public GET-only catalog API，可以接受公开 CORS。

不要因为 CORS 而引入 authentication。

---

# 21. HTTP Methods

只实现：

```text
GET
```

POST / PUT / DELETE 等方法不属于 public API。

---

# 22. API Documentation

创建一个简单、机器友好的 API documentation。

至少说明：

```text
GET /api/v1/models

GET /api/v1/models/{id}

Query parameters:
- data_source
- provider
- capabilities
```

提供完整 examples：

```text
/api/v1/models

/api/v1/models?data_source=nvidia

/api/v1/models?provider=groq

/api/v1/models?capabilities=chat,vision

/api/v1/models?data_source=huggingface&capabilities=vision,reasoning

/api/v1/models/openai/gpt-oss-120b
```

---

# 23. llms.txt

创建：

```text
/llms.txt
```

目标：

> 让 AI Agent 能快速发现 TFI 的机器可读入口。

内容应该简洁，不要复制完整网站文案。

建议结构：

```text
# Token Factory Initializr

TFI is an AI model catalog and Token Factory configuration generator.

## Model Catalog

Machine-readable model catalog:

https://start.magi.website/api/v1/models

The API is OpenAI-compatible and does not require authentication.

## Model Filtering

Filter by data source:

https://start.magi.website/api/v1/models?data_source=nvidia

Filter by provider:

https://start.magi.website/api/v1/models?provider=groq

Filter by capabilities:

https://start.magi.website/api/v1/models?capabilities=chat,vision

Multiple filters can be combined.

## Model Details

Retrieve a specific model:

https://start.magi.website/api/v1/models/{model_id}

Model IDs may contain `/`.

## Human Interface

https://start.magi.website/browse
```

不要在 `llms.txt` 中加入：

* provenance
* internal KV keys
* implementation details
* credentials
* internal APIs

---

# 24. agents.md

创建：

```text
/agents.md
```

这是给 Agent 更详细的操作说明。

建议结构：

```markdown
# TFI Agent Interface

TFI provides a machine-readable model catalog for AI agents.

## Base URL

https://start.magi.website

## Model List

GET /api/v1/models

Returns an OpenAI-compatible model list.

No authentication is required.

## Filters

### Data Source

GET /api/v1/models?data_source=nvidia

### Provider

GET /api/v1/models?provider=groq

### Capabilities

GET /api/v1/models?capabilities=chat,vision

Multiple capabilities use AND semantics.

### Combined Filters

GET /api/v1/models?data_source=huggingface&capabilities=vision,reasoning

All different filter dimensions use AND semantics.

## Model Details

GET /api/v1/models/{id}

Use the model's `id` returned by `/api/v1/models`.

Model IDs may contain `/`.

## Response

The model list follows the OpenAI-compatible:

{
  "object": "list",
  "data": [...]
}

Each model includes:

- id
- object
- created
- owned_by
- data_source
- provider
- capabilities

Model detail responses may include additional canonical model metadata.

## Provenance

The public API does not expose internal provenance metadata.

## Recommended Agent Workflow

1. Fetch `/api/v1/models`.
2. Filter by capability, provider, or data source.
3. Select candidate models.
4. Fetch `/api/v1/models/{id}` for detailed metadata.
5. Use the TFI web interface to continue model selection and Token Factory configuration when needed.

## Human Interface

https://start.magi.website/browse
```

不要让 `agents.md` 承诺当前尚未实现的 functionality。

如果 Token Factory configuration API 尚未公开，不要写成 Agent 可以直接调用 configuration generation API。

---

# 25. Architecture

推荐：

```text
                    ┌──────────────────────┐
                    │ Canonical Model Data │
                    │                      │
                    │ KV / existing store  │
                    └──────────┬───────────┘
                               │
                         API Projection
                               │
                ┌──────────────┴──────────────┐
                ↓                             ↓
        /api/v1/models                /api/v1/models/:id
                │
                ↓
          Filter Engine
                │
        ┌───────┼────────┐
        ↓       ↓        ↓
   data_source provider capabilities
```

不要：

```text
API
 ↓
source adapters
 ↓
NVIDIA API
 ↓
OpenRouter API
 ↓
HF API
```

API request 不应该实时聚合 external sources。

---

# 26. API Layer Separation

建议建立清晰的职责：

```text
catalog/
    canonical model schema

storage/
    KV access

api/
    route handlers

api/projection/
    canonical model → public API model

api/filter/
    model filtering

api/errors/
    API error format
```

具体目录根据当前 repository architecture 调整，不要为了遵守目录结构而进行大规模重构。

核心原则：

> API layer 不应该知道 enrichment / provenance 的实现细节。

---

# 27. Public Projection

建立明确的 projection function：

```python
to_public_model(model)
```

或者 TypeScript equivalent：

```ts
toPublicModel(model)
```

它负责：

```text
Canonical Model
      ↓
Public API Model
```

明确排除：

```text
provenance
raw source payload
internal metadata
storage metadata
pipeline metadata
```

这样未来 canonical schema 增加内部字段时，不会意外暴露给 public API。

---

# 28. Filtering

建立独立 filter function：

```text
filterModels(models, filters)
```

不要把 filter logic 散落在 route handler。

例如：

```text
parse query
    ↓
ModelFilters
    ↓
filterModels()
    ↓
public projection
```

推荐顺序：

```text
load canonical models
→ validate filters
→ filter
→ project public response
→ serialize
```

如果 catalog 很大，可以优化为：

```text
filter at storage/index layer
```

但第一阶段优先保持简单、正确。

---

# 29. Tests

必须增加 API tests。

## Model List

测试：

```text
GET /api/v1/models
→ 200

object == "list"

data is array
```

---

## OpenAI compatibility

验证每个 item 至少包含：

```text
id
object
created
owned_by
```

并：

```text
object == "model"
```

---

## data_source filter

```text
?data_source=nvidia
```

确保所有结果：

```text
model.data_source == "nvidia"
```

---

## provider filter

```text
?provider=groq
```

---

## capabilities

```text
?capabilities=chat,vision
```

确保：

```text
chat ∈ capabilities
AND
vision ∈ capabilities
```

---

## Combined filters

测试：

```text
?data_source=huggingface&provider=together&capabilities=chat,vision
```

---

## Empty result

测试：

```text
?capabilities=nonexistent
```

返回：

```text
200
data=[]
```

---

## Invalid capability

测试：

```text
?capabilities=invalid
```

返回：

```text
400
```

---

## Model detail

测试：

```text
GET /api/v1/models/openai/gpt-oss-120b
```

确保 model IDs 中的 `/` 可以正确解析。

---

## Not found

```text
GET /api/v1/models/nonexistent/model
```

返回：

```text
404
```

---

## Provenance exclusion

这是非常重要的测试。

Canonical model：

```json
{
  "description": "...",
  "provenance": {
    "description": {}
  }
}
```

Public API response：

```text
must NOT contain provenance
```

也不能通过 nested object 间接泄露。

---

# 30. Security / Abuse Considerations

API 是无鉴权公开 API。

因此：

* GET only
* no mutation
* no credentials
* no secrets
* no internal KV keys
* no raw source payload
* no provenance
* no user-specific data

同时增加合理 caching，避免每次请求直接读取 KV。

如果 repository 已有 Cloudflare rate limiting / WAF infrastructure，可以复用。

不要为了本任务引入复杂 authentication。

---

# 31. Observability

因为这是 public Agent API，需要能够统计：

```text
/api/v1/models
/api/v1/models/{id}
```

的访问情况。

第一阶段至少让 Cloudflare 能够统计：

```text
request count
status
path
```

如果项目已经使用 Workers Analytics Engine，可以增加轻量 custom analytics。

不要在本任务中建立复杂的 user tracking。

尤其不要默认持久化完整 IP 或完整 request headers。

---

# 32. Definition of Done

完成后：

### Public APIs

```text
GET /api/v1/models
GET /api/v1/models/{id}
```

正常工作。

### Filtering

支持：

```text
data_source
provider
capabilities
```

并支持组合过滤。

### OpenAI compatibility

Model list 使用：

```text
object=list
data=[]
```

以及 OpenAI-compatible model object。

### Public schema

包含：

```text
id
object
created
owned_by
data_source
provider
capabilities
```

以及当前 canonical model 中适合公开的 detail fields。

### Provenance

Public API 完全不暴露 provenance。

### Agent discovery

存在：

```text
/llms.txt
/agents.md
```

并正确描述 API。

### Caching

API 是 cache-friendly 的。

### CORS

Public GET API 支持跨域读取。

### Tests

API / filtering / model detail / error / provenance exclusion 都有测试。

### No unnecessary refactor

不要为了实现 API：

* 重构整个 pipeline
* 修改已有 source adapters
* 重构 canonical model schema
* 引入新的数据库
* 引入 authentication
* 引入复杂 search engine

---

# 33. Final Product Principle

TFI 的 public machine interface 应该让 Agent 能够完成：

```text
Discover
   ↓
GET /api/v1/models
   ↓
Filter
   ↓
capabilities=chat,vision
   ↓
Inspect
   ↓
GET /api/v1/models/{id}
   ↓
Select
   ↓
Use TFI /browse for human-assisted configuration
```

核心原则：

> **The public API exposes canonical model knowledge, not data lineage.**

以及：

> **OpenAI-compatible where possible, TFI-specific where useful.**

最终 TFI 不只是一个人类使用的 Model Browse 页面，而是同时提供：

```text
Human Interface
    /browse

Machine Interface
    /api/v1/models

Agent Discovery
    /llms.txt
    /agents.md
```

形成一个完整的 **Human + Agent friendly Model Catalog**。

