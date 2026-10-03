# Token Factory Initializr — Data Pipeline Refactor

## Context

You are working on the data pipeline of **Token Factory Initializr (TFI)**.

TFI collects model metadata from multiple data sources and publishes normalized model catalogs to Cloudflare KV. The current data sources include:

* NVIDIA NIM
* AMD Radeon Cloud
* Hugging Face Inference Providers

The current implementation has a structural problem around the meaning of `provider`.

For NVIDIA and AMD, the source itself is also the provider:

```text
NVIDIA
  data_source = nvidia
  provider    = nvidia

AMD
  data_source = amd
  provider    = amd
```

However, Hugging Face is an aggregation/discovery platform. A Hugging Face model may be served by an inference provider such as:

```text
novita
together
deepinfra
nscale
zai-org
...
```

Therefore:

```text
data_source = huggingface
provider    = novita
```

The current implementation incorrectly treats `provider` as the top-level namespace, causing Hugging Face data to produce provider keys such as:

```text
tfi:models:novita:latest
tfi:models:together:latest
tfi:models:zai-org:latest
```

This loses the distinction between:

```text
data source
```

and:

```text
inference provider
```

and creates future namespace-collision risks if another data source also contains a provider with the same identifier.

There is also a lifecycle problem.

KV model keys currently have no TTL. For NVIDIA and AMD, this is acceptable because the source has a stable provider namespace and the daily job can overwrite the current model list.

For Hugging Face, however, providers can disappear from the current source dataset.

For example:

```text
Day 1:
zai-org exists

Day 2:
zai-org no longer appears in Hugging Face data
```

If the old key remains:

```text
tfi:models:zai-org:latest
```

TFI may continue using stale model data and generate configurations for models/providers that are no longer available.

---

# 1. Refactor Goals

Implement the following architectural changes:

### Goal A — Explicit data source dimension

Introduce:

```text
data_source
```

as a first-class field in the normalized model data.

Definitions:

### `data_source`

The platform/source from which TFI discovered or collected the model availability data.

Examples:

```text
nvidia
amd
huggingface
```

### `provider`

The inference/service provider associated with the model within that data source.

Examples:

```text
nvidia
amd

novita
together
deepinfra
nscale
zai-org
```

For example:

```json
{
  "data_source": "huggingface",
  "provider": "novita",
  "model_id": "openai/gpt-oss-20b"
}
```

means:

> TFI discovered this model through Hugging Face, and the model is provided through Novita.

---

# 2. New KV Namespace

The current model key:

```text
tfi:models:${provider}:latest
```

MUST be replaced with:

```text
tfi:models:${data_source}:${provider}:latest
```

Examples:

```text
tfi:models:nvidia:nvidia:latest

tfi:models:amd:amd:latest

tfi:models:huggingface:novita:latest

tfi:models:huggingface:together:latest

tfi:models:huggingface:deepinfra:latest

tfi:models:huggingface:zai-org:latest
```

This makes `(data_source, provider)` the model catalog namespace.

Do not retain the old key format as an active source of truth.

---

# 3. Provider Manifest

Introduce a new KV key:

```text
tfi:providers:${data_source}:latest
```

This key represents the currently active provider set for a data source.

Examples:

```text
tfi:providers:nvidia:latest
tfi:providers:amd:latest
tfi:providers:huggingface:latest
```

For Hugging Face, the manifest may contain:

```json
{
  "data_source": "huggingface",
  "providers": [
    "novita",
    "together",
    "deepinfra",
    "nscale"
  ]
}
```

For NVIDIA:

```json
{
  "data_source": "nvidia",
  "providers": [
    "nvidia"
  ]
}
```

For AMD:

```json
{
  "data_source": "amd",
  "providers": [
    "amd"
  ]
}
```

Keep the provider manifest minimal for now.

Do not over-engineer it with provider metadata unless the existing data model already requires it.

---

# 4. Provider Manifest Invariant

Establish the following invariant:

> Every active `tfi:models:{data_source}:{provider}:latest` key MUST have its provider represented in `tfi:providers:{data_source}:latest`.

Therefore:

```text
provider ∉ tfi:providers:huggingface:latest
```

means:

```text
tfi:models:huggingface:{provider}:latest
```

must not remain as an active model catalog.

This invariant is more important than TTL.

---

# 5. Do Not Use TTL as the Primary Lifecycle Mechanism

Do NOT solve stale providers primarily through TTL.

Provider lifecycle must be explicitly reconciled from the latest source snapshot.

Correct behavior:

```text
provider disappears from source
        ↓
provider appears in removed set
        ↓
delete its model KV key
```

TTL may be considered a future safety mechanism, but it must not replace explicit reconciliation.

---

# 6. Pipeline Architecture

Replace the current conceptual:

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

model with:

```text
fetch
→ parse
→ normalize
→ validate
→ deduplicate
→ snapshot
→ diff
→ reconcile
→ publish
→ summarize
→ notify
```

The important architectural change is:

```text
store
```

is no longer the primary semantic operation.

It should be replaced by:

```text
snapshot
→ diff
→ reconcile
→ publish
```

The pipeline should remain orchestration-oriented.

Do not put business logic directly into the top-level pipeline.

---

# 7. Snapshot Stage

The `snapshot` stage builds the desired state from the latest normalized source data.

Its responsibility is to produce a deterministic representation of the desired state.

Conceptually:

```text
normalized models
        ↓
group by (data_source, provider)
        ↓
desired provider manifest
        ↓
desired provider model catalogs
        ↓
DesiredState
```

The snapshot should contain enough information to determine:

* active providers
* model list for each `(data_source, provider)`
* generated metadata required by the existing storage schema

Conceptual structure:

```python
DesiredState(
    data_source="huggingface",

    providers={
        "novita": [...],
        "together": [...],
        "deepinfra": [...]
    }
)
```

The exact implementation should follow the existing project's schema conventions.

Do not introduce unnecessary abstractions if the existing architecture has an appropriate model.

---

# 8. Diff Stage

The `diff` stage compares:

```text
current published state
```

against:

```text
desired snapshot
```

For each `data_source`, determine:

```text
added providers
updated providers
removed providers
```

For example:

```text
Current:

novita
together
zai-org

Desired:

novita
together
deepinfra
```

Diff:

```text
added:
  deepinfra

updated:
  novita
  together

removed:
  zai-org
```

The diff should be deterministic and idempotent.

Do not infer provider removal from model-level differences alone.

Provider membership must be determined from the provider manifest / desired provider set.

---

# 9. Reconcile Stage

The `reconcile` stage converts the diff into an explicit reconciliation plan.

Conceptually:

```python
ReconciliationPlan(
    data_source="huggingface",

    added_providers=[
        "deepinfra"
    ],

    updated_providers=[
        "novita",
        "together"
    ],

    removed_providers=[
        "zai-org"
    ]
)
```

The reconciliation plan should define:

### Added provider

Create:

```text
tfi:models:{data_source}:{provider}:latest
```

### Updated provider

Replace/update:

```text
tfi:models:{data_source}:{provider}:latest
```

### Removed provider

Delete:

```text
tfi:models:{data_source}:{provider}:latest
```

Do not leave stale provider model keys behind.

---

# 10. Publish Stage

The `publish` stage applies the reconciliation plan to Cloudflare KV.

The preferred logical order is:

```text
1. write/update model keys
2. delete stale provider model keys
3. publish provider manifest LAST
```

The provider manifest acts as the discovery index.

Therefore it should be published only after the corresponding model keys have been reconciled as far as the KV backend allows.

Example:

```text
Current:

providers:huggingface
=
novita
together
zai-org

Desired:

novita
together
deepinfra
```

Publish sequence:

```text
1. PUT models:huggingface:novita
2. PUT models:huggingface:together
3. PUT models:huggingface:deepinfra
4. DELETE models:huggingface:zai-org
5. PUT providers:huggingface
```

This reduces the window in which consumers can discover a provider whose model catalog has not yet been published.

---

# 11. Cloudflare KV Consistency

Cloudflare KV is not a transactional database.

Do not attempt to implement fake multi-key transactions.

Instead, design the publisher to be:

* deterministic
* idempotent
* retryable
* safe to run multiple times

If a workflow fails halfway through, a subsequent run must converge the KV state to the desired snapshot.

The desired state must remain the authoritative source for reconciliation.

---

# 12. Idempotency

Running the same snapshot twice must produce the same final KV state.

For example:

```text
snapshot A
→ diff
→ reconcile
→ publish
```

followed by:

```text
snapshot A
→ diff
→ reconcile
→ publish
```

must not produce additional side effects beyond unnecessary identical writes, and should ideally detect unchanged provider catalogs.

Do not make update logic dependent on execution order or mutable in-memory state from previous runs.

---

# 13. Provider-Level Comparison

Provider comparison must happen at:

```text
(data_source, provider)
```

not at:

```text
provider
```

This is important for future extensibility.

For example, if both:

```text
huggingface → together
openrouter  → together
```

exist, they must remain independent:

```text
tfi:models:huggingface:together:latest

tfi:models:openrouter:together:latest
```

Never merge these datasets merely because the provider identifier is the same.

---

# 14. Data Model Changes

Update the normalized model schema to include:

```text
data_source
provider
```

where appropriate.

Ensure that every source adapter explicitly sets `data_source`.

Examples:

### NVIDIA

```json
{
  "data_source": "nvidia",
  "provider": "nvidia"
}
```

### AMD

```json
{
  "data_source": "amd",
  "provider": "amd"
}
```

### Hugging Face

```json
{
  "data_source": "huggingface",
  "provider": "novita"
}
```

Do not derive `data_source` from `provider` after normalization.

The source adapter should establish the source identity explicitly.

---

# 15. Hugging Face Specific Requirements

Treat Hugging Face as:

```text
data_source = huggingface
```

and its inference providers as:

```text
provider = <inference provider>
```

Examples:

```text
huggingface / novita
huggingface / together
huggingface / deepinfra
huggingface / nscale
huggingface / zai-org
```

Do not treat Hugging Face itself as the provider for these records.

The source adapter must preserve the provider information exposed by the Hugging Face source.

Do not hard-code a fixed provider list.

The provider set must be derived from the latest fetched data.

---

# 16. NVIDIA and AMD

NVIDIA and AMD should use the same generic data model even though their source/provider relationship is currently one-to-one.

NVIDIA:

```text
data_source = nvidia
provider = nvidia
```

AMD:

```text
data_source = amd
provider = amd
```

Do not create a special storage path for NVIDIA or AMD.

All sources should flow through the same:

```text
snapshot
→ diff
→ reconcile
→ publish
```

mechanism.

---

# 17. Backward Compatibility

The old key format:

```text
tfi:models:${provider}:latest
```

must be considered deprecated.

Determine how the current repository handles consumers of the old key.

If the current application directly reads the old keys, update those consumers to use:

```text
tfi:providers:{data_source}:latest
```

followed by:

```text
tfi:models:{data_source}:{provider}:latest
```

Do not silently maintain two competing sources of truth unless a temporary migration mechanism is genuinely required.

If a migration is necessary, document:

* migration period
* source of truth
* removal condition
* compatibility behavior

Do not indefinitely dual-write.

---

# 18. Consumer Access Pattern

The intended data access pattern should become:

```text
1. Read data-source provider manifest
2. Enumerate active providers
3. Read model catalog for each provider
```

For example:

```text
GET/READ

tfi:providers:huggingface:latest

        ↓

[
  "novita",
  "together",
  "deepinfra"
]

        ↓

tfi:models:huggingface:novita:latest
tfi:models:huggingface:together:latest
tfi:models:huggingface:deepinfra:latest
```

This creates an explicit two-level catalog:

```text
Data Source
    ↓
Provider
    ↓
Models
```

---

# 19. Storage Layer

Refactor the Cloudflare KV storage implementation so that storage operations understand the new key model.

Prefer semantic methods such as:

```python
get_provider_manifest(data_source)
put_provider_manifest(data_source, manifest)

get_provider_models(data_source, provider)
put_provider_models(data_source, provider, models)

delete_provider_models(data_source, provider)
```

rather than spreading raw key construction throughout the pipeline.

Centralize key generation:

```python
provider_manifest_key(data_source)
provider_models_key(data_source, provider)
```

This prevents future namespace inconsistencies.

---

# 20. Error Handling

Provider deletion is a meaningful destructive operation.

Before deleting:

```text
tfi:models:{data_source}:{provider}:latest
```

ensure that the provider is genuinely absent from the desired snapshot.

Do not delete a provider because:

* parsing failed
* a single API request timed out
* a source returned an empty response unexpectedly
* one page of pagination failed
* an upstream API temporarily returned incomplete data

The existing validation stage must protect snapshot generation from incomplete source data.

If the source fetch is incomplete or invalid, prefer:

```text
fail the snapshot
```

over:

```text
generate a snapshot that removes many existing providers
```

This is especially important because `diff` can generate destructive deletes.

---

# 21. Empty Snapshot Safety

Be especially careful with:

```text
desired providers = []
```

An empty result may mean:

1. the source genuinely has zero providers
2. the source temporarily failed
3. pagination failed
4. parsing broke
5. upstream changed its response format
6. authentication/rate limiting occurred

Do not automatically delete all existing provider keys merely because the new fetch returned an empty dataset.

Use the existing validation/source-health mechanisms to distinguish valid empty snapshots from broken fetches.

If the current repository does not have sufficient protection for this, add the smallest appropriate validation guard.

---

# 22. Tests

Add/update tests for the new model.

At minimum test:

### NVIDIA

```text
nvidia
  ↓
provider = nvidia
  ↓
tfi:models:nvidia:nvidia:latest
```

### AMD

```text
amd
  ↓
provider = amd
  ↓
tfi:models:amd:amd:latest
```

### Hugging Face multiple providers

Given:

```text
novita
together
zai-org
```

expect:

```text
tfi:models:huggingface:novita:latest
tfi:models:huggingface:together:latest
tfi:models:huggingface:zai-org:latest
```

and:

```text
tfi:providers:huggingface:latest
```

contains all three.

### Provider removal

Current:

```text
novita
together
zai-org
```

Desired:

```text
novita
together
```

Expect:

```text
DELETE tfi:models:huggingface:zai-org:latest
```

and final provider manifest:

```text
novita
together
```

### Provider addition

Current:

```text
novita
together
```

Desired:

```text
novita
together
deepinfra
```

Expect creation of:

```text
tfi:models:huggingface:deepinfra:latest
```

### Provider update

If the provider remains but its model set changes:

```text
novita
```

must result in an update to:

```text
tfi:models:huggingface:novita:latest
```

### Same provider, different data source

Given:

```text
huggingface / together
openrouter / together
```

they must produce two independent model keys.

### Idempotency

Applying the same desired snapshot twice must converge to the same state.

### Empty/incomplete source

An invalid or incomplete source response must not trigger destructive deletion of all provider keys.

---

# 23. Pipeline Tests

Test the semantic stages independently where the existing architecture permits:

```text
snapshot()
diff()
reconcile()
publish()
```

The top-level pipeline should primarily compose these stages.

Avoid putting complex branching logic directly into `pipeline.py`.

The intended architecture is conceptually:

```python
fetch
  .then(parse)
  .then(normalize)
  .then(validate)
  .then(deduplicate)
  .then(snapshot)
  .then(diff)
  .then(reconcile)
  .then(publish)
  .then(summarize)
  .then(notify)
```

Use the repository's existing pipeline conventions rather than introducing a new framework solely for this refactor.

---

# 24. Logging and Summary

The summary stage should expose reconciliation information.

For each data source, report something like:

```text
Hugging Face

providers:
  added: 1
  updated: 12
  removed: 1

models:
  added: ...
  updated: ...
  removed: ...
```

The exact reporting format should follow the existing notification mechanism.

The important requirement is that provider lifecycle changes are visible.

A provider deletion such as:

```text
zai-org removed
```

should be observable in the daily pipeline result.

---

# 25. Documentation

Update the relevant data architecture documentation.

Document:

```text
data_source
provider
provider manifest
model catalog
snapshot
diff
reconcile
publish
```

Explicitly document the new KV schema:

```text
tfi:providers:{data_source}:latest

tfi:models:{data_source}:{provider}:latest
```

Also document the invariant:

> Every active provider model key must be represented by the provider manifest of its data source.

---

# 26. Migration Strategy

Before implementation:

1. inspect the current data models
2. inspect all source adapters
3. inspect KV storage
4. inspect pipeline stages
5. inspect consumers of the existing keys
6. inspect tests
7. identify all references to:

```text
tfi:models:
```

Do not modify blindly.

Produce a short implementation assessment before changing code.

Then implement the refactor in the smallest coherent set of changes.

---

# 27. Guardrails

Do NOT:

* introduce TTL as the primary stale-data solution
* keep `provider` as the only KV namespace
* special-case Hugging Face in storage
* create separate storage logic for NVIDIA/AMD
* introduce unnecessary database infrastructure
* replace Cloudflare KV
* redesign unrelated pipeline stages
* redesign the model schema beyond what this refactor requires
* introduce unrelated provider metadata
* build a generic event-sourcing system
* over-engineer transaction semantics that KV cannot provide
* silently dual-write old and new key formats forever

The purpose of this change is:

```text
correct namespace
+
correct provider lifecycle
+
deterministic reconciliation
+
safe publication
```

---

# 28. Expected End State

The final data architecture should conceptually look like:

```text
                    ┌──────────────────┐
                    │   Data Sources   │
                    └────────┬─────────┘
                             │
            ┌────────────────┼────────────────┐
            ↓                ↓                ↓
         NVIDIA             AMD          Hugging Face
            │                │                │
            ↓                ↓                ↓
         Provider          Provider        Providers
         nvidia             amd        ┌──────┼──────┐
                                       ↓      ↓      ↓
                                    novita together deepinfra
                                       │      │      │
                                       ↓      ↓      ↓
                                     Models Models Models
```

KV:

```text
tfi:providers:nvidia:latest
tfi:models:nvidia:nvidia:latest

tfi:providers:amd:latest
tfi:models:amd:amd:latest

tfi:providers:huggingface:latest
tfi:models:huggingface:novita:latest
tfi:models:huggingface:together:latest
tfi:models:huggingface:deepinfra:latest
```

Pipeline:

```text
fetch
  ↓
parse
  ↓
normalize
  ↓
validate
  ↓
deduplicate
  ↓
snapshot
  ↓
diff
  ↓
reconcile
  ↓
publish
  ↓
summarize
  ↓
notify
```

---

# 29. Definition of Done

The implementation is complete when:

* [ ] `data_source` exists as an explicit normalized field
* [ ] `provider` has a clearly defined source-local meaning
* [ ] model KV keys use `tfi:models:{data_source}:{provider}:latest`
* [ ] provider manifests use `tfi:providers:{data_source}:latest`
* [ ] Hugging Face correctly separates `data_source=huggingface` from inference `provider`
* [ ] NVIDIA uses `nvidia/nvidia`
* [ ] AMD uses `amd/amd`
* [ ] provider lifecycle is derived from the latest source snapshot
* [ ] stale provider model keys are explicitly deleted
* [ ] TTL is not used as the primary lifecycle mechanism
* [ ] snapshot stage produces deterministic desired state
* [ ] diff stage identifies added/updated/removed providers
* [ ] reconcile stage creates an explicit reconciliation plan
* [ ] publish stage applies model changes before publishing the provider manifest
* [ ] KV key construction is centralized
* [ ] operations are idempotent
* [ ] incomplete source data cannot accidentally delete the entire provider catalog
* [ ] consumers no longer depend on the old provider-only key
* [ ] tests cover provider addition/removal/update
* [ ] tests cover same provider across different data sources
* [ ] tests cover idempotency
* [ ] tests cover empty/incomplete source safety
* [ ] pipeline summary exposes provider changes
* [ ] architecture documentation is updated
* [ ] existing unrelated behavior remains unchanged
* [ ] all tests, type checks, linting, and CI checks pass

---

# 30. Implementation Philosophy

Do not treat this as a Hugging Face-specific patch.

Treat it as a normalization of the TFI data model:

```text
Data Source
    ↓
Provider
    ↓
Model Catalog
```

and a transition from:

```text
fetch → store
```

to:

```text
fetch → desired state → diff → reconcile → publish
```

The resulting implementation should make future data sources such as:

```text
OpenRouter
models.dev
other provider aggregators
```

possible without another KV namespace redesign.

The desired end state is a small, explicit, deterministic data reconciliation system rather than a collection of source-specific storage hacks.

