// GET /api/v1/models/{id}
//
// OpenAI-compatible detail endpoint for a single canonical model.
// The path segment is captured as ``params.id`` and is
// intentionally a REST-style catch-all (Pages Functions' double-
// bracket convention) so model_ids containing ``/`` (e.g.
// ``prism-ml/ternary-bonsai-2-27b``) work without URL encoding.
//
// Per docs tfi_agent_friendly_model_catalog_api.md §7 / §8:
//   * model_id is the canonical id returned by /api/v1/models.
//   * Response is the public model projection — same fields as the
//     list endpoint's items, never provenance.
//   * 404 when the model isn't in the catalog.

import { loadFullCatalog, findEndpoint } from "../../../lib/catalog";
import { jsonResponse, notFound } from "../../../lib/errors";
import { toPublicModel } from "../../../lib/projection";
import { FIXTURE_PROVIDERS } from "../../../lib/fixtures";
import type { Env, ModelEndpoint } from "../../../lib/kv";

export async function onRequestGet(context: {
  request: Request;
  env: Env;
  params: { id: string };
}): Promise<Response> {
  const id = context.params.id;
  if (!id) {
    return notFound("model id is required");
  }

  let endpoints: ModelEndpoint[];
  if (context.env.TFI_USE_LOCAL_FIXTURES === "1") {
    endpoints = FIXTURE_PROVIDERS.flatMap((s) => s.models);
  } else {
    const catalog = await loadFullCatalog(context.env);
    endpoints = catalog.endpoints;
  }

  const endpoint = findEndpoint(endpoints, id);
  if (!endpoint) {
    return notFound(`model not found: ${id}`);
  }
  return jsonResponse(toPublicModel(endpoint));
}
