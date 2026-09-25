// POST /api/generate
//
// Body: { model_ids: Array<{provider, model_id}>, format?: string }
// Returns: { id, url, expires_at, yaml }
//
// Validates the requested models against the current KV catalog
// (or the bundled fixtures when ``TFI_USE_LOCAL_FIXTURES=1``),
// generates a LiteLLM YAML for them, stores the artifact with a
// 5-minute TTL, and returns a public URL the user can share.

import {
  loadProviderSnapshot,
  saveGenerated,
  type Env,
  type ModelEndpoint,
} from "../lib/kv";
import { FIXTURE_PROVIDERS } from "../lib/fixtures";
import {
  generateAgentPrompt,
  generateId,
  generateLiteLLM,
} from "../lib/litellm";

interface GenerateRequest {
  model_ids: Array<{ provider: string; model_id: string }>;
  format?: string;
}

const MAX_MODELS = 50;
const TTL_SECONDS_DEFAULT = 300;

export async function onRequestPost(context: {
  request: Request;
  env: Env;
}): Promise<Response> {
  let body: GenerateRequest;
  try {
    body = (await context.request.json()) as GenerateRequest;
  } catch {
    return jsonError(400, "request body must be JSON");
  }

  if (!Array.isArray(body.model_ids) || body.model_ids.length === 0) {
    return jsonError(400, "model_ids must be a non-empty array");
  }
  if (body.model_ids.length > MAX_MODELS) {
    return jsonError(
      400,
      `too many models in one config (limit ${MAX_MODELS})`
    );
  }
  const format = body.format ?? "litellm";
  if (format !== "litellm") {
    return jsonError(400, `unsupported format: ${format}`);
  }

  // Pull provider snapshots either from KV (production) or the bundled
  // fixtures (local dev). Either way the downstream lookup is
  // identical.
  const snapshots = context.env.TFI_USE_LOCAL_FIXTURES === "1"
    ? FIXTURE_PROVIDERS
    : await loadAllFromKV(context.env);

  // Look up each requested endpoint by ``provider::model_id``.
  const index = new Map<string, ModelEndpoint>();
  for (const snap of snapshots) {
    for (const ep of snap.models) {
      index.set(`${ep.provider}::${ep.model_id}`, ep);
    }
  }

  const resolved: ModelEndpoint[] = [];
  const missing: string[] = [];
  for (const req of body.model_ids) {
    const ep = index.get(`${req.provider}::${req.model_id}`);
    if (ep) resolved.push(ep);
    else missing.push(`${req.provider}/${req.model_id}`);
  }
  if (missing.length > 0) {
    return jsonError(
      400,
      `unknown model ids: ${missing.join(", ")} (catalog changed?)`
    );
  }

  const ttl = Number(context.env.TFI_TTL_SECONDS) || TTL_SECONDS_DEFAULT;
  const id = generateId();
  const now = Date.now();
  const yaml = generateLiteLLM({ models: resolved });

  await saveGenerated(context.env, {
    id,
    created_at: now,
    expires_at: now + ttl * 1000,
    models: resolved,
    config_yaml: yaml,
    format,
  });

  const url = new URL(context.request.url);
  const publicUrl = `${url.origin}/generated/${id}`;

  return json({
    id,
    url: publicUrl,
    expires_at: now + ttl * 1000,
    yaml,
    agent_prompt: generateAgentPrompt(publicUrl),
  });
}

async function loadAllFromKV(
  env: Env
): Promise<{ provider: string; models: ModelEndpoint[] }[]> {
  const providers = ["nvidia", "amd", "huggingface"];
  const results = await Promise.all(
    providers.map((p) => loadProviderSnapshot(env, p))
  );
  return results.filter((s): s is NonNullable<typeof s> => s !== null);
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