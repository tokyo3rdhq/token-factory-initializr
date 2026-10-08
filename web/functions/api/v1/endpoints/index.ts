// GET /api/v1/endpoints
//
// Per docs/tfi_provider_and_endpoint_intelligence_api.md §7 + §22 +
// §24. Public read-only endpoint list. Each entry exposes the
// runtime access point (base URL + protocol + authentication
// requirement) but never credentials, secrets, or internal Cloudflare
// URLs (per §38).
//
// Filters: provider, data_source, protocol, status, model_id.
// OR-within-dimension / AND-across-dimensions, same convention as
// /api/v1/models.
//
// ETag-based revalidation: weak ETag derived from the response
// body. 304 Not Modified supported via If-None-Match.

import { loadIndexes } from "../../../lib/endpoints";
import {
  filterPublicEndpoints,
  parseEndpointFilters,
} from "../../../lib/filter";
import {
  jsonResponse,
  invalidRequest,
  makeEtag,
} from "../../../lib/errors";
import { publicListOf } from "../../../lib/projection";
import { isInternalDataSource } from "../../../lib/internal";
import type { Env } from "../../../lib/kv";

export async function onRequestGet(context: {
  request: Request;
  env: Env;
}): Promise<Response> {
  const url = new URL(context.request.url);
  const parsed = parseEndpointFilters(url.searchParams);
  if (!parsed.ok) {
    return invalidRequest(
      "filter must be a non-empty csv",
      parsed.param,
      "invalid_filter",
    );
  }

  const { endpoints } = await loadIndexes(context.env);
  // Internal cross-source data sources (openrouter, models_dev) are
  // not consumer-facing endpoints — hide from public list.
  const consumerEndpoints = endpoints.filter(
    (e) => !isInternalDataSource(e.data_source),
  );

  const filtered = filterPublicEndpoints(consumerEndpoints, parsed.filters);
  const body = publicListOf(filtered);
  const json = JSON.stringify(body);
  return jsonResponse(body, {
    etag: makeEtag(json),
    ifNoneMatch: context.request.headers.get("If-None-Match"),
  });
}
