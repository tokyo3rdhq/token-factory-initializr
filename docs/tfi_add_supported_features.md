# TFI: Add `supported_features` to the ModelEndpoint Data Model and End-to-End Pipeline

## Role

You are a senior full-stack engineer working on Token Factory Initializr (TFI), responsible for data modeling, data pipeline, API contracts, and frontend implementation.

Repository: `https://github.com/tokyo3rdhq/token-factory-initializr`

Primary site: `https://start.magi.website`

Implement this change end-to-end in the existing codebase. Inspect the current implementation before modifying it. Follow established architecture, naming conventions, test patterns, and `@tokyo3rdhq/magi-design-system` design standards.

Do not stop at updating TypeScript interfaces or UI components. Trace the field from its underlying data model and source adapters through normalization, persistence, public APIs, and frontend rendering.

---

## 1. Objectives

Implement two schema changes:

1. Add `decision` to the canonical `capabilities` vocabulary.
2. Introduce `supported_features` as a separate field in the underlying model/ModelEndpoint data model and propagate it through the complete data pipeline and web UI.

The initial canonical `supported_features` vocabulary must include:

- `streaming`

Preserve the distinction between model capabilities and supported features:

- `capabilities`: what the model can do or which specialized tasks it serves.
- `supported_features`: additional model or endpoint features and interface capabilities.
- `input_modalities` / `output_modalities`: the supported input and output data types.

Do not introduce a separate `tasks` field.

Do not move existing capability values unless explicitly required by this task. In particular, this change does not authorize migrating `tools`, `structured_output`, or `reasoning` from `capabilities` into `supported_features` unless the current repository already models them as supported features or an existing implementation explicitly requires such a migration. The requested additions are `capabilities.decision` and `supported_features.streaming`.

## 2. Repository Reconnaissance

Before implementing changes, inspect the repository and identify:

- Canonical model and ModelEndpoint types/interfaces/schemas.
- Model and endpoint identifiers and their relationship.
- Source-specific data adapters and raw source schemas.
- Capability normalization and mapping rules.
- Data pipeline stages, including snapshot, diff, reconcile, validation, deduplication, and publication, where present.
- Persistence and serialization formats, including Cloudflare KV/D1 or other stores actually used by the codebase.
- Public API routes and response serializers.
- Browse page data fetching, filters, filter state, and model-row components.
- Existing tests, fixtures, generated types, API documentation, `agents.md`, and `llms.txt` references affected by the schema.

Provide a concise implementation plan based on the actual repository structure, then proceed with the implementation.

Do not create parallel abstractions or duplicate canonical definitions when existing shared types and normalization utilities can be extended.

## 3. Canonical Data Model Changes

### 3.1 Add `decision` to `capabilities`

Extend the canonical capability vocabulary to accept `decision`.

Requirements:

- Update the canonical type or enum, validators, schema definitions, normalizers, and relevant documentation.
- Ensure `decision` survives every normalization and serialization stage.
- Do not infer `decision` solely from a model ID or free-text description.
- Where source data explicitly identifies a decision output or decision-oriented task, map it to `capabilities: ["decision"]` using a documented source-mapping rule.
- Preserve existing capability mappings and behavior.

### 3.2 Add `supported_features`

Add an optional or default-empty `supported_features` collection according to the existing schema conventions.

Use the repository's existing canonical naming and serialization conventions. The public JSON field should be named `supported_features`.

The initial canonical feature vocabulary must include `streaming`.

Requirements:

- Define a reusable canonical type or enum if the repository uses typed canonical vocabularies.
- Validate values consistently with the existing capability and modality validators.
- Preserve the distinction between `capabilities` and `supported_features`.
- Ensure the field is represented consistently in canonical model and ModelEndpoint data structures wherever applicable.
- Do not automatically assume that a feature supported by one endpoint is supported by every endpoint for the same model.
- If the repository distinguishes model-level facts from endpoint-level facts, store endpoint-specific feature support at the appropriate level and derive model-level aggregates only where existing architecture requires them.
- Do not fabricate `streaming` support when source data is missing, ambiguous, or unavailable.

Prefer a consistent empty-array convention if that matches the current API contract. If the field is optional in stored historical records, normalize missing values safely without treating missing evidence as confirmed support.

### 3.3 Maintain semantic consistency

Keep these concepts distinct:

- `capabilities`: canonical model capability/task labels, including `decision`.
- `supported_features`: supported interface or runtime features, initially including `streaming`.
- `input_modalities` and `output_modalities`: input/output data types and explicitly modeled output semantics.
- `context_length`, `pricing`, `free`, provider identifiers, and endpoint metadata: existing independent properties.

Do not make unrelated taxonomy changes as part of this implementation.

## 4. Data Pipeline Integration

Trace and update the complete data lifecycle.

### 4.1 Source adapters and normalization

- Inspect every relevant source adapter and identify where streaming support is explicitly provided.
- Map source-specific streaming indicators to canonical `supported_features: ["streaming"]`.
- Normalize source-specific decision task/output declarations to canonical `capabilities: ["decision"]` only when the source data supports that interpretation.
- Preserve provenance and source-specific facts according to existing conventions.
- Avoid hard-coded model-name mappings when a source field or documented source-level rule is available.
- Keep provider-specific and endpoint-specific facts scoped correctly.

Do not assume every source exposes the same fields. Missing source information must not be interpreted as `streaming: true`.

### 4.2 Validation, reconciliation, and persistence

Update all applicable pipeline stages, including:

- Snapshot creation and serialization.
- Schema validation.
- Diff generation and comparison.
- Reconciliation and deduplication.
- Publication and persistence.
- Any cached or precomputed model-list artifacts.

Ensure `supported_features` is not dropped during merges, deduplication, enrichment, reconciliation, or serialization.

Ensure `decision` is accepted and preserved by canonical capability validation.

When merging records from multiple providers or endpoints:

- Preserve endpoint-level distinctions.
- Do not let one endpoint's streaming support silently overwrite another endpoint's value.
- Follow existing conflict-resolution and provenance rules.
- Maintain backward compatibility with historical records that do not yet contain `supported_features`.

Add regression tests for missing fields, explicit streaming support, unsupported/unknown streaming, and multi-endpoint merges.

## 5. Public API and Documentation

Update all applicable API responses and shared serializers, including the existing model-list and model-detail endpoints, such as:

- `GET /api/v1/models`
- `GET /api/v1/models/{id}`

Update provider/endpoint API responses if their schemas expose the relevant feature information.

Requirements:

- Expose `supported_features` using the canonical JSON field name.
- Preserve `capabilities`, now allowing `decision`.
- Keep existing response fields and filtering behavior backward compatible unless the existing API versioning policy requires otherwise.
- Ensure list and detail responses follow the same semantics for the fields they expose.
- If the API exposes model-level aggregated features, document how endpoint-level facts are aggregated.
- Update `agents.md`, `llms.txt`, API schemas, examples, and relevant project documentation wherever they describe model response fields, capability vocabularies, or filtering behavior.

Do not document fields as available in an endpoint unless the implementation actually exposes them.

If API filtering by capability already exists, ensure `decision` is accepted. Add `supported_features` filtering only if consistent with the existing API filtering architecture; document the supported query syntax and test it.

## 6. Browse UI Integration

Update the Browse page end-to-end to expose and filter both canonical capabilities and supported features.

### 6.1 Filter UI

Add a `Supported Features` filter using the same established filter interaction patterns as the existing `Capabilities` filter.

Requirements:

- Source available options from the canonical supported-feature vocabulary or validated data, following existing filter conventions.
- Initially support `streaming`.
- Integrate with existing filter state and ensure the filter composes correctly with model search, provider/source filters, capability filters, and other existing filters.
- Preserve existing filter behavior and selected-state semantics.
- Handle models whose `supported_features` field is absent in historical data.
- Use the existing gray badge style for supported-feature options and selected feature labels, consistent with the existing neutral feature-badge treatment.
- Do not style supported features as prominent colored capability badges.

### 6.2 Filter ordering

In the Browse filter area, display the `Supported Features` filter **after the `Capabilities` filter**.

The order must be explicit and consistent at all supported viewport sizes.

Do not place supported-feature controls before capability controls.

### 6.3 Model Row display

Render `supported_features` badges in the existing model-row UI.

Requirements:

- Show capability badges first.
- Render supported-feature badges immediately after the capability badges.
- Use the same gray badge styling already used for supported-feature/filter-related neutral labels.
- Keep the row compact and responsive.
- Preserve existing behavior for rows with no supported features.
- Avoid introducing redundant labels or additional description text solely to explain the field.
- Follow existing truncation, wrapping, overflow, and responsive rules.

The required order in every Model Row is:

1. Model identity and existing metadata according to the current layout.
2. Capability badges.
3. Supported-feature badges.
4. Remaining metadata according to the existing layout.

Do not render supported-feature badges before capability badges.

If the current component architecture groups badges separately, preserve that architecture where practical while guaranteeing the correct visual order.

### 6.4 Design system

Use `@tokyo3rdhq/magi-design-system` components and tokens where appropriate.

Do not introduce arbitrary colors, one-off badge components, or conflicting styling conventions. Reuse the established neutral/gray badge treatment for supported features.

Verify that the filter layout and Model Row remain usable on mobile and desktop.

## 7. Testing Requirements

Add or update tests at the appropriate levels.

### Data model and normalization

- `decision` is accepted as a canonical capability.
- Existing capability values continue to work.
- `streaming` is accepted as a supported feature.
- Explicit source streaming support maps correctly.
- Missing or unknown streaming data does not become confirmed support.
- Decision mappings do not rely solely on model names.
- Endpoint-specific features remain correctly scoped.

### Pipeline and persistence

- `supported_features` survives normalization, validation, snapshots, reconciliation, diffing, and publication.
- Historical records without the field are handled safely.
- Multi-provider and multi-endpoint merges preserve the correct feature semantics.
- Existing pipeline tests remain green.

### API

- Model list and detail responses serialize `supported_features` consistently.
- `decision` appears in `capabilities` when supported by source data.
- Existing response fields and filters remain compatible.
- Feature filters, if implemented, return correct results.

### Frontend

- Supported Features filter renders and filters models correctly.
- Supported Features filter appears after Capabilities.
- Supported-feature badges use the established gray style.
- Model Row renders capability badges before supported-feature badges.
- Empty/missing supported-feature arrays do not break rendering.
- Existing search, selection, sorting, pagination, and responsive behavior remain intact.

## 8. Implementation Constraints

- Follow the current project architecture and coding conventions.
- Reuse canonical types, validators, and normalization helpers.
- Avoid duplicate field definitions and parallel schemas.
- Do not make unrelated UI redesigns or broad refactors.
- Do not fabricate provider capabilities or endpoint support.
- Do not change LiteLLM model-name mapping behavior in this task unless required by an existing regression caused by the schema change.
- Do not modify the semantics of `reasoning`, `tools`, or `structured_output` as part of this task.
- Keep existing model identifiers, endpoint identifiers, and provenance intact.

## 9. Acceptance Criteria

The task is complete only when all applicable criteria are met:

1. Canonical `capabilities` accepts `decision`.
2. Canonical `supported_features` exists and accepts `streaming`.
3. Source normalization and all relevant pipeline stages preserve both fields.
4. Endpoint-level feature facts are not incorrectly promoted to every endpoint.
5. Public model APIs expose `supported_features` consistently.
6. Relevant documentation reflects the actual schema and API behavior.
7. Browse includes a Supported Features filter after Capabilities.
8. Supported-feature filter badges use the existing gray badge styling.
9. Model Row displays supported-feature badges after capability badges.
10. Existing functionality and tests remain intact.

## 10. Final Report

After implementation, provide a concise report containing:

- Files and layers changed.
- The canonical schema and source-mapping rules implemented.
- How endpoint-level feature support is represented.
- API and documentation changes.
- UI changes, including the filter and badge ordering.
- Tests executed and their results.
- Any remaining source-data limitations or decisions requiring confirmation.

Do not claim completion for unimplemented layers. If repository evidence reveals an architectural constraint that prevents full implementation, explain it and implement the safest compatible solution.
