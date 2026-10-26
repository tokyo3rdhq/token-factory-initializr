// Query-string parsing + model filtering for the /api/v1/models
// endpoint. Per docs tfi_agent_friendly_model_catalog_api.md:
//
//   data_source filter  → IN (csv)
//   provider filter     → IN (csv)
//   capabilities filter → ALL of (csv), i.e. AND semantics within
//                          the dimension
//
// Unknown data_source / provider → return empty (per doc §17
// recommendation — they're dynamic catalog data, not a fixed
// vocabulary). Unknown capability → 400 (fixed vocabulary).
//
// Validation runs once via ``parseFilters``; the same object is
// reused by the route handler for cheap in-memory filtering.

import type { ModelEndpoint } from "./kv";
import type { PublicModel } from "./projection";

/** Allowed capability vocabulary (doc §12). Order is stable for
 *  diff-friendly error messages. The three interface/runtime keys
 *  moved to ``KNOWN_SUPPORTED_PARAMETERS`` on 2026-10-19. */
export const KNOWN_CAPABILITIES: ReadonlyArray<string> = [
  "chat",
  "vision",
  "speech",
  "embedding",
  "translation",
  "decision",
];

/** Allowed supported_parameters vocabulary
 *  (docs/tfi_add_supported_parameters.md §3.2). Fixed — an unknown
 *  value is a client error, same contract as capabilities. The three
 *  interface keys migrated from capabilities on 2026-10-19. */
export const KNOWN_SUPPORTED_PARAMETERS: ReadonlyArray<string> = [
  "tool_calling",
  "reasoning",
  "structured_output",
  "streaming",
];

/** Parsed, validated query filter. Always safe to apply. */
export interface ModelFilters {
  data_source?: string[];
  provider?: string[];
  capabilities?: string[];
  supported_parameters?: string[];
  /**
   * Endpoint-level pricing/access classification filter. OR-within-dimension:
   * a model matches if ANY of its endpoints has a pricing_status in this list.
   * Values are validated against the fixed vocabulary; an unknown value is a
   * 400. Priced-status filtering is endpoint-scoped — a model with one free and
   * one paid endpoint matches ``pricing_status=free`` (the free endpoint is
   * indicated in the nested ``endpoints[]``).
   */
  pricing_status?: string[];
  /**
   * Inclusive minimum ``context_length`` (in tokens). Parsed from the
   * ``context_length_min`` query param. Endpoints whose
   * ``context_length`` is null/absent are excluded when this filter is
   * set — unknown is not "at least N".
   */
  context_length_min?: number;
  /** Maximum number of results to return. Default 100, capped at 1000. */
  limit?: number;
  /** Offset for pagination (number of results to skip). Default 0. */
  offset?: number;
}

/** Sentinel returned by ``parseFilters`` when a 400 is warranted. */
export interface FilterParseError {
  error: { message: string; type: string; param: string; code: string };
}

const COMMA = ",";

/**
 * Split a comma-separated value into trimmed, deduped entries.
 *
 * Empty / whitespace entries are dropped. Order is preserved so the
 * filter dimension reads naturally in error messages and matches the
 * canonical-data-source ordering used by the manifest.
 */
export function splitCsv(value: string | null | undefined): string[] {
  if (!value) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of value.split(COMMA)) {
    const v = raw.trim();
    if (!v || seen.has(v)) continue;
    seen.add(v);
    out.push(v);
  }
  return out;
}

/**
 * Parse the raw query params into a typed ``ModelFilters`` value,
 * or return a 400 error descriptor.
 *
 * Note: data_source and provider are NOT validated against the
 * canonical list here — they're dynamic catalog values, so an
 * unknown one is treated as "no matches" downstream rather than a
 * client error.
 */
export function parseFilters(
  params: URLSearchParams
): ModelFilters | FilterParseError {
  const filters: ModelFilters = {};

  const ds = splitCsv(params.get("data_source"));
  if (ds.length > 0) filters.data_source = ds;

  const prov = splitCsv(params.get("provider"));
  if (prov.length > 0) filters.provider = prov;

  const caps = splitCsv(params.get("capabilities"));
  if (caps.length > 0) {
    const unknown = caps.filter((c) => !KNOWN_CAPABILITIES.includes(c));
    if (unknown.length > 0) {
      return {
        error: {
          message: `Unknown capability: ${unknown.join(", ")}. Allowed: ${KNOWN_CAPABILITIES.join(", ")}.`,
          type: "invalid_request_error",
          param: "capabilities",
          code: "invalid_capability",
        },
      };
    }
    filters.capabilities = caps;
  }
  const clMin = params.get("context_length_min");
  if (clMin) {
    const clMinNum = Number(clMin);
    if (Number.isFinite(clMinNum)) {
      filters.context_length_min = clMinNum;
    }
  }
  const paramList = splitCsv(params.get("supported_parameters"));
  if (paramList.length > 0) {
    const unknown = paramList.filter((p) => !KNOWN_SUPPORTED_PARAMETERS.includes(p));
    if (unknown.length > 0) {
      return {
        error: {
          message: `Unknown supported parameter: ${unknown.join(", ")}. Allowed: ${KNOWN_SUPPORTED_PARAMETERS.join(", ")}.`,
          type: "invalid_request_error",
          param: "supported_parameters",
          code: "invalid_supported_parameter",
        },
      };
    }
    filters.supported_parameters = paramList;
  }

  const pricing = splitCsv(params.get("pricing_status"));
  if (pricing.length > 0) {
    const unknown = pricing.filter(
      (p) => !["free", "paid", "unknown"].includes(p),
    );
    if (unknown.length > 0) {
      return {
        error: {
          message: `Unknown pricing_status: ${unknown.join(", ")}. Allowed: free, paid, unknown.`,
          type: "invalid_request_error",
          param: "pricing_status",
          code: "invalid_pricing_status",
        },
      };
    }
    filters.pricing_status = pricing;
  }

  const limitRaw = params.get("limit");
  if (limitRaw) {
    const limitNum = Number(limitRaw);
    if (Number.isFinite(limitNum) && limitNum > 0) {
      filters.limit = Math.min(limitNum, 1000);
    }
  }
  const offsetRaw = params.get("offset");
  if (offsetRaw) {
    const offsetNum = Number(offsetRaw);
    if (Number.isFinite(offsetNum) && offsetNum >= 0) {
      filters.offset = Math.floor(offsetNum);
    }
  }

  return filters;
}

/** Apply parsed filters to a list of canonical endpoints. */
export function filterEndpoints(
  endpoints: ModelEndpoint[],
  filters: ModelFilters
): ModelEndpoint[] {
  const filtered = endpoints.filter((ep) => {
    if (filters.data_source && !filters.data_source.includes(ep.data_source)) {
      return false;
    }
    if (filters.provider && !filters.provider.includes(ep.provider)) {
      return false;
    }
    if (filters.capabilities && filters.capabilities.length > 0) {
      for (const required of filters.capabilities) {
        if (!ep.capabilities || ep.capabilities[required] !== true) {
          return false;
        }
      }
    }
    if (filters.supported_parameters && filters.supported_parameters.length > 0) {
      const have = Array.isArray(ep.supported_parameters) ? ep.supported_parameters : [];
      for (const required of filters.supported_parameters) {
        if (!have.includes(required)) {
          return false;
        }
      }
    }
    if (filters.context_length_min !== undefined) {
      const cl = typeof ep.context_length === "number" ? ep.context_length : null;
      if (!cl || cl < filters.context_length_min) return false;
    }
    if (filters.pricing_status && filters.pricing_status.length > 0) {
      if (!filters.pricing_status.includes(ep.pricing_status ?? "unknown")) {
        return false;
      }
    }
    return true;
  });

  // Pagination: stable deterministic ordering already applied by caller
  // (toPublicModels sorts by model_id). Apply offset then limit here.
  let paged = filtered;
  if (filters.offset && filters.offset > 0) {
    paged = paged.slice(filters.offset);
  }
  if (filters.limit !== undefined) {
    paged = paged.slice(0, filters.limit);
  }
  return paged;
}

/** Apply filters to a list of public models. Equivalent filter
 *  semantics — used by route handlers that already projected. */
export function filterPublicModels(
  models: PublicModel[],
  filters: ModelFilters
): PublicModel[] {
  return models.filter((m) => {
    if (filters.data_source && !filters.data_source.includes(m.data_source)) {
      return false;
    }
    if (filters.provider && !filters.provider.includes(m.provider)) {
      return false;
    }
    if (filters.capabilities && filters.capabilities.length > 0) {
      for (const required of filters.capabilities) {
        if (!m.capabilities.includes(required)) {
          return false;
        }
      }
    }
    if (filters.supported_parameters && filters.supported_parameters.length > 0) {
      const have = Array.isArray(m.supported_parameters) ? m.supported_parameters : [];
      for (const required of filters.supported_parameters) {
        if (!have.includes(required)) {
          return false;
        }
      }
    }
    if (filters.context_length_min !== undefined) {
      const cl = typeof m.context_length === "number" ? m.context_length : null;
      if (!cl || cl < filters.context_length_min) return false;
    }
    if (filters.pricing_status && filters.pricing_status.length > 0) {
      const hasMatch = m.endpoints.some((e) =>
        filters.pricing_status!.includes(e.pricing_status ?? "unknown"),
      );
      if (!hasMatch) return false;
      // Keep only the endpoints that satisfy the pricing filter so the
      // nested list clearly indicates which endpoints match.
      m.endpoints = m.endpoints.filter((e) =>
        filters.pricing_status!.includes(e.pricing_status ?? "unknown"),
      );
    }

    return true;
  });
}

/** Standard OpenAI-compatible list envelope. */
export interface PublicModelList {
  object: "list";
  data: PublicModel[];
}

export function publicListResponse(models: PublicModel[]): PublicModelList {
  return { object: "list", data: models };
}

// ---------------------------------------------------------------------------
// Provider / Endpoint filter dimensions.
//
// Per docs/tfi_provider_and_endpoint_intelligence_api.md §23 + §24.
// Same OR-within-dimension, AND-across-dimensions semantics as the
// model filter; same CSV parsing; same unknown-value policy
// (unknown filter values return empty — capabilities are the only
// fixed-vocabulary dimension and that already returns 400).
// ---------------------------------------------------------------------------

import type { PublicProvider, PublicEndpoint } from "./projection";

/** Per-dimension filter shapes. Each dimension is optional; a
 *  missing key means "do not filter on this dimension". */
export interface ProviderFilters {
  data_source?: string[];
}

export interface EndpointFilters {
  provider?: string[];
  data_source?: string[];
  protocol?: string[];
  status?: string[];
  /** Per §25. Implemented as a cheap O(n) scan over the pre-built
   *  endpoints index; do NOT introduce expensive runtime scans over
   *  raw source data. */
  model_id?: string[];
  /** Maximum number of results to return. Default 100, capped at 1000. */
  limit?: number;
  /** Offset for pagination (number of results to skip). Default 0. */
  offset?: number;
}

/** Apply OR-within-dimension / AND-across-dimensions provider filter. */
export function filterPublicProviders(
  providers: PublicProvider[],
  filters: ProviderFilters,
): PublicProvider[] {
  return providers.filter((p) => {
    if (filters.data_source && !filters.data_source.includes(p.data_source)) {
      return false;
    }
    return true;
  });
}

/** Apply the endpoint filter set. */
export function filterPublicEndpoints(
  endpoints: PublicEndpoint[],
  filters: EndpointFilters,
): PublicEndpoint[] {
  const filtered = endpoints.filter((e) => {
    if (filters.provider && !filters.provider.includes(e.provider)) {
      return false;
    }
    if (filters.data_source && !filters.data_source.includes(e.data_source)) {
      return false;
    }
    if (filters.protocol && e.protocol && !filters.protocol.includes(e.protocol)) {
      return false;
    }
    if (filters.status && e.status && !filters.status.includes(e.status)) {
      return false;
    }
    if (filters.model_id && e.models) {
      // OR-within-dimension: endpoint matches if any of its models
      // intersects the requested model_id set.
      const intersects = e.models.some((m) => filters.model_id!.includes(m));
      if (!intersects) return false;
    }
    return true;
  });

  // Pagination.
  let paged = filtered;
  if (filters.offset && filters.offset > 0) {
    paged = paged.slice(filters.offset);
  }
  if (filters.limit !== undefined) {
    paged = paged.slice(0, filters.limit);
  }
  return paged;
}

/** Parse the query string for the providers list endpoint.
 *  Currently only ``data_source`` is supported per §23. */
export function parseProviderFilters(
  params: URLSearchParams,
): { ok: true; filters: ProviderFilters } | { ok: false; param: string } {
  const dataSourceRaw = params.get("data_source");
  if (dataSourceRaw) {
    const ds = splitCsv(dataSourceRaw).filter((s) => s.length > 0);
    if (ds.length === 0) {
      return { ok: false, param: "data_source" };
    }
    return { ok: true, filters: { data_source: ds } };
  }
  return { ok: true, filters: {} };
}

/** Parse the query string for the endpoints list endpoint. */
export function parseEndpointFilters(
  params: URLSearchParams,
):
  | { ok: true; filters: EndpointFilters }
  | { ok: false; param: string } {
  const out: EndpointFilters = {};
  for (const key of [
    "provider",
    "data_source",
    "protocol",
    "status",
    "model_id",
  ] as const) {
    const raw = params.get(key);
    if (raw === null) continue;
    const values = splitCsv(raw).filter((s) => s.length > 0);
    if (values.length === 0) {
      return { ok: false, param: key };
    }
    (out as Record<string, string[]>)[key] = values;
  }
  return { ok: true, filters: out };
}
