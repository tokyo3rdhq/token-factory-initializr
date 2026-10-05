// Load the full canonical catalog (every active (data_source,
// provider) pair) into a flat list of endpoints. Used by the
// /api/v1/models list endpoint to avoid duplicating the
// ``listAllProviderPairs → loadProviderModels`` traversal in every
// route handler.
//
// Per docs tfi_agent_friendly_model_catalog_api.md §3.1 the API
// layer must NOT re-fetch upstream sources. This module only
// reads what the Python data pipeline already wrote to KV.

import {
  listAllProviderPairs,
  loadProviderModels,
  type Env,
  type ModelEndpoint,
  type ProviderSnapshot,
} from "./kv";

export interface CatalogLoadResult {
  endpoints: ModelEndpoint[];
  /** Per (data_source, provider) snapshot — kept so the API can
   *  surface the catalog's ``fetched_at`` if needed. */
  snapshots: ProviderSnapshot[];
  /** Pair list for diagnostics; not part of the public response. */
  pairs: Array<{ data_source: string; provider: string }>;
}

/**
 * Load every active catalog from KV. Failed snapshots are skipped
 * silently — the catalog is the union of whatever wrote successfully.
 */
export async function loadFullCatalog(env: Env): Promise<CatalogLoadResult> {
  const pairs = await listAllProviderPairs(env);
  const snapshots = (
    await Promise.all(
      pairs.map((p) =>
        loadProviderModels(env, p.data_source, p.provider)
      )
    )
  ).filter((s): s is ProviderSnapshot => s !== null);
  const endpoints: ModelEndpoint[] = [];
  for (const snap of snapshots) {
    for (const ep of snap.models) {
      endpoints.push(ep);
    }
  }
  return { endpoints, snapshots, pairs };
}

/** Look up a single canonical endpoint by its ``model_id``. */
export function findEndpoint(
  endpoints: ModelEndpoint[],
  modelId: string
): ModelEndpoint | null {
  for (const ep of endpoints) {
    if (ep.model_id === modelId) return ep;
  }
  return null;
}
