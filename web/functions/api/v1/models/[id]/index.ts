// GET /api/v1/models/{id}
//
// Single-segment detail endpoint. See [[rest]].ts in this directory
// for the multi-segment case (e.g. ``z-ai/glm-5.3-flash``).

import { loadFullCatalog } from "../../../../lib/catalog";
import { jsonResponse, notFound } from "../../../../lib/errors";
import { toPublicModel } from "../../../../lib/projection";
import { FIXTURE_PROVIDERS } from "../../../../lib/fixtures";
import type { Env, ModelEndpoint } from "../../../../lib/kv";

async function loadEndpoints(env: Env): Promise<ModelEndpoint[]> {
  if (env.TFI_USE_LOCAL_FIXTURES === "1") {
    return FIXTURE_PROVIDERS.flatMap((s) => s.models);
  }
  const catalog = await loadFullCatalog(env);
  return catalog.endpoints;
}

// Inline the single-endpoint lookup to avoid a circular import with
// the [[rest]] sibling handler which also calls findEndpoint.
function findEndpoint(
  endpoints: ModelEndpoint[],
  modelId: string
): ModelEndpoint | null {
  for (const ep of endpoints) {
    if (ep.model_id === modelId) return ep;
  }
  return null;
}

export async function onRequestGet(context: {
  request: Request;
  env: Env;
  params: { id: string };
}): Promise<Response> {
  const id = context.params.id;
  if (!id) {
    return notFound("model id is required");
  }
  const endpoints = await loadEndpoints(context.env);
  const endpoint = findEndpoint(endpoints, id);
  if (!endpoint) {
    return notFound(`model not found: ${id}`);
  }
  return jsonResponse(toPublicModel(endpoint));
}
