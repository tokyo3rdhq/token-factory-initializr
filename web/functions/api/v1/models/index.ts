// GET /api/v1/models
//
// OpenAI-compatible list endpoint. Detail (single + multi-segment)
// lives in [id]/index.ts and [id]/[[rest]].ts respectively.

import { loadFullCatalog } from "../../../lib/catalog";
import {
  filterEndpoints,
  parseFilters,
  publicListResponse,
} from "../../../lib/filter";
import { invalidRequest, jsonResponse } from "../../../lib/errors";
import { toPublicModels } from "../../../lib/projection";
import { FIXTURE_PROVIDERS } from "../../../lib/fixtures";
import type { Env, ModelEndpoint } from "../../../lib/kv";

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
}): Promise<Response> {
  const url = new URL(context.request.url);

  const parsed = parseFilters(url.searchParams);
  if ("error" in parsed) {
    return invalidRequest(
      parsed.error.message,
      parsed.error.param,
      parsed.error.code
    );
  }

  const endpoints = await loadEndpoints(context.env);
  const filtered = filterEndpoints(endpoints, parsed);
  return jsonResponse(publicListResponse(toPublicModels(filtered)));
}
