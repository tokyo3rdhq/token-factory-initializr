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

TFI provides a machine-readable model catalog for AI agents.

## Base URL

\`\`\`
https://start.magi.website
\`\`\`

The public API is **read-only** and does not require authentication.

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
| \`?data_source=nvidia&capabilities=chat\` | \`(data_source == "nvidia") AND (capabilities contains "chat")\` |

### Combined Filters

\`\`\`
GET /api/v1/models?data_source=huggingface&capabilities=vision,reasoning
\`\`\`

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
  (\`chat\`, \`vision\`, \`speech\`, \`embedding\`, \`reasoning\`,
  \`tool_calling\`, \`structured_output\`). An **empty array** means
  TFI doesn't currently have capability data for that model — it
  is NOT a statement that the model has no capabilities.

Optional detail fields (model detail response, may be omitted):
\`name\`, \`description\`, \`architecture: {input, output}\`,
\`context_length\`, \`free\`, \`lab\`.

## Provenance

The public API does not expose internal provenance metadata.

## Recommended Agent Workflow

1. Fetch \`/api/v1/models\`.
2. Filter by capability, provider, or data source.
3. Select candidate models.
4. Fetch \`/api/v1/models/{id}\` for detailed metadata.
5. **Use \`/browse\` for human-assisted Token Factory configuration.**
   The public API exposes the model catalog; it does NOT expose the
   Token Factory generator output (\`/generated/{id}\` requires
   human-driven UI interaction today). Assume every model needs
   manual confirmation before being wired into a downstream
   provider, even if the model itself is "free".

## Human Interface

https://start.magi.website/browse
`;

export async function onRequestGet(context: {
  request: Request;
}): Promise<Response> {
  return textResponse(BODY.trim() + "\n", "text/markdown", {
    etag: makeEtag(BODY),
    ifNoneMatch: context.request.headers.get("If-None-Match"),
  });
}
