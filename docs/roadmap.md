# Free Model Aggregator Roadmap

## 1. Vision

The project starts as a **Free Model Aggregator**, but the long-term goal is to evolve into a **Token Factory / Model Supply Platform**.

The core idea is:

> Discover AI model endpoints from multiple providers, normalize them into a unified catalog, and continuously supply model configurations to AI gateways and runtimes.

The long-term relationship is:

```text
                    Model Supply Plane
                    ┌─────────────────┐
                    │  Token Factory  │
                    │                 │
                    │ Catalog         │
                    │ Discovery       │
                    │ Subscription    │
                    │ Artifact        │
                    └────────┬────────┘
                             │
                   Model Supply Protocol
                             │
                             ▼
                    ┌─────────────────┐
                    │      asrv       │
                    │                 │
                    │ API Gateway     │
                    │ Auth            │
                    │ Routing         │
                    │ Proxy           │
                    │ Rate Limit      │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
           NVIDIA           AMD             HF
```

The architecture intentionally separates:

- **Model Supply Plane** — Token Factory
- **API Gateway / Data Plane** — `asrv`

---

# 2. Product Evolution

The planned evolution is:

```text
Free Model Aggregator
        │
        ▼
Token Factory Initializr
        │
        ▼
Model Subscription
        │
        ▼
Model Supply Protocol
        │
        ▼
AI Infrastructure Supply Network
```

Each stage should build on the previous stage instead of requiring a rewrite.

---

# 3. Phase 1 — Free Model Aggregator

## Goal

Build a reliable catalog of currently available free model endpoints.

Initial providers:

- NVIDIA NIM
- AMD Radeon AI Platform
- Hugging Face Inference

Architecture:

```text
Provider Sources
      │
      ▼
Python Data Pipeline
      │
      ▼
Normalize
      │
      ▼
Validate
      │
      ▼
Deduplicate
      │
      ▼
Cloudflare KV
      │
      ▼
Cloudflare Pages
      │
      ▼
Model Catalog UI
```

## Features

- Provider discovery
- Model discovery
- Free-status detection
- Model normalization
- Provider-specific endpoint records
- Snapshot/versioning
- Cloudflare KV storage
- Daily GitHub Actions update
- Model search/filter
- Provider filtering

## Initial Model Concept

The system should treat:

```text
Model Identity
```

and:

```text
Endpoint Identity
```

as different concepts.

For example:

```text
google/gemma-4-31b
    │
    ├── NVIDIA endpoint
    ├── AMD endpoint
    └── Hugging Face endpoint
```

Do not merge these endpoints merely because they expose the same underlying model.

## MVP Output

The first useful output is a LiteLLM configuration:

```yaml
model_list:
  - model_name: ...
    litellm_params:
      model: ...
      api_key: os.environ/...
```

---

# 4. Phase 2 — Token Factory Initializr

## Goal

Evolve from:

> "Find free models"

to:

> "Initialize an AI runtime with a set of models."

The UX should be inspired by `start.spring.io`.

```text
Provider
   ↓
Model
   ↓
Endpoint
   ↓
Runtime
   ↓
Generate
   ↓
Artifact
```

Example:

```text
Providers
[x] NVIDIA
[x] AMD
[x] Hugging Face

Models
[x] GPT-OSS-120B
[x] Gemma 4 31B

Runtime
○ LiteLLM
○ asrv
○ OpenAI SDK

[ Generate ]
```

---

## 4.1 Model Endpoint

Move from a simple model record:

```json
{
  "provider": "nvidia",
  "model_id": "..."
}
```

toward a richer endpoint abstraction:

```json
{
  "provider": "nvidia",
  "model_id": "...",

  "endpoint": {
    "base_url": "...",
    "protocol": "openai-compatible"
  },

  "auth": {
    "type": "api_key",
    "env_var": "NVIDIA_API_KEY"
  },

  "capabilities": {
    "chat": true,
    "tool_calling": true
  },

  "limits": {
    "rpm": 30,
    "tpm": 8000
  }
}
```

The exact schema should evolve incrementally.

---

# 5. Runtime Profiles

A key abstraction of the Token Factory should be the **Runtime Profile**.

Instead of only asking:

```text
Which models?
```

the system should understand:

```text
Which models?
+
Which runtime?
+
Which protocol?
+
Which configuration format?
```

Example:

```json
{
  "runtime": {
    "solution": "litellm",
    "version": "1.x"
  },

  "requirements": {
    "providers": [
      "nvidia",
      "huggingface"
    ],

    "capabilities": [
      "chat",
      "tool_calling"
    ],

    "free_only": true,

    "max_models": 30
  }
}
```

Possible runtime solutions:

- LiteLLM
- NewAPI
- Sub2API
- asrv
- OpenAI-compatible SDK
- future runtimes

---

# 6. Runtime Adapters

The Token Factory should not hard-code configuration generation into the catalog layer.

Use:

```text
Model Catalog
      │
      ▼
Model Resolver
      │
      ▼
Runtime Adapter
      │
      ▼
Artifact
```

Example:

```text
RuntimeAdapter
├── LiteLLMAdapter
├── NewAPIAdapter
├── Sub2APIAdapter
└── AsrvAdapter
```

Each adapter converts the same canonical model/endpoints into the configuration format required by a specific runtime.

---

# 7. Artifact Model

Do not limit the generated result to a `config.yaml`.

Introduce a generic concept:

```text
Artifact
```

Example:

```json
{
  "type": "model-list",
  "format": "litellm",
  "version": "2026-09-23T02:00:00Z",
  "content": "..."
}
```

Potential future artifact types:

```text
model-list
provider-config
routing-policy
credential-template
health-policy
capability-map
```

This allows the Token Factory to evolve beyond simple configuration generation.

---

# 8. Phase 3 — Model Subscription

## Goal

Move from one-time configuration generation to continuous model-list distribution.

Current model:

```text
User
  │
  │ Generate
  ▼
Token Factory
  │
  ▼
Config
```

Future model:

```text
AI Gateway
  │
  │ Subscribe(Profile)
  ▼
Token Factory
  │
  ▼
Model Artifact
  │
  ▼
AI Gateway
```

The gateway can continuously consume updated model information without manually regenerating configuration.

---

# 9. Subscription Model

A subscription represents:

> "I want to continuously receive models matching this profile."

Example:

```json
{
  "subscription": {
    "catalog": "free-models",

    "profile": {
      "solution": "litellm",

      "providers": [
        "nvidia",
        "amd",
        "huggingface"
      ],

      "filters": {
        "free": true,
        "capabilities": [
          "chat",
          "tool_calling"
        ]
      },

      "limits": {
        "max_models": 30
      }
    }
  }
}
```

The Token Factory resolves the subscription against its current catalog.

```text
Subscription
      │
      ▼
Catalog Query
      │
      ▼
Endpoint Selection
      │
      ▼
Runtime Adapter
      │
      ▼
Artifact
```

---

# 10. Subscription Lifecycle

Conceptually:

```text
AI Gateway
    │
    │ POST /v1/subscriptions
    ▼
Token Factory
    │
    │ subscription_id
    ▼
AI Gateway
    │
    │ GET artifact
    ▼
Token Factory
    │
    │ artifact v001
    ▼
AI Gateway
```

Later:

```text
Day 2

Token Factory
    │
    │ catalog changed
    ▼
artifact v002
    │
    ▼
AI Gateway
```

The gateway should be able to determine whether its local artifact is current.

---

# 11. Artifact Versioning

Artifacts should be versioned.

Example:

```text
artifact v001
artifact v002
artifact v003
```

The gateway may use HTTP caching:

```http
ETag: "model-list-002"
```

and:

```http
If-None-Match: "model-list-002"
```

If there is no update:

```text
304 Not Modified
```

This keeps the model distribution protocol lightweight.

---

# 12. Phase 4 — Model Supply Protocol

## Goal

Define a provider-neutral protocol between AI Gateways and the Token Factory.

The protocol should allow a gateway to declare:

- runtime solution
- protocol
- provider requirements
- model requirements
- capability requirements
- free/paid requirements
- model count limits
- routing preferences
- optional geographic/latency constraints

The Token Factory returns:

- resolved model endpoints
- runtime-compatible configuration
- artifact version
- metadata
- update information

---

# 13. Protocol Layers

The protocol should be conceptually divided into three layers.

## Catalog

Answers:

> What models/endpoints are currently available?

Example:

```http
GET /v1/models
```

---

## Subscription

Answers:

> What model supply do I want to continuously follow?

Example:

```http
POST /v1/subscriptions
```

---

## Artifact

Answers:

> What configuration should my runtime use based on my subscription?

Example:

```http
GET /v1/subscriptions/{id}/artifact
```

Architecture:

```text
Catalog
   │
   ▼
Subscription
   │
   ▼
Artifact
```

---

# 14. Model Supply Protocol vs A2A

The protocol should initially be considered a:

> **Model Supply Protocol**

rather than a traditional Agent-to-Agent protocol.

The primary relationship is:

```text
AI Gateway
     ↕
Model Supply Service
```

rather than:

```text
Agent
     ↕
Agent
```

However, the protocol could later evolve toward agent-style negotiation.

For example:

```json
{
  "requirements": {
    "task": "coding",
    "capabilities": [
      "tool_calling"
    ],
    "context_length": 128000,
    "free_only": true,
    "latency_ms": 500
  }
}
```

The Token Factory could dynamically resolve an appropriate model pool.

At that point the protocol begins to resemble Agent-to-Agent capability negotiation.

---

# 15. Token Factory Responsibilities

The Token Factory should own the **Model Supply Plane**.

Responsibilities:

```text
Provider Discovery
       │
       ▼
Model Catalog
       │
       ▼
Endpoint Registry
       │
       ▼
Model Resolution
       │
       ▼
Policy / Filtering
       │
       ▼
Runtime Adapter
       │
       ▼
Artifact
```

Potential future capabilities:

- model discovery
- endpoint discovery
- canonical model identity
- model metadata enrichment
- model scoring
- free/paid classification
- endpoint health
- quota metadata
- model pool construction
- runtime configuration generation
- subscription management
- artifact versioning
- model supply API

---

# 16. asrv Responsibilities

`asrv` should remain an independent API Gateway.

Its responsibilities include:

- API routing
- authentication
- rewrite
- redirect
- proxy
- rate limiting
- policy
- upstream management

Architecture:

```text
Token Factory
      │
      │ Model Supply
      ▼
    asrv
      │
      │ API Gateway
      ▼
Model Providers
```

Do NOT turn Token Factory into another API Gateway.

Do NOT duplicate the responsibilities of `asrv` inside Token Factory.

---

# 17. Token Factory + asrv

The intended relationship is:

```text
                 Token Factory
                 Model Supply
                      │
                      │
                      ▼
                    asrv
                API Gateway
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       NVIDIA        AMD          HF
```

The two projects should remain conceptually independent:

### Token Factory

```text
"What models should my gateway use?"
```

### asrv

```text
"How should API traffic reach those models?"
```

This creates a clean separation between:

- Model Supply Plane
- API Gateway / Data Plane

---

# 18. Phase 5 — Model Pool & Routing

Once subscriptions exist, the Token Factory can evolve from individual models to model pools.

Example:

```text
gpt-oss-120b
    │
    ├── NVIDIA
    ├── Groq
    ├── Hugging Face
    └── other providers
```

The Token Factory could generate a logical pool:

```text
model: gpt-oss-120b

providers:
  - NVIDIA
  - Groq
  - Hugging Face
```

Potential routing policies:

```text
fallback
weighted
priority
latency-aware
quota-aware
health-aware
```

This should be implemented only after the basic subscription/artifact system is stable.

---

# 19. Phase 6 — Canonical Model Identity

Eventually introduce:

```text
canonical_model_id
```

Example:

```text
canonical_model_id:
  openai/gpt-oss-120b

endpoints:
  ├── NVIDIA
  ├── Groq
  └── Hugging Face
```

This enables:

- cross-provider deduplication
- model comparison
- model scoring
- endpoint selection
- routing
- fallback
- provider switching

Canonical identity resolution should not block the MVP.

---

# 20. Phase 7 — Model Scoring

Introduce model scoring as an enrichment layer.

Potential sources:

- Artificial Analysis
- Hugging Face evaluations
- OpenRouter metadata
- Arena / human preference data
- Models.dev
- custom benchmarks

Architecture:

```text
Model Endpoint
      │
      ▼
Enrichment
      │
      ▼
Score
```

Scoring must remain optional.

A model without an external score must remain valid in the catalog.

---

# 21. Long-Term Vision — AI Infrastructure Supply Network

The ultimate direction is to make the Token Factory a model infrastructure supply layer.

```text
                   Token Factory
                        │
             ┌──────────┼──────────┐
             │          │          │
          Catalog   Subscription  Artifact
             │          │          │
             └──────────┼──────────┘
                        │
              Model Supply Protocol
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
      asrv           LiteLLM          NewAPI
        │               │               │
        └───────────────┼───────────────┘
                        │
                AI Model Providers
```

Potential consumers:

- API gateways
- LiteLLM deployments
- NewAPI
- Sub2API
- `asrv`
- personal AI agents
- agent runtimes
- internal AI platforms
- developer tools
- OpenAI-compatible clients

The Token Factory becomes a **Model Supply Plane** rather than merely a model directory.

---

# 22. Roadmap Summary

| Phase | Product | Main Capability |
|---|---|---|
| 1 | Free Model Aggregator | Discover and catalog free models |
| 2 | Token Factory Initializr | Generate runtime-specific configurations |
| 3 | Model Subscription | Continuously receive model-list updates |
| 4 | Model Supply Protocol | Standardize Gateway ↔ Token Factory communication |
| 5 | Model Pool & Routing | Combine multiple endpoints into logical pools |
| 6 | Canonical Model Identity | Resolve the same model across providers |
| 7 | Model Scoring | Enrich models with quality/performance data |
| 8 | AI Infrastructure Supply Network | Supply models/configuration to multiple AI runtimes |

---

# 23. Guiding Principles

### 1. Catalog first

Build reliable model discovery before building complex routing.

### 2. Endpoint over model

A model can have multiple independent provider endpoints.

### 3. Runtime-neutral core

The model catalog must not depend on LiteLLM, NewAPI, Sub2API, or asrv.

### 4. Adapter-based output

Runtime-specific configuration belongs in adapters.

### 5. Artifact-based distribution

Treat generated configuration as a versioned artifact.

### 6. Subscription over polling complexity

Let gateways subscribe to a desired model supply profile instead of manually maintaining model lists.

### 7. Separate supply from gateway

Token Factory supplies model configuration.

`asrv` handles API traffic.

### 8. Incremental protocol design

Start with simple HTTP APIs and artifacts.

Do not build a complex protocol before real consumers exist.

### 9. MVP before network

Do not implement routing, scoring, canonical identity, or complex subscriptions before the basic catalog is reliable.

### 10. Design for machine consumption

The long-term primary consumer should not necessarily be a human UI.

It should be possible for:

```text
AI Gateway
Agent Runtime
CLI
CI/CD
Developer Tool
```

to consume the Token Factory programmatically.

---

# 24. Target Architecture

The long-term target is:

```text
                         ┌───────────────────────┐
                         │     Token Factory     │
                         │                       │
                         │ Provider Discovery    │
                         │ Model Catalog         │
                         │ Endpoint Registry     │
                         │ Model Resolution      │
                         │ Model Scoring         │
                         │ Subscription          │
                         │ Artifact Generation   │
                         └───────────┬───────────┘
                                     │
                          Model Supply Protocol
                                     │
             ┌───────────────────────┼───────────────────────┐
             │                       │                       │
             ▼                       ▼                       ▼
          asrv                    LiteLLM                  NewAPI
       AI Gateway               Runtime                  Runtime
             │                       │                       │
             └───────────────────────┼───────────────────────┘
                                     │
                          AI Model Providers
                                     │
             ┌───────────────────────┼───────────────────────┐
             ▼                       ▼                       ▼
          NVIDIA                    AMD                     HF
```

The project should evolve toward this architecture without prematurely implementing the entire system.

The immediate objective remains:

> **Build a reliable Free Model Aggregator first, then turn its model catalog into a Model Supply Plane through Initializr, Subscription, and Artifact APIs.**
::
