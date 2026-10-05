// Shared KV access for Pages Functions.
//
// Pages Functions have a binding ``TFI_KV`` declared in wrangler.toml
// that maps to the same KV namespace the Python data pipeline writes
// to. The KV key shape mirrors ``data/storage/cloudflare_kv.py``:
//
//   tfi:providers:<data_source>:latest           per-source provider manifest
//   tfi:models:<data_source>:<provider>:latest   per-(data_source, provider) model catalog
//   tfi:manifest:latest                          aggregated manifest
//   tfi:manifest:YYYY-MM-DD                      dated manifest
//   tfi:gen:<id>                                 generated artifact (5-min TTL)
//
// Refactor: data_source_provider_refactor.md §17 / §18 / §19.
// The legacy ``tfi:models:<provider>:latest`` keys are no longer
// written by the pipeline; this module reads through the new
// (data_source, provider) namespace exclusively — see
// ``loadProviderModels`` + ``loadProviderManifest``.
//
// The runtime injects the binding through the Pages Functions
// ``env`` argument — this module is the only place that knows the
// binding name, so rename it here if the binding ever changes.

export interface Env {
  TFI_KV: KVNamespace;
  TFI_TTL_SECONDS?: string;
  TFI_USE_LOCAL_FIXTURES?: string;
}

export interface ModelEndpoint {
  data_source: string;
  provider: string;
  model_id: string;
  name: string | null;
  description: string | null;
  free: boolean;
  capabilities: Record<string, unknown>;
  architecture: { input: string[]; output: string[] } | null;
  lab: string | null;
  metadata: Record<string, unknown>;
  fetched_at: string;
  context_length?: number | null;
  pricing?: Record<string, unknown> | null;
}

export interface ProviderSnapshot {
  data_source: string;
  provider: string;
  /** ISO 8601 timestamp of when this catalog snapshot was written.
   *  Optional — the Python pipeline writes it but legacy fixtures
   *  (and older snapshots) may not have it. */
  fetched_at?: string;
  models: ModelEndpoint[];
}

export interface ProviderManifest {
  data_source: string;
  providers: string[];
  generated_at: string;
}

export interface Manifest {
  version: string;
  generated_at: string;
  total: number;
  providers: Record<
    string,
    {
      data_source: string;
      count: number;
      status: "success" | "partial" | "failed" | "invalid";
      last_success?: string;
      error?: string;
      /** ISO timestamp when this provider's catalog was last PUT to KV.
       * Optional because older manifest records (pre-provenance-rewrite)
       * may not carry the field yet. */
      generated_at?: string;
    }
  >;
}

export interface GeneratedArtifact {
  id: string;
  created_at: number;
  expires_at: number;
  models: ProviderSnapshot["models"];
  config_yaml: string;
  format: string;
}

const TTL_SECONDS_DEFAULT = 300;

// Known data sources — kept in sync with data/storage/cloudflare_kv.py
// KNOWN_DATA_SOURCES so the manifest reader can enumerate every
// pipeline source (including ones whose manifest has never been
// written).
const KNOWN_DATA_SOURCES = ["nvidia", "amd", "huggingface"] as const;

// ---------------------------------------------------------------------------
// Manifest / catalog readers — (data_source, provider) namespace
// ---------------------------------------------------------------------------

export async function loadProviderManifest(
  env: Env,
  dataSource: string
): Promise<ProviderManifest | null> {
  const raw = await env.TFI_KV.get(`tfi:providers:${dataSource}:latest`);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as ProviderManifest;
  } catch {
    return null;
  }
}

export async function loadProviderModels(
  env: Env,
  dataSource: string,
  provider: string
): Promise<ProviderSnapshot | null> {
  const raw = await env.TFI_KV.get(
    `tfi:models:${dataSource}:${provider}:latest`
  );
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as ProviderSnapshot;
  } catch {
    return null;
  }
}

export async function loadManifest(env: Env): Promise<Manifest | null> {
  // The aggregated ``tfi:manifest:latest`` keeps the legacy shape
  // (provider → count/status) for back-compat with /api/manifest.
  // The new (data_source, provider) manifests at
  // ``tfi:providers:<ds>:latest`` are the source of truth.
  const raw = await env.TFI_KV.get("tfi:manifest:latest");
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as Manifest;
  } catch {
    return null;
  }
}

/**
 * Enumerate every (data_source, provider) pair currently published.
 *
 * Refactor §18: the access pattern is
 *   1. read per-source provider manifest
 *   2. enumerate active providers
 *   3. read each per-provider catalog
 *
 * Returns a flat array of tuples. The caller (typically
 * /api/models?all=1) maps each tuple to a per-provider catalog
 * fetch.
 */
export async function listAllProviderPairs(
  env: Env
): Promise<Array<{ data_source: string; provider: string }>> {
  const pairs: Array<{ data_source: string; provider: string }> = [];
  for (const ds of KNOWN_DATA_SOURCES) {
    const manifest = await loadProviderManifest(env, ds);
    if (!manifest) continue;
    for (const provider of manifest.providers) {
      pairs.push({ data_source: ds, provider });
    }
  }
  return pairs;
}

/**
 * Enumerate providers (legacy single-level shape — preserved for
 * back-compat with /api/providers which the web UI still polls).
 *
 * Returns provider identifiers with the data source encoded as a
 * ``<data_source>/<provider>`` tuple string when the new shape is
 * available; falls back to the canonical list
 * (``nvidia``, ``amd``, ``huggingface``) when no manifests exist
 * yet so the UI still renders the right tabs.
 */
export async function listProviders(env: Env): Promise<string[]> {
  const pairs = await listAllProviderPairs(env);
  if (pairs.length === 0) {
    // KV empty / no manifest yet — fall back to the canonical list so
    // the UI at least renders the right tabs even when the data
    // pipeline hasn't run.
    return ["nvidia", "amd", "huggingface"];
  }
  return pairs.map((p) => `${p.data_source}/${p.provider}`);
}

// ---------------------------------------------------------------------------
// Generated artifact store (5-minute TTL) — unchanged from the legacy
// namespace; the artifact payload is opaque to the pipeline.
// ---------------------------------------------------------------------------

export async function saveGenerated(
  env: Env,
  artifact: GeneratedArtifact
): Promise<void> {
  const ttl = Number(env.TFI_TTL_SECONDS) || TTL_SECONDS_DEFAULT;
  // The TTL argument is a Cloudflare KV feature; the worker runtime
  // accepts an expirationTtl. We still embed ``expires_at`` so the
  // page-side React UI can show a "this URL expires in N seconds"
  // countdown without parsing the raw KV TTL.
  await env.TFI_KV.put(
    `tfi:gen:${artifact.id}`,
    JSON.stringify(artifact),
    { expirationTtl: ttl }
  );
}

export async function loadGenerated(
  env: Env,
  id: string
): Promise<GeneratedArtifact | null> {
  if (!/^[A-Za-z0-9_-]{6,32}$/.test(id)) {
    return null;
  }
  const raw = await env.TFI_KV.get(`tfi:gen:${id}`);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as GeneratedArtifact;
  } catch {
    return null;
  }
}