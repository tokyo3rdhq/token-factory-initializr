# Coding Agent Prompt: Integrate Ollama as a TFI Data Source

## 1. Objective

Integrate `ollama.com` as a first-class data source in Token Factory Initializr (TFI).

Repository: `https://github.com/tokyo3rdhq/token-factory-initializr`

The integration should discover Ollama cloud-hosted models through the OpenAI-compatible model list API, enrich model and endpoint metadata through Ollama's `/api/show` API and the existing parser at `/tmp/ollama_parser.py`, filter out models without `free_until` information, and publish the normalized results through TFI's existing data pipeline and APIs.

**Follow the existing TFI architecture and conventions. Do not implement a parallel pipeline or introduce a new storage mechanism.**

## 2. Mandatory reconnaissance before implementation

Before writing code:

1. Inspect the repository structure, current data ingestion pipeline, data source adapters, normalized schemas, persistence layer, validation and reconciliation logic, and publishing workflow.
2. Locate existing implementations for NVIDIA NIM, Hugging Face, AMD Radeon Cloud, and any other relevant sources. Identify the correct integration points.
3. Read `/tmp/ollama_parser.py` in full. Treat it as the reference implementation for Ollama-specific enrichment, including:
   - `description`
   - `capabilities`
   - `pricing`
   - `free_until`
   - Any related metadata parsing and normalization
4. Inspect the current `ModelEndpoint` and underlying model schemas to determine where each field belongs. Reuse existing types and enums wherever possible.
5. Inspect the existing LiteLLM model ID mapping rules in `agents.md`, along with the corresponding implementation and tests.
6. Review existing test fixtures, test commands, linting, type checking, and CI requirements.

Do not assume the repository's current architecture matches an earlier implementation. Base all changes on the current code.

If `/tmp/ollama_parser.py` is unavailable, stop and report that dependency rather than silently inventing its enrichment logic.

## 3. Data ingestion workflow

Implement the following end-to-end workflow:

`Discover → Fetch Details → Enrich → Normalize → Filter → Validate → Reconcile → Publish`

### Stage A: Discover models

Use the Ollama OpenAI-compatible endpoint:

`GET https://ollama.com/v1/models`

This is the primary entry point for discovering models available through Ollama's cloud service.

Requirements:

- Implement the request in Python, following the existing repository's conventions for HTTP clients, configuration, error handling, and logging.
- Parse the response according to its actual structure. Extract each valid model ID from the returned records.
- Preserve the original model ID exactly as returned by the API unless the existing parser explicitly defines a safe, documented normalization rule.
- Do not crawl the entire Ollama Library as a substitute for this endpoint. The initial integration targets models exposed through the cloud model-list API.
- Handle missing or malformed model IDs gracefully and report skipped records.
- Support the authentication required by the cloud API through an environment variable such as `OLLAMA_API_KEY`. Follow existing project conventions if a standard credential mechanism already exists.
- Never hardcode credentials, log API keys, or expose secrets in published model data.

### Stage B: Fetch model details

For every discovered model, request:

`POST https://ollama.com/api/show`

Example request:

```http
POST /api/show
Authorization: Bearer <OLLAMA_API_KEY>
Content-Type: application/json
```

```json
{
  "model": "gemma4:31b",
  "verbose": true
}
```

The example above is illustrative only. In production, use the actual model ID discovered in Stage A.

Implementation requirements:

- Use Python HTTP requests, not shelling out to `curl`.
- Send the model identifier using the request field required by the current Ollama API contract.
- Enable verbose metadata retrieval where supported.
- Extract and normalize the available context-length and architecture/input-modality information from the actual response structure.
- Inspect real response fixtures or representative responses before deciding which nested fields map to TFI's schema.
- Do not assume `architecture.input` exists as a literal field in the Ollama response. Derive the canonical value from the appropriate metadata only when the evidence supports that mapping.
- Preserve unknown values as unknown (`null`, absent fields, or the repository's established representation). Do not invent context lengths, modalities, or architecture metadata.
- Handle per-model errors without silently losing the failure information.

Add configurable concurrency and reasonable request timeouts. Respect rate limits and implement bounded retries with backoff for transient failures, including HTTP 429 and retryable server errors.

A single model-detail failure should not crash the entire ingestion run. Record the failure and continue processing other models unless the existing pipeline explicitly requires fail-fast behavior.

### Stage C: Enrich using `ollama_parser.py`

Reuse the existing logic in `/tmp/ollama_parser.py` to enrich each model.

The enrichment layer must support, at minimum:

- `description`
- `capabilities`
- `pricing`
- `free_until`

Requirements:

1. Read the parser and understand its inputs, outputs, assumptions, and dependencies before integrating it.
2. Reuse its established parsing logic rather than duplicating or approximating it in the new adapter.
3. Refactor reusable logic into the appropriate repository module if necessary, while keeping the implementation maintainable and testable.
4. Preserve the distinction between raw source data and normalized TFI metadata.
5. Normalize capabilities using TFI's existing canonical vocabulary and validation rules.
6. Normalize pricing using the existing schema and units. Do not assume that an absent price means a free model.
7. Parse `free_until` into the project's canonical timestamp/date representation. Preserve the meaning and timezone semantics of the source data.
8. If the parser obtains information from HTML, embedded page data, or another source, preserve its existing behavior where appropriate and document any additional network dependency.
9. Avoid introducing unnecessary duplicate requests if the parser already fetches information that can be reused from the current ingestion stage.

The final enriched record should combine the model-list record, `/api/show` metadata, and parser-derived metadata without overwriting valid fields with empty or lower-quality values.

Define and follow a consistent precedence policy:

- Source API metadata is authoritative for the fields it explicitly provides and that map reliably to TFI.
- The parser supplies additional metadata such as descriptions, capabilities, pricing, and `free_until`.
- Missing or ambiguous values remain unknown.
- Conflicting values must be resolved by an explicit rule, not accidental dictionary merge order.

### Stage D: Filter by `free_until`

**Only models with valid `free_until` information should be retained for publication.**

After enrichment:

- Retain a model only if `free_until` exists and can be parsed into the expected canonical representation.
- Drop records with missing, empty, malformed, or otherwise invalid `free_until` values.
- Do not infer `free_until` from pricing, model names, availability, or other indirect signals.
- Log aggregate counts and actionable diagnostics for filtered records without unnecessarily dumping raw response bodies.
- Apply the filter before the final published snapshot is constructed, using the existing pipeline's established stage ordering.

Clarify and preserve the existing meaning of `free_until`: this filter means the source provides free-access eligibility or expiry information; it does not by itself prove that a model is currently free or guarantee availability.

Do not add an additional “must not have expired” condition unless the existing parser or product requirements explicitly define that behavior.

### Stage E: Validate, reconcile, and publish

Feed the enriched and filtered records into TFI's existing pipeline.

Requirements:

- Use the current `snapshot / diff / reconcile / publish` workflow, or the repository's actual equivalent.
- Follow the existing data-source and provider key conventions.
- Use the appropriate Ollama-specific data-source identifier, consistently represented as `ollama`.
- Preserve deterministic identifiers so repeated ingestion runs do not create duplicate models or endpoints.
- Ensure stale records are handled according to existing reconciliation semantics.
- Do not publish partially populated records that violate required schema constraints.
- Preserve other data sources' records during Ollama refreshes.
- Do not change global deduplication or deletion semantics solely to accommodate Ollama.

## 4. Model and endpoint metadata mapping

Map Ollama data into the existing TFI schema rather than introducing Ollama-specific duplicate fields.

| TFI field | Mapping rule |
|---|---|
| `data_source` | `ollama` |
| `model_id` | Exact normalized model ID from `GET /v1/models`, following existing ID conventions |
| `description` | Enriched using `ollama_parser.py` |
| `capabilities` | Enriched and normalized using `ollama_parser.py` and TFI's canonical capability vocabulary |
| `pricing` | Enriched and normalized using `ollama_parser.py` |
| `free_until` | Parser-derived, validated value; required for retention |
| `context_length` | Derived from `/api/show` metadata when reliably available |
| `architecture.input` | Derived from `/api/show` metadata when reliably available |
| `source_url` | `https://ollama.com/library/${model_id}` |
| `endpoint.base_url` | `https://ollama.com/` |
| LiteLLM model ID | `ollama_chat/${model_id}` |

Important schema considerations:

1. Keep model-level metadata and endpoint-level metadata at their existing respective levels.
2. If `ModelEndpoint` owns pricing, free-access eligibility, or endpoint-specific capabilities, populate those fields there rather than incorrectly treating them as universal model properties.
3. Follow existing conventions for providers, endpoint IDs, source provenance, timestamps, and optional fields.
4. Do not add new schema fields unless they are necessary and compatible with the existing data model.
5. Use the existing source URL and base URL conventions, including trailing-slash conventions where required.
6. Treat `https://ollama.com/library/${model_id}` as the requested URL format, and validate the resulting URL against representative IDs before publishing.
7. Do not assume every field in `/api/show` maps one-to-one to the TFI schema. Explicitly normalize and validate mappings.

### LiteLLM model ID mapping

The canonical mapping must be:

```text
data_source = ollama
LiteLLM model ID = ollama_chat/${model_id}
```

For example:

```text
model_id: gemma4:31b
LiteLLM model ID: ollama_chat/gemma4:31b
```

Use the exact model ID from the normalized TFI record. Do not add or remove model tags unless an existing, documented normalization rule requires it.

**Use the `ollama_chat/` prefix, including the underscore.** Do not implement `ollamachat/`.

Apply the mapping in the appropriate existing mapping layer rather than duplicating it in multiple adapters or UI components.

## 5. Update `agents.md`

Update the LiteLLM model ID mapping documentation in `agents.md` to include Ollama.

The documentation should explicitly state:

- Data source: `ollama`
- LiteLLM model ID format: `ollama_chat/${model_id}`
- The prefix includes the underscore.
- The mapping applies to Ollama records and must preserve the original normalized model ID after the prefix.

Review nearby mapping documentation for consistency, but do not rewrite unrelated provider mappings or change their behavior.

If TFI exposes the same mapping rules in `llms.txt`, API documentation, generated configuration help, or other agent-facing documentation, update those locations when appropriate so the documented behavior matches the implementation.

## 6. Data source registration and pipeline integration

Register Ollama using the same mechanisms as the existing data sources.

Verify all relevant integration points, including:

- Data source registry and identifiers
- Fetcher/adapter registration
- Pipeline orchestration
- Shared model and endpoint types
- Normalization and validation
- Deduplication and stable identity
- Persistence and source-specific snapshots
- Diff and reconciliation
- Publishing and public API visibility
- Configuration and secrets
- CI and test workflows
- Agent-facing documentation

Do not create an isolated Ollama script that works only when executed manually. The integration must run through the same supported pipeline and deployment process as other sources.

If the project separates fetching from publishing through GitHub Actions or another workflow, add or update the appropriate workflow integration following current conventions. Avoid unnecessary workflow duplication.

## 7. Tests

Add automated tests using the repository's existing testing framework and style. Network calls must be mocked or fixture-backed in unit tests.

At minimum, cover the following cases.

### Discovery and detail fetching

- A valid `/v1/models` response produces the expected model IDs.
- Invalid or missing IDs are handled safely.
- `/api/show` receives the expected model identifier and verbose option.
- Authentication is supplied through configuration or environment variables.
- Transient HTTP errors trigger bounded retries.
- A failed detail request does not silently produce a valid-looking complete record.

### Enrichment and normalization

- Parser-derived descriptions, capabilities, pricing, and `free_until` are mapped correctly.
- `/api/show` metadata maps to the expected context length and input architecture fields.
- Missing source metadata remains unknown rather than receiving fabricated defaults.
- Conflicting metadata follows the documented precedence rules.
- Existing canonical capability normalization is reused.

### Free-until filtering

- A valid `free_until` retains a model.
- Missing `free_until` drops a model.
- An invalid `free_until` drops a model.
- Pricing alone does not cause a model to be retained.
- Expiration is not treated as an automatic exclusion unless required by existing semantics.

### Model and endpoint mapping

- `data_source` is `ollama`.
- The model ID remains stable and follows the existing normalization conventions.
- `source_url` uses the required Ollama Library URL pattern.
- `endpoint.base_url` is `https://ollama.com/`.
- The LiteLLM model ID is exactly `ollama_chat/${model_id}`.
- Model-level and endpoint-level fields are populated at the correct levels.
- Repeated ingestion does not create duplicate models or endpoints.

### Regression and integration

- Existing NVIDIA, Hugging Face, and AMD records are unaffected.
- An Ollama refresh does not delete or overwrite other data sources' records.
- The end-to-end pipeline publishes only validated, eligible Ollama records.
- `agents.md` documents the same LiteLLM mapping implemented by the code.

Include representative fixtures from actual Ollama API responses when available. Keep fixtures free of credentials and other secrets.

## 8. Operational requirements

- Reuse the repository's existing Python dependency management and logging conventions.
- Do not introduce unnecessary dependencies.
- Make request timeouts, concurrency, and retry behavior configurable where consistent with the project.
- Report discovered, successfully enriched, filtered, failed, and published record counts.
- Distinguish API failures, parsing failures, schema-validation failures, and eligibility filtering in diagnostics.
- Never log API keys.
- Ensure a temporary Ollama API failure cannot accidentally publish an empty snapshot and delete previously valid Ollama records. Follow the repository's existing safeguards for failed or incomplete source runs.
- Keep the integration deterministic and safe to rerun.

## 9. Explicit non-goals

Do not:

- Crawl the entire public Ollama Library as the primary model discovery mechanism.
- Publish models that lack valid `free_until` information.
- Assume all Ollama models are free because they are listed by the API.
- Infer capabilities, modalities, context lengths, or prices from model names alone.
- Hardcode API credentials.
- Change other data sources' ID mapping rules.
- Introduce an alternative database, storage format, or ingestion architecture.
- Perform unrelated schema migrations or UI redesigns.
- Silently change existing model identity, deduplication, or reconciliation behavior.

## 10. Implementation sequence

Execute in this order:

1. Inspect the repository and `/tmp/ollama_parser.py`.
2. Produce a concise implementation plan identifying the exact files/modules to change and any schema considerations.
3. Implement the Ollama discovery and detail-fetching adapter.
4. Integrate the existing parser's enrichment logic.
5. Implement normalization and the mandatory `free_until` filter.
6. Connect the adapter to the existing ingestion, validation, reconciliation, and publishing pipeline.
7. Implement and test the LiteLLM mapping.
8. Update `agents.md` and any directly related mapping documentation.
9. Add unit tests, integration tests, and representative fixtures.
10. Run the relevant tests, type checks, lint checks, and CI-equivalent validation.
11. Fix regressions introduced by the implementation and review the final diff.

Do not stop after producing a plan. Proceed with implementation unless blocked by a missing required dependency or a material ambiguity that cannot be resolved from the repository and source code.

## 11. Definition of done

The work is complete only when:

- Ollama is registered as a first-class TFI data source.
- Models are discovered through `https://ollama.com/v1/models`.
- Model details are fetched through `https://ollama.com/api/show`.
- The existing `/tmp/ollama_parser.py` logic is integrated or cleanly refactored into the repository.
- Description, capabilities, pricing, and `free_until` are enriched and normalized.
- Context length and input architecture metadata are populated when supported by actual API responses.
- Models without valid `free_until` information are excluded.
- Ollama model and endpoint records follow TFI's existing schemas and identity conventions.
- The LiteLLM mapping is `ollama_chat/${model_id}`.
- `agents.md` accurately documents the mapping.
- Tests verify the data flow, filtering, endpoint mapping, error handling, and cross-source regression safety.
- All relevant checks pass, and the final report identifies any remaining limitations.

## 12. Final report

After implementation, provide:

1. **Summary** — what was implemented.
2. **Changed files** — each file and its purpose.
3. **Data flow** — discovery → detail retrieval → enrichment → filtering → publishing.
4. **Schema mapping** — how each requested field is populated and where it is stored.
5. **LiteLLM mapping** — the exact rule and documentation changes.
6. **Tests and validation** — commands executed and their results.
7. **Limitations** — any source API constraints, missing metadata, or unresolved issues.
8. **Operational instructions** — required environment variables and how to run the ingestion workflow.

Clearly distinguish completed implementation from unverified assumptions. Do not claim tests passed unless they were actually executed.
