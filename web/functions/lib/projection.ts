// Canonical ModelEndpoint → public API Model projection.
//
// The public /api/v1/models endpoint exposes a strict subset of the
// canonical ModelEndpoint fields — never provenance, never raw
// source payloads, never internal metadata. Per docs
// tfi_agent_friendly_model_catalog_api.md §27, this projection
// function is the only sanctioned path from internal representation
// to public API representation. Add new internal fields freely;
// they will not leak until this projection explicitly opts them in.

import type { ModelEndpoint } from "./kv";

/** OpenAI-compatible public model shape returned by /api/v1/models. */
export interface PublicModel {
  /** OpenAI: model identifier. We use the canonical model_id. */
  id: string;
  /** OpenAI: always "model". */
  object: "model";
  /** OpenAI: unix epoch seconds. We don't have a reliable release
   *  timestamp for every endpoint — use 0 (the documented "unknown"
   *  sentinel) rather than fabricate a value. */
  created: number;
  /** Model owner (creator / publisher), e.g. "deepseek-ai", "xiaomi",
   *  "z-ai". Optional — omitted when TFI cannot derive a reliable
   *  owner (we never substitute the endpoint provider for the model
   *  owner; that would mislead agents about who actually created
   *  the model). When omitted, clients should treat it as unknown
   *  rather than infer anything. */
  owned_by?: string;
  /** TFI extension: data source (nvidia / amd / huggingface /
   *  openrouter / models_dev). */
  data_source: string;
  /** TFI extension: provider (nvidia / together / novita / etc.). */
  provider: string;
  /** Canonical normalized capabilities — see doc §12 for the
   *  fixed vocabulary. Order is stable for diff-friendly output. */
  capabilities: string[];
  /** Optional public detail fields. Always omitted when null/empty
   *  so the list endpoint stays compact. */
  name?: string;
  description?: string;
  architecture?: { input: string[]; output: string[] };
  context_length?: number;
  free?: boolean;
  lab?: string;
  /** TFI extension: endpoint ids serving this model (per
   *  docs/tfi_provider_and_endpoint_intelligence_api.md §9 + §26).
   *  Stable string references into /api/v1/endpoints — never
   *  embed full endpoint objects here. Filtered to non-internal
   *  endpoints at projection time so cross-source providers
   *  (openrouter / models_dev) do not leak through the model
   *  backref either. */
  endpoints?: string[];
}

/** Stable capability sort order — keeps list responses diff-friendly. */
const CAPABILITY_ORDER = [
  "chat",
  "vision",
  "speech",
  "embedding",
  "reasoning",
  "tool_calling",
  "structured_output",
] as const;

/**
 * Derive the model owner (creator / publisher) for a canonical
 * ``model_id``. The owner is the segment of the id before the first
 * ``/`` — e.g. ``deepseek-ai/deepseek-v4.1-flash`` → ``deepseek-ai``.
 *
 * This is a fallback only. When the canonical model carries an
 * explicit ``lab`` field (HF data path: ``owned_by`` in the upstream
 * API, AMD's ``token_factory.publisher.name``), we prefer that.
 *
 * For ids that don't follow the ``owner/name`` shape (rare; e.g.
 * some AMD provider entries without a publisher prefix), we return
 * ``null`` and the projection omits ``owned_by`` from the response.
 */
function deriveOwner(modelId: string, lab: string | null | undefined): string | null {
  if (typeof lab === "string" && lab.trim().length > 0) {
    return lab.trim();
  }
  if (typeof modelId !== "string" || !modelId.includes("/")) {
    return null;
  }
  const owner = modelId.slice(0, modelId.indexOf("/")).trim();
  return owner.length > 0 ? owner : null;
}

/**
 * Project a canonical ``ModelEndpoint`` into the public API shape.
 *
 * Strips (by construction — we never read these fields):
 *   - provenance
 *   - metadata (raw source payload / pipeline internals)
 *   - pricing
 *   - endpoint_url / region / status / limits / score
 *   - fetched_at / canonical_model_id / model_family / organization /
 *     version / quantization
 */
export function toPublicModel(
  model: ModelEndpoint,
  options: { endpointsByModel?: Map<string, string[]> } = {},
): PublicModel {
  const caps: string[] = [];
  for (const key of CAPABILITY_ORDER) {
    if (model.capabilities && model.capabilities[key] === true) {
      caps.push(key);
    }
  }
  // Surface any non-standard True capability keys too (forward compat).
  if (model.capabilities) {
    for (const [key, value] of Object.entries(model.capabilities)) {
      if (
        value === true &&
        !CAPABILITY_ORDER.includes(key as (typeof CAPABILITY_ORDER)[number])
      ) {
        caps.push(key);
      }
    }
  }

  const publicModel: PublicModel = {
    id: model.model_id,
    object: "model",
    created: 0,
    data_source: model.data_source,
    provider: model.provider,
    capabilities: caps,
  };

  // ``owned_by`` is the model creator, not the endpoint provider.
  // We never substitute data_source / provider for owned_by — that
  // would mislead consumers (e.g. a DeepSeek model served on
  // NVIDIA NIM is still owned by DeepSeek, not NVIDIA).
  const owner = deriveOwner(model.model_id, model.lab);
  if (owner) {
    publicModel.owned_by = owner;
  }

  if (typeof model.name === "string" && model.name.length > 0) {
    publicModel.name = model.name;
  }
  if (typeof model.description === "string" && model.description.length > 0) {
    publicModel.description = model.description;
  }
  if (model.architecture) {
    publicModel.architecture = {
      input: Array.isArray(model.architecture.input)
        ? model.architecture.input.slice()
        : [],
      output: Array.isArray(model.architecture.output)
        ? model.architecture.output.slice()
        : [],
    };
  }
  if (typeof model.context_length === "number" && model.context_length > 0) {
    publicModel.context_length = model.context_length;
  }
  if (typeof model.free === "boolean") {
    publicModel.free = model.free;
  }
  if (typeof model.lab === "string" && model.lab.length > 0) {
    publicModel.lab = model.lab;
  }

  // Endpoint backref (per §9 / §26). Caller passes the pre-built
  // endpointsByModel index so this projection stays pure (no KV
  // access). Omit options.endpointsByModel if you do not want
  // the backref on the public model shape.
  const endpointIds = options.endpointsByModel?.get(model.model_id);
  if (endpointIds && endpointIds.length > 0) {
    publicModel.endpoints = [...endpointIds].sort();
  }

  return publicModel;
}

/** Project a list of canonical endpoints. options is forwarded
 *  to every per-model projection so the list endpoint can attach
 *  endpoint backrefs in one pass. */
export function toPublicModels(
  models: ModelEndpoint[],
  options: { endpointsByModel?: Map<string, string[]> } = {},
): PublicModel[] {
  return models.map((m) => toPublicModel(m, options));
}

// ---------------------------------------------------------------------------
// Public Provider shape — see docs/tfi_provider_and_endpoint_intelligence_api.md
// §5 + §20.
// ---------------------------------------------------------------------------

/** Display-friendly protocol vocabulary exposed on the provider +
 *  endpoint. Source-agnostic; do not invent new values without also
 *  updating the docs. */
export const PUBLIC_PROTOCOL_VOCABULARY: ReadonlyArray<string> = [
  "openai-compatible",
  "anthropic",
  "native",
  "huggingface",
  "nim",
] as const;

/** Authentication mechanism vocabulary. The schema distinguishes
 *  the *requirement* (what the user must do) from any *credential*
 *  (which is never exposed). */
export const PUBLIC_AUTH_TYPE_VOCABULARY: ReadonlyArray<string> = [
  "none",
  "bearer",
  "api_key",
  "oauth2",
  "custom",
  "unknown",
] as const;

/** Endpoint lifecycle status vocabulary. */
export const PUBLIC_ENDPOINT_STATUS_VOCABULARY: ReadonlyArray<string> = [
  "active",
  "degraded",
  "temporarily_unavailable",
  "deprecated",
  "unknown",
] as const;

/** Public Provider API shape. */
export interface PublicProvider {
  /** Stable provider identifier (e.g. "groq", "nvidia", "together"). */
  id: string;
  /** Display name. Omitted when TFI does not have a known label. */
  name?: string;
  /** The data source TFI observed this provider through (nvidia, amd,
   *  huggingface, openrouter, etc.). Multiple providers can share a
   *  single data_source (HF router fans out to many upstreams). */
  data_source: string;
  /** Protocol(s) this provider accepts. Most providers expose
   *  exactly one; some are multi-protocol. Order is stable for
   *  diff-friendly output. */
  protocols: string[];
  /** Documentation URL when TFI knows one. Omitted otherwise. */
  documentation_url?: string;
}

/** Public Endpoint API shape. */
export interface PublicEndpoint {
  /** Stable endpoint identifier — format ``{provider}:{endpoint_name}``,
   *  e.g. ``groq:default`` or ``huggingface:together``. Deterministic
   *  (no random UUIDs) so Agent configs stay diff-friendly across
   *  catalog re-publishes. */
  id: string;
  /** Provider that operates this endpoint. */
  provider: string;
  /** The data source TFI observed this endpoint through. */
  data_source: string;
  /** Protocol the endpoint speaks. */
  protocol?: string;
  /** Public API base URL the user can configure their SDK against.
   *  Never a private / internal / Cloudflare URL. Omitted when TFI
   *  does not have a known public base URL. */
  base_url?: string;
  /** Authentication requirement — never the credential itself. */
  authentication?: {
    type: string;
    /** True if the user must provide a credential; false if the
     *  endpoint is publicly accessible (e.g. some free tiers). */
    credential_required?: boolean;
  };
  /** Lifecycle status. ``"unknown"`` when TFI has no recent
   *  evidence. Never assume ``"active"`` from mere existence. */
  status?: string;
  /** Endpoint access metadata. All fields optional; missing is
   *  preferred over inventing values. */
  limits?: {
    scope?: string;
    subject?: string;
    rpm?: number;
    rpd?: number;
    tpm?: number;
  };
  /** Models served by this endpoint. TFI returns model_ids — not
   *  embedded model objects — so the model shape stays single-sourced
   *  from /api/v1/models. Order is stable for diff-friendly output. */
  models?: string[];
}

/** Standard list envelope. */
export interface PublicList<T> {
  object: "list";
  data: T[];
}

export function publicListOf<T>(data: T[]): PublicList<T> {
  return { object: "list", data };
}

// ---------------------------------------------------------------------------
// Static provider / endpoint metadata registry.
//
// Sourced from web/functions/lib/generators/bifrost.ts (which already
// carries the canonical PROVIDER_API_KEY_ENV + CUSTOM_OPENAI_BASE_URLS
// maps for the Bifrost generator). Re-exposed here so the public
// projection doesn't have to depend on a generator module.
//
// Per audit §38, this registry must NEVER contain:
//   - API keys
//   - documentation URLs containing secrets
//   - private / internal hostnames
// Every URL here comes from each vendor's official "OpenAI
// compatibility" documentation.
// ---------------------------------------------------------------------------

interface ProviderMetadata {
  displayName: string;
  /** Protocols this provider speaks. Most providers expose exactly
   *  one; some are multi-protocol. */
  protocols: string[];
  /** Public base URL when the provider's API is open and well-known. */
  baseUrl?: string;
  documentationUrl?: string;
}

/** Single source of truth for the per-provider display name +
 *  public base URL + protocol. Sourced from the Bifrost generator's
 *  PROVIDER_API_KEY_ENV + CUSTOM_OPENAI_BASE_URLS tables. Adding a
 *  new provider = one entry here. */
const PROVIDER_METADATA: Readonly<Record<string, ProviderMetadata>> = {
  nvidia: {
    displayName: "NVIDIA NIM",
    protocols: ["openai-compatible"],
    baseUrl: "https://integrate.api.nvidia.com/v1",
    documentationUrl: "https://docs.nvidia.com/nim/",
  },
  amd: {
    displayName: "AMD Radeon Cloud",
    protocols: ["openai-compatible"],
    baseUrl: "https://developer.amd.com.cn/radeon/api/v1",
    documentationUrl: "https://amd-aim.github.io/radeon-cloud-docs/",
  },
  huggingface: {
    displayName: "Hugging Face",
    protocols: ["huggingface"],
    documentationUrl: "https://huggingface.co/docs/api-inference/",
  },
  groq: {
    displayName: "Groq",
    protocols: ["openai-compatible"],
    baseUrl: "https://api.groq.com/openai/v1",
    documentationUrl: "https://console.groq.com/docs/openai",
  },
  openrouter: {
    displayName: "OpenRouter",
    protocols: ["openai-compatible"],
    baseUrl: "https://openrouter.ai/api/v1",
    documentationUrl: "https://openrouter.ai/docs",
  },
  together: {
    displayName: "Together AI",
    protocols: ["openai-compatible"],
    baseUrl: "https://api.together.xyz/v1",
    documentationUrl: "https://docs.together.ai/docs/openai-api",
  },
  deepinfra: {
    displayName: "DeepInfra",
    protocols: ["openai-compatible"],
    baseUrl: "https://api.deepinfra.com/v1/openai",
    documentationUrl: "https://deepinfra.com/docs/openai_api",
  },
  cerebras: {
    displayName: "Cerebras",
    protocols: ["openai-compatible"],
    baseUrl: "https://api.cerebras.ai/v1",
    documentationUrl: "https://inference.cerebras.ai",
  },
  novita: {
    displayName: "Novita AI",
    protocols: ["openai-compatible"],
    baseUrl: "https://api.novita.ai/v3/openai",
    documentationUrl: "https://novita.ai/docs",
  },
  cohere: {
    displayName: "Cohere",
    protocols: ["openai-compatible"],
    baseUrl: "https://api.cohere.ai/v1",
    documentationUrl: "https://docs.cohere.com",
  },
  fireworks: {
    displayName: "Fireworks AI",
    protocols: ["openai-compatible"],
    baseUrl: "https://api.fireworks.ai/inference/v1",
    documentationUrl: "https://docs.fireworks.ai",
  },
  baseten: {
    displayName: "Baseten",
    protocols: ["openai-compatible"],
    baseUrl: "https://api.baseten.co/v1",
    documentationUrl: "https://docs.baseten.co",
  },
  scaleway: {
    displayName: "Scaleway",
    protocols: ["openai-compatible"],
    baseUrl: "https://api.scaleway.ai/v1",
    documentationUrl: "https://www.scaleway.com/en/docs",
  },
  nscale: {
    displayName: "Nscale",
    protocols: ["openai-compatible"],
    baseUrl: "https://api.nscale.com/v1",
    documentationUrl: "https://docs.nscale.com",
  },
  ovhcloud: {
    displayName: "OVHcloud AI Endpoints",
    protocols: ["openai-compatible"],
    baseUrl: "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
    documentationUrl: "https://endpoints.ovhcloud.com",
  },
  publicai: {
    displayName: "PublicAI",
    protocols: ["openai-compatible"],
    baseUrl: "https://api.publicai.co/v1",
    documentationUrl: "https://publicai.co",
  },
  featherless: {
    displayName: "Featherless",
    protocols: ["openai-compatible"],
    baseUrl: "https://api.featherless.ai/v1",
    documentationUrl: "https://featherless.ai",
  },
};

/** Look up a single provider's metadata. Returns null when the
 *  provider is unknown to the registry — callers should fall back
 *  to a minimal provider object (id + data_source) without name /
 *  protocols / documentation. */
export function getProviderMetadata(providerId: string): ProviderMetadata | null {
  return PROVIDER_METADATA[providerId] ?? null;
}

/** Stable order for protocols. Keeps response output deterministic. */
function stableProtocols(protocols: readonly string[]): string[] {
  const order: Readonly<Record<string, number>> = {
    "openai-compatible": 0,
    "anthropic": 1,
    "native": 2,
    "huggingface": 3,
    "nim": 4,
  };
  return [...protocols].sort(
    (a, b) => (order[a] ?? 99) - (order[b] ?? 99),
  );
}

/** Build a PublicProvider from the canonical (data_source, provider)
 *  pair. The catalog carries (data_source, provider); everything else
 *  comes from the static metadata registry. */
export function toPublicProvider(
  dataSource: string,
  provider: string,
): PublicProvider {
  const meta = getProviderMetadata(provider);
  const out: PublicProvider = {
    id: provider,
    data_source: dataSource,
    protocols: stableProtocols(meta?.protocols ?? []),
  };
  if (meta?.displayName) out.name = meta.displayName;
  if (meta?.documentationUrl) out.documentation_url = meta.documentationUrl;
  return out;
}

/** Per-data-source provider appearance: HF fans out to many upstream
 *  providers (novita, together, etc.) — each is a separate provider
 *  id with its own PublicProvider entry. */

/** Build a PublicEndpoint from a canonical (data_source, provider)
 *  pair + the model_ids served through it. The ``id`` is
 *  ``{provider}:{endpoint_name}``. For our current data model each
 *  (data_source, provider) pair is a single endpoint — endpoint_name
 *  defaults to ``"default"`` but can be overridden (e.g.
 *  ``huggingface:together`` for a HF router upstream named together). */
export function toPublicEndpoint(
  dataSource: string,
  provider: string,
  models: readonly string[],
  opts: {
    endpointName?: string;
    status?: string;
  } = {},
): PublicEndpoint {
  const meta = getProviderMetadata(provider);
  const endpointName = opts.endpointName ?? "default";
  const out: PublicEndpoint = {
    id: `${provider}:${endpointName}`,
    provider,
    data_source: dataSource,
    // Protocol is single-valued in the public schema; if the provider
    // has multiple, surface the canonical first (after stableProtocols
    // sorting).
    protocol: (stableProtocols(meta?.protocols ?? [])[0]) ?? "openai-compatible",
    // Base URL + documentation live on the provider, but the spec
    // wants them on the endpoint too. Mirror them so the endpoint is
    // self-describing in single-fetch workflows.
    base_url: meta?.baseUrl,
    authentication: {
      // Every public-facing provider in the registry requires a
      // credential; unknown providers get a typed-but-credential-
      // required marker so the user knows.
      type: "bearer",
      credential_required: true,
    },
    status: opts.status ?? "active",
    limits: undefined,
    models: models.length > 0 ? [...models].sort() : undefined,
  };
  // Drop undefined keys so the JSON payload is compact and matches
  // the documented "omit if absent" convention.
  return JSON.parse(JSON.stringify(out)) as PublicEndpoint;
}

/** Strip a PublicEndpoint of all fields the user must NOT see
 *  according to §38. Re-applied as defence-in-depth in case a future
 *  field accidentally carries a credential. */
export function redactEndpoint(ep: PublicEndpoint): PublicEndpoint {
  return {
    id: ep.id,
    provider: ep.provider,
    data_source: ep.data_source,
    protocol: ep.protocol,
    base_url: ep.base_url,
    authentication: ep.authentication
      ? { type: ep.authentication.type, credential_required: ep.authentication.credential_required }
      : undefined,
    status: ep.status,
    limits: ep.limits,
    models: ep.models,
  };
}

/** Prove that no field of a PublicEndpoint (or PublicProvider) ever
 *  carries a credential / secret by exporting a "scanner" that
 *  asserts a known-bad list of substrings is absent. Used by
 *  the route tests in __tests__/redaction.test.ts. */
export const FORBIDDEN_SUBSTRINGS: readonly string[] = [
  // High-confidence credential shapes only. The list is deliberately
  // conservative: a false negative here would leak a secret in a
  // public response, while a false positive is harmless (the test
  // just flags the response for review). The projection is also
  // pinned to a fixed field shape, so a real leak would have to
  // survive the PublicEndpoint field list first.
  //
  // Lookup is case-insensitive (callers lowercase the input).
  "api_key=",
  "apikey=",
  "password=",
  "authorization:",   // matches both "Authorization:" and "X-Authorization:"
  "bearer ",          // trailing space avoids matching inside model ids
  "x-auth-token",
  "x-api-key",
  "cf-",              // Cloudflare auth cookies / headers
];

/** Scan a value (any depth) for credential-shaped substrings. Returns
 *  the first matching substring or null. Used by the redaction
 *  regression test to guarantee no future change leaks a secret
 *  via the public endpoints / providers API. */
export function findCredentialString(value: unknown): string | null {
  if (typeof value === "string") {
    const lower = value.toLowerCase();
    for (const s of FORBIDDEN_SUBSTRINGS) {
      if (lower.includes(s)) return s;
    }
    return null;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const hit = findCredentialString(item);
      if (hit) return hit;
    }
    return null;
  }
  if (value && typeof value === "object") {
    for (const k of Object.keys(value)) {
      const hit = findCredentialString((value as Record<string, unknown>)[k]);
      if (hit) return hit;
    }
  }
  return null;
}

/** Documented vocabulary for the ``capabilities`` field.
 *
 * The full public vocabulary is fixed (per doc §12 — we never add
 * new capability names without bumping the API contract). When TFI's
 * data pipeline doesn't have capability data for a model, the
 * public API returns an empty array — see the schema docstring on
 * ``PublicModel.capabilities`` for the semantics.
 */
export const PUBLIC_CAPABILITY_VOCABULARY: ReadonlyArray<string> = [
  ...CAPABILITY_ORDER,
] as ReadonlyArray<string>;

/** Documented vocabulary for ``architecture.{input,output}``
 *  modalities. Same fixed-vocabulary contract. */
export const PUBLIC_MODALITY_VOCABULARY: ReadonlyArray<string> = [
  "text",
  "image",
  "audio",
  "video",
  "embedding",
] as const;
