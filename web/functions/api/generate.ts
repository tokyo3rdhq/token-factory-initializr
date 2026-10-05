// POST /api/generate
//
// Body: { model_ids: Array<{ data_source, provider, model_id }>, format?: "litellm" | "newapi" }
// Returns: { id, url, expires_at, format, content }
//
// Validates the requested models against the current KV catalog
// (or the bundled fixtures when ``TFI_USE_LOCAL_FIXTURES=1``),
// dispatches to the right Token Factory generator (per
// docs/tfi_phase_1_initializr_core_workflow.md §4 — model selection
// is independent from Token Factory implementation), stores it with
// a 5-minute TTL, and returns a public URL the user can share.

import {
  listAllProviderPairs,
  loadProviderModels,
  saveGenerated,
  type Env,
  type ModelEndpoint,
} from "../lib/kv";
import { FIXTURE_PROVIDERS } from "../lib/fixtures";
import { generateId } from "../lib/litellm";
import {
  buildAgentPrompt,
  generateWith,
  SUPPORTED_TOKEN_FACTORIES,
  type TokenFactoryId,
} from "../lib/generators";
import { GeneratorError } from "../lib/generators/types";

interface GenerateRequest {
  model_ids: Array<{ data_source?: string; provider: string; model_id: string }>;
  format?: TokenFactoryId;
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
    return jsonError(400, `at most ${MAX_MODELS} models per request`);
  }

  // Resolve Token Factory. Per doc §4 — the format MUST be selected
  // by the user (it is not inferred from the model selection). If the
  // request doesn't carry it we still accept the legacy "litellm"
  // default but a Phase-2 follow-up should require it explicitly.
  const requestedFormat = body.format ?? "litellm";
  if (!SUPPORTED_TOKEN_FACTORIES.includes(requestedFormat)) {
    return jsonError(
      400,
      `unsupported format: ${requestedFormat}. Supported: ${SUPPORTED_TOKEN_FACTORIES.join(", ")}`,
    );
  }

  // Pull (data_source, provider) snapshots either from KV (production)
  // or the bundled fixtures (local dev). Either way the downstream
  // lookup is identical.
  const snapshots = context.env.TFI_USE_LOCAL_FIXTURES === "1"
    ? FIXTURE_PROVIDERS
    : await loadAllFromKV(context.env);

  // Index by (data_source, provider, model_id).
  const index = new Map<string, ModelEndpoint>();
  for (const snap of snapshots) {
    for (const ep of snap.models) {
      const ds = ep.data_source || snap.data_source || "";
      const key = ds
        ? `${ds}::${ep.provider}::${ep.model_id}`
        : `${ep.provider}::${ep.model_id}`;
      index.set(key, ep);
    }
  }

  const resolved: ModelEndpoint[] = [];
  const missing: string[] = [];
  for (const req of body.model_ids) {
    let ep = req.data_source
      ? index.get(`${req.data_source}::${req.provider}::${req.model_id}`)
      : undefined;
    if (!ep) {
      ep = index.get(`${req.provider}::${req.model_id}`);
    }
    if (ep) {
      resolved.push(ep);
    } else {
      missing.push(
        `${req.data_source ? req.data_source + "/" : ""}${req.provider}/${req.model_id}`,
      );
    }
  }
  if (missing.length > 0) {
    return jsonError(404, `unknown models: ${missing.join(", ")}`);
  }

  // Dispatch to the right Token Factory generator.
  //
  // Domain-level validation (§9):
  //   - selectedModels.length > 0   → enforced by the generator
  //   - tokenFactory !== null      → enforced above (defaulted here;
  //                                  client picker should require an
  //                                  explicit choice).
  const ttl = Number(context.env.TFI_TTL_SECONDS) || TTL_SECONDS_DEFAULT;
  const id = generateId();
  const now = Date.now();
  const publicBase = new URL(context.request.url).origin;
  const generatedUrl = `${publicBase}/generated/${id}`;

  let generated;
  try {
    generated = generateWith(requestedFormat, resolved, { generatedUrl });
  } catch (e) {
    if (e instanceof GeneratorError) {
      return jsonError(e.status, e.message);
    }
    throw e;
  }

  await saveGenerated(context.env, {
    id,
    created_at: now,
    expires_at: now + ttl * 1000,
    models: resolved,
    config_yaml: generated.content,
    format: generated.format,
  });

  // Per-selection agent prompt — the React result panel surfaces it
  // via the "Agent Prompt" copy button. The prompt is regenerated
  // every time the user clicks Initialize (no server state beyond the
  // KV artifact), so the prompt's selection manifest and the
  // artifact URL stay in sync at all times.
  const agent_prompt = buildAgentPrompt(
    requestedFormat,
    generatedUrl,
    resolved,
  );

  const url = generatedUrl;
  return json({
    id,
    url,
    expires_at: now + ttl * 1000,
    format: generated.format,
    yaml: generated.content,
    agent_prompt,
  });
}

async function loadAllFromKV(env: Env): Promise<
  Array<{ data_source: string; provider: string; models: ModelEndpoint[] }>
> {
  const pairs = await listAllProviderPairs(env);
  const snaps = await Promise.all(
    pairs.map((p) => loadProviderModels(env, p.data_source, p.provider)),
  );
  return snaps
    .filter((s): s is NonNullable<typeof s> => s !== null)
    .map((s) => ({
      data_source: s.data_source,
      provider: s.provider,
      models: s.models,
    }));
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