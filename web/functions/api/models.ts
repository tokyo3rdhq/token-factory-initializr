// GET /api/models[?provider=<name>]
//
// Returns the per-provider model snapshot(s) as written by the
// Python data pipeline. When ``provider`` is supplied, returns the
// single matching snapshot or 404. Without it, returns every
// provider's snapshot in a list.
//
// Falls back to the bundled fixture when
// ``TFI_USE_LOCAL_FIXTURES=1`` so the React UI has something to
// render even before the data pipeline has populated KV.

import { loadProviderSnapshot, type Env } from "../lib/kv";
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
    const snap = await loadProviderSnapshot(context.env, provider);
    if (!snap) {
      return jsonError(
        404,
        `no snapshot for provider '${provider}' (pipeline not run yet?)`
      );
    }
    return json([snap]);
  }

  const providers = ["nvidia", "amd", "huggingface"];
  const results = await Promise.all(
    providers.map((p) => loadProviderSnapshot(context.env, p))
  );
  return json(results.filter((s) => s !== null));
}

function filterByProvider(
  snaps: typeof FIXTURE_PROVIDERS,
  provider: string | null
): typeof FIXTURE_PROVIDERS {
  if (!provider) return snaps;
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