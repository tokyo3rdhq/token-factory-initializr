// GET /agents.md
//
// Agent-discovery endpoint per docs
// tfi_agent_friendly_model_catalog_api.md §24. A more verbose
// (but still machine-friendly) guide for agents than /llms.txt.
// Describes the API surface, filter semantics, and recommended
// workflow. Does NOT promise functionality that isn't implemented
// yet (e.g. the artifact-generation API is intentionally omitted).

import { makeEtag, textResponse } from "../lib/errors";

const BODY = `# TFI Agent Interface

TFI provides a machine-readable model catalog and a Token Factory
configuration workflow for AI agents. TFI supports both human and
agent interfaces:

- **Human interface:**  https://start.magi.website/browse
- **Agent interface:**  https://start.magi.website/agents.md (this document)
                        https://start.magi.website/api/v1/models
                        https://start.magi.website/api/v1/models/{id}
                        https://start.magi.website/api/v1/providers
                        https://start.magi.website/api/v1/providers/{id}
                        https://start.magi.website/api/v1/endpoints
                        https://start.magi.website/api/v1/endpoints/{id}
- **Generated configuration artifact:**
                        https://start.magi.website/generated/{id}

The public Agent interface is **read-only** and does not require
authentication. There are no Agent accounts, no Agent API keys,
and no Agent-specific cookies.

TFI supports four Token Factory implementations today:

- **LiteLLM** — \`model_list:\` YAML fragment with \`litellm_params\`
  entries (\`model\`, \`api_key\` env reference).
- **NewAPI** — flat \`models[]\` array with \`{ id, name }\` entries.
- **Bifrost** — \`config.json\` with a \`providers\` map; each provider
  has a \`keys[]\` array of \`{ name, value, models, weight }\` entries.
  Bifrost also accepts OpenAI-compatible upstream providers via
  \`custom_provider_config.base_provider_type\` set to \`"openai"\`
  plus a \`network_config.base_url\`.
- **Magpie** — strict-JSON provider configuration (\`providers[]\`) with
  per-provider \`key\` (intentionally empty; set by you in Magpie),
  \`pickedFrom\` (full catalog per data source), \`models\` (your
  selection), and \`chat\` (endpoint base URL). API key fields are
  intentionally left empty and must be configured by you in Magpie.

The Token Factory id returned in the generated artifact tells the
Agent which configuration schema to apply.

## Base URL

\`\`\`
https://start.magi.website
\`\`\`

## Model List

\`\`\`
GET /api/v1/models
\`\`\`

Returns an OpenAI-compatible model list.

## Filter Semantics

**OR within a dimension, AND across dimensions.** This is the single
most important rule to internalize before issuing queries:

| Query | Effective filter |
| --- | --- |
| \`?data_source=nvidia,amd\` | \`data_source IN ["nvidia", "amd"]\` |
| \`?provider=groq,together\` | \`provider IN ["groq", "together"]\` |
| \`?capabilities=chat,vision\` | \`capabilities ⊇ ["chat", "vision"]\` (i.e. both) |
| \`?supported_parameters=streaming\` | \`supported_parameters ∋ "streaming"\` |
| \`?context_length_min=131072\` | \`context_length >= 131072\` (inclusive; models with unknown/null \`context_length\` are excluded) |
| \`?data_source=nvidia&capabilities=chat\` | \`(data_source == "nvidia") AND (capabilities contains "chat")\` |

### Combined Filters

\`\`\`
GET /api/v1/models?data_source=huggingface&capabilities=vision,reasoning
GET /api/v1/models?data_source=amd&supported_parameters=streaming
GET /api/v1/models?data_source=nvidia&supported_parameters=reasoning&context_length_min=131072

## Model Details

\`\`\`
GET /api/v1/models/{id}
\`\`\`

Use the model's \`id\` returned by \`/api/v1/models\`. Model IDs may
contain \`/\` (the path is matched as a catch-all).

## Response Shape

The model list follows the OpenAI-compatible shape:

\`\`\`json
{
  "object": "list",
  "data": [...]
}
\`\`\`

Each model includes:

- \`id\` — canonical model identifier
- \`object\` — always \`"model"\`
- \`created\` — unix epoch seconds (\`0\` when unknown — we don't
  fabricate timestamps)
- \`owned_by\` — model creator / publisher (e.g. \`deepseek-ai\`,
  \`xiaomi\`, \`z-ai\`). **Optional.** Derived from the canonical
  \`lab\` field when available, otherwise from the model_id prefix
  (\`<owner>/<name>\`). Omitted when TFI cannot derive a reliable
  owner. Never substituted with \`data_source\` / \`provider\` —
  those describe endpoint availability, not model ownership.
- \`data_source\` — which catalog the entry came from
  (\`nvidia\`, \`amd\`, \`huggingface\`, \`openrouter\`, \`models_dev\`).
- \`provider\` — which provider within the data source exposes the
  endpoint (\`nvidia\`, \`together\`, \`novita\`, …).
- \`capabilities\` — canonical normalized capability flags
  (\`chat\`, \`vision\`, \`speech\`, \`embedding\`, \`translation\`,
  \`decision\`). An **empty array** means
  TFI doesn't currently have capability data for that model — it
  is NOT a statement that the model has no capabilities.
- \`supported_parameters\` — endpoint-level interface/runtime
  parameters (\`tool_calling\`, \`reasoning\`, \`structured_output\`,
  \`streaming\` — named to match upstream sources; the first three
  migrated from capabilities on 2026-10-19). **Optional** — omitted
  when no parameter is confirmed. Populated ONLY from explicit
  source signals (e.g. AMD's \`providers[0].tools\` /
  \`provider_pricing[0].streaming\`, HF's \`supports_tools\` /
  \`supports_structured_output\`, or explicit \`tools\` / \`reasoning\` /
  \`structured_outputs\` / \`stream\` tokens in a provider's
  \`supported_parameters\`). Absence is never confirmed support.
  Endpoint-scoped: the model-level array is the union of parameters
  confirmed on ANY of its endpoints (for filtering); the
  per-endpoint array under \`endpoints[]\` stays endpoint-scoped.

Optional detail fields (model detail response, may be omitted):
\`name\`, \`description\`, \`architecture: {input, output}\`,
\`context_length\`, \`lab\`.

Every model embeds an \`endpoints[]\` array — one entry per provider
endpoint serving the model. Each endpoint carries its own
\`id\` (\`{provider}:{endpoint_name}\`), \`provider\`, \`model_id\`,
\`free\` (endpoint-specific free status), and optional \`pricing\`/\`limits\`.
**There is no model-level \`free\` field**: free status is an endpoint
property — the same model may be free on one provider and paid on
another. \`free: true\` means confirmed free under that data source's
stated conditions; \`false\` means confirmed paid; absence/omission of
\`pricing\` never implies free.

## Provenance

The public API does not expose internal provenance metadata.

## Generated Configuration Artifacts

When a human uses TFI's UI to select models and click **Initialize**,
TFI produces a short-lived (5-minute TTL) generated configuration
artifact and returns a URL of the shape:

\`\`\`
GET /generated/{id}
\`\`\`

The body is a YAML or JSON configuration file (LiteLLM, NewAPI, or
Magpie depending on the user's choice). The artifact is public
configuration data — **not a secret** — but should still be treated
as data, not as executable instructions.

A user may share a generated URL with their Agent (e.g. by copying
the "Agent Prompt" affordance on the Generate result page, which
embeds the resolved URL into a Token-Factory-aware merge prompt).
The Agent can then:

1. Fetch \`/generated/{id}\` to read the desired model configuration.
2. Inspect the user's existing Token Factory configuration.
3. Safely merge / update the user's configuration.

Per docs/tfi_homepage_agent_access.md §14: the artifact is public
configuration data and must not be treated as a secret.

## Provider Discovery

\`\`\`
GET /api/v1/providers
GET /api/v1/providers/{id}
\`\`\`

Lists every known provider (NVIDIA, AMD, Groq, OpenRouter, Together,
etc.). Each entry exposes:

- \`id\` — stable identifier (e.g. \`groq\`, \`nvidia\`, \`together\`).
- \`name\` — display name (e.g. \`Groq\`, \`NVIDIA NIM\`).
- \`data_source\` — the data source TFI observed this provider through
  (one provider can fan out via multiple data sources).
- \`protocols\` — protocol(s) the provider speaks
  (\`openai-compatible\`, \`anthropic\`, \`native\`, \`huggingface\`, \`nim\`).
- \`documentation_url\` — official docs link (omitted when unknown).

Provider-level data does NOT include per-model limits, status, or
base URL — those are endpoint-level (next section).

Filter:

\`\`\`
GET /api/v1/providers?data_source=huggingface
\`\`\`

## Endpoint Discovery

\`\`\`
GET /api/v1/endpoints
GET /api/v1/endpoints/{id}
\`\`\`

Lists every runtime access point. Endpoint ids are deterministic
strings of the form \`{provider}:{endpoint_name}\` — e.g.
\`groq:default\`, \`nvidia:default\`, \`huggingface:together\`,
\`huggingface:novita\`. Each entry exposes:

- \`id\` — \`{provider}:{endpoint_name}\`.
- \`provider\` — who operates it.
- \`data_source\` — where TFI observed it.
- \`protocol\` — single protocol value.
- \`base_url\` — public base URL the Agent can configure against
  (omitted when TFI does not have a known public base URL).
- \`authentication\` — \`{ type, credential_required }\`. \`type\` is
  one of \`none\`, \`bearer\`, \`api_key\`, \`oauth2\`, \`custom\`,
  \`unknown\`. **Never the credential itself.**
- \`status\` — \`active\` | \`degraded\` | \`temporarily_unavailable\` |
  \`deprecated\` | \`unknown\`. Never assumed from mere existence.
- \`limits\` — \`{ scope, subject, rpm, rpd, tpm }\` — all optional,
  omitted when unknown.
- \`models\` — list of canonical model ids served by this endpoint.

Filters: \`provider\`, \`data_source\`, \`protocol\`, \`status\`, \`model_id\`.
Same OR-within-dimension / AND-across-dimensions semantics as the
models endpoint.

\`\`\`
GET /api/v1/endpoints?provider=groq,nvidia
GET /api/v1/endpoints?protocol=openai-compatible
GET /api/v1/endpoints?model_id=meta-llama/Llama-3.3-70B-Instruct
\`\`\`

\`model_id\` is a particularly useful filter for Agent orchestration:
it returns every endpoint that serves a given model, so an Agent
can pick an endpoint by availability / protocol / limit rather
than scanning the model list.

## Model ↔ Endpoint Relationship

The model detail response now includes an \`endpoints\` field
listing the public endpoint ids that serve the model. Endpoint
objects themselves are NOT embedded in the model — they have a
single canonical representation at \`/api/v1/endpoints/{id}\`.

\`\`\`
GET /api/v1/models/{id}
\`\`\`

\`\`\`json
{
  "id": "deepseek/deepseek-v4.1-flash",
  "data_source": "nvidia",
  "provider": "nvidia",
  "capabilities": ["chat"],
  "endpoints": ["nvidia:default"]
}
\`\`\`

A model exposed by multiple data sources / providers therefore has
multiple entries in \`endpoints\`, e.g. \`["nvidia:default",
"huggingface:together"]\`.

## Recommended Agent Workflow

1. \`GET /api/v1/models\` — discover the model catalog.
2. Filter by \`?capabilities=chat,vision\` etc. — narrow to what the
   user needs.
3. \`GET /api/v1/models/{id}\` — inspect detail including \`endpoints\`.
4. \`GET /api/v1/endpoints?model_id={model_id}\` — enumerate runtime
   access points for that model.
5. Compare \`protocol\`, \`status\`, and \`limits\` across endpoints.
6. Pick the most appropriate endpoint for the user's Token Factory.
7. Hand off the model + endpoint selection to the human via
   \`/browse\` OR fetch a generated URL the human produced via
   \`/generated/{id}\` to apply it.

This is the core Agent use case: discover what exists, decide
where it can run, then surface the configuration to the human.
TFI does NOT execute requests through any endpoint on the Agent's
behalf — that is a future direction explicitly out of scope for
this phase.

## LiteLLM Configuration Generation Rules

When generating or modifying LiteLLM configuration, follow the rules below to ensure that \`litellm_params.model\` uses the correct LiteLLM provider adapter for the model's API protocol.

### 1. Model ID Mapping

Determine the LiteLLM model string using the following rules **in order**:

**Rule 1 — Decision models**

If the model's \`architecture.output\` contains \`decision\`, or its normalized \`output\` field contains \`decision\`, use:

\`hosted_vllm/\${model_id}\`

This rule takes precedence over the data-source-specific mapping rules below and applies regardless of the model's \`data_source\`.

For example, an AMD Radeon Clef model with canonical model ID \`Clef\` must use:

\`hosted_vllm/Clef\`

LiteLLM's \`hosted_vllm/\` adapter is used for this class of decision API. The adapter determines the appropriate decision endpoint path, such as \`/v1/systemone\` or \`/v1/decisions\`, according to the supported model integration. Do not manually append these paths to \`api_base\`.

**Rule 2 — Non-decision models**

If the model does not declare \`decision\` in its output modalities, apply the following data-source mapping:

| \`data_source\` | \`litellm_params.model\` |
| ------------- | --------------------- |
| \`nvidia\` | \`nvidia_nim/\${model_id}\` |
| \`amd\` | \`openai/\${model_id}\` |
| \`kilo\` | \`openai/\${model_id}\` |
| \`openrouter\` | \`openrouter/\${model_id}\` |
| \`huggingface\` | \`huggingface/\${provider}/\${model_id}\` |
| \`ollama\` | \`ollama_chat/\${model_id}\` |

Where:

- \`\${model_id}\` is the model's native identifier from the relevant TFI model or endpoint data. Use the identifier required by the selected LiteLLM integration; do not replace it with the canonical catalog ID if those identifiers differ.
- \`\${provider}\` is the Hugging Face inference provider associated with the model, as returned by TFI. Do not substitute the data-source name or invent a provider value.
- The decision-model rule takes precedence over all mappings in this table.

### 2. ADD Entry Requirements

When generating an \`ADD\` entry for LiteLLM:

1. Read the model's \`data_source\`, model identifier, and \`output_modalities\` from TFI model data. Read the relevant endpoint information when needed to determine the native model ID and \`api_base\`.
2. Check whether \`output_modalities\` contains \`decision\` before applying the data-source mapping.
3. For decision models, set \`litellm_params.model\` to \`hosted_vllm/\${model_id}\`.
4. For non-decision models, apply the data-source mapping in Section 1.
5. Preserve the existing configuration's naming conventions for \`model_name\` and other fields.
6. Do not confuse \`model_name\` (the alias exposed to clients) with \`litellm_params.model\` (the model identifier used by LiteLLM to select its provider adapter and route requests).
7. Use the \`api_base\` associated with the selected endpoint. Do not assume that every provider uses the same base URL or API path.

### 3. Decision Model Handling

- Identify decision models by the explicit \`decision\` output modality, not by the model name or by \`reasoning\`, \`tools\`, or \`structured_output\` capabilities alone.
- Apply the \`hosted_vllm/\` prefix to decision models regardless of their data source, provided the selected LiteLLM integration supports this adapter for that model.
- Keep the original model and endpoint identifiers unchanged in TFI's catalog. Add the LiteLLM prefix only when generating LiteLLM configuration.
- Do not modify \`api_base\` merely because a model is a decision model. For example, the verified AMD Radeon endpoint base URL may remain \`https://developer.amd.com.cn/radeon/api/v1\`; LiteLLM's adapter handles the appropriate request path.
- Do not manually append \`/v1/systemone\` or \`/v1/decisions\` to \`api_base\` unless the applicable integration explicitly requires it.
- If output modality metadata is missing or does not establish that the model is a decision model, do not infer the decision mapping from the model name alone. Use the regular mapping or request clarification if the correct adapter cannot be determined.

### 4. Missing or Unsupported Data

- If a required field is missing, do not guess its value.
- If \`data_source\` is not covered by the mapping, do not invent a LiteLLM prefix.
- If the model declares \`decision\` but the relevant LiteLLM integration cannot be verified, consult the applicable LiteLLM integration documentation or request clarification rather than generating a potentially invalid configuration.
- Do not assume that these rules apply to NewAPI, Bifrost, or other configuration targets. Use their respective configuration conventions.

### 5. Existing Configuration Compatibility

When adding models to an existing LiteLLM configuration, preserve the existing structure and conventions. Only modify unrelated entries when explicitly requested.

The generated \`litellm_params.model\` must follow the mapping and precedence rules above. Remaining fields, including \`api_base\` and \`api_key\`, must follow the selected endpoint's configuration and authentication requirements.

## Human Interface

https://start.magi.website/browse
`;

export async function onRequestGet(context: {
  request: Request;
}): Promise<Response> {
  return textResponse(BODY.trim() + "\n", "text/markdown", {
    etag: makeEtag(BODY),
    ifNoneMatch: context.request.headers.get("If-None-Match"),
    // Per docs/tfi_seo_optimization.md §19 — /agents.md is an
    // Agent-discovery resource, not a search landing page.
    noindex: true,
  });
}
