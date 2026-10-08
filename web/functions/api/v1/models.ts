// /api/v1/models
//
// OpenAI-compatible Agent-friendly catalog endpoint
// (docs/tfi_agent_friendly_model_catalog_api.md).
//
// Single-file route handler — Pages Functions' file-based routing
// resolves both:
//   - GET /api/v1/models               → list with optional filters
//   - GET /api/v1/models/{id...}       → detail (id may contain `/`)
//
// (We use a single ``models.ts`` because Pages Functions' catch-all
// ``[[id]].ts`` filename currently emits an unsupported path-to-
// regexp variant — see cloudflare/workers-sdk#13643 — that 500s at
// runtime. A single handler that dispatches off the request URL is
// the portable workaround.)
//
// ETag-based revalidation: each response carries a weak ETag
// derived from the response body. Clients send ``If-None-Match``
// and get ``304 Not Modified`` with no body when the content is
// unchanged. This is critical for the catalog use case where
// Agents may re-poll the list every few minutes — the cost of a
// 304 is a single KV read for the manifest version vs. a full
// catalog re-projection.

import { loadFullCatalog, findEndpoint } from "../../lib/catalog";
import { loadIndexes } from "../../lib/endpoints";
import {
  filterEndpoints,
  parseFilters,
  publicListResponse,
} from "../../lib/filter";
import {
  invalidRequest,
  jsonResponse,
  makeEtag,
  notFound,
} from "../../lib/errors";
import { toPublicModels, toPublicModel } from "../../lib/projection";
import { FIXTURE_PROVIDERS } from "../../lib/fixtures";
import type { Env, ModelEndpoint } from "../../lib/kv";

const BASE = "/api/v1/models";

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
  const path = url.pathname;

  // List endpoint: /api/v1/models (exact) or /api/v1/models/ (trailing
  // slash, equivalent).
  if (path === BASE || path === BASE + "/") {
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
    const { modelsByEndpoint } = await loadIndexes(context.env);
    const body = publicListResponse(
      toPublicModels(filtered, { endpointsByModel: modelsByEndpoint }),
    );
    const json = JSON.stringify(body);
    return jsonResponse(body, {
      etag: makeEtag(json),
      ifNoneMatch: context.request.headers.get("If-None-Match"),
    });
  }

  // Detail endpoint: /api/v1/models/{id...} — the id may contain
  // forward slashes. Strip the BASE prefix and any leading slash to
  // recover the canonical model_id.
  if (path.startsWith(BASE + "/")) {
    const id = decodeURIComponent(path.slice(BASE.length + 1));
    if (!id) {
      return notFound("model id is required");
    }
    const endpoints = await loadEndpoints(context.env);
    const endpoint = findEndpoint(endpoints, id);
    if (!endpoint) {
      return notFound(`model not found: ${id}`);
    }
    const { modelsByEndpoint } = await loadIndexes(context.env);
    const model = toPublicModel(endpoint, { endpointsByModel: modelsByEndpoint });
    const json = JSON.stringify(model);
    return jsonResponse(model, {
      etag: makeEtag(json),
      ifNoneMatch: context.request.headers.get("If-None-Match"),
    });
  }

  // Anything else under this path is a 404.
  return notFound("not found");
}
