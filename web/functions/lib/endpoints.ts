// Build, list, and look up the public provider/endpoint indexes from
// the canonical (data_source, provider) catalog.
//
// Per docs/tfi_provider_and_endpoint_intelligence_api.md §20, every
// endpoint must reference exactly one provider and exactly one
// data_source. The current catalog is 1-to-1 between
// (data_source, provider) and endpoint, so we collapse them — but
// the model stays extensible: if a future provider has multiple
// endpoints under one (data_source, provider) pair (e.g. regional
// deployments), the ``endpointName`` override on ``toPublicEndpoint``
// supports it without breaking existing IDs.
//
// Storage: derived on-demand from the existing model catalog at
// /api/v1/* read time. No second KV key shape is introduced
// (per spec §28, §42 — reuse existing storage; do not create a
// second storage convention).

import { loadFullCatalog, type CatalogLoadResult } from "./catalog";
import {
  toPublicProvider,
  toPublicEndpoint,
  type PublicProvider,
  type PublicEndpoint,
} from "./projection";
import type { Env } from "./kv";
import { FIXTURE_PROVIDERS } from "./fixtures";

export interface IndexBuildResult {
  providers: PublicProvider[];
  endpoints: PublicEndpoint[];
  /** Lookup by endpoint id (e.g. "groq:default"). Single source of
   *  truth for both list and detail endpoints. */
  endpointById: Map<string, PublicEndpoint>;
  /** Lookup by provider id (e.g. "groq"). */
  providerById: Map<string, PublicProvider>;
  /** For the model backref: model_id -> endpoint ids. Built
   *  alongside the endpoints so the projection layer doesn't have
   *  to re-scan. */
  modelsByEndpoint: Map<string, string[]>;
}

/** Build the public provider + endpoint indexes from the canonical
 *  catalog. Pure function — no I/O, no env — so it's trivially
 *  unit-testable. */
export function buildIndexes(
  catalog: CatalogLoadResult,
): IndexBuildResult {
  // Group model_ids by (data_source, provider). Each unique pair
  // becomes one PublicEndpoint.
  const modelsByPair = new Map<string, string[]>();
  for (const ep of catalog.endpoints) {
    const key = `${ep.data_source}|${ep.provider}`;
    let arr = modelsByPair.get(key);
    if (!arr) {
      arr = [];
      modelsByPair.set(key, arr);
    }
    arr.push(ep.model_id);
  }

  const providerSet = new Map<string, { data_source: string; provider: string }>();
  for (const [k] of modelsByPair) {
    const [ds, provider] = k.split("|", 2);
    // First occurrence wins; keying on (data_source, provider) means
    // we get exactly one entry per pair.
    providerSet.set(`${ds}|${provider}`, { data_source: ds, provider });
  }

  const providers: PublicProvider[] = [];
  const providerById = new Map<string, PublicProvider>();
  const endpoints: PublicEndpoint[] = [];
  const endpointById = new Map<string, PublicEndpoint>();

  // Stable order: data_source first, then provider, both alphabetical.
  const sortedPairs = [...providerSet.values()].sort((a, b) => {
    if (a.data_source !== b.data_source) return a.data_source < b.data_source ? -1 : 1;
    return a.provider < b.provider ? -1 : 1;
  });

  for (const { data_source, provider } of sortedPairs) {
    // Provider entry.
    const pub = toPublicProvider(data_source, provider);
    providers.push(pub);
    providerById.set(provider, pub);

    // Endpoint entry.
    const modelIds = modelsByPair.get(`${data_source}|${provider}`) ?? [];
    const ep = toPublicEndpoint(data_source, provider, modelIds);
    endpoints.push(ep);
    endpointById.set(ep.id, ep);
  }

  // Build the model_id -> endpoint ids index. Single scan.
  const modelsByEndpoint = new Map<string, string[]>();
  for (const ep of endpoints) {
    if (!ep.models) continue;
    for (const m of ep.models) {
      let arr = modelsByEndpoint.get(m);
      if (!arr) {
        arr = [];
        modelsByEndpoint.set(m, arr);
      }
      arr.push(ep.id);
    }
  }

  return { providers, endpoints, endpointById, providerById, modelsByEndpoint };
}

/** Load the canonical catalog and build the public indexes. The
 *  ``FIXTURE_PROVIDERS`` short-circuit mirrors the same pattern in
 *  /api/v1/models — the ``TFI_USE_LOCAL_FIXTURES=1`` env flag
 *  forces local-fixture mode for development. */
export async function loadIndexes(env: Env): Promise<IndexBuildResult> {
  if (env.TFI_USE_LOCAL_FIXTURES === "1") {
    return buildIndexes({
      endpoints: FIXTURE_PROVIDERS.flatMap((s) => s.models),
      snapshots: FIXTURE_PROVIDERS,
      pairs: FIXTURE_PROVIDERS.map((s) => ({
        data_source: s.data_source,
        provider: s.provider,
      })),
    });
  }
  const catalog = await loadFullCatalog(env);
  return buildIndexes(catalog);
}
