# TFI Provider & Endpoint Intelligence API Implementation

## 0. Role

You are implementing the next phase of the Token Factory Initializr (TFI) public Model Intelligence API.

Repository context:

* Product: Token Factory Initializr
* Website: `https://start.magi.website`
* Public model API:

  * `GET /api/v1/models`
  * `GET /api/v1/models/{id}`
* Agent discovery:

  * `/llms.txt`
  * `/agents.md`
* TFI is built on Cloudflare Workers / Pages infrastructure.
* Canonical model data is already normalized and stored by the existing data pipeline.
* The existing model API is already implemented and should be preserved.

The goal of this task is to add:

```text
GET /api/v1/providers
GET /api/v1/providers/{id}

GET /api/v1/endpoints
GET /api/v1/endpoints/{id}
```

These APIs extend the existing Model Catalog into a broader **Model & Endpoint Intelligence API**.

---

# 1. Product Principle

The API hierarchy is:

```text
Model
  ↓
Endpoint
  ↓
Provider
  ↓
Constraints / Runtime Metadata
```

The three concepts must remain distinct.

### Model

Answers:

> What model is this and what can it do?

Examples:

* model ID
* capabilities
* modalities
* context length
* description

Existing API:

```text
/api/v1/models
```

### Endpoint

Answers:

> Where and how can this model be called?

Examples:

* base URL
* protocol
* authentication scheme
* availability
* limits
* endpoint status

Future API:

```text
/api/v1/endpoints
```

### Provider

Answers:

> Who operates/provides this endpoint?

Examples:

* Groq
* NVIDIA
* AMD
* OpenRouter
* Together
* etc.

API:

```text
/api/v1/providers
```

Do NOT collapse these concepts into a single `provider` field on the model.

---

# 2. Important Architectural Distinction

Do not confuse:

```text
data_source
provider
endpoint
model
```

Example:

```text
data_source = huggingface

provider = together

endpoint = Hugging Face / Together inference endpoint

model = meta-llama/Llama-3.3-70B-Instruct
```

Another example:

```text
data_source = groq

provider = groq

endpoint = https://api.groq.com/openai/v1

model = openai/gpt-oss-120b
```

The existing `data_source` concept must remain intact.

Do not reuse `data_source` as `provider`.

---

# 3. Scope

## In scope

Implement:

```text
/api/v1/providers
/api/v1/providers/{id}

/api/v1/endpoints
/api/v1/endpoints/{id}
```

Also:

* public response schemas
* provider/endpoint projection
* filtering where useful
* model ↔ endpoint relationships
* endpoint status
* endpoint limits
* endpoint API metadata
* provenance internally
* caching
* CORS
* tests
* API documentation
* updates to `/llms.txt`
* updates to `/agents.md`

## Explicitly out of scope

Do NOT implement:

* model recommendation API
* `/recommend`
* automatic model routing
* runtime proxying
* API key management
* user accounts
* billing
* usage metering
* orchestration execution
* fallback execution
* automatic provider selection
* MCP server
* A2A
* provider credential storage
* private API keys
* secret management
* a new database
* a new KV namespace unless strictly required
* a second independent model schema
* a second independent provenance system

This phase is metadata and discovery only.

---

# 4. Public API Architecture

The target architecture is:

```text
                    TFI Model Intelligence API

                             Model
                               │
                      ┌────────┴────────┐
                      │                 │
                 /models          /endpoints
                                        │
                              ┌─────────┴─────────┐
                              │                   │
                           Provider           Constraints
                              │                   │
                           /providers        limits/status
```

Public APIs:

```text
GET /api/v1/models
GET /api/v1/models/{id}

GET /api/v1/providers
GET /api/v1/providers/{id}

GET /api/v1/endpoints
GET /api/v1/endpoints/{id}
```

---

# 5. Provider API

## 5.1 List

```http
GET /api/v1/providers
```

Response:

```json
{
  "object": "list",
  "data": [
    {
      "id": "groq",
      "name": "Groq",
      "data_source": "groq",
      "protocols": [
        "openai-compatible"
      ]
    }
  ]
}
```

Provider objects should contain stable identity and general metadata.

Do not put model-specific data into the provider object.

Do not put volatile per-model limits into the provider object unless the limit is genuinely provider-wide.

---

# 6. Provider Detail

```http
GET /api/v1/providers/{id}
```

Example:

```json
{
  "id": "groq",
  "name": "Groq",
  "data_source": "groq",
  "protocols": [
    "openai-compatible"
  ]
}
```

Provider detail may eventually contain:

* display name
* website
* documentation URL
* supported protocols
* general authentication scheme
* provider status

But keep the initial schema minimal.

Do not turn this endpoint into a general provider directory.

The primary purpose is to support Agent model/endpoint discovery.

---

# 7. Endpoint API

Endpoint is the important new abstraction.

An endpoint represents a concrete runtime access point.

Example:

```json
{
  "id": "groq:default",
  "provider": "groq",
  "data_source": "groq",
  "protocol": "openai-compatible",
  "base_url": "https://api.groq.com/openai/v1",
  "authentication": {
    "type": "bearer",
    "credential_required": true
  },
  "status": "active"
}
```

Endpoint metadata must NOT contain:

* API keys
* access tokens
* credentials
* secrets
* user-specific authentication data

---

# 8. Endpoint Identity

Endpoint IDs must be deterministic and stable.

Recommended format:

```text
{provider}:{endpoint_name}
```

Examples:

```text
groq:default
nvidia:default
amd:default
openrouter:default
```

If a provider has multiple endpoints:

```text
huggingface:together
huggingface:novita
provider-x:region-eu
provider-x:region-us
```

Do not use the base URL directly as the endpoint ID.

Centralize endpoint ID generation.

Do not generate random UUIDs for stable catalog endpoints.

---

# 9. Endpoint ↔ Model Relationship

A model can be available through multiple endpoints.

Conceptually:

```text
Model
 ├── Endpoint A
 ├── Endpoint B
 └── Endpoint C
```

For example:

```text
deepseek/deepseek-v4.1-flash
    │
    ├── NVIDIA endpoint
    ├── AMD endpoint
    └── OpenRouter endpoint
```

The public model API should eventually be able to expose available endpoints for a model.

For this phase, choose the least disruptive implementation compatible with the existing model schema.

Preferred approach:

Add an optional field to the public model projection:

```json
{
  "id": "openai/gpt-oss-120b",
  "provider": "groq",
  "endpoints": [
    "groq:default"
  ]
}
```

If the existing `/models` contract should not be changed in this release, document the relationship through endpoint objects instead.

Do not duplicate complete endpoint objects inside every model.

Use endpoint IDs as references.

---

# 10. Endpoint Response Schema

Initial public endpoint schema:

```json
{
  "id": "groq:default",
  "provider": "groq",
  "data_source": "groq",
  "protocol": "openai-compatible",
  "base_url": "https://api.groq.com/openai/v1",
  "authentication": {
    "type": "bearer",
    "credential_required": true
  },
  "status": "active",
  "limits": {
    "scope": "free_tier",
    "subject": "api_key",
    "rpm": 30,
    "rpd": 14400,
    "tpm": 6000
  }
}
```

Not every field is required.

If a value is unknown, do not invent it.

Prefer omission or `null` according to the existing API schema convention.

---

# 11. Protocol

Use a normalized vocabulary.

Initial values may include:

```text
openai-compatible
anthropic
native
huggingface
nim
```

Do not assume every provider is OpenAI-compatible.

Protocol describes the API contract exposed by the endpoint.

It is NOT the same as provider.

---

# 12. Base URL

Expose the public API base URL when known.

Example:

```json
{
  "base_url": "https://api.groq.com/openai/v1"
}
```

This information is intended for:

* Agent configuration
* LiteLLM configuration generation
* NewAPI configuration generation
* human developer configuration
* endpoint discovery

Never expose:

```text
API keys
Authorization headers
Service tokens
Secrets
Private URLs
Internal Cloudflare URLs
```

---

# 13. Authentication

Represent authentication requirements, not credentials.

Example:

```json
{
  "authentication": {
    "type": "bearer",
    "credential_required": true
  }
}
```

Possible normalized types:

```text
none
bearer
api_key
oauth2
custom
unknown
```

Do not expose credential names unless there is a clear public reason.

---

# 14. Endpoint Status

Every endpoint should have a normalized status.

Initial vocabulary:

```text
active
degraded
temporarily_unavailable
deprecated
unknown
```

Meaning:

### active

Endpoint is currently considered usable.

### degraded

Endpoint exists but has known limitations.

### temporarily_unavailable

Endpoint exists but is currently unavailable.

### deprecated

Endpoint should no longer be selected for new configurations.

### unknown

TFI does not have enough information to determine current status.

Do not infer `active` merely because an endpoint exists in historical data.

---

# 15. Limits

Limits are endpoint-level or access-plan-level metadata.

Do NOT model:

```json
{
  "provider": "groq",
  "rpm": 30
}
```

as a universal provider property.

Instead:

```json
{
  "limits": {
    "scope": "free_tier",
    "subject": "api_key",
    "rpm": 30,
    "rpd": 14400,
    "tpm": 6000
  }
}
```

The schema must acknowledge that limits can depend on:

* plan
* API key
* organization
* IP
* model
* endpoint
* region

Do not over-model these dimensions in Phase 1.

The minimum abstraction is:

```text
Limit
├── scope
├── subject
├── rpm
├── rpd
└── tpm
```

All fields are optional.

---

# 16. Limit Semantics

Document these carefully.

### RPM

Requests per minute.

### RPD

Requests per day.

### TPM

Tokens per minute.

Do not assume these limits are interchangeable.

Do not convert between them.

Do not derive RPM from TPM.

Do not derive RPD from RPM.

If the source provides a different limit type, do not silently transform it.

---

# 17. Limit Provenance

Limits are volatile and must support provenance internally.

For example:

```json
{
  "limits": {
    "scope": "free_tier",
    "subject": "api_key",
    "rpm": 30
  }
}
```

Internal provenance:

```json
{
  "provenance": {
    "limits.rpm": {
      "source": "groq",
      "source_url": "...",
      "source_field": "...",
      "method": "native",
      "observed_at": "2026-10-05T..."
    }
  }
}
```

Reuse the existing TFI field-level provenance architecture.

Do NOT create another provenance system.

Do NOT expose internal provenance in public API responses.

---

# 18. Free Tier

Be careful with the existing `free` concept.

A model itself is not inherently free.

Availability may be:

```text
Model
  ↓
Endpoint
  ↓
Plan
  ↓
Pricing / Limits
```

For this phase, do not perform a large breaking schema migration if the existing `/models` API already exposes:

```json
"free": true
```

Keep backward compatibility.

However, new endpoint metadata should model free availability at the endpoint/plan level where possible.

Example:

```json
{
  "limits": {
    "scope": "free_tier"
  }
}
```

Do not assume:

```text free model = unlimited
```

---

# 19. Endpoint ↔ Provider Relationship

Every endpoint must reference exactly one provider.

Example:

```json
{
  "id": "groq:default",
  "provider": "groq"
}
```

Every endpoint must also have a `data_source`.

Example:

```json
{
  "data_source": "groq"
}
```

These fields serve different purposes:

```text
data_source
= where TFI observed/discovered this information

provider
= who operates/provides the endpoint
```

Do not remove either field.

---

# 20. Data Model

Introduce an internal canonical endpoint model.

Example:

```typescript
type Endpoint = {
  id: string
  provider: string
  data_source: string

  protocol?: string
  base_url?: string

  authentication?: {
    type: string
    credential_required?: boolean
  }

  status?: EndpointStatus

  limits?: {
    scope?: string
    subject?: string
    rpm?: number
    rpd?: number
    tpm?: number
  }

  provenance?: Record<string, Provenance>
}
```

Provider:

```typescript
type Provider = {
  id: string
  name?: string
  data_source: string
  protocols?: string[]
}
```

Do not create a second model schema specifically for the HTTP API.

The public API must be a projection of canonical data.

---

# 21. Public Projection

Follow the same pattern already used by `/api/v1/models`.

Create:

```text
toPublicProvider()
toPublicEndpoint()
```

The functions should:

* expose only stable public fields
* exclude provenance
* exclude raw source payloads
* exclude internal storage metadata
* exclude secrets
* exclude internal keys
* exclude pipeline metadata

Conceptually:

```text
Canonical Provider
       ↓
toPublicProvider()
       ↓
Public Provider API
```

and:

```text
Canonical Endpoint
       ↓
toPublicEndpoint()
       ↓
Public Endpoint API
```

---

# 22. List API

Implement:

```text
GET /api/v1/providers
GET /api/v1/endpoints
```

Use the existing API response convention:

```json
{
  "object": "list",
  "data": []
}
```

Do not introduce pagination unless the existing catalog size requires it.

Keep pagination extensible.

---

# 23. Provider Filters

At minimum support:

```text
GET /api/v1/providers?data_source=groq
```

Multiple values:

```text
GET /api/v1/providers?data_source=groq,nvidia
```

Semantics:

```text
same parameter values = OR
different filter dimensions = AND
```

Keep behavior consistent with `/api/v1/models`.

---

# 24. Endpoint Filters

Support useful filters without overengineering.

Recommended initial filters:

```text
provider
data_source
protocol
status
```

Examples:

```text
/api/v1/endpoints?provider=groq

/api/v1/endpoints?data_source=nvidia

/api/v1/endpoints?protocol=openai-compatible

/api/v1/endpoints?status=active
```

Multiple values:

```text
/api/v1/endpoints?provider=groq,nvidia
```

means:

```text
groq OR nvidia
```

Different dimensions:

```text
/api/v1/endpoints?provider=groq&protocol=openai-compatible
```

means:

```text
provider = groq
AND
protocol = openai-compatible
```

---

# 25. Model Filter on Endpoints

If practical with the existing canonical data, support:

```text
/api/v1/endpoints?model_id=openai/gpt-oss-120b
```

This is highly valuable for Agent orchestration.

However, do not introduce expensive runtime scans over raw source data.

Use existing normalized/catalog data.

If implementing this requires a major storage redesign, defer it and document it as a follow-up.

---

# 26. Model Detail Relationship

Ideally:

```text
GET /api/v1/models/{id}
```

can expose:

```json
{
  "id": "openai/gpt-oss-120b",
  "endpoints": [
    "groq:default",
    "openrouter:default"
  ]
}
```

Do not embed:

```json
"endpoints": [
  {
    "... entire endpoint object ..."
  }
]
```

Endpoint information should have one canonical public representation.

---

# 27. Storage

Reuse the existing canonical storage architecture.

Do NOT make API requests to external providers at request time.

The request path must be:

```text
Client
  ↓
Cloudflare Worker
  ↓
Canonical storage
  ↓
Projection
  ↓
JSON
```

NOT:

```text
Client
  ↓
Cloudflare Worker
  ↓
Groq API
NVIDIA API
HF API
OpenRouter API
  ↓
aggregate
  ↓
response
```

External source fetching belongs to the existing data pipeline.

---

# 28. KV Design

If Cloudflare KV is used, centralize key generation.

Recommended conceptual keys:

```text
tfi:providers:{data_source}:latest

tfi:endpoints:{data_source}:{provider}:latest
```

If the current implementation prefers a global provider catalog:

```text
tfi:providers:latest
```

and:

```text
tfi:endpoints:latest
```

is also acceptable.

Choose the structure that best matches the existing snapshot/diff/reconcile/publish pipeline.

Do not introduce a second unrelated storage convention.

The important invariant is:

> Public API reads published canonical state, not raw source state.

---

# 29. Provider Manifest

The existing provider manifest concept should be reused.

For each data source:

```text
tfi:providers:{data_source}:latest
```

contains active providers.

For example:

```json
[
  "novita",
  "together",
  "zai-org"
]
```

The endpoint publication pipeline should similarly maintain an explicit desired state.

Do not rely on TTL to remove stale endpoints.

Use:

```text
snapshot
→ diff
→ reconcile
→ publish
```

to remove stale endpoints.

---

# 30. Stale Endpoint Safety

This is critical.

An incomplete source fetch must NOT cause destructive endpoint deletion.

For example:

```text
Source fetch fails
        ↓
empty result
```

must NOT automatically mean:

```text
delete all endpoints
```

The existing pipeline's incomplete/invalid snapshot safety rules must be reused.

Only reconcile deletions when the source snapshot is validated as complete enough to establish absence.

---

# 31. Endpoint Status vs Reconciliation

Do not use endpoint status as a substitute for lifecycle reconciliation.

For example:

```text
deprecated
```

and:

```text
removed from source
```

are different events.

If an endpoint is no longer part of the desired published catalog:

```text
reconcile
→ remove it
```

If the source explicitly reports:

```text
deprecated
```

it may remain published with:

```json
"status": "deprecated"
```

This distinction should remain explicit.

---

# 32. Caching

These are public read-only APIs.

Use public caching.

Example:

```http
Cache-Control: public, max-age=300
```

Add:

```text
ETag
```

if practical.

The API should support conditional requests:

```http
If-None-Match
```

and:

```http
304 Not Modified
```

when the catalog has not changed.

Do not over-engineer cache invalidation.

The canonical catalog publication pipeline should be the source of cache versioning.

---

# 33. CORS

Keep public GET APIs accessible to:

* browsers
* external tools
* Agents
* scripts

Use:

```http
Access-Control-Allow-Origin: *
```

for public GET endpoints unless the existing deployment has a stronger reason not to.

No authentication is required for these public metadata APIs.

---

# 34. Error Handling

Maintain the existing API error format.

For unknown provider:

```text
GET /api/v1/providers/not-found
```

return:

```text
404
```

For unknown endpoint:

```text
GET /api/v1/endpoints/not-found
```

return:

```text
404
```

For invalid filter values, follow the existing `/models` semantics.

Do not invent a separate error format.

---

# 35. Agent Contract

Update:

```text
/llms.txt
/agents.md
```

The discovery documentation should now describe:

```text
Model discovery
Provider discovery
Endpoint discovery
```

Recommended Agent workflow:

```text
1. GET /api/v1/models
2. Filter models by capability
3. Identify candidate models
4. Inspect model details
5. Discover available endpoints
6. Compare endpoint protocol/status/limits
7. Select a suitable endpoint
8. Use TFI UI for human-assisted configuration
```

Do not claim that TFI automatically executes requests through these endpoints.

This phase is discovery/configuration metadata only.

---

# 36. Recommended Agent Queries

Document examples such as:

```text
GET /api/v1/models?capabilities=chat,vision
```

then:

```text
GET /api/v1/endpoints?model_id=...
```

then:

```text
GET /api/v1/endpoints/groq:default
```

An Agent should be able to answer:

> Find a free vision model with an active OpenAI-compatible endpoint.

using:

```text
models
→ capabilities
→ endpoints
→ status
→ limits
```

This is the core use case.

---

# 37. Do Not Expose Provenance Publicly

The public API must NOT expose:

```text
provenance
source_field
confidence
raw source payload
pipeline timestamps
KV keys
snapshot IDs
reconcile metadata
```

These remain internal canonical data.

The public API exposes the resulting normalized facts.

---

# 38. Security

Verify that no response contains:

* API keys
* access tokens
* service tokens
* Cloudflare credentials
* environment variables
* internal URLs
* private endpoints
* user-specific limits
* user identifiers

Public endpoint metadata must be safe to expose.

---

# 39. Testing

Add tests for:

## Provider

* provider list
* provider detail
* unknown provider → 404
* data_source filter
* multiple provider values
* projection excludes provenance
* projection excludes secrets

## Endpoint

* endpoint list
* endpoint detail
* unknown endpoint → 404
* provider filter
* data_source filter
* protocol filter
* status filter
* multiple provider values
* combined filters
* model_id filter if implemented
* projection excludes provenance
* projection excludes secrets
* base URL is exposed correctly
* authentication metadata is exposed without credentials

## Limits

Test:

```text
rpm
rpd
tpm
```

independently.

Test missing limits.

Test partial limits:

```json
{
  "rpm": 30
}
```

without assuming `rpd` or `tpm`.

## Relationships

Test:

```text
model → endpoint
endpoint → provider
endpoint → data_source
```

Test multiple endpoints for one model.

---

# 40. Backward Compatibility

The existing:

```text
GET /api/v1/models
GET /api/v1/models/{id}
```

must continue to work.

Do not break:

* existing field names
* existing filter semantics
* existing response shape
* existing Agent documentation assumptions

If adding:

```text
endpoints
```

to model detail, make it additive.

Do not rename:

```text
data_source
provider
capabilities
```

in this task.

---

# 41. API Documentation

Document all six endpoints:

```text
GET /api/v1/models
GET /api/v1/models/{id}

GET /api/v1/providers
GET /api/v1/providers/{id}

GET /api/v1/endpoints
GET /api/v1/endpoints/{id}
```

For each endpoint document:

* purpose
* parameters
* response schema
* filtering
* error behavior
* example request
* example response

Make the documentation Agent-readable.

---

# 42. Implementation Constraints

Before writing code:

1. Inspect the existing `/api/v1/models` implementation.
2. Reuse existing API routing conventions.
3. Reuse existing storage abstractions.
4. Reuse existing public projection patterns.
5. Reuse existing filter semantics.
6. Reuse existing provenance implementation.
7. Reuse existing snapshot/diff/reconcile/publish pipeline.
8. Identify the minimum changes required.

Do NOT create parallel abstractions when an existing one can be extended.

---

# 43. Architecture Boundary

Maintain this boundary:

```text
Source Adapters
      ↓
Raw Observations
      ↓
Normalize
      ↓
Identity Match
      ↓
Enrich
      ↓
Validate
      ↓
Derive
      ↓
Snapshot
      ↓
Diff
      ↓
Reconcile
      ↓
Publish
      ↓
Canonical Model / Provider / Endpoint Data
      ↓
Public Projection
      ↓
HTTP API
```

The HTTP API must remain read-only.

The HTTP API must never become part of the ingestion pipeline.

---

# 44. Definition of Done

The implementation is complete when:

### Provider API

* [ ] `/api/v1/providers` works
* [ ] `/api/v1/providers/{id}` works
* [ ] provider filtering works
* [ ] provider schema is documented
* [ ] provider projection excludes internal metadata

### Endpoint API

* [ ] `/api/v1/endpoints` works
* [ ] `/api/v1/endpoints/{id}` works
* [ ] endpoint filtering works
* [ ] protocol is normalized
* [ ] base URL is exposed
* [ ] authentication requirements are exposed without credentials
* [ ] endpoint status is exposed
* [ ] limits are exposed where known
* [ ] endpoint projection excludes provenance/secrets

### Model relationship

* [ ] model → endpoint relationship is defined
* [ ] endpoint → provider relationship is defined
* [ ] data_source remains distinct from provider
* [ ] existing `/models` API remains backward compatible

### Agent

* [ ] `/llms.txt` updated
* [ ] `/agents.md` updated
* [ ] Agent workflow documented
* [ ] filtering semantics documented

### Infrastructure

* [ ] canonical storage reused
* [ ] snapshot/diff/reconcile/publish lifecycle reused
* [ ] stale endpoint cleanup is supported
* [ ] incomplete source snapshots cannot cause destructive deletion
* [ ] public caching enabled
* [ ] ETag implemented if practical
* [ ] CORS enabled

### Quality

* [ ] tests pass
* [ ] no secrets exposed
* [ ] no unnecessary schema duplication
* [ ] no unnecessary refactor
* [ ] no runtime dependency on upstream provider APIs
* [ ] API responses are deterministic

---

# 45. Future Direction — Do Not Implement Yet

The architecture should leave room for:

```text
/api/v1/models
/api/v1/providers
/api/v1/endpoints
```

to eventually support:

```text
Model
   ↓
Endpoint
   ↓
Provider
   ↓
Availability
   ↓
Limits
   ↓
Pricing
   ↓
Recommendation
   ↓
Configuration
```

Future APIs may eventually include:

```text
/api/v1/recommend
/api/v1/configurations
```

or similar.

Do NOT implement these now.

The current goal is to establish reliable Model + Endpoint intelligence.

---

# 46. Product Principle

TFI should evolve from:

> A model selector and configuration generator

toward:

> **An AI Model & Endpoint Intelligence layer for developers and Agents.**

The public API should allow an Agent to answer:

```text
What models exist?
        ↓
What can they do?
        ↓
Where can they run?
        ↓
How can they be called?
        ↓
Is the endpoint currently available?
        ↓
What are the relevant constraints?
```

But this phase should stop there.

**Do not implement orchestration execution yet.**

The core principle is:

> **Models describe capability. Endpoints describe access. Providers describe ownership. Constraints describe runtime conditions.**

And:

> **TFI exposes normalized intelligence, not raw provider data.**

