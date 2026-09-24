# Model Intelligence Layer Evolution

## 1. Context

We are building an open-source project currently named **Free Model Aggregator**.

The short-term goal is:

> Discover free AI models from multiple providers, normalize their metadata, validate endpoint availability, and generate runtime configurations.

Current providers include:

- NVIDIA NIM
- AMD Radeon AI Platform
- Hugging Face Inference

Current architecture:

```text
Provider Sources
      ↓
Fetch
      ↓
Parse
      ↓
Normalize
      ↓
Validate
      ↓
Store
      ↓
Summarize
      ↓
Notify
```

The project is implemented as a monorepo with a Python data pipeline and a Cloudflare Pages/API layer.

The project is expected to evolve into a **Model Intelligence / Model Supply Layer**, eventually supporting a **Token Factory Initializr**.

The long-term direction is:

```text
Provider
   ↓
Model Intelligence
   ↓
User Intent
   ↓
Model Selection
   ↓
Model Supply
   ↓
Runtime Configuration
   ↓
End User
```

The project should therefore avoid being designed as merely a "free model list scraper".

---

# 2. New Architectural Direction

The processing layer after `fetch` and `parse` should become substantially richer.

The target pipeline is:

```text
fetch
  ↓
parse
  ↓
normalize
  ↓
validate
  ↓
enrich
  ↓
score
  ↓
store
  ↓
summarize
  ↓
notify
```

However, the pipeline must remain modular.

Not every stage needs to be implemented immediately.

The architecture should allow future processing stages to be added without changing the pipeline orchestration framework.

The Pipeline remains responsible for:

- stage ordering
- execution
- context passing
- lifecycle
- error handling
- stage metrics

The Pipeline must NOT contain provider-specific or scoring-specific business logic.

---

# 3. Processing Layer

The processing layer is the core transformation and intelligence layer.

It should eventually contain:

```text
process/
├── normalize/
├── enrichment/
├── identity/
├── scoring/
└── ranking/
```

For the current MVP, do not implement all of these.

Start with:

```text
process/
├── normalize.py
├── enrich.py
└── ...
```

Future processing capabilities should be designed for gradual introduction.

---

# 4. Normalize

`normalize` converts heterogeneous provider data into a canonical model representation.

Examples:

- normalize model IDs
- normalize model names
- normalize modalities
- normalize context window
- normalize pricing
- normalize capabilities
- normalize provider-specific metadata
- normalize availability information

Example:

```json
{
  "model_id": "xxx",
  "name": "XXX",
  "modalities": {
    "input": ["text", "image"],
    "output": ["text"]
  },
  "context_window": 131072,
  "pricing": {
    "input": 0,
    "output": 0,
    "unit": "1M_tokens"
  }
}
```

Important rule:

**Normalize must not invent data.**

Unknown information must remain unknown.

For example:

```text
context_window = unknown
```

is preferable to:

```text
context_window = 1
```

Do not silently turn missing values into misleading defaults.

Where useful, distinguish:

```text
known
unknown
not_applicable
```

---

# 5. Validate

Validation should primarily mean **endpoint / provider validation**, rather than only schema validation.

The validation stage should answer:

> Can this model actually be accessed through the provider with a valid credential and produce a normal response?

Validation may include:

- API key authentication
- endpoint reachability
- model existence
- successful request
- valid response
- timeout
- rate limiting
- provider error
- unsupported operation

Potential status:

```text
available
unavailable
invalid_model
invalid_key
rate_limited
server_error
timeout
unsupported
```

Validation results should eventually be stored as operational facts.

Example:

```json
{
  "availability": {
    "status": "available",
    "latency_ms": 823,
    "last_checked_at": "..."
  }
}
```

Do not confuse:

```text
Provider Catalog Presence
```

with:

```text
Currently Callable Endpoint
```

---

# 6. Enrich Stage

Introduce a first-class:

```text
EnrichStage
```

The purpose of enrichment is to combine multiple external references and provider-specific sources to build richer knowledge about a model.

Potential references:

- models.dev
- OpenRouter
- Hugging Face
- modelparams.dev
- provider `/v1/models`
- provider-specific APIs
- provider documentation
- model cards
- other trustworthy model databases
- future benchmark/evaluation sources

Example:

```text
NVIDIA
Hugging Face
OpenRouter
models.dev
modelparams.dev
Provider API
Provider docs
       │
       ▼
    Enrich
       │
       ▼
 Model Facts
```

Important:

**Enrichment must not simply overwrite the canonical model object.**

It should collect evidence/facts from each source.

---

# 7. Model Fact

Introduce a first-class `ModelFact` / `Fact` concept.

A fact represents an observation about a model from a particular source.

Example:

```python
@dataclass
class ModelFact:
    model_id: str
    field: str
    value: Any

    source: str
    source_field: str | None

    confidence: float | None

    observed_at: datetime
    fetched_at: datetime

    evidence_type: str | None
```

Example:

```json
{
  "model_id": "nvidia/magpie-tts-zeroshot",
  "field": "modalities.output",
  "value": ["audio"],

  "source": "nvidia",
  "source_field": "output_modality",

  "confidence": 0.99,

  "observed_at": "2026-09-24T02:00:00Z",
  "fetched_at": "2026-09-24T02:00:00Z",

  "evidence_type": "provider_official"
}
```

The goal is to preserve not only:

> What do we believe?

but also:

> Why do we believe it?

---

# 8. Evidence and Provenance

Every enriched field should eventually be traceable to its source.

For example:

```text
context_window = 131072

Sources:
  NVIDIA official API → 131072
  models.dev         → 131072
  OpenRouter         → 131072
```

The canonical value can then be resolved from these observations.

The system should preserve:

- source
- source field
- source value
- fetch time
- observation time
- confidence
- evidence type
- resolution result

This is important because the long-term value of the system is not just model metadata.

It is the accumulated **evidence and provenance graph**.

---

# 9. Source Authority

Different sources should have different authority for different fields.

Do NOT implement a single global rule such as:

```text
NVIDIA > Hugging Face > OpenRouter > models.dev
```

Instead, source priority should eventually be field-specific.

For example:

```text
Pricing:
  provider official
  >
  provider API
  >
  OpenRouter
  >
  models.dev
```

While:

```text
Parameter count:
  official model card
  >
  Hugging Face
  >
  models.dev
```

And:

```text
API capabilities:
  provider API
  >
  provider documentation
  >
  OpenRouter
  >
  models.dev
```

The architecture should allow policies such as:

```python
SOURCE_POLICY = {
    "context_window": [...],
    "pricing": [...],
    "capabilities": [...],
    "parameter_count": [...],
}
```

Do not over-engineer the policy engine in MVP.

The data model should simply leave room for it.

---

# 10. Confidence

Facts may have a confidence score:

```text
0.0 ~ 1.0
```

Confidence can eventually take into account:

```text
source reliability
× freshness
× agreement between sources
× extraction quality
× evidence type
```

For MVP, do NOT build a sophisticated confidence algorithm.

Store the necessary evidence first.

The confidence algorithm can be improved later without re-fetching all providers.

This is important:

> Preserve raw evidence so derived confidence can be recalculated later.

---

# 11. Example: NVIDIA Magpie TTS Zeroshot

The architecture must support models that exist in one provider catalog but are missing from traditional LLM databases.

For example:

```text
nvidia/magpie-tts-zeroshot
```

Possible situation:

```text
NVIDIA               → exists
models.dev           → missing
Hugging Face         → missing
modelparams.dev      → missing
Enterprise catalog   → exists but incomplete/default metadata
```

The system must NOT discard the model because secondary sources do not know it.

Instead:

```text
Provider Discovery
       ↓
Canonical Model
       ↓
Enrichment
       ↓
Available Facts
       ↓
Unknown Facts remain unknown
```

This is a key principle:

> **Discovery source is the source of truth for model existence. External databases are enrichment sources, not universal model registries.**

---

# 12. Deduplication

Do not assume that identical model IDs across providers represent identical endpoints.

For example:

```text
gpt-oss-120b

NVIDIA
Groq
Hugging Face
OpenRouter
```

These should not be blindly deduplicated.

Distinguish:

```text
Model Identity
```

from:

```text
Endpoint Identity
```

and:

```text
Provider / Quota Identity
```

For MVP, it is acceptable to remove or defer the existing `DeduplicateStage`.

Do NOT implement aggressive deduplication.

Future evolution should preferably be:

```text
ResolveIdentityStage
```

rather than a simplistic:

```text
DeduplicateStage
```

The future model may look like:

```text
Canonical Model
    │
    ├── NVIDIA Endpoint
    ├── Groq Endpoint
    ├── Hugging Face Endpoint
    └── OpenRouter Endpoint
```

---

# 13. Scoring / ELO

Introduce a future:

```text
ScoreStage
```

The goal is to provide comparable model quality scores.

Potential dimensions:

```text
overall
coding
reasoning
agent
vision
tool_calling
writing
etc.
```

Example:

```json
{
  "model_id": "xxx",

  "scores": {
    "overall": 82.4,
    "coding": 87.2,
    "reasoning": 84.1,
    "agent": 79.8
  },

  "algorithm_version": "v1"
}
```

Score should remain separate from raw model metadata.

Potential score inputs:

- external benchmarks
- Artificial Analysis
- Hugging Face evaluations
- Arena / preference data
- provider benchmarks
- custom benchmarks
- internal scoring algorithms
- ELO/rating systems

Important:

A missing score must NOT remove a model from the registry.

```text
model exists
+
score unavailable
```

is a valid state.

---

# 14. Score Versioning

Scores should be reproducible and versioned.

Example:

```text
score-v1
score-v2
score-v3
```

A score should be conceptually:

```text
score =
    input evidence
    +
    algorithm version
    +
    generated result
```

Do not permanently overwrite historical scores without retaining provenance.

This allows the scoring algorithm to evolve independently from model discovery.

---

# 15. User Intent

The long-term product should not force users to manually understand model names.

The website:

```text
models.magi.website
```

should eventually allow natural-language requirements.

Example:

> I need to write documents and generate videos, with video generation being more important.

The system should convert this into a structured:

```text
UserRequirementProfile
```

Example:

```json
{
  "intent": "content_creation",

  "requirements": [
    {
      "capability": "text_generation",
      "weight": 0.7
    },
    {
      "capability": "video_generation",
      "weight": 1.0
    }
  ],

  "constraints": {
    "free_only": true
  }
}
```

Do NOT directly map user prompt → model list.

Use an intermediate structured representation:

```text
Natural Language
      ↓
User Intent
      ↓
Requirement Profile
      ↓
Model Selection
```

This creates a stable boundary between LLM-based intent understanding and deterministic model selection.

---

# 16. Capability Matching

Model recommendation should be based on model facts and user requirements.

Example:

```text
User:
"写文稿，生成视频（重要）"
```

Requirement:

```text
text_generation       weight 0.7
video_generation      weight 1.0
```

Candidate models can then be evaluated using:

```text
capability_match
+
quality_score
+
availability
+
cost
+
user preference
```

Conceptually:

```text
Model Selection Score
=
Capability Match
×
User Preference
×
Model Quality
×
Availability
×
Cost Preference
```

The exact scoring formula is intentionally not fixed yet.

The architecture should support replacing the selection algorithm later.

---

# 17. Explainable Recommendation

The system should eventually be able to explain:

> Why was this model recommended?

For example:

```text
Qwen X

✓ Strong text generation
✓ Supports Chinese
✓ Large context window
✓ Free endpoint
✓ Currently available

Video Model Y

✓ Video generation
✓ High match with your primary requirement
✓ Free
⚠ Daily quota is limited
```

This requires the Model Knowledge Layer to retain facts and evidence.

Therefore:

> Explainability is not a UI-only feature. It is a consequence of the Fact/Evidence architecture.

---

# 18. Model Knowledge Graph

The long-term system should conceptually become a:

**Model Knowledge Graph**

with relationships such as:

```text
Model
 ├── belongs_to → Provider
 ├── belongs_to → Model Family
 ├── has_endpoint → Endpoint
 ├── supports → Capability
 ├── has_fact → Fact
 ├── evidenced_by → Source
 ├── evaluated_by → Benchmark
 ├── has_score → Score
 └── related_to → Canonical Model
```

The implementation does NOT need to use a graph database.

The term "knowledge graph" describes the conceptual data model.

A relational/KV implementation is acceptable for MVP.

---

# 19. Historical Model Knowledge

Facts should eventually support historical observations.

Example:

```text
gpt-oss-120b
```

Context window:

```text
2026-08-01 → 131072
2026-08-15 → 131072
2026-09-01 → 262144
2026-09-24 → 262144
```

This enables future capabilities such as:

- model lifecycle
- pricing changes
- endpoint availability history
- quota changes
- context-window changes
- model deprecation
- score evolution

Do not implement a sophisticated time-series system now.

Simply ensure the data model does not destroy historical observations.

---

# 20. Product Evolution

The project should evolve through the following phases.

### Phase 1 — Free Model Aggregator

```text
Provider
 ↓
Fetch
 ↓
Parse
 ↓
Normalize
 ↓
Validate
 ↓
Store
 ↓
Generate Config
```

Goal:

> Collect free models and generate runtime configurations.

---

### Phase 2 — Model Intelligence

```text
Provider
 ↓
Fetch
 ↓
Parse
 ↓
Normalize
 ↓
Validate
 ↓
Enrich
 ↓
Store
```

Goal:

> Build a richer canonical model registry using multiple references.

---

### Phase 3 — Model Intelligence + Scoring

```text
Normalize
 ↓
Validate
 ↓
Enrich
 ↓
Score
 ↓
Store
```

Goal:

> Provide comparable model quality and capability scores.

---

### Phase 4 — User-oriented Model Selection

```text
User Natural Language
 ↓
User Intent
 ↓
Requirement Profile
 ↓
Model Knowledge Graph
 ↓
Candidate Models
 ↓
Ranking
```

Goal:

> Reduce the user's model-selection decision cost.

---

### Phase 5 — Token Factory Initializr

```text
User Requirement
 ↓
Model Selection
 ↓
Provider Selection
 ↓
Runtime Selection
 ↓
Config Generation
 ↓
Token Factory
```

Goal:

> Turn a user requirement into a runnable model stack.

---

# 21. Long-term Product Positioning

Do not define the long-term product merely as:

> A free model database.

A better conceptual positioning is:

> **An open Model Intelligence and Supply Layer that turns provider model data into user-oriented AI model stacks.**

The long-term relationship is:

```text
Provider
   ↓
Provider Data
   ↓
Model Intelligence
   ↓
User Intent
   ↓
Model Selection
   ↓
Model Supply
   ↓
Token Factory Initializr
   ↓
AI Runtime / Gateway
   ↓
End User
```

The platform acts as a bridge between:

```text
Provider
```

and:

```text
End User
```

Its value is reducing:

- model discovery cost
- metadata uncertainty
- model comparison cost
- provider selection cost
- runtime configuration cost
- model supply setup cost

The project should therefore optimize not merely for:

> "How many models can we collect?"

but increasingly for:

> **"How effectively can we turn provider data into a useful model stack for a specific user requirement?"**

---

# 22. Important Architectural Principles

### Principle 1 — Discovery ≠ Metadata

A provider catalog proves that a model exists.

Secondary databases enrich it.

Do not discard models because enrichment sources do not contain them.

### Principle 2 — Model ≠ Endpoint

Keep:

```text
Canonical Model
Endpoint
Provider
Quota
```

as separate concepts.

### Principle 3 — Raw Evidence ≠ Canonical Value

Keep source observations.

Resolve them into canonical values.

Do not lose provenance.

### Principle 4 — Missing ≠ Zero

Do not convert unknown values into misleading defaults.

### Principle 5 — Score ≠ Identity

A model can exist without a score.

Scoring is an enrichment/evaluation layer.

### Principle 6 — User Intent ≠ Model Query

Introduce a structured `UserRequirementProfile`.

### Principle 7 — Pipeline ≠ Business Logic

Pipeline orchestrates.

Stages adapt.

Processing modules implement business logic.

### Principle 8 — Preserve Data for Future Algorithms

Do not discard source evidence merely because MVP does not use it yet.

---

# 23. Immediate Implementation Scope

Do NOT implement the entire long-term architecture at once.

For the current iteration:

### Implement

```text
fetch
parse
normalize
validate
enrich
store
summarize
notify
```

### Add

```text
ModelFact
```

and enough provenance metadata to support:

```text
source
source_field
value
fetched_at
confidence
```

### Keep simple

```text
EnrichStage
```

can initially call a small set of enrichers.

For example:

```text
ModelsDevEnricher
OpenRouterEnricher
HuggingFaceEnricher
ProviderEnricher
```

Only add the sources that provide meaningful value.

### Defer

```text
advanced identity resolution
complex source authority engine
advanced confidence calculation
ELO engine
full ranking engine
knowledge graph database
natural-language recommendation engine
subscription infrastructure
```

The architecture must leave room for them, but MVP should not implement them.

---

# 24. Desired Repository Direction

Conceptually:

```text
data/
├── pipeline/
│   ├── pipeline.py
│   ├── stage.py
│   ├── context.py
│   └── result.py
│
├── stages/
│   ├── fetch.py
│   ├── parse.py
│   ├── normalize.py
│   ├── validate.py
│   ├── enrich.py
│   ├── score.py              # future
│   ├── store.py
│   ├── summarize.py
│   └── notify.py
│
├── providers/
│   ├── nvidia.py
│   ├── amd.py
│   └── huggingface.py
│
├── process/
│   ├── normalize.py
│   ├── enrich.py
│   ├── identity/             # future
│   └── scoring/              # future
│
├── models/
│   ├── schema.py
│   ├── fact.py
│   └── evidence.py
│
├── storage/
│   └── cloudflare_kv.py
│
├── notify/
│   └── feishu.py
│
└── tests/
```

Do not create unnecessary abstractions just to match this structure.

Refactor incrementally.

---

# 25. Final Architectural Target

The eventual architecture should converge toward:

```text
                         PROVIDERS
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
          NVIDIA           AMD             HF
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                     MODEL DISCOVERY
                            │
                            ▼
                    CANONICAL MODEL
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
        FACTS            ENDPOINTS          SCORES
          │                 │                 │
          └─────────────────┼─────────────────┘
                            ▼
                  MODEL KNOWLEDGE LAYER
                            │
                            ▼
                     USER INTENT
                            │
                            ▼
                 REQUIREMENT PROFILE
                            │
                            ▼
                  MODEL SELECTION
                            │
                            ▼
                 TOKEN FACTORY INITIALIZR
                            │
                            ▼
                MODEL SUPPLY / ARTIFACT
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
          LiteLLM          asrv         NewAPI
```

The immediate goal is not to build the entire graph.

The immediate goal is to build the **data foundation** correctly:

```text
Fetch
 ↓
Parse
 ↓
Normalize
 ↓
Validate
 ↓
Enrich
 ↓
Store
```

with:

```text
Fact
+
Source
+
Evidence
+
Confidence
+
Freshness
```

as first-class concepts.

That foundation should make future **Model Scoring, User Intent, Model Recommendation, Model Supply, and Token Factory Initializr** possible without requiring a fundamental rewrite of the data layer.
