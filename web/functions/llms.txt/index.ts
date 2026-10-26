// GET /llms.txt
//
// Agent-discovery endpoint per docs
// tfi_agent_friendly_model_catalog_api.md §23. Short, machine-
// readable pointer to TFI's machine-readable entry points — NOT
// a copy of the marketing website copy. Agents land here, scan
// the URLs, and follow the one they need.
//
// Stable ETag (weak validator on the literal body) so clients can
// cheaply revalidate without re-downloading the whole file. The
// text is hand-authored and only changes when the spec evolves.

import { makeEtag, textResponse } from "../lib/errors";

const BODY = `# Token Factory Initializr

TFI is an AI model catalog and Token Factory configuration generator.

## API

The public API is read-only and does not require authentication.

Base URL: \`https://start.magi.website\`

### Model Catalog

Machine-readable model catalog:

https://start.magi.website/api/v1/models

The API is OpenAI-compatible and does not require authentication.

### Filter Semantics

When multiple values are passed in a single dimension, they are
combined with **OR**. When multiple dimensions are combined, they are
joined with **AND**.

\`\`\`
?data_source=nvidia,amd
   → data_source IN ["nvidia", "amd"]

?provider=groq,together
   → provider IN ["groq", "together"]

?capabilities=chat,vision
   → capabilities contains "chat" AND "vision"

?supported_parameters=streaming
   → supported_parameters contains "streaming"

?pricing_status=free,paid
   → pricing_status IN ["free", "paid"] (endpoint-scoped)

?data_source=nvidia&capabilities=vision
   → (data_source == "nvidia") AND (capabilities contains "vision")
\`\`\`

### Model Details

Retrieve a specific model:

https://start.magi.website/api/v1/models/{model_id}

Model IDs may contain \`/\`. The model detail response embeds an
\`endpoints\` array — one record per provider endpoint serving the
model, each with its own \`provider\`, \`model_id\`, endpoint-specific
\`free\` status, \`pricing_status\` (\`free\`/\`paid\`/\`unknown\`),
and optional \`pricing\`. There is no model-level
same model may be free on one provider and paid on another.

### Provider Catalog

List every known provider (NVIDIA, AMD, Groq, OpenRouter, Together,
…) and their public metadata (display name, protocol, docs link):

https://start.magi.website/api/v1/providers
https://start.magi.website/api/v1/providers/{id}

### Endpoint Catalog

List every runtime access point. Each endpoint exposes the public
base URL + protocol + authentication requirement (never the
credential itself) + status + limits + the model ids it serves:

https://start.magi.website/api/v1/endpoints
https://start.magi.website/api/v1/endpoints/{id}

Useful filter:

\`\`\`
?model_id=meta-llama/Llama-3.3-70B-Instruct
   → every endpoint serving that model
\`\`\`

### Configuration Generation

TFI generates short-lived configuration artifacts for AI gateways and
tools from your model selection. Supported output formats:

- **LiteLLM** — model_list: YAML fragment with litellm_params entries.
- **NewAPI** — flat models[] array with { id, name } entries.
- **Bifrost** — config.json with a providers map; each provider has a
  keys[] array of { name, value, models, weight } entries.
- **Magpie** — strict-JSON provider configuration (providers[]) with
  per-provider key (intentionally empty; set by you in Magpie),
  pickedFrom (full catalog per data source), models (your selection),
  and chat (endpoint base URL). API key fields are intentionally left
  empty and must be configured by you in Magpie.

Generated artifacts live at https://start.magi.website/generated/{id} and
expire after 5 minutes by design. Share the URL with an agent or paste it
into your gateway configuration manually.

### Human Interface

https://start.magi.website/browse
`;

export async function onRequestGet(context: {
  request: Request;
}): Promise<Response> {
  return textResponse(BODY.trim() + "\n", "text/plain", {
    etag: makeEtag(BODY),
    ifNoneMatch: context.request.headers.get("If-None-Match"),
    // Per docs/tfi_seo_optimization.md §19 — /llms.txt is an
    // Agent-discovery resource, not a search landing page.
    noindex: true,
  });
}
