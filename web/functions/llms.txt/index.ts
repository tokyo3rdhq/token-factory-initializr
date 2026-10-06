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

?data_source=nvidia&capabilities=vision
   → (data_source == "nvidia") AND (capabilities contains "vision")
\`\`\`

### Model Details

Retrieve a specific model:

https://start.magi.website/api/v1/models/{model_id}

Model IDs may contain \`/\`.

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
