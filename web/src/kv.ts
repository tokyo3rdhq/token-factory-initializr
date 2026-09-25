// KV reader for the React UI.
//
// Pages Functions live in a separate runtime (Cloudflare Workers)
// and have direct access to the TFI_KV binding. The browser-side
// React app does NOT have direct KV access — it talks to the
// Pages Functions via fetch. So this module is a thin client for
// those endpoints, NOT a KV reader.
//
// What this module does:
//   * fetch JSON from /api/manifest, /api/providers, /api/models,
//     /api/generate, /generated/{id}, etc.
//   * Provide a graceful "offline mode" fallback to a bundled
//     fixture (web/src/data/fixtures.json) when /api/* 503s or the
//     fetch fails. The data pipeline may not have run yet (KV empty)
//     and the developer should still be able to navigate the UI.
//
// The contract for each helper is:
//   * returns the parsed JSON on 2xx
//   * throws an Error on 4xx/5xx
//   * fallback happens only when the env var TFI_USE_LOCAL_FIXTURES is
//     explicitly set to "1" — the worker runtime passes that value
//     via /api/manifest?fallback=1 so we don't silently serve stale
//     data in production.
//
// We keep this module tiny — no caching, no retries. The Pages
// Functions layer handles KV caching.

import type { Manifest, ProviderSnapshot } from "./types";

const BASE = ""; // same-origin (Pages Functions)

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(
      `${res.status} ${res.statusText} for ${path}: ${text.slice(0, 200)}`
    );
  }
  return (await res.json()) as T;
}

export async function fetchManifest(): Promise<Manifest> {
  return jsonFetch<Manifest>("/api/manifest");
}

export async function fetchProviders(): Promise<string[]> {
  return jsonFetch<string[]>("/api/providers");
}

export async function fetchModels(
  provider?: string
): Promise<ProviderSnapshot[]> {
  const qs = provider ? `?provider=${encodeURIComponent(provider)}` : "";
  return jsonFetch<ProviderSnapshot[]>(`/api/models${qs}`);
}

export async function fetchGenerated(id: string): Promise<{
  id: string;
  config_yaml: string;
  format: string;
  expires_at: number;
  model_count: number;
}> {
  return jsonFetch(`/api/generated/${encodeURIComponent(id)}`);
}

export interface GenerateRequest {
  model_ids: Array<{ provider: string; model_id: string }>;
  format?: string;
}

export interface GenerateResponse {
  id: string;
  url: string;
  expires_at: number;
  yaml: string;
}

export async function postGenerate(
  req: GenerateRequest
): Promise<GenerateResponse> {
  const resp = await jsonFetch<GenerateResponse>("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return resp;
}

// ---------------------------------------------------------------------------
// Local-fixture fallback (browser-side only)
// ---------------------------------------------------------------------------
//
// Used when /api/* is unreachable (e.g. fresh clone before the data
// pipeline has run, or local dev with KV empty). The fixture is a
// static JSON file shipped with the build; it carries a small subset
// of real provider endpoints so the UI renders meaningfully without
// needing network/KV access. Production builds default to NOT using
// the fallback (TFI_USE_LOCAL_FIXTURES=0) so a 404 from the API
// surfaces as a real error rather than masking infrastructure
// breakage with stale data.

import rawFixtures from "./data/fixtures.json";

export const FIXTURES: {
  manifest: Manifest;
  providers: string[];
  models: ProviderSnapshot[];
} = rawFixtures as never;

export function shouldUseLocalFixtures(envFlag: string | undefined): boolean {
  return envFlag === "1";
}