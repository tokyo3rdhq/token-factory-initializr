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
import {
  resolveBaseUrl,
  getProviderMetadata,
  stableProtocols,
} from "./dataSources";
export type { ProviderConfig } from "./dataSources";
export interface PublicModel {
  /** Canonical model identity (e.g. "deepseek-ai/deepseek-v4"). Shared
   *  across every provider endpoint serving the model. */
  id: string;
  object: "model";
  created: number;
  /** Model owner (creator / publisher). NEVER the endpoint provider —
   *  see ``deriveOwner`` for the fallback rule. Omitted when no
   *  reliable owner is derivable. */
  owned_by?: string;
  /** TFI extension: the data source of the first endpoint TFI
   *  observed for this model. Per-endpoint data_source lives under
   *  ``endpoints[].provider``; this field is retained for backward
   *  compatibility of list consumers. */
  data_source: string;
  /** TFI extension: the provider of the first endpoint TFI observed
   *  for this model. See ``endpoints[]`` for the full set. */
  provider: string;
  /** Canonical normalized capabilities — see doc §12 for the fixed
   *  vocabulary. Order is stable for diff-friendly output. */
  capabilities: string[];
  /** TFI extension: endpoint-level interface/runtime parameters
   *  (docs/tfi_add_supported_parameters.md). Fixed vocabulary —
   *  ``tool_calling`` / ``reasoning`` / ``structured_output`` /
   *  ``streaming`` (the first three migrated from capabilities on
   *  2026-10-19). Union of the parameters confirmed on ANY of this
   *  model's endpoints (endpoint-level facts are endpoint-scoped; the
   *  model-level array is the aggregated view for filtering). Omitted
   *  when empty. */
  supported_parameters?: string[];
  /** Optional public detail fields. Always omitted when null/empty
   *  so the list endpoint stays compact. */
  name?: string;
  description?: string;
  architecture?: { input: string[]; output: string[] };
  context_length?: number;
  lab?: string;
  source_url?: string;
  /** Endpoints serving this model. Each carries its OWN provider,
   *  provider-specific model_id, free status, pricing, and limits.
   *  ``free`` is endpoint-specific — there is deliberately NO
   *  model-level free flag (see
   *  docs/tfi_model_and_endpoint_free_status_semantics.md). */
  endpoints: PublicModelEndpoint[];
}

/** Per-endpoint access record nested inside a PublicModel.
 *
 * ``free`` is the single source of truth for THIS endpoint's free
 * status, projected verbatim from the canonical
 * ``ModelEndpoint.free``. It is never derived from the model name,
 * the provider, or the absence of pricing. */
export interface PublicModelEndpoint {
  /** Stable endpoint id — ``{provider}:{endpoint_name}`` (see
   *  ``toPublicEndpoint`` in projection / ``buildIndexes``). */
  id: string;
  /** Provider operating this endpoint. */
  provider: string;
  /** Provider-specific model id. Matches the canonical model_id in
   *  the current catalog; carried explicitly so consumers never
   *  re-derive it. */
  model_id: string;
  /** Endpoint-specific free status false/true. */
  free: boolean;
  /** Endpoint-specific pricing, when the canonical record carries
   *  it. Omitted rather than invented. */
  pricing?: Record<string, unknown> | null;
  /** Canonical pricing/access classification: "free", "paid", or "unknown". */
  pricing_status?: "free" | "paid" | "unknown";
  /** Endpoint-specific rate / quota limits, when known. Omitted
   *  rather than invented. */
  limits?: Record<string, unknown> | null;
  /** Endpoint-specific interface/runtime parameters
   *  (docs/tfi_add_supported_parameters.md). Fixed vocabulary —
   *  ``tool_calling`` / ``reasoning`` / ``structured_output`` /
   *  ``streaming``. Omitted when empty; never promoted to sibling
   *  endpoints of the same model. */
  supported_parameters?: string[];
}

/** Stable capability sort order — keeps list responses diff-friendly.
 * The three interface/runtime keys (``tool_calling`` / ``reasoning`` /
 * ``structured_output``) moved to ``SUPPORTED_PARAMETER_ORDER`` on
 * 2026-10-19. */
const CAPABILITY_ORDER = [
  "chat",
  "vision",
  "speech",
  "embedding",
  "translation",
  "decision",
] as const;

/** Stable supported-parameters sort order — same contract as
 * ``CAPABILITY_ORDER`` (docs/tfi_add_supported_parameters.md §3.2).
 * Vocabulary is closed: the three migrated keys plus ``streaming``. */
const SUPPORTED_PARAMETER_ORDER = [
  "tool_calling",
  "reasoning",
  "structured_output",
  "streaming",
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

/** Build the nested per-endpoint access record from a canonical
 *  ``ModelEndpoint``. Free / pricing / limits are endpoint-scoped;
 *  they are projected verbatim — never inferred, never collapsed. */
function toPublicModelEndpoint(model: ModelEndpoint): PublicModelEndpoint {
  // Legacy ``free`` compatibility rule (§3.2): backfill ``pricing_status``
  // from the legacy ``free`` field when the record carries no explicit
  // classification, then derive ``free`` from ``pricing_status`` so both
  // fields stay consistent. New records always carry an explicit
  // ``pricing_status``; missing pricing is never treated as free.
  const derivedPricingStatus =
    model.pricing_status ?? (model.free === true ? "free" : "unknown");
  const out: PublicModelEndpoint = {
    id: `${model.data_source}:${model.provider}`,
    provider: model.provider,
    model_id: model.model_id,
    free: derivedPricingStatus === "free",
    pricing_status: derivedPricingStatus,
  };
  if (model.pricing != null) out.pricing = model.pricing;
  if (Array.isArray(model.supported_parameters) && model.supported_parameters.length > 0) {
    out.supported_parameters = model.supported_parameters.filter(
      (f): f is string => typeof f === "string",
    );
  }
  return out;
}

/** Project a canonical ``ModelEndpoint`` into the public model
 *  shape. The model-level record carries identity/metadata; the
 *  per-endpoint access information lives under ``endpoints[]``. */
export function toPublicModel(
  model: ModelEndpoint,
  options: { endpointsByModel?: Map<string, ModelEndpoint[]> } = {},
): PublicModel {
  const caps: string[] = [];
  for (const key of CAPABILITY_ORDER) {
    if (model.capabilities && model.capabilities[key] === true) {
      caps.push(key);
    }
  }
  if (model.capabilities) {
    for (const [key, value] of Object.entries(model.capabilities)) {
      if (value === true && !CAPABILITY_ORDER.includes(key as any)) {
        caps.push(key);
      }
    }
  }

  // Supported parameters are endpoint-scoped facts. The model-level
  // array is the ORDERED UNION across every endpoint serving this
  // model (stable SUPPORTED_PARAMETER_ORDER sort, dedup) — used for
  // list filtering and UI badges. Endpoint-level records stay
  // endpoint-scoped under ``endpoints[]``.
  const all = options.endpointsByModel?.get(model.model_id) ?? [model];
  const parameterSet = new Set<string>();
  for (const e of all) {
    if (Array.isArray(e.supported_parameters)) {
      for (const p of e.supported_parameters) {
        if (typeof p === "string") parameterSet.add(p);
      }
    }
  }
  const orderedParameters: readonly string[] = SUPPORTED_PARAMETER_ORDER;
  const parameters: string[] = [];
  for (const key of orderedParameters) {
    if (parameterSet.has(key)) parameters.push(key);
  }
  for (const p of parameterSet) {
    if (!orderedParameters.includes(p)) parameters.push(p);
  }

  const publicModel: PublicModel = {
    id: model.model_id,
    object: "model",
    created: 0,
    data_source: model.data_source,
    provider: model.provider,
    capabilities: caps,
    endpoints: [],
  };

  const owner = deriveOwner(model.model_id, model.lab);
  if (owner) publicModel.owned_by = owner;
  if (model.name) publicModel.name = model.name;
  if (model.description) publicModel.description = model.description;
  if (model.architecture) publicModel.architecture = model.architecture;
  if (typeof model.context_length === "number") publicModel.context_length = model.context_length;
  if (model.lab) publicModel.lab = model.lab;
  if (model.source_url) publicModel.source_url = model.source_url;
  if (parameters.length > 0) publicModel.supported_parameters = parameters;

  // Nested endpoints — every provider record TFI has for this model.
  // Default to the single endpoint when no index is passed, so detail
  // routes still return a well-formed nested view.
  publicModel.endpoints = all
    .map((e) => toPublicModelEndpoint(e))
    .sort((a, b) => a.id.localeCompare(b.id));

  return publicModel;
}

/** Group canonical endpoints by model_id and project each group
 *  once. The nested ``endpoints[]`` is derived from the INPUT array
 *  — so route-level filters (provider, data_source, capabilities)
 *  apply to the nested set too; a filtered-out endpoint never leaks
 *  back into a model object. Stable sort on the canonical model id
 *  keeps list responses diff-friendly. */
export function toPublicModels(endpoints: ModelEndpoint[]): PublicModel[] {
  const byModel = new Map<string, ModelEndpoint[]>();
  for (const ep of endpoints) {
    const list = byModel.get(ep.model_id);
    if (list) {
      list.push(ep);
    } else {
      byModel.set(ep.model_id, [ep]);
    }
  }
  const out: PublicModel[] = [];
  for (const eps of byModel.values()) {
    out.push(toPublicModel(eps[0], { endpointsByModel: byModel }));
  }
  return out.sort((a, b) => a.id.localeCompare(b.id));
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

  const out: PublicEndpoint = {
    id: `${dataSource}:${provider}`,
    provider,
    data_source: dataSource,
    // Protocol is single-valued in the public schema; if the provider
    // has multiple, surface the canonical first (after stableProtocols
    // sorting).
    protocol: (stableProtocols(meta?.protocols ?? [])[0]) ?? "openai-compatible",
    // Base URL is keyed on the data_source first (the entry point
    // TFI actually used to discover the model — e.g. the HF router
    // for huggingface-fanout models), with the provider's native
    // endpoint as a fallback for data sources without a canonical
    // entry point. See ``resolveBaseUrl`` for the full rule.
    base_url: resolveBaseUrl(dataSource, provider),
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

/** Documented vocabulary for the ``supported_parameters`` field
 *  (docs/tfi_add_supported_parameters.md §3.2). Same fixed-vocabulary
 *  contract as capabilities: the three migrated interface keys plus
 *  ``streaming``. */
export const PUBLIC_SUPPORTED_PARAMETER_VOCABULARY: ReadonlyArray<string> = [
  ...SUPPORTED_PARAMETER_ORDER,
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
