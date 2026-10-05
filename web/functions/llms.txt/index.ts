// GET /llms.txt
//
// Agent-discovery endpoint per docs
// tfi_agent_friendly_model_catalog_api.md §23. Short, machine-
// readable pointer to TFI's machine-readable entry points — NOT
// a copy of the marketing website copy. Agents land here, scan
// the URLs, and follow the one they need.

import { textResponse } from "../lib/errors";

const BODY = `# Token Factory Initializr

TFI is an AI model catalog and Token Factory configuration generator.

## Model Catalog

Machine-readable model catalog:

https://start.magi.website/api/v1/models

The API is OpenAI-compatible and does not require authentication.

## Model Filtering

Filter by data source:

https://start.magi.website/api/v1/models?data_source=nvidia

Filter by provider:

https://start.magi.website/api/v1/models?provider=groq

Filter by capabilities:

https://start.magi.website/api/v1/models?capabilities=chat,vision

Multiple filters can be combined.

## Model Details

Retrieve a specific model:

https://start.magi.website/api/v1/models/{model_id}

Model IDs may contain \`/\`.

## Human Interface

https://start.magi.website/browse
`;

export async function onRequestGet(): Promise<Response> {
  return textResponse(BODY.trim() + "\n", "text/plain");
}
