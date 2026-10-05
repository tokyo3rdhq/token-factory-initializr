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
 *  diff-friendly error messages. */
export const KNOWN_CAPABILITIES: ReadonlyArray<string> = [
  "chat",
  "vision",
  "speech",
  "embedding",
  "reasoning",
  "tool_calling",
  "structured_output",
];

/** Parsed, validated query filter. Always safe to apply. */
export interface ModelFilters {
  data_source?: string[];
  provider?: string[];
  capabilities?: string[];
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

  return filters;
}

/** Apply parsed filters to a list of canonical endpoints. */
export function filterEndpoints(
  endpoints: ModelEndpoint[],
  filters: ModelFilters
): ModelEndpoint[] {
  return endpoints.filter((ep) => {
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
    return true;
  });
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
