// GET /api/v1/models
//
// OpenAI-compatible list endpoint for the public Agent-friendly
// model catalog. Per docs tfi_agent_friendly_model_catalog_api.md:
//
//   * Reads the canonical KV catalog — never re-fetches upstream.
//   * Supports ?data_source=, ?provider=, ?capabilities= filters
//     with the AND/OR semantics from §13 of the spec.
//   * Strips provenance, raw payload, internal metadata via
//     toPublicModel() — only canonical, public-safe fields appear.
//   * Sets cache-friendly + CORS headers via jsonResponse().
//
// This route handler lives at /api/v1/models/ but Pages Functions
// resolves the bare path through the parent index file. See
// ``[[id]].ts`` for the detail endpoint.

import { loadFullCatalog } from "../../../lib/catalog";
import {
  filterEndpoints,
  parseFilters,
  publicListResponse,
} from "../../../lib/filter";
import {
  invalidRequest,
  jsonResponse,
} from "../../../lib/errors";
import { toPublicModels } from "../../../lib/projection";
import { FIXTURE_PROVIDERS } from "../../../lib/fixtures";
import type { Env } from "../../../lib/kv";
import type { ModelEndpoint } from "../../../lib/kv";

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

  let endpoints: ModelEndpoint[];
  if (context.env.TFI_USE_LOCAL_FIXTURES === "1") {
    endpoints = FIXTURE_PROVIDERS.flatMap((s) => s.models);
  } else {
    const catalog = await loadFullCatalog(context.env);
    endpoints = catalog.endpoints;
  }

  const filtered = filterEndpoints(endpoints, parsed);
  const projected = toPublicModels(filtered);
  return jsonResponse(publicListResponse(projected));
}

// Some bundlers don't pick up `onRequestGet` from a parent index.ts
// when there's also a sibling `[[id]].ts` file. Exporting a noop
// default is the Pages-Functions convention to keep both routes
// discoverable.
export default function noop() {}
