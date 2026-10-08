// GET /api/v1/providers
//
// Per docs/tfi_provider_and_endpoint_intelligence_api.md §5 + §22.
// Public read-only provider list. Supports the same OR-within-
// dimension / AND-across-dimensions filter semantics as /api/v1/models
// (per §23).
//
// ETag-based revalidation: each response carries a weak ETag
// derived from the response body. Clients send ``If-None-Match`` and
// get ``304 Not Modified`` when the catalog has not changed — same
// pattern as /api/v1/models. Crucial for Agent re-poll workloads.

import { loadIndexes } from "../../../lib/endpoints";
import {
  filterPublicProviders,
  parseProviderFilters,
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
  const parsed = parseProviderFilters(url.searchParams);
  if (!parsed.ok) {
    return invalidRequest(
      "filter must be a non-empty csv",
      parsed.param,
      "invalid_filter",
    );
  }

  const { providers } = await loadIndexes(context.env);
  // Internal cross-source data sources (openrouter, models_dev) are
  // not consumer-facing provider catalogs — hide them from the
  // public list to match the /api/models default listing behaviour.
  const consumerProviders = providers.filter(
    (p) => !isInternalDataSource(p.data_source),
  );

  const filtered = filterPublicProviders(consumerProviders, parsed.filters);
  const body = publicListOf(filtered);
  const json = JSON.stringify(body);
  return jsonResponse(body, {
    etag: makeEtag(json),
    ifNoneMatch: context.request.headers.get("If-None-Match"),
  });
}
