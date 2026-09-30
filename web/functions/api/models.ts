// GET /api/models[?provider=<name>]
//
// Returns the per-(data_source, provider) model catalog(s) as
// written by the Python data pipeline.
//
// Query string:
//   ?provider=nvidia          → "nvidia" matched against the full
//                              pair string "<data_source>/<provider>".
//                              Back-compat: bare provider names
//                              (no "/") match data_source AND
//                              provider == the supplied string (so
//                              legacy "?provider=nvidia" still
//                              returns the nvidia/nvidia catalog).
//
// Falls back to the bundled fixture when
// ``TFI_USE_LOCAL_FIXTURES=1`` so the React UI has something to
// render even before the data pipeline has populated KV.

import {
  loadProviderModels,
  listAllProviderPairs,
  type Env,
} from "../lib/kv";
import { FIXTURE_PROVIDERS } from "../lib/fixtures";

export async function onRequestGet(context: {
  request: Request;
  env: Env;
}): Promise<Response> {
  const url = new URL(context.request.url);
  const provider = url.searchParams.get("provider");

  if (context.env.TFI_USE_LOCAL_FIXTURES === "1") {
    return json(filterByProvider(FIXTURE_PROVIDERS, provider));
  }

  if (provider) {
    const snap = await loadSingleProvider(context.env, provider);
    if (!snap) {
      return jsonError(
        404,
        `no snapshot for provider '${provider}' (pipeline not run yet?)`
      );
    }
    return json([snap]);
  }

  // No filter — return every active (data_source, provider) catalog.
  const pairs = await listAllProviderPairs(context.env);
  const results = await Promise.all(
    pairs.map((p) =>
      loadProviderModels(context.env, p.data_source, p.provider)
    )
  );
  return json(results.filter((s) => s !== null));
}

/**
 * Resolve a `provider` query string into a single catalog.
 *
 * Accepts two shapes:
 *   - "<data_source>/<provider>" → straight lookup.
 *   - "<name>" (no slash)         → first match where
 *     (data_source OR provider) == name. Keeps the legacy
 *     `?provider=nvidia` working without an explicit data_source.
 */
async function loadSingleProvider(env: Env, query: string) {
  if (query.includes("/")) {
    const [ds, provider] = query.split("/", 2);
    return loadProviderModels(env, ds, provider);
  }
  // Legacy: bare provider name. Try data_source first then provider.
  const dsFirst = await loadProviderModels(env, query, query);
  if (dsFirst) return dsFirst;
  const pairs = await listAllProviderPairs(env);
  for (const p of pairs) {
    if (p.provider === query) {
      return loadProviderModels(env, p.data_source, p.provider);
    }
  }
  return null;
}

function filterByProvider(
  snaps: typeof FIXTURE_PROVIDERS,
  provider: string | null
): typeof FIXTURE_PROVIDERS {
  if (!provider) return snaps;
  // Fixture entries don't carry data_source yet; match on provider
  // alone for the local-fixture fallback.
  return snaps.filter((s) => s.provider === provider);
}

function json(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
}

function jsonError(status: number, message: string): Response {
  return json({ error: message }, { status });
}