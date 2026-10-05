# TFI Public Model Catalog API — Contract Fixes

## Objective

Review and fix the currently implemented public Model Catalog API and Agent discovery documents at:

* `GET /api/v1/models`
* `GET /api/v1/models/{model_id}`
* `/llms.txt`
* `/agents.md`

The API is already implemented and deployed. **Do not redesign or rewrite the existing catalog architecture.**

This task is a focused contract-quality pass based on the current implementation.

The primary goals are:

1. Correct the semantics of `owned_by`.
2. Explicitly document `capabilities` semantics.
3. Explicitly document filter combination semantics.
4. Clarify the relationship between `architecture` and `capabilities`.
5. Preserve the current public API shape and backward compatibility wherever possible.
6. Improve `/agents.md` as a machine-oriented contract.
7. Add/verify HTTP caching headers if not already implemented.
8. Add tests for all corrected semantics.

---

# 1. First: Audit Before Modifying

Inspect the existing implementation and identify:

* canonical model schema
* model normalization/enrichment pipeline
* public API projection
* `/api/v1/models`
* `/api/v1/models/{model_id}`
* filter implementation
* `/llms.txt`
* `/agents.md`
* existing tests
* existing cache headers
* existing OpenAI-compatible fields

Do not assume the current architecture is wrong.

Prefer the smallest change that establishes a stable public contract.

Do not introduce:

* a new database
* a new model storage layer
* a new API version
* pagination
* search
* authentication
* a new provenance API
* endpoint/entity redesign
* a new frontend architecture

---

# 2. `owned_by` Semantics

## Problem

The current public projection uses values such as:

```json
{
  "id": "deepseek-ai/deepseek-v4.1-flash",
  "owned_by": "nvidia",
  "data_source": "nvidia",
  "provider": "nvidia"
}
```

This incorrectly makes `owned_by` appear to mean the model's actual owner/developer.

In TFI:

```text
data_source
    = where the catalog observation comes from

provider
    = provider/endpoint through which the model is available

owned_by
    = model owner/developer, if reliably known
```

These are different concepts.

## Required behavior

Do NOT populate `owned_by` with `provider` merely to satisfy OpenAI compatibility.

If reliable model ownership information is available from the canonical model data, use it.

For example:

```json
{
  "id": "openai/gpt-oss-20b",
  "owned_by": "openai",
  "data_source": "nvidia",
  "provider": "nvidia"
}
```

If reliable ownership information is NOT available:

* do not invent it
* do not infer it merely from `data_source`
* do not use the endpoint provider as model owner

Depending on the current public API compatibility requirements, either:

1. omit `owned_by`, or
2. keep it only if the existing contract explicitly requires the field, but document its fallback semantics clearly.

Prefer semantically correct data over fabricated compatibility values.

## Important

Do not rename `provider`.

Do not remove:

```text
data_source
provider
```

These are important parts of TFI's canonical catalog model.

---

# 3. `capabilities` Contract

Keep the current field:

```json
"capabilities": [
  "chat",
  "vision",
  "reasoning",
  "tool_calling"
]
```

Do not replace it with raw provider/source-specific capability fields.

`capabilities` is the TFI canonical normalized capability vocabulary.

## Define the semantics

Document:

```text
capabilities
    = canonical functional capabilities normalized by TFI
```

Examples:

```text
chat
vision
reasoning
tool_calling
image_generation
speech
embedding
reranking
moderation
```

Use the actual vocabulary already defined by the project. Do not invent a second capability taxonomy if one already exists.

---

# 4. `capabilities: []` Semantics

Do NOT try to eliminate every empty capability array by guessing capabilities.

The following is valid:

```json
"capabilities": []
```

But its meaning MUST be explicitly defined as:

> Capability information is currently unavailable, not normalized, or could not be reliably determined.

It MUST NOT mean:

> The model has no capabilities.

This distinction is important for Agents and for `/browse` filtering.

Keep the current `[]` representation unless there is a strong existing schema reason to use `null`.

Do not introduce speculative capability inference merely to reduce empty arrays.

---

# 5. `architecture` vs `capabilities`

Preserve both concepts.

Define their responsibilities clearly.

## `architecture`

Represents input/output modalities:

```json
"architecture": {
  "input": ["text", "image"],
  "output": ["text"]
}
```

Examples of modalities:

```text
text
image
audio
video
```

## `capabilities`

Represents normalized functional behavior:

```json
"capabilities": [
  "chat",
  "vision",
  "reasoning",
  "tool_calling"
]
```

Conceptual contract:

```text
architecture.input/output
    ↓
what modalities the model accepts/produces

capabilities
    ↓
what functional capabilities TFI considers the model to support
```

Do not merge these fields.

Do not make `/api/v1/models` reinterpret raw source fields at request time.

The API should consume the already-normalized canonical data.

---

# 6. Filter Semantics

This must become an explicit public API contract.

Current supported filters:

```text
data_source
provider
capabilities
```

## Multiple values within the same filter

### `data_source`

OR semantics:

```text
?data_source=nvidia,amd
```

means:

```text
data_source = nvidia OR amd
```

### `provider`

OR semantics:

```text
?provider=groq,together
```

means:

```text
provider = groq OR together
```

### `capabilities`

AND semantics:

```text
?capabilities=chat,vision
```

means:

```text
capabilities contains chat
AND
capabilities contains vision
```

## Different filter types

Different filter dimensions combine with AND.

Example:

```text
?provider=groq,together&capabilities=chat,vision
```

means:

```text
(provider = groq OR provider = together)
AND
(capabilities contains chat AND capabilities contains vision)
```

Likewise:

```text
?data_source=nvidia,amd&provider=nvidia&capabilities=chat
```

means:

```text
(data_source = nvidia OR data_source = amd)
AND
provider = nvidia
AND
capabilities contains chat
```

Ensure the implementation matches this contract.

Do not change the existing filter syntax unless required by the current implementation.

---

# 7. Unknown Capability Behavior

Preserve the existing intended behavior:

```text
unknown capability → HTTP 400
```

Return a machine-readable error.

Example:

```json
{
  "error": {
    "code": "invalid_capability",
    "message": "Unknown capability: foo"
  }
}
```

Use the project's existing error schema if one already exists.

Do not invent a second error format.

Unknown `provider` or `data_source` may continue to return:

```http
200 OK
```

with:

```json
{
  "object": "list",
  "data": []
}
```

unless the current implementation has an established alternative contract.

---

# 8. `/llms.txt`

Update `/llms.txt` to explicitly document:

## API discovery

```text
GET /api/v1/models
GET /api/v1/models/{model_id}
```

## Authentication

Explicitly state:

```text
The public Model Catalog API is read-only and does not require authentication.
```

## Filter semantics

Add:

```text
Filter semantics:
- Multiple capabilities are combined with AND.
- Multiple providers are combined with OR.
- Multiple data sources are combined with OR.
- Different filter types are combined with AND.
```

## Capability semantics

Briefly state:

```text
Capabilities use TFI's canonical normalized capability vocabulary.
An empty capabilities array means capability information is currently unavailable or not normalized; it does not mean the model has no capabilities.
```

Keep `/llms.txt` concise.

Do not turn it into full API documentation.

---

# 9. `/agents.md`

Make `/agents.md` the detailed machine-oriented contract.

It should explain:

## Identity

TFI is:

> an AI model catalog and Token Factory configuration initializer.

## Base URL

```text
https://start.magi.website
```

## Public API

```text
GET /api/v1/models
GET /api/v1/models/{model_id}
```

## Authentication

No authentication is required.

The API is public and read-only.

## Recommended Agent Workflow

Document:

```text
1. Fetch /api/v1/models.
2. Filter candidates by provider, data source, and/or capability.
3. Inspect candidate models.
4. Fetch /api/v1/models/{model_id} when more detail is required.
5. Use /browse when a human needs to continue configuration.
```

Do not claim that a public configuration-generation API exists unless it is actually implemented.

## Model semantics

Explain:

```text
data_source
provider
owned_by
architecture
capabilities
free
```

Especially clarify:

```text
data_source ≠ provider
provider ≠ owned_by
architecture ≠ capabilities
```

## Filter semantics

Document the complete AND/OR behavior described above.

## Capability semantics

Document:

```text
capabilities = canonical normalized functional capabilities

architecture.input/output = input/output modalities

capabilities=[] = capability information unavailable/not normalized
```

---

# 10. `free` Field

Do NOT perform a major schema migration in this task.

Keep the existing:

```json
"free": true
```

field if it is already part of the public contract.

However, document its current semantics accurately.

For this phase:

```text
free
    = TFI currently considers this catalog entry available through a free/free-tier path.
```

Do not describe `free` as an intrinsic property of the underlying model.

Do not introduce a new endpoint/pricing schema in this task.

Create a TODO or architecture note for a future model/endpoint separation if the repository already has a roadmap mechanism.

---

# 11. `created`

If the current API returns:

```json
"created": 0
```

keep it for OpenAI-compatible response shape unless a real model creation timestamp is available.

Do NOT fabricate timestamps.

Do not use:

```text
observed_at
updated_at
generated_at
```

as fake replacements for `created`.

If provenance or observation timestamps already exist internally, keep them internal.

---

# 12. HTTP Caching

Inspect the current API response headers.

If caching is not already configured, add a reasonable public cache policy.

For example:

```http
Cache-Control: public, max-age=300
```

If the API is already behind Cloudflare caching, preserve the existing architecture and avoid unnecessary duplicate cache layers.

## ETag

If there is a simple existing mechanism for generating a deterministic catalog version/hash, consider adding:

```http
ETag: "..."
```

and support:

```http
If-None-Match
```

with:

```http
304 Not Modified
```

However:

**Do not introduce a complicated catalog-version system solely for this task.**

ETag is optional if it would require substantial architectural work.

Cache correctness is more important than implementing ETag.

---

# 13. Model Detail Route

Verify:

```text
GET /api/v1/models/{model_id}
```

works for IDs containing `/`.

Example:

```text
/api/v1/models/deepseek-ai/deepseek-v4.1-flash
```

The routing implementation must support slash-containing model IDs.

Do not change model IDs or URL-encode them into a different public identifier.

Verify:

* existing model → `200`
* unknown model → `404`
* returned `id` exactly matches the requested model ID

---

# 14. Public Projection Boundary

Keep the public projection isolated from internal canonical model data.

Conceptually:

```text
Canonical Model
      ↓
toPublicModel()
      ↓
Public API
```

Do not expose:

```text
provenance
source observations
raw provider payloads
internal KV keys
pipeline metadata
internal scoring
internal timestamps
secrets
```

The public API should expose canonical model knowledge, not data lineage.

---

# 15. Tests

Add or update tests for all corrected behavior.

## `owned_by`

Test:

* provider is not automatically used as owner
* reliable owner is preserved when available
* unavailable owner is not fabricated

## capabilities

Test:

```text
capabilities = canonical values
capabilities = []
```

and ensure empty array does not cause errors.

## filter semantics

Test:

```text
provider=groq,together
```

→ OR

```text
data_source=nvidia,amd
```

→ OR

```text
capabilities=chat,vision
```

→ AND

```text
provider=groq,together&capabilities=chat,vision
```

→ OR inside provider + AND inside capabilities + AND between dimensions

## detail route

Test slash-containing model IDs.

## public projection

Test that provenance/internal metadata is not exposed.

## caching

If caching behavior is implemented, test the response headers.

---

# 16. Do Not Over-Refactor

This task is NOT permission to:

* redesign the model schema
* introduce Model/Endpoint entities
* redesign KV storage
* rewrite the pipeline
* add pagination
* add search
* add authentication
* add model ranking
* add AI recommendation
* add Agent/MCP APIs
* add configuration-generation APIs
* create a new API version
* rename existing public fields unnecessarily

The goal is to make the existing API contract precise and trustworthy.

---

# 17. Documentation Principle

The public contract should converge on:

```text
Model Catalog
    ↓
Canonical Model
    ├── data_source
    ├── provider
    ├── owned_by
    ├── architecture
    ├── capabilities
    └── free
```

With these semantic boundaries:

```text
data_source
    = source of catalog observation

provider
    = provider/endpoint

owned_by
    = model owner/developer, when known

architecture
    = input/output modalities

capabilities
    = normalized functional capabilities

free
    = current TFI availability classification
```

---

# 18. Definition of Done

The task is complete when:

* [ ] `owned_by` no longer incorrectly means `provider`
* [ ] no ownership information is fabricated
* [ ] `data_source` and `provider` semantics remain unchanged
* [ ] `capabilities` has a documented canonical meaning
* [ ] `capabilities=[]` semantics are documented
* [ ] `architecture.input/output` vs `capabilities` semantics are documented
* [ ] provider filter uses OR semantics
* [ ] data_source filter uses OR semantics
* [ ] capability filter uses AND semantics
* [ ] different filter dimensions use AND semantics
* [ ] `/llms.txt` contains the concise filter contract
* [ ] `/llms.txt` states that the API is public/read-only/no-auth
* [ ] `/agents.md` contains the detailed Agent contract
* [ ] `free` semantics are documented without redesigning the schema
* [ ] `created: 0` is preserved if no real timestamp exists
* [ ] slash-containing model IDs work
* [ ] public API does not expose provenance/internal metadata
* [ ] cache headers are present and reasonable
* [ ] tests cover the corrected behavior
* [ ] no unnecessary architectural refactor was introduced

---

# Final Principle

**Freeze the public Model Catalog contract before adding more consumers.**

The API should communicate:

> **What model is this? Where is it available? What can it do? What modalities does it support?**

It should NOT expose:

> How TFI internally discovered, enriched, scored, reconciled, or stored the model.

The public machine interface should remain:

```text
Human:
    /browse

Machine:
    /api/v1/models
    /api/v1/models/{id}

Agent discovery:
    /llms.txt
    /agents.md
```

Keep the API small, deterministic, semantically precise, and stable.

