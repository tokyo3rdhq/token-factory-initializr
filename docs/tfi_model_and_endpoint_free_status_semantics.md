# Refactor Model and Endpoint Free Status Semantics

## Objective

Refactor the Token Factory Initializr (TFI) model catalog so that `free` describes the access conditions of a specific model-provider endpoint, rather than an intrinsic property of a model.

Repository: https://github.com/tokyo3rdhq/token-factory-initializr

Production site: https://start.magi.website

The implementation must align the internal schema, aggregation pipeline, public API, `/browse` UI, endpoint selection, configuration generation, tests, and documentation.

**Core decision: `ModelEndpoint.free` is the authoritative field. A model may have multiple endpoints with different free/paid statuses. The model-level API representation must not expose a misleading model-level `free` boolean.**

Do not implement this as a superficial JSON field move. Inspect the actual repository and trace the complete data flow before changing code.

---

## Strategic Architecture Requirement: All Models, Not Free Models Only

TFI is evolving from a free-model discovery tool into a general AI Model Catalog and endpoint configuration tool.

The current catalog may primarily contain free models, but the underlying architecture must support future ingestion of all model types, including:

* Free models.
* Paid models.
* Models with both free and paid provider endpoints.
* Models with unknown or incomplete pricing information.
* Models that are known to exist but do not yet have a verified, usable endpoint.

This requirement is architectural guidance for the current `free` refactor. It does NOT authorize a broad product redesign, adding new data sources, or implementing a complete paid-model ingestion pipeline in this task.

### A. Keep model identity independent of pricing

A canonical `Model` represents model identity and model-level metadata. Its existence must not depend on whether the model is free, paid, or has known pricing.

Do not use `Model.free` as a canonical attribute.

Do not require every model to have a free endpoint or even a currently usable endpoint.

`ModelEndpoint.free` describes the free status of a specific provider/model access option. Pricing, usage limits, availability, and other access conditions must remain associated with the appropriate endpoint or access-offer representation.

### B. Treat pricing as first-class endpoint metadata

Ensure the existing schema and API can distinguish:

* Known zero-cost access.
* Known non-zero pricing.
* Unknown or unavailable pricing information.

Do not infer that an endpoint is free merely because pricing is missing. Do not infer that it is paid merely because its free status is unknown.

Preserve existing pricing conventions where practical. Do not invent a comprehensive billing schema or add unrelated pricing fields without evidence that the current data sources require them.

If a source only supplies model discovery information, allow the model to exist without fabricating pricing or endpoint records.

### C. Do not encode a free-only assumption into shared layers

Audit schema validators, normalization, deduplication, reconciliation, publication, storage, API serialization, frontend predicates, and configuration generation for assumptions that all models must be free.

Remove or isolate those assumptions where required for correctness.

In particular:

* Catalog inclusion must not depend on `free === true`.
* Deduplication must preserve distinct provider offers and their different access conditions.
* A model with free and paid endpoints must retain both.
* A model with unknown pricing must not be silently classified as free or paid.
* Endpoint usability must be represented separately from price classification.
* Configuration generation must continue to use a valid, explicitly selected or otherwise legitimately resolved endpoint; do not introduce new automatic provider-routing behavior in this task.

### D. Keep product filters separate from canonical data

The canonical model and endpoint schemas must not be designed around a particular browse filter.

The current free-model browsing experience can remain intact, but future catalog filters should be able to distinguish:

* All models.
* Models with at least one confirmed-free endpoint.
* Models with paid endpoint options.
* Models whose pricing or free status is unknown.
* Models with no verified usable endpoint, if this state is represented by the existing schema.

Do not implement every future filter unless required by the current API or frontend refactor. Preserve existing UI behavior while ensuring the new schema does not prevent these filters from being added later.

### E. Maintain backward compatibility and limit scope

The purpose of this task is to make the data model and API semantics future-proof, not to launch the all-model catalog.

Do not add new providers, data sources, pricing ingestion pipelines, billing integrations, or new catalog sections as part of this refactor.

Do not remove current free-model functionality. Instead, implement free status as one property of an endpoint in a general-purpose catalog.

### F. Additional acceptance criteria

In addition to the existing tests, verify that:

1. A paid endpoint can be represented without being incorrectly excluded from the canonical catalog.
2. A model with both free and paid endpoints preserves both endpoint records.
3. A model with unknown pricing is not silently assigned a free or paid classification.
4. A model can exist without an endpoint if the existing canonical data model permits this.
5. Shared schema, serialization, filtering, and aggregation logic does not require `free === true` for catalog inclusion.
6. Existing free-model browsing and configuration generation continue to work.

Use synthetic fixtures for these cases when real catalog data does not currently contain them. Do not add fabricated records to production data.

## 1. Audit the current implementation first

Inspect the repository to identify the actual implementation of:

* `Model` and `ModelEndpoint` TypeScript types/interfaces.
* Python data schemas, if they mirror the TypeScript types.
* Model normalization, enrichment, deduplication, and aggregation.
* Provider and data-source identity handling.
* The storage representation and serialization format.
* `GET /api/v1/models`.
* `GET /api/v1/models/{id}`.
* `GET /api/v1/providers` and `GET /api/v1/endpoints`, if implemented.
* The `/browse` list, filters, selection state, and selected-model representation.
* The configuration generation flow for LiteLLM, NewAPI, and Bifrost.
* Public documentation, including `llms.txt`, `agents.md`, and API documentation.
* Existing tests, fixtures, CI workflows, and validation commands.

Establish whether `free` currently exists at model level, endpoint level, both, or neither. Trace how its current value is calculated and consumed.

Before making changes, produce a concise internal implementation plan identifying all affected files and compatibility risks. Then proceed with implementation; do not stop after the audit unless a genuine blocker prevents safe progress.

Do not assume routes, schemas, data sources, or UI behaviors exist without verifying them in the repository.

## 2. Define the data semantics

Preserve these distinctions:

* **Model**: the canonical model identity and model-level metadata.
* **Provider**: the inference provider or operator that offers access.
* **Endpoint**: a specific model-provider access option, including provider-specific model ID and access conditions.
* **Data source**: where TFI discovered or collected the information.

Do not confuse `data_source` with `provider`.

### 2.1 Model-level fields

Model-level fields may include:

* Canonical model ID.
* Display name.
* Model family or ownership metadata, where available.
* Capabilities.
* Context length or other model metadata, subject to the existing schema.

Remove the model-level `free` field from the canonical model schema and public model representation if the current implementation has one.

Do not arbitrarily relocate unrelated fields. Preserve the existing schema unless a change is required by the new semantics.

### 2.2 Endpoint-level fields

`ModelEndpoint` should carry endpoint-specific access information, including existing fields where supported:

* Stable endpoint ID.
* Canonical model reference or model ID.
* Provider ID.
* Provider-specific `model_id`.
* `free`.
* `pricing`.
* `limits`.
* `status`.
* Endpoint-specific capability or context overrides, if the existing schema supports them.

Retain existing naming conventions unless a concrete inconsistency requires a change.

`ModelEndpoint.free` is the single source of truth for the endpoint's free status.

### 2.3 Unknown free status

Distinguish confirmed paid access from unknown pricing information.

If the existing data sources support uncertainty, prefer:

* `true`: confirmed free under the data source's stated conditions.
* `false`: confirmed paid.
* `null`: unknown or unverified.

Before introducing nullable values, audit the current data pipeline, schema validators, TypeScript consumers, and API contract.

If nullability is safe and supported, implement it consistently across the pipeline, storage, API, and frontend. If a boolean-only contract must be preserved temporarily, do not silently treat unknown as free. Document the limitation and propose an explicit migration rather than inventing certainty.

Do not infer free status from model names, provider names, or missing pricing fields.

Free status is not a guarantee of unlimited usage. Preserve available quota, rate-limit, and credit information separately.

## 3. Public API contract

First verify the current API contract and its consumers. Implement the following logical contract while preserving unrelated fields and established conventions.

### 3.1 `GET /api/v1/models`

The canonical model catalog should represent one model with its available endpoints.

Illustrative target shape:

```json
{
  "object": "list",
  "data": [
    {
      "id": "Qwen/Qwen3-Next-80B-A3B-Instruct",
      "object": "model",
      "name": "Qwen3-Next-80B-A3B-Instruct",
      "owned_by": "Qwen",
      "capabilities": ["chat", "tools"],
      "context_length": 131072,
      "endpoints": [
        {
          "id": "together/Qwen/Qwen3-Next-80B-A3B-Instruct",
          "provider": "together",
          "model_id": "Qwen/Qwen3-Next-80B-A3B-Instruct",
          "free": false,
          "pricing": {
            "input": 0.2,
            "output": 0.6,
            "unit": "USD/1M tokens"
          },
          "limits": {}
        },
        {
          "id": "novita/Qwen/Qwen3-Next-80B-A3B-Instruct",
          "provider": "novita",
          "model_id": "Qwen/Qwen3-Next-80B-A3B-Instruct",
          "free": true,
          "pricing": {
            "input": 0,
            "output": 0,
            "unit": "USD/1M tokens"
          },
          "limits": {}
        }
      ]
    }
  ]
}
```

This is a structural example only. Do not copy its sample pricing, IDs, capabilities, or free status into production data.

Requirements:

* Do not expose a model-level `free` boolean in the canonical model representation.
* Represent endpoint-specific free status under `endpoints[].free`.
* Preserve existing response envelope, pagination, filter, and error conventions where applicable.
* Preserve model identity separately from provider-specific `model_id`.
* Keep endpoint IDs stable and deterministic under existing identity rules.
* Avoid returning duplicated or inconsistent endpoint data.
* Do not invent missing providers, endpoint URLs, pricing, or limits.

If `/api/v1/models` is currently used by OpenAI-compatible clients and its established contract cannot safely accommodate nested endpoints, preserve the compatibility contract and introduce or retain a separate canonical TFI catalog representation. Document the separation clearly.

Do not accidentally claim that a nested TFI catalog response is fully OpenAI Models API compatible.

### 3.2 `GET /api/v1/models/{id}`

If implemented, ensure the detail endpoint uses the same model/endpoint semantics as the list endpoint.

* Model-level `free` must not contradict or summarize endpoint-level values.
* Endpoint-specific free status must be exposed consistently.
* Preserve current 404 and invalid-ID behavior.

### 3.3 `GET /api/v1/endpoints`

If this route exists, it should expose one record per actual endpoint, with its own `free`, `pricing`, `limits`, provider, model reference, and status.

If it does not exist, do not automatically expand the scope to add it unless the existing API architecture or frontend genuinely requires it. Document the gap and recommend a follow-up if needed.

### 3.4 Filters

Inspect existing query parameters before modifying them.

If the current API supports `free` or an equivalent filter, redefine its semantics explicitly:

* `free=true`: return endpoints confirmed free, or models that have at least one confirmed-free endpoint, according to the resource represented by the route.
* For endpoint-level results, `free=true` must match only endpoints whose own `free` value is `true`.
* For model-level results, a free-model filter may include a model if at least one of its endpoints is confirmed free, but the response must still show the individual endpoint statuses.
* Unknown values must not be silently included as confirmed free.
* Preserve existing filter behavior unrelated to free status.

Do not introduce query parameters that the existing API does not need merely for symmetry.

## 4. Data pipeline and migration

Update all affected stages of the actual pipeline, including schema validation, normalization, reconciliation, deduplication, publication, and storage, as applicable.

Requirements:

1. Preserve endpoint-level free status from authoritative source data.
2. Do not derive one endpoint's free status from another endpoint belonging to the same model.
3. Do not collapse endpoints with different providers or access conditions into a single record.
4. Ensure deduplication preserves genuinely distinct provider/model access combinations.
5. Remove any aggregation logic that incorrectly copies a single endpoint's `free` value onto the canonical model.
6. Validate the published catalog against the updated schema.
7. Keep the pipeline deterministic and idempotent.
8. Ensure storage keys, serialization, and cached data remain compatible with the updated representation.

If historical stored records need migration or a fresh rebuild, implement the smallest safe mechanism supported by the repository. Do not fabricate historical endpoint pricing or free status.

When existing records only contain model-level `free`, do not blindly copy that value to every endpoint unless source lineage proves it applies to that endpoint. Prefer re-enrichment from authoritative source data. Where that is impossible, preserve the uncertainty or follow the documented compatibility policy.

Do not rewrite unrelated data pipeline stages.

## 5. `/browse` frontend behavior

The UI must treat a model and its endpoints as distinct entities.

### 5.1 Model list

Keep the existing compact, model-first browsing experience.

* Display model identity and capabilities as before.
* Do not present a model-level `Free` badge based on an arbitrary endpoint.
* If the existing design benefits from a model-level summary, show a derived label such as `Free option available` only when at least one endpoint has `free === true`.
* Never interpret an unknown status as free.
* Avoid suggesting that all endpoints for a model are free when only one is free.

Do not redesign the entire `/browse` page.

### 5.2 Endpoint details and selection

Where users can inspect or select providers/endpoints:

* Display the free/paid status for the specific endpoint.
* Display provider-specific pricing and limits when available.
* Ensure endpoint selection retains the selected provider and provider-specific model ID.
* Keep existing selection behavior, bulk selection, filters, and generated configuration workflow intact unless changes are required to support the new contract.

If the current UI selects only canonical models and resolves endpoints later, trace that behavior carefully. Do not silently change routing or provider-selection policy as part of this refactor.

### 5.3 Free filters

Audit the existing free filter.

* If it means “models with at least one confirmed-free endpoint,” preserve that user-facing meaning and implement it as a derived predicate.
* If it means “only free endpoints,” apply it to endpoint choices, not just model identity.
* Update labels and help text if the old wording becomes misleading.
* Ensure the filter, visible-row selection, select-all-visible, and selected-item counts remain consistent.

Add tests for models with mixed endpoint statuses.

## 6. Configuration generation

Inspect the complete path from selected model to generated LiteLLM, NewAPI, and Bifrost configuration.

Requirements:

* Keep provider routing and provider-specific model IDs intact.
* Do not select a paid endpoint merely because the canonical model previously had `free: true`.
* Do not claim the generated configuration is free solely because the model has one free endpoint.
* If endpoint selection already exists, ensure it carries the selected endpoint's identity and associated metadata through generation.
* If endpoint selection does not exist, preserve the current behavior and document the limitation. Do not introduce a new automatic provider-routing algorithm without explicit requirements.
* Do not place TFI's internal `free` metadata into downstream gateway configuration unless that gateway's schema explicitly supports it.

The purpose is accurate catalog semantics, not a redesign of gateway configuration generation.

## 7. Backward compatibility and rollout

Before removing any public field, identify actual consumers:

* Frontend components.
* Agent instructions and examples.
* API consumers and integration tests.
* Generated configuration logic.
* Public documentation and sample responses.

Choose the smallest safe rollout:

* If the API is not yet a stable public contract, update it consistently and remove the model-level `free` field.
* If the existing contract has known consumers, consider a documented deprecation period or a versioned canonical endpoint.
* Do not keep contradictory model-level and endpoint-level `free` values indefinitely.
* Do not add a versioning framework solely for this change if the project does not already use one.

Update all internal callers in the same change where feasible.

## 8. Documentation

Update the documentation that describes the model schema, endpoint schema, API filters, and Agent usage.

At minimum:

* Explain that `free` is endpoint-specific.
* Explain the difference between a model and a provider endpoint.
* Explain how a model with multiple endpoints can have mixed free/paid access.
* Clarify that free does not imply unlimited access or guaranteed availability.
* Document unknown-status semantics if supported.
* Update `llms.txt`, `agents.md`, API documentation, schema examples, and fixtures only where they contain affected information.
* Remove stale examples that treat `model.free` as authoritative.

Do not claim that a route, field, or filter exists unless it is actually implemented.

## 9. Tests and acceptance criteria

Add or update tests for at least these cases:

1. One model with two endpoints, one free and one paid.
2. A model whose endpoints are all free.
3. A model whose endpoints are all paid.
4. A model with unknown free status, if nullability is supported.
5. A model with no endpoints.
6. A provider/model ID mismatch or normalization edge case, using valid repository fixtures.
7. Deduplication preserves endpoints with different providers and pricing.
8. Model-list serialization does not expose a misleading model-level `free` field.
9. Endpoint serialization returns the correct endpoint-specific `free` value.
10. Free filters behave correctly for both model-level and endpoint-level resources.
11. `/browse` accurately represents mixed endpoint statuses.
12. Bulk selection and configuration generation remain functional.
13. Existing API filters and unrelated fields retain their established behavior.
14. Existing fixtures and generated catalog data pass validation.

Run the actual repository checks:

* Relevant unit/integration tests.
* Schema validation and pipeline tests.
* Type checking.
* Linting, if configured.
* Production build.

Do not claim that a test passed unless it was executed. Report failures honestly.

## 10. Scope constraints

* Preserve the existing Cloudflare Pages/Functions, React, TypeScript, Vite, KV, and Python architecture.
* Reuse existing schema conventions and helpers.
* Avoid unnecessary dependencies and infrastructure changes.
* Do not change the meanings of `provider`, `data_source`, or canonical model identity.
* Do not modify unrelated model ranking, scoring, or enrichment logic.
* Do not introduce an automatic free-provider selection algorithm.
* Do not invent data or infer pricing from missing values.
* Keep UI changes consistent with `@tokyo3rdhq/magi-design-system`.
* Avoid unrelated visual redesigns.

## 11. Final implementation report

When complete, provide:

1. A concise description of the old and new data semantics.
2. The final `Model` and `ModelEndpoint` field changes.
3. The actual public API response changes and any compatibility decisions.
4. The changes made to pipeline, storage, and frontend.
5. How unknown free status is represented or why it remains constrained.
6. How the free filter and endpoint selection now behave.
7. Documentation updated.
8. Tests and checks actually executed, including results.
9. Any migration requirements, compatibility risks, or remaining gaps.

**Definition of done:** Endpoint-level free status is authoritative and consistent throughout the pipeline, public API, `/browse`, and downstream selection/generation flows. No code path silently treats a model's single endpoint status as the truth for every provider serving that model.

## 12. Legacy `free` compatibility rule (§3.2 of tfi_model_endpoint_support_paid_model.md)

A canonical `pricing_status` field (`"free" | "paid" | "unknown"`) is the endpoint-scoped source of truth for access classification:

* `"free"` — confirmed free under documented source conditions.
* `"paid"` — confirmed to require payment, with pricing evidence where available.
* `"unknown"` — insufficient evidence to classify as free or paid.

The legacy Boolean `free` field is retained for backward compatibility and is derived deterministically:

> `free: true` **only when** `pricing_status === "free"`; otherwise `false` for legacy clients.

Missing pricing ⇒ `unknown` (kept, never dropped). Pricing must never be inferred free from absence, nor paid from absence. New consumers must use `pricing_status` to distinguish paid from unknown.

Implementation locations:
* `data/models/schema.py` — `ModelEndpoint.pricing_status: Optional[Literal["free","paid","unknown"]]`; `legacy_free_compatible()` helper.
* `data/process/normalize.py` — `endpoint_to_dict()` applies `legacy_free_compatible()` at KV serialization.
* `web/functions/lib/projection.ts` — `toPublicModelEndpoint()` sets `free = pricing_status === "free"` and `pricing_status ?? "unknown"`.
* `web/src/types.ts` / `web/functions/lib/kv.ts` — TS mirror of the canonical field.
