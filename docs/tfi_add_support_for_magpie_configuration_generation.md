# Coding Agent Prompt: Implement Magpie Configuration Generation in TFI

## 1. Objective

Implement Magpie configuration generation in Token Factory Initializr (TFI).

TFI allows users to browse models from multiple data sources, select the models they want, and generate configuration files for AI gateways and related tools.

Add Magpie as a supported configuration export target. The generated artifact must follow the exact JSON structure and field conventions of the supplied reference file:

`/tmp/providers.json`

Treat this file as the reference template for the Magpie provider configuration format. Preserve its structure and existing provider-specific settings unless explicitly required to substitute TFI-generated data.

Before implementation, inspect the current repository, model-selection flow, configuration generation architecture, data-source mappings, and existing output formats. Reuse existing abstractions and UI conventions wherever possible.

Do not create a separate model discovery or data ingestion pipeline for Magpie.

## 2. Core transformation rules

For each provider configuration entry, distinguish between:

- `key`: user-supplied API credential; always generate as an empty string.
- `pickedFrom`: the complete set of model IDs available from the corresponding data source in TFI.
- `models`: only the model IDs explicitly selected by the user in TFI.
- `chat`: the base URL from the corresponding TFI `ModelEndpoint`.
- All other provider fields: preserve the reference template's default values unless an explicit rule below requires otherwise.

### 2.1 `key`

Always output:

```json
"key": ""
```

Never populate this field from TFI model data, environment variables, browser storage, or other credential sources.

API keys must be entered by the user separately in Magpie. Do not request, collect, persist, or export API keys as part of this feature.

### 2.2 `pickedFrom`

`pickedFrom` must contain the complete set of model IDs belonging to the corresponding data source currently available in TFI, not merely the selected models.

Requirements:

1. Retrieve model IDs from TFI's existing model catalog or public API, using the same normalized data that powers the Browse page.
2. Match models to the appropriate Magpie provider/data-source mapping.
3. Include all currently available model IDs for that source, including models the user has not selected.
4. Preserve the model ID format expected by Magpie and the corresponding provider.
5. Deduplicate model IDs while preserving deterministic output ordering.
6. Do not hardcode model IDs from the reference file as the live `pickedFrom` list.
7. Do not confuse a model's internal TFI ID, provider-specific endpoint ID, and upstream API model ID. Determine which identifier Magpie expects from the reference configuration and current integration conventions.

For example, if TFI currently exposes model IDs `model-a`, `model-b`, and `model-c` for a source, the generated configuration should include all three in `pickedFrom`, even if the user selected only `model-b`.

### 2.3 `models`

`models` must contain only the model IDs explicitly selected by the user for the corresponding data source.

Requirements:

- Reuse the existing TFI selection state and model ID mapping.
- Do not populate `models` with every model in `pickedFrom`.
- Do not include models selected for another data source.
- Ensure every generated selected model is represented in the appropriate `pickedFrom` list, using the same identifier convention.
- Preserve selection order if that order is already meaningful in the current UI; otherwise use deterministic ordering.
- If no model is selected for a provider, follow the existing export UX convention. Do not silently invent a selection or substitute all available models.

### 2.4 `chat`

For each provider, `chat` must be populated from the corresponding selected model endpoint's `endpoint.base_url`, following the reference configuration's expected format.

Requirements:

1. Use TFI's normalized endpoint data, not a hardcoded URL derived solely from the provider name.
2. Do not use `source_url`, a model detail URL, or a frontend route as the chat endpoint.
3. Do not accidentally append a model ID or API route path unless the reference format explicitly requires it.
4. Normalize trailing slashes only according to the existing endpoint and Magpie configuration conventions.
5. Handle multiple endpoints belonging to the same data source explicitly. If selected models resolve to different base URLs, do not silently choose one. Follow an existing documented provider/endpoint grouping rule if available; otherwise surface a clear validation error and explain the conflict to the user.
6. If a selected model has no usable endpoint base URL, do not generate a misleading configuration. Report the affected model/provider and prevent export until the issue is resolved or the model is excluded.

The generated `chat` value must represent the endpoint associated with the provider configuration being generated.

## 3. Reference template and provider mapping

Use `providers(1).json` as the source of truth for provider-specific static configuration.

The reference contains these provider entries:

- `nvidia`
- `openrouter`
- `kilo`
- `amd`
- `ollama-cloud`
- `huggingface`

For each supported provider:

1. Preserve the template's static fields, including `id`, `name`, `icon`, `preset`, `catalog`, `website`, `keysUrl`, `anthropic`, `decide`, `baseAPI`, and `proxy`, wherever present.
2. Do not add optional fields to entries that do not have them in the template unless Magpie's current schema or an explicit product requirement calls for it.
3. Do not remove provider-specific fields merely because other providers do not use them.
4. Replace only the dynamic fields required by the transformation rules: `key`, `pickedFrom`, `models`, and `chat`.
5. Preserve the reference's provider ordering unless the existing TFI export conventions require a different deterministic ordering.
6. Do not assume that every TFI `data_source` maps directly to a Magpie `id`. Implement and test an explicit mapping layer.

Use the following initial mapping candidates, validating each against the current TFI schema and reference file:

| Magpie provider ID | TFI data-source mapping candidate |
|---|---|
| `nvidia` | NVIDIA NIM data source |
| `openrouter` | OpenRouter data source |
| `kilo` | Kilo Gateway data source |
| `amd` | AMD Radeon Cloud data source |
| `ollama-cloud` | Ollama Cloud data source |
| `huggingface` | Hugging Face data source |

These are mapping candidates, not permission to assume that the identifiers are already identical in code. Verify the actual values and endpoint semantics before implementing the mapping.

If a reference provider is not yet represented in TFI's current catalog, preserve its static template definition, but do not invent models or claim that its dynamic catalog is populated. Handle its empty or unsupported state according to the existing product UX.

Conversely, do not silently create new Magpie provider definitions for unrelated TFI sources without an explicit product requirement.

## 4. Strict JSON output requirements

The generated file must be valid, strict JSON.

Mandatory rules:

- Use double quotes for all JSON property names and string values.
- Do not emit comments.
- Do not emit trailing commas.
- Do not emit JavaScript expressions, `undefined`, `NaN`, or other non-JSON values.
- Do not wrap the generated JSON in Markdown fences in the downloadable artifact.
- Do not append explanatory text before or after the JSON content.
- Preserve valid escaping for special characters in strings.
- Preserve arrays as arrays and objects as objects.
- Validate the final serialized content with a standards-compliant JSON parser before offering it for download.

Use the project's existing JSON serialization mechanism, such as `JSON.stringify` on the final data structure. Do not manually construct JSON strings using concatenation.

The exported artifact should be directly importable by Magpie without manual syntax correction.

## 5. Static defaults and preservation

The supplied template defines provider-specific defaults that must be retained.

For each provider:

- Start from a parsed, validated copy of the reference template or an equivalent checked-in canonical template.
- Deep-clone or otherwise safely copy the template before modification.
- Update only the approved dynamic fields.
- Preserve all unrelated nested objects and provider-specific settings.
- Avoid mutating a shared template object in place across exports.
- Do not use one provider's defaults to fill another provider's fields.
- If a provider has an empty or missing static field in the template, preserve the template's semantics rather than guessing a value.

If the template is checked into the repository, document its source and purpose. If it remains an external user-provided fixture, determine the appropriate project convention for storing the canonical Magpie template.

Do not silently overwrite the supplied template's defaults based on generic assumptions about Magpie.

## 6. UI and export flow

Integrate Magpie into TFI's existing configuration generation experience.

Requirements:

1. Add Magpie as an export target using the existing configuration-target selection UI.
2. Reuse the existing model selection state and endpoint metadata.
3. Generate the Magpie JSON only from the current selection and current catalog data.
4. Provide a clear export action, such as download JSON or copy JSON, following existing TFI interaction conventions.
5. Ensure the output contains no API keys or secrets.
6. Explain any missing endpoint or provider-mapping issues before export.
7. Do not require users to reselect models in a separate Magpie-specific interface.
8. Preserve existing export targets and avoid regressions to LiteLLM, NewAPI, Bifrost, or other supported outputs.

The UI should make it clear that:

- `models` represents the user's selected models.
- `pickedFrom` represents the complete model catalog for the corresponding data source.
- `key` is intentionally empty and must be configured by the user in Magpie.

## 7. Implementation architecture

Before coding, identify the best existing extension point for a new configuration target.

Prefer a structure such as:

- A typed Magpie provider-template definition.
- A deterministic data-source-to-Magpie-provider mapping.
- A pure transformation function that takes the template, catalog, selected models, and endpoint metadata.
- Strict validation before serialization.
- A UI integration that calls the transformation function and exports the resulting JSON.

Adapt this structure to the actual repository. Do not introduce unnecessary new layers if the project already has an equivalent abstraction.

Keep transformation logic separate from UI rendering so it can be tested without a browser.

## 8. Validation and error handling

Validate the configuration before download.

At minimum, verify:

- The root JSON structure matches the reference template.
- `providers` is an array.
- Every generated provider has valid required fields.
- `key` is an empty string.
- `pickedFrom` is an array of unique strings.
- `models` is an array of unique strings.
- Each selected model belongs to the correct source's `pickedFrom` list.
- `chat` is a valid string in the expected format.
- Static provider-specific fields are preserved.
- No unsupported provider is populated with fabricated model data.
- The output parses as strict JSON.
- No credential or secret values appear in the output.

If validation fails, show a useful error that identifies the affected provider or model. Do not silently generate a partially incorrect configuration.

## 9. Automated tests

Add tests using the repository's existing testing framework.

Cover at least:

### Transformation rules

- `key` is always empty.
- `pickedFrom` contains all current model IDs for the corresponding source.
- `models` contains only the user's selected models.
- Models are grouped under the correct Magpie provider.
- Duplicate model IDs are removed deterministically.
- Model IDs preserve the expected provider-specific format.
- `chat` comes from the correct `endpoint.base_url`.
- Conflicting endpoint base URLs are detected and handled explicitly.
- Missing endpoint URLs are handled safely.

### Template preservation

- Static fields match the reference template.
- Optional provider-specific fields remain present when defined in the template.
- No fields are accidentally copied between providers.
- Repeated exports do not mutate the canonical template.
- Provider ordering is deterministic.

### Strict JSON

- Generated output parses with a standard JSON parser.
- No trailing commas, comments, or undefined values are emitted.
- String escaping is correct.
- No credentials or secrets are present.

### Regression

- Existing TFI configuration exports continue to work.
- Empty selections do not produce fabricated model choices.
- Catalog refreshes are reflected in `pickedFrom`.
- The generated configuration is deterministic for identical inputs.

## 10. Definition of done

The feature is complete when:

1. Magpie appears as a supported TFI configuration export target.
2. The supplied `providers(1).json` structure is faithfully preserved.
3. Dynamic fields are populated according to the rules above.
4. `pickedFrom` reflects the full current TFI model catalog per source.
5. `models` reflects only the user's selected models per source.
6. `chat` is derived from the correct `ModelEndpoint.base_url`.
7. All `key` fields remain empty.
8. Provider-specific static defaults are preserved.
9. The artifact is valid strict JSON and can be imported without manual edits.
10. Tests pass, and existing export targets are unaffected.

## 11. Final implementation report

After implementation, report:

- Files changed and their purpose.
- How each Magpie provider maps to TFI's data sources.
- How `pickedFrom`, `models`, and `chat` are populated.
- How static defaults are preserved.
- How conflicting or missing endpoints are handled.
- Test commands and actual results.
- Any remaining incompatibilities or assumptions about Magpie's import format.

Do not claim that the generated file has been verified against Magpie itself unless an actual import or schema-validation test has been performed.


## Additional Requirements: Documentation, Agent Discoverability, and Generate Page

### 1. Objective

In addition to implementing Magpie configuration generation, update all existing user-facing and agent-facing documentation that describes TFI's supported configuration targets.

TFI currently supports configuration generation for LiteLLM, NewAPI, and Bifrost. After this implementation, Magpie must be included wherever supported configuration formats, gateway integrations, or configuration-generation capabilities are described.

The goal is to maintain consistency across:

- `/llms.txt`
- `/agents.md` (or the actual canonical agent documentation path, such as `/agent.md`, if that is what the repository currently uses)
- The Generate page and its related UI components
- Relevant links, helper text, empty states, tooltips, and configuration-target descriptions
- Any other maintained documentation that explicitly lists supported configuration targets

**Do not update only the main Generate page heading or one documentation file. Audit all relevant occurrences and update them consistently.**

### 2. Audit existing references before editing

Search the entire repository for references to:

- `LiteLLM`
- `NewAPI`
- `Bifrost`
- Supported configuration formats and gateway targets
- Configuration generation and export capabilities
- Generate page descriptions and Agent instructions
- `/llms.txt`, `/agents.md`, and `/agent.md`

Identify every relevant location, including:

- Static Markdown files
- Dynamically generated `llms.txt` and agent documentation
- Pages Functions or API routes that serve these documents
- Generate page components and configuration-target selectors
- Shared constants, feature registries, navigation descriptions, and UI helper text
- Tests and fixtures that assert the supported-target list

Do not blindly replace every occurrence of these product names. Update only the contexts that enumerate or describe TFI's supported configuration-generation targets. Preserve unrelated technical documentation and provider-specific implementation details.

### 3. Update `/llms.txt`

Update the served `/llms.txt` content to explicitly include Magpie as a supported configuration-generation target.

Requirements:

1. Preserve the existing document structure, formatting conventions, and URLs.
2. Keep LiteLLM, NewAPI, and Bifrost listed.
3. Add Magpie with an accurate, concise description of its JSON provider configuration export.
4. Explain that TFI generates the configuration based on the user's selected models and corresponding endpoint information.
5. Make it clear that API key fields are intentionally left empty and must be configured by the user separately.
6. Include a link to the Generate page or the relevant documentation using the repository's existing canonical URL conventions.
7. If the document is generated dynamically, update its source template or generator rather than editing a generated artifact that will be overwritten.
8. Ensure the deployed `/llms.txt` response actually includes the new information.

Do not claim that TFI connects to Magpie accounts, imports configurations into Magpie automatically, or manages user credentials unless those capabilities are explicitly implemented.

### 4. Update `/agents.md` or `/agent.md`

Inspect the repository to determine the canonical agent-facing document and the actual route exposed by TFI.

Update the relevant document to include Magpie in all applicable supported-target lists and configuration-generation instructions.

The updated agent documentation must explain:

- Magpie is a supported configuration export target.
- The output is a strict JSON provider configuration.
- `key` fields are intentionally empty.
- `pickedFrom` contains the full set of currently available TFI model IDs for the corresponding data source.
- `models` contains only the models selected by the user.
- `chat` is populated from the corresponding `ModelEndpoint.base_url`.
- Provider-specific static fields are preserved from the canonical Magpie template.
- The resulting JSON can be downloaded or copied and then configured/imported into Magpie according to its supported workflow.

Keep these instructions aligned with the actual implementation. Do not document unsupported features or invent additional Magpie-specific capabilities.

Preserve existing LiteLLM, NewAPI, and Bifrost instructions. Do not alter their mapping rules as part of this documentation change unless required to correct a directly related inconsistency.

If TFI exposes both `/agents.md` and `/agent.md`, determine whether they are aliases, separate documents, or distinct routes. Update all relevant canonical sources and ensure that every advertised route serves consistent content.

### 5. Update the Generate page

Audit the entire Generate page and its related components, not just the primary configuration-target selector.

Wherever the page describes supported output formats, gateway integrations, or generated configurations, include Magpie.

At minimum, verify and update:

- The configuration-target selector or list
- The Generate page introduction and supporting description
- Any supported-target summary or comparison
- Target-specific helper text
- Empty states and validation messages that enumerate supported formats
- Export actions and output-format labels
- Any links to documentation or agent instructions
- Any contextual text that claims TFI supports only LiteLLM, NewAPI, and Bifrost

Use concise, consistent wording. For example:

"Generate configuration for LiteLLM, NewAPI, Bifrost, or Magpie."

For Magpie, use a clear target label such as:

"Magpie — JSON provider configuration"

Follow the existing design system and Generate page visual conventions. Do not introduce a separate, inconsistent visual style for Magpie.

The Generate page must accurately distinguish Magpie JSON export from the other supported configuration formats. Do not imply that all targets share the same schema or that Magpie uses the LiteLLM model ID mapping rules.

### 6. Keep documentation and implementation in sync

Avoid maintaining multiple independent lists of supported configuration targets when the existing architecture provides a shared configuration-target registry or equivalent abstraction.

If an appropriate shared registry already exists, update it and reuse it where practical. Otherwise, make the smallest maintainable change consistent with the existing architecture.

The documentation must describe the implemented feature, not merely announce a planned feature.

Verify that:

- The Generate page offers Magpie after implementation.
- `/llms.txt` mentions Magpie.
- The canonical agent documentation mentions Magpie and explains its actual export semantics.
- Any other relevant target lists no longer incorrectly imply that LiteLLM, NewAPI, and Bifrost are the only supported targets.
- Existing target descriptions remain accurate.
- All documentation links point to real routes or files.

### 7. Tests and acceptance criteria

Add or update tests where the project currently tests generated documentation or Generate page content.

At minimum, verify:

1. The Generate page exposes Magpie as a configuration target.
2. The served `/llms.txt` includes Magpie and an accurate description of its JSON export.
3. The served agent documentation includes Magpie and documents the `key`, `pickedFrom`, `models`, and `chat` semantics.
4. LiteLLM, NewAPI, and Bifrost remain documented and available.
5. No stale supported-target summary incorrectly states that only the original three targets are supported.
6. Documentation routes and links resolve correctly.
7. The documentation does not claim automatic account integration, credential management, or other unimplemented capabilities.

Run the relevant tests, type checks, lint checks, and build validation.

### 8. Final audit report

In the final implementation report, include a dedicated "Documentation and Discoverability" section listing:

- Every documentation file or route changed
- Every Generate page component or related UI description changed
- Any shared configuration-target registry updated
- Tests verifying documentation and UI consistency
- Any remaining occurrences of the original three-target list that were intentionally left unchanged, with reasons

Do not claim a complete documentation audit unless the repository search and relevant checks were actually performed.
