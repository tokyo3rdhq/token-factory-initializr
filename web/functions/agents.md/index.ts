// GET /agents.md
//
// Agent-discovery endpoint per docs
// tfi_agent_friendly_model_catalog_api.md §24. A more verbose
// (but still machine-friendly) guide for agents than /llms.txt.
// Describes the API surface, filter semantics, and recommended
// workflow. Does NOT promise functionality that isn't implemented
// yet (e.g. the artifact-generation API is intentionally omitted).

import { textResponse } from "../lib/errors";

const BODY = `# TFI Agent Interface

TFI provides a machine-readable model catalog for AI agents.

## Base URL

\`\`\`
https://start.magi.website
\`\`\`

## Model List

\`\`\`
GET /api/v1/models
\`\`\`

Returns an OpenAI-compatible model list.

No authentication is required.

## Filters

### Data Source

\`\`\`
GET /api/v1/models?data_source=nvidia
\`\`\`

### Provider

\`\`\`
GET /api/v1/models?provider=groq
\`\`\`

### Capabilities

\`\`\`
GET /api/v1/models?capabilities=chat,vision
\`\`\`

Multiple capabilities use AND semantics — every requested capability
must be present.

### Combined Filters

\`\`\`
GET /api/v1/models?data_source=huggingface&capabilities=vision,reasoning
\`\`\`

All different filter dimensions use AND semantics. Multiple values
within one dimension use OR.

## Model Details

\`\`\`
GET /api/v1/models/{id}
\`\`\`

Use the model's \`id\` returned by \`/api/v1/models\`. Model IDs may
contain \`/\` (path is matched as a catch-all).

## Response

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
- \`created\` — unix epoch seconds (0 when unknown)
- \`owned_by\` — data_source label (nvidia, huggingface, …)
- \`data_source\` — same as owned_by
- \`provider\` — provider within the data source
- \`capabilities\` — canonical normalized capability flags

Model detail responses may include additional canonical fields
(name, description, architecture, context_length, free, lab).

## Provenance

The public API does not expose internal provenance metadata.

## Recommended Agent Workflow

1. Fetch \`/api/v1/models\`.
2. Filter by capability, provider, or data source.
3. Select candidate models.
4. Fetch \`/api/v1/models/{id}\` for detailed metadata.
5. Direct the user to the TFI web interface to continue model
   selection and Token Factory configuration when needed.

## Human Interface

https://start.magi.website/browse
`;

export async function onRequestGet(): Promise<Response> {
  return textResponse(BODY.trim() + "\n", "text/markdown");
}
