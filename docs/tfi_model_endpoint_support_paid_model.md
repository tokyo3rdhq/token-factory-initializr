# TFI ModelEndpoint Evolution: Support Free and Paid Model Catalogs

## Role

You are a senior full-stack engineer responsible for evolving Token Factory Initializr (TFI), an existing production-oriented model catalog and configuration generation service.

Repository: https://github.com/tokyo3rdhq/token-factory-initializr

Your task is to implement a backward-compatible evolution of TFI's current `ModelEndpoint` data model and ingestion pipeline so that TFI can support a rapidly expanding catalog of free and paid models, potentially 1,000+ models and multiple endpoints per model.

This is an implementation task, not a proposal-only task. Inspect the actual repository, implement the changes, run relevant tests, and report the results.

## 1. Product and engineering objectives

TFI currently focuses on discovering free models and generating configurations for LiteLLM, NewAPI, Bifrost, and Magpie.

The next phase must support:

- Free, paid, and pricing-unknown endpoints.
- Multiple endpoints for the same logical model, potentially with different prices, limits, capabilities, and availability.
- Consistent pricing and access semantics across heterogeneous data sources.
- Model discovery and filtering without requiring the entire catalog to be loaded into the browser.
- Reliable ingestion, reconciliation, and publication of a growing catalog.
- Backward compatibility for existing consumers and configuration generators.

The objective is to evolve the existing architecture rather than rewrite the product.

Do not introduce an independent search service, database, queue, or external dependency without demonstrating that the current architecture cannot reasonably meet the requirements.

## 2. Audit the actual implementation first

Before editing code, inspect the relevant implementation, tests, workflows, and documentation.

Start with these known areas, but search for all additional references:

- `data/models/schema.py`
- `data/process/normalize.py`
- `data/process/free_filter.py` and its callers
- Source-specific fetchers and parsers under `data/`
- Snapshot, diff, reconcile, publish, and manifest logic
- `web/functions/lib/kv.ts`
- `web/functions/lib/projection.ts`
- `web/functions/lib/dataSources.ts`
- `web/functions/lib/generators/*.ts`
- `/api/v1/models`, `/api/v1/models/{id}`, `/api/v1/providers`, `/api/v1/endpoints`
- Browse/search UI and model-detail components
- CI and scheduled ingestion workflows
- API schemas, `agents.md`/`llms.txt`, tests, and other documentation

Confirm the current behavior from source code. Do not assume that every field in the current design document is implemented exactly as described.

Produce a concise implementation audit covering:

1. The actual ingestion and publication flow.
2. Where non-free endpoints are currently removed.
3. How `free`, `pricing`, `limits`, `metadata`, and `supported_parameters` are populated.
4. How models and endpoints are deduplicated and identified.
5. How KV keys and manifests are organized.
6. How public API projection and configuration generation consume the existing fields.
7. Which current tests encode free-only assumptions.

Then proceed with implementation. Do not stop after producing the audit unless a genuine blocker requires clarification.

## 3. Define explicit access and pricing semantics

The current canonical `ModelEndpoint` has a required Boolean `free` field and optional `pricing` metadata.

A Boolean alone cannot distinguish a confirmed paid endpoint from an endpoint whose pricing is unknown. Fix this semantic gap without breaking existing clients.

### 3.1 Introduce a canonical pricing/access classification

Define a normalized representation with at least these states:

- `free`: confirmed free under documented source conditions.
- `paid`: confirmed to require payment, with pricing evidence where available.
- `unknown`: insufficient evidence to classify the endpoint as free or paid.

Choose a clear field name, such as `pricing_status`, and use a documented enum/type consistently in Python and TypeScript.

Keep this classification endpoint-scoped.

Do not infer that an endpoint is free because:

- Its price is missing.
- Its price is zero in an incomplete or malformed record.
- The source offers a free tier for other models.
- A model is listed on a free-model website.

Do not infer that an endpoint is paid merely because its pricing metadata is absent.

If a source explicitly marks an endpoint as free but provides no numeric price, preserve the confirmed free classification and represent the missing numeric price as unknown.

If a source reports all applicable token prices as zero, treat that as evidence of zero-priced access only when the source's pricing semantics support that interpretation.

### 3.2 Preserve legacy `free` compatibility

The existing public API exposes endpoint-level `free: boolean`. Existing generators and clients may depend on it.

Retain the field during this migration.

Define and document one deterministic compatibility rule. Prefer `free: true` only when `pricing_status === "free"`; otherwise return `false` for legacy clients.

New consumers must use `pricing_status` when distinguishing paid from unknown.

Do not silently change the meaning or type of the existing `free` field. Search all consumers before finalizing the compatibility rule.

Add tests for free, paid, and unknown endpoints.

### 3.3 Normalize pricing into a documented schema

Audit the current `pricing` formats before designing a replacement. Existing source-specific data may use strings, nested objects, scientific notation, or provider-specific field names.

Define a canonical pricing representation that can express, where available:

- Input token price.
- Output token price.
- Currency and billing unit.
- Cached-input or cache-read pricing when supported.
- Image, audio, or other modality-specific pricing when supported by the source.
- Whether a price is explicitly zero, positive, unavailable, or not applicable.
- Source and observation timestamp, or equivalent provenance references.

Avoid requiring every source to provide every field.

Specify the unit of every numeric value. For example, do not mix price per token with price per million tokens without an explicit unit.

Preserve raw source-specific pricing in the existing opaque metadata or provenance mechanism where useful, but ensure filtering and sorting use normalized values.

Do not invent pricing for sources that do not provide it.

If a full pricing-schema migration would create unnecessary risk, implement an incremental schema with explicit versioning and a compatibility adapter for existing records.

## 4. Evolve the canonical ModelEndpoint

Keep the current separation between data source, provider, model identifier, and endpoint.

Preserve these core invariants:

- `data_source` identifies the catalog/source through which TFI discovered a record.
- `provider` identifies the upstream provider or runtime provider.
- `model_id` retains the provider/source identifier required for the corresponding integration.
- Endpoint-specific properties must not be promoted to the model level without evidence that they are genuinely model-wide.
- Distinct runtime endpoints must remain distinct when their access conditions, pricing, authentication, or limits differ.

Evolve the schema incrementally to support:

- `pricing_status`: `free | paid | unknown`.
- Canonical normalized `pricing`, with documented units.
- Endpoint-level access and quota information.
- Endpoint lifecycle/availability status where reliably observable.
- Explicit freshness timestamps or equivalent existing freshness metadata.
- Provenance for pricing and access classification when supported by the existing provenance system.

Review the scope of existing fields before moving or duplicating them.

In particular:

- `context_length` may be a model characteristic or an endpoint-specific serving limit. Preserve the current field for compatibility and introduce endpoint-specific context data only when source evidence requires it.
- `capabilities` may describe model capabilities; `supported_parameters` describes endpoint/runtime support. Do not conflate them.
- `limits` must retain its existing meaning and should not be mixed with pricing.
- `metadata` remains opaque and provider-specific; new cross-source behavior must rely on normalized fields, not undocumented provider-specific JSON paths.
- `free_until`, where applicable, is endpoint-specific. Preserve its current representation if one exists; otherwise add a documented representation without treating it as universal pricing metadata.

Update both Python and TypeScript types, validators, serializers, fixtures, and relevant documentation.

Do not introduce a second conflicting source of truth for fields already managed by a shared registry or canonical schema.

## 5. Refactor the ingestion pipeline

The current pipeline includes source adapters, normalization, validation, enrichment, deduplication, snapshotting, and publication. Preserve that structure unless the audit identifies a concrete architectural issue.

### 5.1 Remove the free-only catalog assumption

Refactor `free_filter.py` and its callers so that ingestion can retain eligible paid and unknown-pricing endpoints.

Do not simply delete every filter.

Replace the old free-only behavior with explicit catalog eligibility and source-quality rules. The pipeline must still reject malformed records and records that violate required invariants.

If free-only ingestion remains useful for a specific view or API, implement it as a downstream query/filter rather than as the only published catalog.

### 5.2 Make source adapters classification-aware

For each existing source adapter:

- Determine whether the source provides explicit access classification.
- Normalize source pricing into the canonical schema.
- Assign `pricing_status` only when supported by source evidence.
- Preserve unknown pricing when evidence is missing.
- Keep source-specific model identifiers, provider mappings, endpoint mappings, and generator compatibility intact.
- Avoid fabricating prices, free status, limits, or capabilities.

Do not invent support for new data sources as part of this task unless a source is already configured and requires an adapter update.

Add tests for representative source payloads, including missing pricing, explicit free status, positive prices, zero-priced endpoints, and malformed pricing.

### 5.3 Preserve deterministic deduplication and reconciliation

Review the existing endpoint identity rule, currently documented as:

`(data_source, provider, model_id)`

Do not change it casually.

Confirm whether it uniquely identifies each runtime endpoint in actual data. If additional endpoint identity is required, propose and implement the smallest compatible adjustment.

Ensure:

- Identical models from different sources do not lose source attribution.
- Different endpoints for the same model do not have their prices or access states merged.
- Missing data in one ingestion run does not overwrite better existing information without a defined reconciliation rule.
- Temporary upstream failures do not immediately remove valid published records.
- Removed or deprecated endpoints can be distinguished from transiently missing records.
- Repeated ingestion of the same source data produces deterministic results.

Retain field-level provenance where already supported.

## 6. Storage and publication

The current system uses Cloudflare KV for canonical snapshots and a manifest.

Do not automatically replace KV with D1 merely because the catalog will contain 1,000+ models.

First inspect the actual record size, KV key layout, publication workflow, query patterns, pagination requirements, and Cloudflare limits relevant to this repository.

Implement the smallest architecture that supports reliable full-catalog ingestion and efficient queries.

### Required behavior

- Publish the complete eligible catalog, not only free endpoints.
- Preserve existing snapshot keys or provide a migration/compatibility strategy.
- Ensure the manifest describes the published version and record counts consistently.
- Avoid partially publishing a catalog if ingestion fails halfway through.
- Handle pagination and query limits explicitly in public APIs.
- Do not scan every KV record on every user search request.
- Keep source-specific snapshots or provenance if they are required for reliable reconciliation.

If KV is insufficient for efficient multi-dimensional filtering, recommend and implement D1 as a query index only after confirming the need. If D1 is introduced:

- Define schema and indexes.
- Provide an idempotent backfill/rebuild process from the canonical published catalog.
- Make publication consistency and rollback behavior explicit.
- Keep ingestion and query responsibilities separate.
- Avoid making the D1 index an undocumented second source of truth.

Include a short architecture decision record explaining the chosen approach and why it is sufficient for the current expected scale.

## 7. Evolve the public API compatibly

Inspect actual route implementations and current response fixtures before changing contracts.

### 7.1 Model list and detail

Preserve the existing `/api/v1/models` and `/api/v1/models/{id}` behavior wherever possible.

Expose the new endpoint-level `pricing_status` and normalized pricing fields through `PublicModelEndpoint`.

Do not add a model-level `free` flag.

If model-level summary fields are introduced, define aggregation rules explicitly. For example, a model with one free endpoint and one paid endpoint must not be presented as universally free.

Keep `data_source`, `provider`, endpoint identifiers, and source attribution semantics consistent with the existing contract.

Avoid leaking raw provider payloads or internal provenance records through public endpoints.

### 7.2 Filtering and search

Add or extend server-side filtering so consumers can query:

- All eligible models.
- Free endpoints.
- Paid endpoints.
- Unknown-pricing endpoints.
- Provider and data source.
- Capabilities and supported parameters.
- Context length and other normalized attributes.
- Keyword search where supported.

Define how endpoint-level filtering affects model-level results.

For example, when querying `pricing_status=free`, return a model only if at least one eligible endpoint is confirmed free. The returned endpoint list should clearly indicate which endpoints satisfy the filter.

Do not claim that a model is free simply because another endpoint for the same model is free.

Use stable pagination and deterministic ordering. Add explicit limits to prevent unbounded responses.

Do not break existing clients that expect the current list format.

### 7.3 Endpoint catalog

Keep `/api/v1/endpoints` consistent with the new semantics.

Expose pricing classification and normalized pricing only where supported and appropriate.

Distinguish endpoint lifecycle status from pricing status. A paid endpoint may be unavailable, and a free endpoint may be degraded.

Update API documentation and fixtures for all new fields and query parameters.

## 8. Update Browse and downstream consumers

The product will support a substantially larger catalog. Ensure the existing Browse experience and API consumers no longer assume that every published endpoint is free.

Implement the minimum required UI and query changes:

- Provide filters for free, paid, and unknown pricing.
- Label pricing clearly; do not show unknown prices as zero.
- Make clear that free status belongs to an endpoint, not necessarily the entire model.
- Preserve provider selection and endpoint-specific information.
- Handle missing prices, limits, and capabilities gracefully.
- Use server-side search/filtering if the existing UI currently requires loading the entire catalog.
- Keep loading, empty, error, and pagination states correct.

Do not redesign the entire product UI as part of this schema migration. Keep the visual scope limited to changes needed for correct catalog semantics and scalability.

Audit every configuration generator:

- LiteLLM
- NewAPI
- Bifrost
- Magpie

Confirm that adding paid endpoints does not accidentally exclude them or generate incorrect model identifiers, API base URLs, or environment-variable references.

Keep API keys out of generated artifacts. Do not generate literal user credentials.

For Magpie, preserve the existing distinction between `pickedFrom` (all available model IDs for a source) and `models` (user-selected model IDs).

Update any shared selection or filtering logic that currently assumes free-only catalog data.

## 9. Tests and migration safety

Add or update tests across the Python ingestion pipeline and TypeScript API/generator layers.

At minimum, cover:

1. Explicitly free endpoint with no numeric price.
2. Paid endpoint with valid pricing.
3. Endpoint with unknown pricing.
4. Zero price versus missing price.
5. Same model available through both free and paid endpoints.
6. Same model available through multiple providers.
7. Source-specific pricing normalization and units.
8. Reconciliation when pricing changes between ingestion runs.
9. Missing or malformed pricing fields.
10. Temporary upstream failure and incomplete source snapshots.
11. Public API backward compatibility for the legacy `free` field.
12. New API filtering for free, paid, and unknown endpoints.
13. Stable pagination and deterministic results.
14. Existing LiteLLM, NewAPI, Bifrost, and Magpie generation.
15. Empty, stale, and partially populated catalog behavior.
16. Manifest and published record-count consistency.

Add regression tests proving that a confirmed paid endpoint is not dropped by the former free-only filter and that unknown pricing is never silently classified as free.

Use realistic source fixtures and avoid tests that only assert implementation details without checking externally observable behavior.

Run the repository's existing CI-equivalent test commands and relevant type checks. Report failures honestly; do not claim checks passed if they were not run.

## 10. Documentation and agent discoverability

Update documentation to reflect the actual implemented behavior.

Audit:

- `README.md`
- API documentation
- `llms.txt`
- `agents.md` or `agent.md`, whichever is actually served
- Model schema/design documentation
- Source adapter and ingestion documentation
- Any UI copy that describes the catalog as free-only

Document:

- The distinction between model, data source, provider, and endpoint.
- The semantics of `pricing_status` and legacy `free`.
- Normalized pricing units and missing-data behavior.
- Endpoint-level filtering and pagination.
- API compatibility and migration behavior.
- How agents can discover and filter paid/free/unknown endpoints.

Avoid leaving contradictory claims that the catalog contains only free models.

## 11. Implementation constraints

- Follow the existing project conventions and package structure.
- Reuse the current `DATA_SOURCE_REGISTRY` and existing generator mappings.
- Keep Python and TypeScript schema semantics aligned.
- Avoid unnecessary new dependencies.
- Avoid a broad rewrite of the ingestion system.
- Do not silently drop fields needed by existing generators.
- Do not infer provider behavior from a matching name alone.
- Do not introduce model-level pricing/access fields that contradict endpoint-level semantics.
- Prefer incremental, reversible migrations.
- Keep implementation, tests, API schemas, and documentation synchronized.

If the audit discovers a conflict between the current design document and actual code, treat the code as the implementation baseline, document the discrepancy, and resolve it explicitly.

## 12. Definition of done

The task is complete only when:

- The ingestion pipeline can retain eligible free, paid, and unknown-pricing endpoints.
- Access and pricing semantics are documented and tested.
- Existing canonical records and KV snapshots have a safe compatibility/migration path.
- The public API exposes the new endpoint-level classification without breaking legacy `free` consumers.
- Browse and search no longer assume the catalog is free-only.
- All four configuration generators continue to work correctly.
- CI-relevant tests and type checks have been run, with outcomes reported.
- Documentation and agent-facing discovery files match the implementation.
- No secrets or literal API keys are introduced.

## 13. Final report

When finished, provide a concise engineering report with:

1. The actual baseline architecture discovered.
2. The final schema changes and compatibility rules.
3. The ingestion and storage changes.
4. API and UI changes.
5. Generator compatibility results.
6. Files changed, grouped by subsystem.
7. Tests and commands run, with pass/fail status.
8. Migration and deployment instructions.
9. Remaining risks or deferred work.

Separate completed work from recommendations for future work. Do not claim implementation is complete when only the plan or partial code has been produced.
