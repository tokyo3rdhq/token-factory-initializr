# Free Model Aggregator — Architecture & Implementation Prompt

## 0. Project Overview

Build a lightweight **Free Model Aggregator** that discovers, normalizes, stores, and exposes currently available free AI model endpoints from multiple providers.

Initial providers:

- NVIDIA NIM
- AMD Radeon AI Platform
- Hugging Face Inference

The project should provide:

1. Automated daily model discovery
2. Provider-specific model/endpoint metadata
3. A unified model catalog
4. A web UI for browsing/selecting models
5. LiteLLM configuration generation
6. Short-lived generated configuration URLs
7. Agent-friendly prompts for importing generated configurations

The project is an **MVP**, so prioritize simplicity, reliability, and low operational cost.

---

# 1. Core Architecture

Use a **monorepo**, but strictly separate runtime responsibilities.

```text
free-model-aggregator/
│
├── data/                       # Python data ingestion pipeline
│   ├── providers/
│   │   ├── nvidia.py
│   │   ├── amd.py
│   │   └── huggingface.py
│   │
│   ├── models/
│   │   ├── schema.py
│   │   ├── normalize.py
│   │   └── deduplicate.py
│   │
│   ├── storage/
│   │   └── cloudflare_kv.py
│   │
│   ├── tests/
│   │   ├── test_nvidia.py
│   │   ├── test_amd.py
│   │   ├── test_huggingface.py
│   │   ├── test_normalize.py
│   │   └── test_storage.py
│   │
│   ├── main.py
│   └── pyproject.toml
│
├── web/                        # Cloudflare Pages application
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── ...
│   │
│   ├── functions/
│   │   ├── api/
│   │   │   ├── providers.ts
│   │   │   ├── models.ts
│   │   │   └── generate.ts
│   │   │
│   │   └── generated/
│   │       └── [id].ts
│   │
│   ├── package.json
│   └── ...
│
├── shared/                     # Cross-runtime data contracts
│   └── schema/
│       └── model.schema.json
│
├── .github/
│   └── workflows/
│       └── fetch-models.yml
│
├── README.md
└── ...
```

Important architectural principle:

> Same repository does NOT mean same runtime.

The Python data pipeline and Cloudflare Pages application must remain independently runnable and deployable.

---

# 2. Runtime Separation

## 2.1 Data Runtime

The data pipeline runs as an offline scheduled job.

```text
GitHub Actions
      │
      ▼
Python
      │
      ├── NVIDIA
      ├── AMD
      └── Hugging Face
      │
      ▼
normalize
      │
      ▼
validate
      │
      ▼
deduplicate
      │
      ▼
snapshot
      │
      ▼
Cloudflare KV
```

Python must NOT be deployed as a long-running backend service for the MVP.

Do not introduce:

- FastAPI
- Flask
- Django
- Kubernetes
- Docker service
- persistent Python server

unless a future requirement explicitly justifies it.

---

## 2.2 Web Runtime

The web application runs on Cloudflare Pages / Pages Functions.

```text
User
 │
 ▼
models.magi.website
 │
 ├── Static UI
 │
 └── Pages Functions
        │
        ├── /api/providers
        ├── /api/models
        ├── /api/generate
        └── /generated/:id
                │
                ▼
           Cloudflare KV
```

The web application reads the catalog from KV and provides the online user experience.

---

# 3. Shared Contract

Python and TypeScript should NOT share runtime code.

They should communicate through a stable JSON data contract.

Define the canonical model endpoint schema under:

```text
shared/schema/model.schema.json
```

Example:

```json
{
  "provider": "nvidia",
  "model_id": "google/gemma-4-31b-it",
  "name": "Gemma 4 31B IT",
  "description": null,
  "free": true,
  "capabilities": {},
  "metadata": {},
  "fetched_at": "2026-09-23T02:00:00Z"
}
```

Python can use:

- dataclass
- Pydantic

for runtime validation.

TypeScript can use:

- TypeScript interfaces
- Zod or equivalent

for runtime validation if necessary.

The JSON schema is the source of truth.

Avoid tightly coupling Python modules to TypeScript modules.

---

# 4. Provider Abstraction

Implement a common provider interface.

Conceptually:

```python
class Provider(Protocol):
    def fetch_models(self) -> list[ModelEndpoint]:
        ...
```

Each provider implementation must be independent.

Example:

```text
data/providers/
├── nvidia.py
├── amd.py
└── huggingface.py
```

Each provider should be responsible for:

1. Fetching source data
2. Parsing source-specific formats
3. Extracting model metadata
4. Determining provider-specific free availability
5. Converting results into the canonical model schema

Provider-specific parsing logic must NOT leak into the web layer.

---

# 5. Canonical Model Endpoint

Use the concept of **Model Endpoint**, rather than treating a model ID as globally unique.

Example:

```text
google/gemma-4-31b-it
```

may exist through:

```text
NVIDIA endpoint
AMD endpoint
Hugging Face endpoint
OpenRouter endpoint
```

These are different endpoints and potentially have different:

- quotas
- authentication
- latency
- availability
- rate limits
- capabilities
- provider policies

Therefore:

> Model identity != Endpoint identity != Quota identity

Do NOT merge different provider endpoints merely because they expose the same underlying model.

For MVP, preserve provider-specific records.

---

# 6. Model Schema

The canonical model endpoint should contain at least:

```python
@dataclass
class ModelEndpoint:
    provider: str
    model_id: str
    name: str | None
    description: str | None
    free: bool
    capabilities: dict
    metadata: dict
    fetched_at: datetime
```

The schema should remain extensible.

Possible future fields:

```text
canonical_model_id
model_family
organization
version
context_length
modalities
license
quantization
pricing
endpoint_url
region
status
limits
score
```

Do not add complex fields unless the current provider data actually requires them.

---

# 7. NVIDIA Provider

NVIDIA model discovery should use the current NVIDIA Build Catalog / NIM data source.

Relevant source:

```text
https://build.nvidia.com/models
```

NVIDIA's server-rendered page contains Next.js React Server Components / Flight payloads.

The parser should:

1. HTTP GET the page
2. Extract RSC / Flight payloads
3. Locate model objects
4. Parse complete model objects
5. Normalize them into the canonical schema

Do NOT rely solely on a regex extracting:

```text
provider/model
```

A regex can be used for candidate discovery, but not as the final parser.

Investigate fields such as:

```text
slug
modelId
model_id
id
name
displayName
publisher
description
nimType
type
capabilities
modalities
tags
```

The parser must not depend on:

- fixed RSC record IDs
- fixed character offsets
- model ordering
- hard-coded model IDs
- a particular number of RSC chunks

If NVIDIA changes its page structure, the parser should fail loudly rather than silently returning an empty catalog.

Diagnostics should include:

```text
HTTP status
response size
RSC chunk count
candidate model count
parsed model count
```

---

# 8. AMD Provider

Implement AMD Radeon AI Platform discovery as an independent provider.

Responsibilities:

```text
AMD API
  ↓
AMD parser
  ↓
canonical ModelEndpoint
```

Do not expose AMD-specific structures to the web layer.

---

# 9. Hugging Face Provider

Use Hugging Face APIs / inference provider metadata to discover models available through the relevant free inference offerings.

Potential sources include:

```text
https://router.huggingface.co/v1/models
```

and Hugging Face Hub model metadata.

The implementation should distinguish:

- model metadata
- inference provider availability
- actual free access

Do not assume that every model visible in the Hub is a free inference endpoint.

Normalize the result into the same `ModelEndpoint` schema.

---

# 10. Data Pipeline

The complete data pipeline should be:

```text
Provider APIs / Web Data
        │
        ▼
provider parser
        │
        ▼
canonical normalization
        │
        ▼
validation
        │
        ▼
deduplication
        │
        ▼
snapshot
        │
        ▼
Cloudflare KV
```

Each provider should be processed independently.

If one provider fails:

```text
NVIDIA      success
AMD         success
HuggingFace failure
```

do NOT destroy the previous valid Hugging Face snapshot.

Instead:

```text
HuggingFace:
last_success = previous snapshot
status = failed
```

The latest valid provider snapshot should remain available.

---

# 11. Snapshot Model

Use versioned snapshots.

Recommended KV keys:

```text
models:latest
models:nvidia:latest
models:amd:latest
models:huggingface:latest

snapshot:2026-09-23
snapshot:2026-09-22

manifest:latest
```

Manifest example:

```json
{
  "version": "2026-09-23",
  "generated_at": "2026-09-23T02:00:13Z",
  "providers": {
    "nvidia": {
      "count": 37,
      "last_success": "2026-09-23T02:00:10Z"
    },
    "amd": {
      "count": 21,
      "last_success": "2026-09-23T02:00:11Z"
    },
    "huggingface": {
      "count": 184,
      "last_success": "2026-09-23T02:00:13Z"
    }
  }
}
```

Never overwrite a valid `latest` snapshot with an empty or invalid result.

---

# 12. GitHub Actions

The initial data update mechanism is GitHub Actions.

Run once per day:

```yaml
on:
  schedule:
    - cron: "0 2 * * *"

  workflow_dispatch:
```

The workflow should:

1. Checkout repository
2. Setup Python
3. Install dependencies
4. Run tests
5. Run provider fetchers
6. Validate results
7. Compare against previous snapshot
8. Upload valid data to Cloudflare KV

Use GitHub Secrets for:

```text
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_API_TOKEN
```

Do not store API keys inside model records.

---

# 13. Cloudflare KV

Use Cloudflare KV for MVP.

Reasons:

- simple
- inexpensive
- sufficient for mostly read-heavy catalog data
- naturally fits Pages Functions
- no relational queries are required initially

Do NOT introduce D1 for MVP unless relational querying becomes necessary.

Potential future migration:

```text
KV
 ↓
D1
```

when requirements include:

- historical analysis
- complex filtering
- relational model/provider tables
- scoring history
- endpoint health history
- usage statistics

---

# 14. Web Application

Domain:

```text
models.magi.website
```

The UX should be inspired by:

```text
start.spring.io
```

The primary flow:

```text
Provider Selection
        ↓
Model Selection
        ↓
Output Format
        ↓
Generate
        ↓
Configuration
```

---

# 15. Provider Selection

The first UI should allow:

```text
[x] NVIDIA
[x] AMD
[x] Hugging Face
```

The user can select one or multiple providers.

---

# 16. Model Selection

Provide:

- search
- provider filter
- free filter
- model selection
- model metadata
- capability information where available

The UI should make it obvious that the same underlying model may appear from multiple providers.

Example:

```text
Gemma 4 31B

NVIDIA
AMD
Hugging Face
```

Do not silently merge them into one endpoint.

---

# 17. Output Format

MVP initially supports:

```text
LiteLLM
```

Future formats may include:

```text
asrv
OpenAI-compatible proxy
other gateway formats
```

The architecture must make adding generators straightforward.

Use an abstraction such as:

```python
class ConfigGenerator(Protocol):
    def generate(
        self,
        models: list[ModelEndpoint]
    ) -> GeneratedConfig:
        ...
```

The first implementation:

```text
LiteLLMGenerator
```

---

# 18. LiteLLM Generator

Example output:

```yaml
model_list:
  - model_name: nvidia-gemma-4-31b
    litellm_params:
      model: nvidia/google/gemma-4-31b-it
      api_key: os.environ/NVIDIA_API_KEY
```

Never store real API keys.

Always reference environment variables.

For example:

```text
os.environ/NVIDIA_API_KEY
os.environ/HF_TOKEN
```

Provider-specific authentication should be configurable later.

---

# 19. Generated Configuration

When the user clicks Generate:

```text
POST /api/generate
```

The backend should:

1. Validate selected model IDs
2. Verify they exist in the current catalog
3. Generate the requested configuration
4. Generate a random short ID
5. Store the generated configuration in KV
6. Set a short TTL
7. Return the generated content and URL

Example:

```text
/generated/ABCDabcd
```

Recommended TTL:

```text
~5 minutes
```

Generated configurations should NOT become permanent user data.

---

# 20. Agent-Friendly URL

The generated configuration should be retrievable by an agent.

Example:

```bash
curl -X GET https://models.magi.website/generated/ABCDabcd
```

Also provide:

```text
GET /generated/{id}/prompt
```

which returns an agent prompt instructing the agent to:

1. Fetch the generated URL
2. Parse the LiteLLM configuration
3. Merge the model entries into the user's existing configuration
4. Preserve existing models
5. Avoid duplicate model names
6. Do not overwrite unrelated configuration

The prompt should be short and machine-friendly.

---

# 21. API Design

Initial API:

```text
GET  /api/providers
GET  /api/models
GET  /api/models?provider=nvidia
GET  /api/models?provider=amd
GET  /api/models?provider=huggingface

POST /api/generate

GET /generated/{id}
GET /generated/{id}/prompt
```

Keep the API stateless where possible.

The web layer should primarily read from KV and generate short-lived artifacts.

---

# 22. Deployment Architecture

The final MVP deployment should look like:

```text
                    GitHub Repository
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
       GitHub Actions               Cloudflare Pages
             │                           │
             ▼                           ▼
       Python data/                  web/
             │                           │
             │                           ├── UI
             │                           └── Pages Functions
             │                                  │
             └──────────────┐                   │
                            ▼                   │
                     Cloudflare KV ◄───────────┘
```

The two sides are independently executable:

```text
data/
  Python
  GitHub Actions

web/
  TypeScript
  Cloudflare Pages
```

---

# 23. Testing Strategy

Provider parsers should have fixture-based tests.

Example:

```text
data/tests/
├── fixtures/
│   ├── nvidia.html
│   ├── amd.json
│   └── huggingface.json
│
├── test_nvidia.py
├── test_amd.py
└── test_huggingface.py
```

Tests should verify:

- source parsing
- normalization
- free-status detection
- malformed input handling
- empty result detection
- schema validation
- deduplication

For NVIDIA RSC parsing, include regression fixtures because the source format may change.

---

# 24. Failure Handling

The system must distinguish:

```text
provider returned zero models
```

from:

```text
provider parser failed
```

and:

```text
provider temporarily unavailable
```

Never interpret:

```text
parser returned []
```

as:

```text
there are currently zero free models
```

without additional validation.

Recommended status model:

```text
success
partial
failed
invalid
```

---

# 25. MVP Scope

The MVP MUST include:

- NVIDIA provider
- AMD provider
- Hugging Face provider
- Python provider abstraction
- canonical model endpoint schema
- normalization
- validation
- deduplication
- daily GitHub Actions execution
- Cloudflare KV
- snapshot/versioning
- Cloudflare Pages
- model browsing
- model selection
- LiteLLM generation
- short-lived generated URL
- agent prompt generation

---

# 26. Explicitly Out of Scope

Do NOT implement these in MVP:

- user accounts
- authentication system
- API key management
- inference proxy
- model execution
- billing
- subscriptions
- D1
- Redis
- queue infrastructure
- benchmark platform
- complex ranking
- automatic deployment
- browser automation
- Playwright
- Puppeteer
- browser-use
- agent-browser
- chrome-use
- persistent user configurations

The aggregator is a **catalog + configuration generator**, not an inference service.

---

# 27. Future Architecture

The architecture should leave room for additional providers:

```text
NVIDIA
AMD
Hugging Face
OpenRouter
Groq
Google
...
```

and additional generators:

```text
LiteLLM
asrv
OpenAI-compatible proxy
Other gateway formats
```

Potential future architecture:

```text
                     Canonical Model
                           │
             ┌─────────────┼─────────────┐
             │             │             │
          NVIDIA          AMD            HF
          endpoint       endpoint       endpoint
             │             │             │
             └─────────────┼─────────────┘
                           │
                    Routing Layer
                           │
                    fallback / weight
                    latency / quota
```

This is future work, not MVP.

---

# 28. Future Canonical Model Identity

Eventually introduce:

```text
canonical_model_id
```

to represent the underlying model separately from provider endpoints.

Example:

```text
canonical_model_id:
  google/gemma-4-31b

endpoints:
  ├── NVIDIA
  ├── AMD
  └── Hugging Face
```

This enables future:

- model deduplication in UI
- benchmark aggregation
- model scoring
- endpoint comparison
- routing
- fallback
- provider selection

But the MVP should not over-engineer canonical identity resolution.

---

# 29. Future Model Scoring

Scoring is explicitly a later layer.

Potential data sources:

```text
Artificial Analysis
Hugging Face evaluations
OpenRouter metadata
Arena / human preference data
Models.dev
custom benchmarks
```

The architecture should allow:

```text
ModelEndpoint
      │
      ▼
Enrichment
      │
      ▼
Score
```

Do not make external scoring availability a prerequisite for provider discovery.

A model missing an external score must remain in the catalog.

---

# 30. Design Principles

Follow these principles throughout implementation:

### 1. Provider independence

Provider-specific code stays inside the provider module.

### 2. Runtime independence

Python data ingestion and Cloudflare web application are independently executable.

### 3. Contract over coupling

Use JSON schema/data contracts rather than sharing runtime code between Python and TypeScript.

### 4. Endpoint over model

Do not confuse model identity with provider endpoint identity.

### 5. Fail safely

Never replace valid data with an invalid or empty provider snapshot.

### 6. MVP first

Prefer a small reliable pipeline over a sophisticated platform.

### 7. Cloudflare-native

Use Cloudflare KV and Pages where they fit naturally.

### 8. No unnecessary backend

Python is an offline ingestion worker, not an online API server.

### 9. Generator extensibility

LiteLLM is the first output format, not the permanent architecture.

### 10. Data source and presentation are separate

The web application should never need to know how NVIDIA, AMD, or Hugging Face data was originally obtained.

---

# 31. Expected Final Repository

The initial implementation should converge toward:

```text
free-model-aggregator/
│
├── data/
│   ├── providers/
│   │   ├── nvidia.py
│   │   ├── amd.py
│   │   └── huggingface.py
│   │
│   ├── models/
│   │   ├── schema.py
│   │   ├── normalize.py
│   │   └── deduplicate.py
│   │
│   ├── storage/
│   │   └── cloudflare_kv.py
│   │
│   ├── tests/
│   ├── main.py
│   └── pyproject.toml
│
├── web/
│   ├── src/
│   ├── functions/
│   │   ├── api/
│   │   │   ├── providers.ts
│   │   │   ├── models.ts
│   │   │   └── generate.ts
│   │   └── generated/
│   │       └── [id].ts
│   ├── package.json
│   └── ...
│
├── shared/
│   └── schema/
│       └── model.schema.json
│
├── .github/
│   └── workflows/
│       └── fetch-models.yml
│
└── README.md
```

The implementation should preserve this separation unless a concrete requirement justifies changing it.
