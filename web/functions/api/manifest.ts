// GET /api/manifest
//
// Returns the latest manifest from KV, or falls back to the
// bundled fixture when ``TFI_USE_LOCAL_FIXTURES=1``. The fixture
// path is for local dev (KV empty before the data pipeline has
// run) — production should always hit live KV.

import { loadManifest, type Env } from "../lib/kv";
import { FIXTURE_MANIFEST_EXPORT } from "../lib/fixtures";

export async function onRequestGet(context: {
  request: Request;
  env: Env;
}): Promise<Response> {
  if (context.env.TFI_USE_LOCAL_FIXTURES === "1") {
    return json(FIXTURE_MANIFEST_EXPORT);
  }
  const manifest = await loadManifest(context.env);
  if (!manifest) {
    return jsonError(404, "manifest not found in KV");
  }
  return json(manifest);
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