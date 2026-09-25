// GET /api/generated/{id}
//
// Returns the JSON metadata for a generated artifact: id,
// expires_at, model_count, format, config_yaml. The TTL is
// enforced by the Pages Function itself (KV stores a 5-minute
// expirationTtl); once the artifact is gone, this returns 404.

import { loadGenerated, type Env } from "../../lib/kv";

export async function onRequestGet(context: {
  request: Request;
  env: Env;
  params: { id: string };
}): Promise<Response> {
  const id = context.params.id;
  const art = await loadGenerated(context.env, id);
  if (!art) {
    return jsonError(404, "artifact not found or expired");
  }
  if (art.expires_at <= Date.now()) {
    // KV may have returned the value because the key still exists in
    // the metadata layer (KV expirationTtl is best-effort, not
    // strict). Honor the embedded expires_at for safety.
    return jsonError(410, "artifact expired");
  }
  return json({
    id: art.id,
    expires_at: art.expires_at,
    model_count: art.models.length,
    format: art.format,
    config_yaml: art.config_yaml,
  });
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