// GET /api/v1/models/{id}/{rest...}
//
// OpenAI-compatible detail endpoint using Pages Functions' double-
// bracket rest pattern. ``[id]`` matches the first path segment
// after ``/api/v1/models/`` and ``[[rest]]`` matches the remainder,
// so a model_id like ``z-ai/glm-5.3-flash`` arrives as
// id="z-ai" + rest="glm-5.3-flash" (we join with "/").
//
// The first file name ([id]) is matched even when the rest is empty,
// but if no [[rest]] file exists in the directory Pages Functions
// 404s on the bare-detail path. We handle that case by also
// defining an index.ts in [id]/ that catches ``/api/v1/models/{id}``
// (one segment, no rest).

import { loadFullCatalog, findEndpoint } from "../../../../lib/catalog";
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

export async function onRequestGet(context: {
  request: Request;
  env: Env;
  params: { id: string; rest?: string };
}): Promise<Response> {
  const id = context.params.id;
  const rest = context.params.rest || "";
  const fullId = rest ? `${id}/${rest}` : id;
  if (!fullId) {
    return notFound("model id is required");
  }

  const endpoints = await loadEndpoints(context.env);
  const endpoint = findEndpoint(endpoints, fullId);
  if (!endpoint) {
    return notFound(`model not found: ${fullId}`);
  }
  return jsonResponse(toPublicModel(endpoint));
}
