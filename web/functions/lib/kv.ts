// Shared KV access for Pages Functions.
//
// Pages Functions have a binding ``TFI_KV`` declared in wrangler.toml
// that maps to the same KV namespace the Python data pipeline writes
// to. The KV key shape mirrors ``data/storage/cloudflare_kv.py``:
//
//   tfi:models:<provider>:latest        per-provider model snapshot
//   tfi:models:latest                   aggregated snapshot
//   tfi:manifest:latest                 most recent manifest
//   tfi:manifest:YYYY-MM-DD             dated manifest
//   tfi:gen:<id>                        generated artifact (5-min TTL)
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
  provider: string;
  fetched_at: string;
  models: ModelEndpoint[];
}

export interface Manifest {
  version: string;
  generated_at: string;
  total: number;
  providers: Record<
    string,
    {
      provider: string;
      count: number;
      status: "success" | "partial" | "failed" | "invalid";
      last_success?: string;
      error?: string;
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

// ---------------------------------------------------------------------------
// Snapshot / manifest readers
// ---------------------------------------------------------------------------

export async function loadManifest(env: Env): Promise<Manifest | null> {
  const raw = await env.TFI_KV.get("tfi:manifest:latest");
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as Manifest;
  } catch {
    // Malformed manifest — the data pipeline wrote garbage; surface as
    // a missing manifest rather than a 500 to the UI.
    return null;
  }
}

export async function loadProviderSnapshot(
  env: Env,
  provider: string
): Promise<ProviderSnapshot | null> {
  const raw = await env.TFI_KV.get(`tfi:models:${provider}:latest`);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as ProviderSnapshot;
  } catch {
    return null;
  }
}

export async function listProviders(env: Env): Promise<string[]> {
  const manifest = await loadManifest(env);
  if (manifest) {
    return Object.keys(manifest.providers);
  }
  // KV empty / no manifest yet — fall back to the canonical list so
  // the UI at least renders the right tabs even when the data
  // pipeline hasn't run.
  return ["nvidia", "amd", "huggingface"];
}

// ---------------------------------------------------------------------------
// Generated artifact store (5-minute TTL)
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