# TFI Implementation Prompt: Integrate Kilo AI and Promote OpenRouter into the Model Catalog

## 1. Role and Objective

You are working on Token Factory Initializr (TFI), an open-source model discovery and gateway configuration generator.

Repository: https://github.com/tokyo3rdhq/token-factory-initializr  
Production site: https://start.magi.website

Implement the following data-source changes:

1. **Kilo AI**: Add `kilo` as a new model data source, fetching models from `https://api.kilo.ai/api/gateway/models`.
2. **OpenRouter**: Promote the already-integrated OpenRouter data source from calibration-only usage into the production model catalog. Its API endpoint is `https://openrouter.ai/api/v1/models`. Do not implement a duplicate OpenRouter integration if reusable ingestion, fetching, or calibration code already exists.

Both sources should independently ingest their own models, apply the same fundamental free-model filtering rule, normalize model metadata, construct source-specific endpoints, and publish catalog records.

Before making changes, inspect the repository and establish how its existing ingestion, normalization, pipeline, storage, and publishing mechanisms work. Treat the existing implementation as the source of truth for architecture and conventions.

## 2. Core Design Principles

### 2.1 Independent data sources and independent records

Kilo and OpenRouter are independent model data sources.

A model returned by both sources must remain two independent catalog records, even if both records have the same `model_id`.

For example, if both APIs return `z-ai/glm-5.3`, TFI should retain:

- The Kilo record, with Kilo-specific metadata and endpoint.
- The OpenRouter record, with OpenRouter-specific metadata and endpoint.

These records must not be merged, deduplicated across sources, or reconciled into a single record solely because their `model_id` values match.

Preserve the original `model_id` required by each service. Do not add source prefixes to `model_id` merely to resolve internal identity conflicts.

Inspect the existing model identity and storage keys. If necessary, ensure internal record identity includes sufficient source context, while preserving the public API contract and native model IDs.

### 2.2 Source isolation

Each source must independently own its:

- Fetching and source-specific parsing.
- Raw snapshot and source-specific processing.
- Free-model filtering.
- Metadata normalization.
- Endpoint association.
- Model record lifecycle and publication.
- Error handling and operational status.

Follow the repository's existing pipeline architecture, including its snapshot, diff, reconcile, and publish stages if those are the current conventions.

A failure in one source must not corrupt, overwrite, or prevent publication of valid data from the other source.

Do not use one source's metadata to silently fill or overwrite another source's record.

### 2.3 Preserve existing contracts

- Do not rename existing public API fields.
- Do not expose internal-only metadata such as `lab` unless the existing public schema explicitly requires it.
- Do not introduce unrelated API routes or schema migrations.
- Do not broadly refactor unrelated data sources.
- Reuse existing shared model, endpoint, capability, pricing, and provenance abstractions wherever possible.
- Keep the current technology stack and project conventions.
- Follow the existing MAGI design system and frontend conventions if any UI changes are required.

## 3. Data Sources and Fetching

### 3.1 Kilo AI

Source identifier: `kilo`

API endpoint:

`https://api.kilo.ai/api/gateway/models`

Fetch the model catalog using the existing project's HTTP client, retry, timeout, error-handling, and validation conventions.

Inspect real response examples and the existing calibration/source integration patterns before implementing the parser. Do not assume an undocumented response envelope or invent fields that are absent from the actual response.

### 3.2 OpenRouter

Source identifier: `openrouter`

API endpoint:

`https://openrouter.ai/api/v1/models`

OpenRouter is already integrated for calibration. Reuse the existing fetching and parsing logic where appropriate, but ensure its records are now processed by the production model-catalog pipeline.

Specifically:

- Identify the existing calibration-only path and its dependencies.
- Separate calibration responsibilities from production catalog ingestion where necessary.
- Avoid duplicate HTTP fetching implementations when existing code can be safely reused.
- Ensure promotion into the catalog does not accidentally change the semantics of existing calibration consumers.
- Verify that the production pipeline can publish OpenRouter records independently of other sources.

Do not treat this as a completely new OpenRouter integration unless repository inspection demonstrates that the existing implementation cannot be reused.

## 4. Free-Model Filtering

Both sources should follow the same fundamental rule:

**Retain a model only when every value in its `pricing` object's key-value pairs is numerically zero.**

Conceptually:

`is_free = pricing is valid and non-empty AND every pricing value equals numeric zero`

Implementation requirements:

1. Inspect the actual source response schema and existing pricing normalization utilities.
2. Apply the rule independently within each source pipeline.
3. Do not assume that a missing, `null`, malformed, or empty `pricing` object represents a free model.
4. Do not treat a missing pricing key as equivalent to a zero value.
5. Validate the numeric representation according to actual source responses. If prices are strings such as `"0"`, normalize them safely using existing conventions or an explicit, tested conversion.
6. Reject or exclude records with missing, malformed, negative, or nonzero pricing values unless the existing domain contract explicitly defines different handling.
7. Apply the filter before publishing catalog records.
8. Do not infer free status from a model name, a `:free` suffix, source branding, or pricing from another provider.

Keep filtering semantics consistent between Kilo and OpenRouter. Any source-specific representation differences should be handled in source adapters, not by weakening the shared rule.

Add tests covering zero prices, nonzero prices, mixed zero/nonzero values, missing pricing, empty pricing, malformed values, and string-formatted numeric values where relevant.

## 5. Metadata Normalization

Use the source response to construct TFI's existing normalized model representation.

The following source fields should be considered where available and compatible with the current schema:

| Source field | Intended normalized use |
|---|---|
| `id` or the actual source model identifier field | TFI's native `model_id` |
| `name` or equivalent | Display name |
| `description` | Model description |
| `architecture` | Architecture metadata, if supported by the current schema |
| `context_length` | Context-window metadata, if supported |
| `pricing` | Model-and-endpoint-specific pricing |
| `supported_parameters` | Input for capability normalization |
| Other existing supported fields | Preserve or normalize according to current project conventions |

The exact source field mapping must be verified against real response examples and the repository's types. Do not assume every field exists in every record.

### 5.1 Description and architecture

Preserve the source's description and architecture information where available.

Use the existing normalized model schema. Do not add duplicate fields or expose arbitrary source fields directly unless that is already the project's established pattern.

### 5.2 Context length

Normalize `context_length` according to the existing schema and units.

Do not confuse context length with maximum output tokens. Do not invent missing values or silently substitute a different limit.

### 5.3 Pricing and free status

Preserve the pricing values from the corresponding source record, normalized into the existing TFI pricing structure.

A zero-priced record should be represented consistently with the current model/endpoint schema. Ensure the model's `free` status and pricing data do not contradict one another.

Do not merge pricing from Kilo and OpenRouter, even for identical model IDs.

### 5.4 Capability inference

Use `supported_parameters` to infer capabilities only where the parameter-to-capability mapping is justified.

Potential mappings include:

- `tools` → tool/function calling capability.
- `reasoning` → reasoning capability.
- `structured_outputs` → structured output capability.

Requirements:

1. Inspect the existing capability vocabulary and normalization implementation.
2. Reuse existing capability names and mapping conventions.
3. Add mappings only if the current implementation does not already support them.
4. Verify the exact source parameter names and semantics.
5. Avoid false positives from substring matching or unrelated parameters.
6. Preserve unknown source parameters where the existing schema supports raw metadata, without automatically treating every parameter as a capability.
7. Add unit tests for recognized, unrecognized, malformed, and missing parameter lists.

Do not assume that all models support a capability simply because the API or provider supports it generally.

## 6. Source URLs

Each source record must have a source-specific `source_url`, constructed from its native `model_id`.

### Kilo

Template:

`https://kilo.ai/models/${model_id}`

Example:

`https://kilo.ai/models/z-ai/glm-5.3`

### OpenRouter

Template:

`https://openrouter.ai/models/${model_id}`

Example:

`https://openrouter.ai/models/nvidia/nemotron-3.5-lightning:free`

Requirements:

- Preserve the native model ID, including namespace separators and meaningful suffixes.
- Do not substitute the other source's URL template.
- Follow the existing project's URL encoding and URL construction conventions.
- Verify generated URLs for namespaced model IDs and IDs containing suffixes such as `:free`.
- Do not generate source URLs by copying another provider's record.

## 7. Endpoint Construction

Each data source must have an endpoint associated with its model records.

### Kilo

`base_url`: `https://api.kilo.ai/api/gateway`

### OpenRouter

`base_url`: `https://openrouter.ai/api/v1`

Use the existing endpoint schema to populate protocol, authentication metadata, status, source attribution, and other required fields. Confirm the actual source contract and current TFI conventions before deciding values that are not specified in this prompt.

Both services expose OpenAI-compatible API interfaces, but do not assume all endpoint metadata or authentication requirements are identical merely because the protocols are compatible.

### 7.1 Endpoint identity

Inspect the current endpoint registry, ID generation, and model-to-endpoint association logic before implementing these sources.

Requirements:

- Every model record must reference the endpoint corresponding to its own data source.
- The endpoint registry and model-level `endpoints[]` references must use exactly the same IDs.
- Do not derive an endpoint ID from `model_id`.
- Do not infer an endpoint's actual `base_url` from `provider`.
- Do not merge endpoint records from Kilo and OpenRouter just because their model IDs match.
- Follow the existing endpoint identity convention unless repository inspection reveals a correctness problem. Any necessary change must be scoped, justified, tested, and compatible with existing consumers.

In particular, ensure a model returned by both sources retains two independent endpoint associations, each with the correct base URL.

## 8. Pipeline and Storage Integration

Integrate both sources into the current production data pipeline rather than creating parallel, ad hoc publication mechanisms.

Inspect and update, as applicable:

- Source registration and configuration.
- Fetching and response validation.
- Raw snapshots.
- Source-specific diffs.
- Reconciliation and stale-record handling.
- Normalization and endpoint construction.
- KV/storage keys and publication.
- Scheduled workflows and source execution configuration.
- Source-specific error reporting and observability.
- Existing fixtures, tests, and generated artifacts.

Use source-scoped storage keys or the project's existing equivalent so records from different sources cannot overwrite one another.

Ensure that:

1. A shared `model_id` across Kilo and OpenRouter is not treated as a cross-source duplicate.
2. A model removed from Kilo does not cause the corresponding OpenRouter model to be removed.
3. A failed or empty fetch cannot accidentally wipe another source's catalog.
4. Re-running the pipeline with unchanged source data is idempotent.
5. Reconciliation affects only the relevant source namespace.
6. Published model and endpoint data remain internally consistent.
7. The production catalog can contain both records even when their `model_id` values are identical.

Do not silently change the behavior of other existing sources.

## 9. Public API and Consumer Compatibility

Review the current API implementation and actual serialized responses for:

- `GET /api/v1/models`
- `GET /api/v1/models/{id}`
- `GET /api/v1/endpoints`, if implemented
- `GET /llms.txt`
- `GET /agents.md`

Ensure that both data sources appear in the public model catalog after publication.

### Model identity and lookup

Because the same `model_id` may now identify records from multiple sources, verify how the current API resolves model IDs.

Do not assume that a model ID is globally unique if the new data requires source-scoped identity.

If the current detail API cannot unambiguously resolve duplicate IDs, investigate the least disruptive compatible solution. Do not invent a new public route, change the meaning of existing fields, or silently return an arbitrary source record. Document any unresolved API limitation and propose a narrowly scoped follow-up if a safe compatible solution cannot be implemented in the current task.

Preserve the existing public `model_id` format. Distinguish internal record identity from the native model ID where the architecture requires it.

### Browse and config generation

Inspect how the frontend and configuration generators select models and resolve endpoint information.

Verify that users can independently select the Kilo and OpenRouter records, and that generated configurations use:

- The correct native model ID.
- The correct endpoint base URL.
- The appropriate endpoint-specific pricing/free metadata where relevant.
- The correct source-specific metadata.

Do not combine the two sources' endpoint information or pricing during selection or generation.

## 10. Tests and Validation

Add or update tests following the existing test framework and conventions.

At minimum, validate the following cases:

1. Kilo model fetching and parsing.
2. OpenRouter production ingestion using reusable existing source logic where possible.
3. Filtering models with all-zero pricing.
4. Excluding nonzero, mixed, missing, empty, or malformed pricing.
5. Mapping description, architecture, context length, and pricing.
6. Capability mapping from supported parameters.
7. Correct source-specific `source_url` construction.
8. Correct endpoint base URLs.
9. Consistent endpoint IDs between the registry and model references.
10. Two records with the same `model_id` but different data sources coexist without overwriting one another.
11. Source-scoped reconciliation and stale-record removal.
12. Independent source failures.
13. Public API serialization and detail lookup behavior with duplicate model IDs.
14. Correct model selection and configuration generation for each source.
15. Idempotent publication.

Use fixtures based on real API response shapes. Do not make tests depend on live external API availability unless the repository already has a clearly separated integration-test convention.

Run the relevant existing tests, type checks, linting, and build commands that are available. Fix regressions introduced by the implementation.

## 11. Documentation

Update the appropriate documentation, including `agents.md`, `llms.txt`, or source-specific documentation if the current project maintains them.

Document that:

- Kilo and OpenRouter are independent catalog data sources.
- Identical `model_id` values across different sources represent distinct configurable service records.
- `data_source`, `provider`, `model_id`, and `endpoint` have distinct semantics.
- Endpoint identity and `base_url` must not be conflated.
- Pricing and free status are source- and endpoint-specific.
- Model identity and API lookup must not assume that `model_id` is globally unique across all sources.

Do not duplicate large documentation sections unnecessarily. Prefer updating the authoritative definitions and linking to them.

## 12. Implementation Workflow

Follow this sequence:

1. Inspect the repository structure, architecture documentation, current data-source adapters, calibration logic, endpoint model, pipeline stages, public API, frontend selection flow, and configuration generators.
2. Identify the smallest set of changes required for Kilo ingestion and OpenRouter catalog promotion.
3. Implement Kilo as an independent data source.
4. Reuse and adapt the existing OpenRouter integration for production catalog publication.
5. Add source-specific fixtures and regression tests.
6. Validate duplicate `model_id` behavior across storage, API lookup, UI selection, and config generation.
7. Update documentation and operational workflow configuration as necessary.
8. Run relevant validation commands and inspect the final diff.

Do not stop after implementing the fetchers. The task is complete only when the source records can flow through the production pipeline into the catalog without cross-source collisions and can be selected for correct configuration generation.

## 13. Final Report

When finished, provide a concise but specific implementation report containing:

- Files changed and the purpose of each change.
- How Kilo and OpenRouter are independently integrated.
- How the free-model filtering rule is implemented.
- How endpoint identity and source-scoped model identity are handled.
- Whether duplicate model IDs work correctly across public APIs, UI selection, and configuration generation.
- Tests, type checks, linting, and builds actually executed, with their real results.
- Any known limitations, unresolved compatibility issues, or recommended follow-up work.

Never claim a check passed unless it was actually executed and passed.
