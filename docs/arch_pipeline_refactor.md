# Pipeline Architecture Refactoring

## 1. Background

当前 `data/` 模块已经具备完整的数据处理流程：

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

当前 Pipeline 的实现方式是：在 `pipeline.py` 中通过 `for loop` 依次调用各个 stage，同时 `pipeline.py` 本身还包含部分具体业务逻辑。

现在需要对 Pipeline 进行一次架构重构：

> **Pipeline 只负责 orchestration（流程编排和执行），具体业务逻辑由各个 Stage implementation 以及其对应的 domain/infrastructure module 负责。**

目标是形成一个轻量、可扩展的 Pipeline DSL，而不是构建重量级 Workflow Engine。

---

# 2. Refactoring Goals

本次重构需要实现以下目标：

### 2.1 Pipeline 只负责 orchestration

Pipeline 应该只关注：

- Stage 的注册
- Stage 的执行顺序
- Pipeline Context 的传递
- 基础 execution lifecycle
- 基础错误处理
- 基础执行结果/metrics

Pipeline 不应该知道：

- NVIDIA 如何抓取
- HuggingFace 如何抓取
- Model 如何 normalize
- Model 如何 deduplicate
- Cloudflare KV 如何存储
- Feishu 如何发送消息

禁止将这些具体业务逻辑继续写入 `pipeline.py`。

---

### 2.2 Stage 负责具体 Pipeline Step

每个 Stage 是 Pipeline 中的一个步骤。

例如：

```text
FetchStage
ParseStage
NormalizeStage
ValidateStage
DeduplicateStage
StoreStage
SummarizeStage
NotifyStage
```

Stage 负责：

> 将某个具体业务能力适配到 Pipeline Context。

Stage 本身也不应该承载大量底层实现。

例如：

```text
NormalizeStage
    ↓
process/normalize.py

DeduplicateStage
    ↓
process/deduplicate.py

StoreStage
    ↓
storage/cloudflare_kv.py

NotifyStage
    ↓
notify/feishu.py
```

Stage 更像 orchestration adapter，而不是业务逻辑容器。

---

# 3. Target DSL

第一阶段只实现最小 Fluent API：

```python
pipeline = (
    Pipeline()
    .then(FetchStage())
    .then(ParseStage())
    .then(NormalizeStage())
    .then(ValidateStage())
    .then(DeduplicateStage())
    .then(StoreStage())
    .then(SummarizeStage())
    .then(NotifyStage())
    .end()
)
```

然后：

```python
pipeline.run(context)
```

Pipeline 应支持：

```python
Pipeline()
    .then(stage)
    .then(stage)
    .end()
```

其中：

```text
then()
    注册一个 Stage

end()
    表示 Pipeline Definition 完成

run()
    执行 Pipeline
```

`end()` 不应该自动执行 Pipeline。

Pipeline Definition 与 Pipeline Execution 应保持概念上的分离。

---

# 4. Stage Interface

实现一个统一的 Stage abstraction。

建议：

```python
class Stage(Protocol):

    @property
    def name(self) -> str:
        ...

    def execute(
        self,
        context: PipelineContext,
    ) -> PipelineContext:
        ...
```

具体实现：

```python
class NormalizeStage:

    @property
    def name(self) -> str:
        return "normalize"

    def execute(self, context: PipelineContext) -> PipelineContext:
        context.data["models"] = normalize(
            context.data["models"]
        )

        return context
```

要求：

- Stage 必须有稳定、可读的 `name`
- Stage 负责调用具体 implementation
- Stage 返回更新后的 `PipelineContext`
- Stage 不应该直接控制下一个 Stage
- Stage 不应该了解 Pipeline 的内部执行机制

---

# 5. PipelineContext

不要让 Stage 简单地通过：

```python
data = stage.execute(data)
```

传递数据。

因为不同 Stage 的输入输出语义不同：

```text
fetch       → models
parse       → models
store       → side effect
summarize   → summary
notify      → side effect
```

因此引入：

```python
PipelineContext
```

建议至少包含：

```python
@dataclass
class PipelineContext:
    data: dict
    state: dict
    metrics: dict
    artifacts: dict
    errors: list
```

具体字段可以根据现有代码实际情况调整，不要求一次性设计得非常复杂。

核心原则：

> Pipeline Context 是 Stage 之间共享运行状态的容器，而不是某个具体业务对象。

---

# 6. Pipeline Execution

Pipeline 内部可以继续使用 `for loop`。

注意：

> 本次重构并不是禁止 `for loop`。

需要解决的问题是：

```text
当前：
pipeline.py
    ↓
for loop
    ↓
具体业务逻辑
```

重构之后应该变成：

```text
Pipeline
    ↓
for loop
    ↓
Stage.execute()
    ↓
具体 implementation
```

也就是说，`for loop` 本身属于 orchestration，是合理的。

推荐最小实现：

```python
class Pipeline:

    def __init__(self):
        self.stages: list[Stage] = []

    def then(self, stage: Stage) -> "Pipeline":
        self.stages.append(stage)
        return self

    def end(self) -> "Pipeline":
        return self

    def run(self, context: PipelineContext) -> PipelineContext:
        for stage in self.stages:
            context = stage.execute(context)

        return context
```

不要为了消除 `for loop` 而引入不必要的 abstraction。

---

# 7. Execution Lifecycle

Pipeline 可以统一负责基础 execution lifecycle，例如：

```text
Stage
 ↓
start
 ↓
execute
 ↓
success / failed
 ↓
next Stage
```

Pipeline 可以统一记录：

```text
stage name
start time
end time
duration
status
error
```

例如最终能够得到类似：

```text
Pipeline Summary

fetch         SUCCESS   1.23s
parse         SUCCESS   0.32s
normalize     SUCCESS   0.11s
validate      SUCCESS   0.08s
deduplicate   SUCCESS   0.04s
store         SUCCESS   0.72s
summarize     SUCCESS   0.13s
notify        SUCCESS   0.21s

Total: 2.84s
```

但本阶段不需要实现复杂 observability system。

保持轻量。

---

# 8. Error Handling

Pipeline 应该负责基础的 Stage execution error handling。

Stage 不应该自行决定整个 Pipeline 的 orchestration。

例如：

```text
Stage.execute()
    ↓
exception
    ↓
Pipeline
    ↓
record failure
    ↓
stop / continue
```

具体策略应基于现有业务行为进行迁移，**不要因为重构而改变现有 pipeline 的错误语义**。

如果当前 pipeline 对：

```text
success
partial
failed
invalid
```

已有约定，应尽量保留。

如果现有代码没有完整抽象，则本次只建立必要的基础结构，不要提前设计复杂状态机。

---

# 9. Current Directory Structure

保持当前目录结构，不要为了本次重构重新设计整个项目。

目标结构：

```text
data/
├── pipeline/
│   ├── __init__.py
│   ├── pipeline.py
│   ├── stage.py
│   ├── context.py
│   └── result.py
│
├── stages/
│   ├── __init__.py
│   ├── fetch.py
│   ├── parse.py
│   ├── normalize.py
│   ├── validate.py
│   ├── deduplicate.py
│   ├── store.py
│   ├── summarize.py
│   └── notify.py
│
├── providers/
│   ├── nvidia.py
│   ├── amd.py
│   └── huggingface.py
│
├── models/
│   └── schema.py
│
├── process/
│   ├── normalize.py
│   └── deduplicate.py
│
├── storage/
│   └── cloudflare_kv.py
│
├── notify/
│   └── feishu.py
│
├── tests/
│   ├── test_pipeline.py
│   ├── test_process.py
│   ├── test_providers.py
│   ├── test_storage.py
│   └── test_notify.py
│
└── main.py
```

---

# 10. Module Responsibilities

## `pipeline/`

负责：

- Pipeline definition
- Stage abstraction
- PipelineContext
- Stage execution
- 基础 execution result
- 基础 execution lifecycle

不负责任何 provider/storage/notification 业务。

---

## `stages/`

负责：

> 将业务能力连接到 Pipeline execution model。

例如：

```text
FetchStage
    → providers/

NormalizeStage
    → process/normalize.py

DeduplicateStage
    → process/deduplicate.py

StoreStage
    → storage/cloudflare_kv.py

NotifyStage
    → notify/feishu.py
```

Stage 应尽量保持薄。

---

## `providers/`

负责：

> 数据源访问与 provider-specific fetching/parsing。

例如：

```text
NvidiaProvider
AMDProvider
HuggingFaceProvider
```

Provider 不应该知道 Pipeline 的执行顺序。

---

## `models/`

只负责：

> Domain data schema / data contract。

当前只保留：

```text
models/schema.py
```

不要把 normalize/deduplicate 等处理逻辑放回 `models/`。

---

## `process/`

负责：

> Model 数据的具体 transformation / processing logic。

当前：

```text
process/normalize.py
process/deduplicate.py
```

这些逻辑应该尽量设计为可独立测试的函数。

例如：

```python
def normalize(models):
    ...

def deduplicate(models):
    ...
```

---

## `storage/`

负责：

> 持久化实现。

当前：

```text
storage/cloudflare_kv.py
```

`StoreStage` 调用 storage implementation。

Storage implementation 不应该知道 Pipeline 中自己前面/后面有哪些 Stage。

---

## `notify/`

负责：

> 外部通知系统的具体实现。

当前：

```text
notify/feishu.py
```

`NotifyStage` 调用 Feishu implementation。

未来可以自然扩展：

```text
notify/
├── feishu.py
├── slack.py
└── email.py
```

---

## `tests/`

测试应该按照模块职责进行拆分。

```text
test_pipeline.py
    Pipeline / Stage / Context / execution order

test_process.py
    normalize / deduplicate

test_providers.py
    provider-specific fetching/parsing

test_storage.py
    Cloudflare KV behavior

test_notify.py
    Feishu payload / notification behavior
```

Pipeline 测试应该重点验证：

```text
Stage 是否按照定义顺序执行
Context 是否正确传递
Stage failure 是否正确处理
Pipeline lifecycle 是否正确
```

而不是在 Pipeline test 中重复测试 normalize/deduplicate 的业务细节。

---

# 11. Dependency Direction

尽量保持单向依赖：

```text
main.py
    ↓
pipeline
    ↓
stages
    ↓
providers / process / storage / notify
    ↓
models/schema
```

核心原则：

### Pipeline 不依赖具体业务实现

避免：

```python
pipeline.py
    import NvidiaProvider
    import CloudflareKV
    import Feishu
```

### Stage 可以依赖具体 implementation

例如：

```text
NormalizeStage
    ↓
process.normalize

StoreStage
    ↓
storage.cloudflare_kv

NotifyStage
    ↓
notify.feishu
```

### Implementation 不应该反向依赖 Pipeline

例如避免：

```text
process.normalize
    ↓
pipeline
```

形成循环依赖。

---

# 12. Provider 与 Stage 必须保持独立

不要混淆：

```text
Stage ≠ Provider
```

例如：

```text
FetchStage
    ↓
Provider abstraction
    ├── NvidiaProvider
    ├── AMDProvider
    └── HuggingFaceProvider
```

其中：

> Stage 决定“什么时候执行 fetch”。

而：

> Provider 决定“从哪里获取数据以及如何处理 provider-specific 数据”。

未来如果增加：

```text
OpenRouterProvider
GroqProvider
GoogleProvider
```

不应该修改 Pipeline orchestration。

---

# 13. Scope Control

本次重构只做：

```text
Pipeline
    ↓
Stage abstraction
    ↓
PipelineContext
    ↓
.then()
    ↓
.end()
    ↓
.run()
```

不要实现以下高级能力：

```text
❌ parallel()
❌ branch()
❌ when()
❌ retry DSL
❌ dependency graph
❌ DAG engine
❌ distributed execution
❌ persistent workflow state
❌ scheduling engine
❌ Airflow/Dagster-like workflow engine
```

除非现有代码已经明确需要，否则不要提前抽象。

未来可以自然演进为：

```text
.then()
.retry()
.parallel()
.when()
.branch()
```

但当前只实现最小可用 DSL。

---

# 14. Backward Compatibility

这是一次架构重构，而不是业务重写。

必须保证：

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

的业务行为保持不变。

特别注意：

- Provider fetching behavior 不变
- Model normalization behavior 不变
- Deduplication behavior 不变
- Validation behavior 不变
- Cloudflare KV storage behavior 不变
- Feishu notification behavior 不变
- Summary 内容不应因为架构重构发生非必要变化
- Error handling semantics 不应无理由改变

如果发现现有代码存在问题：

1. 优先保持原行为；
2. 只有为了适配新的 Pipeline abstraction 才进行必要修改；
3. 不要在本次 refactor 中顺便进行无关业务重构。

---

# 15. Testing Requirements

重构完成后至少保证：

```text
pytest
```

全部通过。

新增/更新：

```text
test_pipeline.py
```

至少覆盖：

1. `.then()` 可以连续注册 Stage；
2. Stage 按注册顺序执行；
3. Context 可以在 Stage 之间传递；
4. `end()` 不会自动执行 Pipeline；
5. `run()` 执行 Pipeline；
6. Stage failure 能被 Pipeline 正确处理。

同时确保原有：

```text
provider tests
process tests
storage tests
notify tests
```

不被破坏。

---

# 16. Desired Final Architecture

最终希望达到：

```text
                        main.py
                           │
                           ▼
                       Pipeline
                    orchestration
                           │
                           ▼
                         Stages
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
      Providers          Process          Storage
          │                │                │
    ┌─────┼─────┐      normalize       Cloudflare KV
    │     │     │      deduplicate
   NIM   AMD    HF
          │                │
          └────────────────┼────────────────┐
                           │                │
                           ▼                ▼
                        Models            Notify
                        schema             │
                                          ▼
                                        Feishu
```

核心职责：

```text
Pipeline
    = 怎么编排

Stage
    = Pipeline 中的步骤适配

Provider
    = 从哪里获取数据

Process
    = 如何处理数据

Storage
    = 如何持久化

Notify
    = 如何通知外部系统

Models
    = 数据是什么结构

Tests
    = 验证各层行为
```

最终应该让 Pipeline 代码接近：

```python
pipeline = (
    Pipeline()
    .then(FetchStage())
    .then(ParseStage())
    .then(NormalizeStage())
    .then(ValidateStage())
    .then(DeduplicateStage())
    .then(StoreStage())
    .then(SummarizeStage())
    .then(NotifyStage())
    .end()
)

pipeline.run(context)
```

而不是：

```python
for ...:
    # fetch logic
    # parse logic
    # normalize logic
    # validation logic
    # deduplication logic
    # storage logic
    # summary logic
    # notification logic
```

**最终目标：Pipeline 成为一个轻量的 execution/orchestration framework，而不是业务逻辑容器。**

---

# 17. Implementation Principle

遵循以下优先级：

```text
Correctness
    >
Clear separation of responsibilities
    >
Minimal abstraction
    >
Extensibility
```

尤其遵循：

> **Don't build a workflow engine. Build just enough Pipeline abstraction to make the current data pipeline clean.**

不要为了未来可能存在的需求提前引入复杂框架。
