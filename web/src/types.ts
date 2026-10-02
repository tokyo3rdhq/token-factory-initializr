// ModelEndpoint types — mirror of shared/schema/model.schema.json
// and data/models/schema.py. This file is the TS-side hand-rolled
// counterpart to the JSON schema; keep them in sync.

export interface ModelEndpoint {
  /** Data source the endpoint was discovered through (nvidia/amd/huggingface). */
  data_source: string;

  /** Provider identifier — for NVIDIA/AMD this equals data_source;
   *  for Hugging Face this is the per-inference provider
   *  (novita/together/deepinfra/...). */
  provider: string;

  /** Provider-specific model id (e.g. "deepseek-ai/deepseek-v4.1-flash"). */
  model_id: string;

  /** Human-readable model name. */
  name: string | null;

  /** Optional longer description. */
  description: string | null;

  /** True iff the upstream provider offers free access. */
  free: boolean;

  /** Capability flags (chat, tool_calling, vision, speech, embedding, ...). */
  capabilities: Record<string, unknown>;

  /** Input / output modalities — null when upstream doesn't expose them. */
  architecture: { input: string[]; output: string[] } | null;

  /** Lab / organization (HF: owned_by, AMD: token_factory.publisher.name). */
  lab: string | null;

  /** Per-provider metadata — fields differ by provider; not canonicalized. */
  metadata: Record<string, unknown>;

  /** ISO 8601 timestamp when this endpoint was fetched. */
  fetched_at: string;

  /** Optional top-level context window length. */
  context_length?: number | null;

  /** Optional per-token pricing. */
  pricing?: Record<string, unknown> | null;
}

export interface ProviderSnapshot {
  data_source: string;
  provider: string;
  /** All endpoints for this provider (free + paid; UI filters client-side). */
  models: ModelEndpoint[];
  /** ISO 8601 timestamp of when this catalog snapshot was written.
   *  Optional — the Python pipeline writes it but legacy fixtures
   *  (and older snapshots) may not have it. */
  fetched_at?: string;
}

export interface ManifestProvider {
  provider: string;
  count: number;
  status: "success" | "partial" | "failed" | "invalid";
  last_success?: string;
  error?: string;
}

export interface Manifest {
  version: string;
  generated_at: string;
  total: number;
  providers: Record<string, ManifestProvider>;
}

export interface GeneratedArtifact {
  /** Random 8-char id used in the public URL ``/generated/{id}``. */
  id: string;
  /** UTC epoch ms when this artifact was created. */
  created_at: number;
  /** UTC epoch ms when the artifact becomes unreachable. */
  expires_at: number;
  /** Source provider endpoints (selected by the user). */
  models: ModelEndpoint[];
  /** Rendered LiteLLM config (YAML). */
  config_yaml: string;
  /** Config format key (currently only "litellm"; "newapi"
     *  follows from the Phase-1 Token Factory refactor). */
  format: string;
}

/** Phase-1 Token Factory refactor — single explicit Initializr state
 *  shared between Browse and Generate. Mirrors
 *  /web/functions/lib/generators/types.ts on the server side. */
export interface InitializrTranslations {
  /** Heading on the picker section. */
  pickerHeading: string;
  /** Picker description text. */
  pickerDescription: string;
  /** Selection summary text (e.g. "{n} models selected"). */
  selectionCountTemplate: (n: number) => string;
  /** Validation messages per doc §9 / §19. */
  validation: {
    noModels: string;
    noFactory: string;
  };
  /** Generic error prefix when generation fails. Server-side errors
   *  are usually actionable on their own; this is the fallback
   *  when the request simply failed. */
  errorPrefix: string;
  /** Result-panel format label (e.g. "LiteLLM configuration"). */
  formatLabelTemplate: (factoryName: string) => string;
  /** Per-Token-Factory display labels / descriptions rendered in the
   *  picker UI. Keys must match the server-side TokenFactoryId union. */
  factories: {
    litellm: { name: string; description: string };
    newapi: { name: string; description: string };
  };
}

/** Lifted to the top level because both KV and Functions use it. */
export const TTL_SECONDS = 300;

// ModelRequirement — mirror of shared/schema/model_requirement.schema.json.
// Used by the web UI to filter / rank endpoints against what the user
// actually needs. Every field is optional; an empty requirement
// matches every endpoint.
export interface ModelRequirement {
  /** Use-case tags the user wants to satisfy. */
  useCases?: string[];

  /** Required capability flags. An endpoint matches a flag when it's
   *  set on the endpoint's `capabilities` dict (or derived from
   *  architecture / use_case labels per provider). */
  capabilities?: {
    /** Endpoint must accept image inputs. */
    vision?: boolean;
    /** Endpoint must support tool/function calling. */
    toolCalling?: boolean;
    /** Endpoint must support structured output. */
    structuredOutput?: boolean;
    /** Endpoint advertises a reasoning/CoT capability.
     *  Reserved — no provider exposes this today. */
    reasoning?: boolean;
  };

  /** Minimum acceptable context window (tokens). Endpoints with
   *  unknown / null context_length are treated as matches. */
  contextWindow?: {
    min?: number;
  };

  /** Pricing constraints. All sub-fields are AND-combined. */
  pricing?: {
    /** Maximum acceptable input price (USD per token). */
    input?: number;
    /** Maximum acceptable output price (USD per token). */
    output?: number;
    /** If true, only free endpoints match. If false, only paid
     *  endpoints match (`endpoint.free === false`). If omitted,
     *  no constraint is applied. */
    free?: boolean;
  };

  /** Whitelist of provider names. If non-empty, an endpoint matches
   *  only when its `provider` is in the list. If empty / omitted,
   *  all providers match. */
  providers?: string[];

  /** Reserved — intended to express "I need N endpoints that satisfy
   *  the rest of this requirement". The current web UI does not
   *  enforce this field. */
  endpointCount?: number;

  /** Non-functional constraints. Reserved for future provider
   *  metadata; all providers currently leave these unset. */
  constraints?: {
    /** Required geographic region (e.g. "us-east", "eu-west"). */
    region?: string;
    /** Maximum acceptable first-token latency (ms). */
    latency?: number;
    /** Minimum acceptable throughput (tokens/sec). */
    throughput?: number;
  };
}

// ---------------------------------------------------------------------------
// Endpoint-vs-requirement matcher
// ---------------------------------------------------------------------------

/**
 * True iff `endpoint` satisfies every constraint in `requirement`.
 *
 * Missing requirement fields are no-ops (i.e. `{}` matches
 * everything). Missing endpoint fields (e.g. `context_length ===
 * null`) are treated as permissive — the requirement says "I need at
 * least N", and unknown is treated as a pass.
 */
export function matchesRequirement(
  endpoint: ModelEndpoint,
  requirement: ModelRequirement,
): boolean {
  // capabilities — vision / toolCalling / structuredOutput
  //
  // The capability flag in the schema is camelCase (user-facing).
  // The actual data emits snake_case (``tool_calling``,
  // ``structured_output``). We accept either, and additionally
  // derive ``vision`` from architecture when the explicit flag is
  // missing — AMD/NVIDIA/HF all carry modality info on
  // architecture.input rather than the capability flag.
  const caps = requirement.capabilities;
  if (caps) {
    if (caps.vision === true && !hasVision(endpoint)) return false;
    if (caps.toolCalling === true && !hasToolCalling(endpoint)) return false;
    if (caps.structuredOutput === true && !hasStructuredOutput(endpoint)) {
      return false;
    }
    if (caps.reasoning === true && !hasReasoning(endpoint)) return false;
  }

  // contextWindow.min — endpoint must have a known context length
  // at or above the floor. Null/unknown treated as match.
  if (requirement.contextWindow?.min !== undefined) {
    const ctx = endpoint.context_length;
    if (ctx !== null && ctx !== undefined && ctx < requirement.contextWindow.min) {
      return false;
    }
  }

  // pricing — all sub-constraints AND-combined
  const price = requirement.pricing;
  if (price) {
    if (price.free === true && !endpoint.free) return false;
    if (price.free === false && endpoint.free) return false;
    const epPrice = endpoint.pricing;
    if (price.input !== undefined && epPrice) {
      const epInput = readPrice(epPrice, "input");
      if (epInput !== null && epInput > price.input) return false;
    }
    if (price.output !== undefined && epPrice) {
      const epOutput = readPrice(epPrice, "output");
      if (epOutput !== null && epOutput > price.output) return false;
    }
  }

  // data_sources whitelist — non-empty list filters; empty means all
  //
  // The field is named ``providers`` for backward compatibility with
  // the pre-refactor JSON contract, but semantically the values are
  // data_sources (one of {"nvidia", "amd", "huggingface"}). Per the
  // refactor, an HF inference provider like "cohere" lives at
  // (huggingface, cohere); when the user selects "huggingface" they
  // mean "anything from the huggingface data source", not just
  // (huggingface, huggingface). Matching against ``data_source``
  // is what makes the filter intuitive.
  if (requirement.providers && requirement.providers.length > 0) {
    if (!requirement.providers.includes(endpoint.data_source)) return false;
  }

  // endpointCount / constraints / useCases — reserved for future
  // implementation; the current matcher treats them as no-ops.
  return true;
}

// ---------------------------------------------------------------------------
// Capability predicates — bridge the user-facing camelCase schema to the
// per-provider snake_case capability keys / architecture modalities.
// ---------------------------------------------------------------------------

function hasVision(ep: ModelEndpoint): boolean {
  const eCaps = ep.capabilities || {};
  if (eCaps.vision) return true;
  if (eCaps.image_input) return true;
  const arch = ep.architecture;
  if (arch && Array.isArray(arch.input) && arch.input.includes("image")) {
    return true;
  }
  return false;
}

function hasToolCalling(ep: ModelEndpoint): boolean {
  const eCaps = ep.capabilities || {};
  if (eCaps.tool_calling || eCaps.toolCalling) return true;
  // AMD stores the tool flag inside metadata. We don't read metadata
  // here (capability-style), but the dedicated AMD capability key
  // ``use_case == "chat+tools"`` etc. would route through this path
  // if AMD ever stops omitting the boolean on the top-level dict.
  return false;
}

function hasStructuredOutput(ep: ModelEndpoint): boolean {
  const eCaps = ep.capabilities || {};
  if (eCaps.structured_output || eCaps.structuredOutput) return true;
  return false;
}

function hasReasoning(ep: ModelEndpoint): boolean {
  const eCaps = ep.capabilities || {};
  if (eCaps.reasoning) return true;
  return false;
}

/** Read a numeric price field, tolerating string-encoded values. */
function readPrice(price: Record<string, unknown>, key: string): number | null {
  const v = price[key];
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}