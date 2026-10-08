// GET /api/v1/endpoints/{id}
//
// Per docs/tfi_provider_and_endpoint_intelligence_api.md §7. The
// endpoint id is ``{provider}:{endpoint_name}`` and never contains
// forward slashes — single-segment routing is sufficient.

import { loadIndexes } from "../../../../lib/endpoints";
import { jsonResponse, notFound } from "../../../../lib/errors";
import { isInternalDataSource } from "../../../../lib/internal";
import type { Env } from "../../../../lib/kv";

export async function onRequestGet(context: {
  request: Request;
  env: Env;
  params: { id: string };
}): Promise<Response> {
  // Endpoint ids contain `:` (e.g. `groq:default`). Cloudflare
  // passes path segments URL-encoded, so we decode here. Idempotent
  // for already-decoded strings.
  const id = context.params.id ? decodeURIComponent(context.params.id) : "";
  if (!id) {
    return notFound("endpoint id is required");
  }
  const { endpointById } = await loadIndexes(context.env);
  const endpoint = endpointById.get(id);
  if (!endpoint) {
    return notFound(`endpoint not found: ${id}`);
  }
  // Internal cross-source endpoints stay hidden.
  if (isInternalDataSource(endpoint.data_source)) {
    return notFound(`endpoint not found: ${id}`);
  }
  return jsonResponse(endpoint);
}
