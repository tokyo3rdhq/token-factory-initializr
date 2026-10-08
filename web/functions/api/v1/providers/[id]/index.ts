// GET /api/v1/providers/{id}
//
// Per docs/tfi_provider_and_endpoint_intelligence_api.md §6. Returns
// the canonical projection of a single provider. 404 when the id
// is unknown.

import { loadIndexes } from "../../../../lib/endpoints";
import { jsonResponse, notFound } from "../../../../lib/errors";
import { isInternalDataSource } from "../../../../lib/internal";
import type { Env } from "../../../../lib/kv";

export async function onRequestGet(context: {
  request: Request;
  env: Env;
  params: { id: string };
}): Promise<Response> {
  // Cloudflare passes path segments URL-encoded; decode so callers
  // can hit ids containing special characters directly. Idempotent.
  const id = context.params.id ? decodeURIComponent(context.params.id) : "";
  if (!id) {
    return notFound("provider id is required");
  }
  const { providerById } = await loadIndexes(context.env);
  const provider = providerById.get(id);
  if (!provider) {
    return notFound(`provider not found: ${id}`);
  }
  // Internal cross-source providers stay hidden even via direct lookup
  // — they're not consumer-facing.
  if (isInternalDataSource(provider.data_source)) {
    return notFound(`provider not found: ${id}`);
  }
  return jsonResponse(provider);
}
