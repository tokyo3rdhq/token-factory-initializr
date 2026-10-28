/**
 * Pricing presentation utilities.
 *
 * Handles parsing, formatting, and normalizing pricing data from various
 * providers (Hugging Face, OpenRouter, Kilo) into consistent, human-readable
 * display entries. Follows the specification in
 * docs/tfi_pricing_badge_and_tooltips_adaption.md.
 */

import type { ModelEndpoint } from "../types";

/**
 * Pricing field metadata for presentation.
 * Maps raw field names to human-readable labels, display order, and unit info.
 */
export interface PricingFieldMeta {
  /** Raw field name in the pricing dictionary. */
  rawKey: string;
  /** Human-readable label for display. */
  label: string;
  /** Display order (lower = shown first). */
  order: number;
  /** Unit or formatting policy. */
  unit: "per_1M_tokens" | "per_request" | "per_image" | "per_search" | "percentage" | "unknown" | "discount";
  /** Source applicability: which providers use this field. */
  sources: string[];
  /** Whether this field is a monetary charge (vs a modifier like discount). */
  isCharge: boolean;
  /** Canonical key for alias normalization. */
  canonicalKey: string;
}

/**
 * Canonical field metadata registry.
 * Maps raw field names to presentation metadata.
 * Extensible for new providers without changing core logic.
 */
export const PRICING_FIELD_META: Record<string, PricingFieldMeta> = {
  // Hugging Face style
  input: {
    rawKey: "input",
    label: "Input tokens",
    order: 10,
    unit: "per_1M_tokens",
    sources: ["huggingface"],
    isCharge: true,
    canonicalKey: "input_tokens",
  },
  output: {
    rawKey: "output",
    label: "Output tokens",
    order: 20,
    unit: "per_1M_tokens",
    sources: ["huggingface"],
    isCharge: true,
    canonicalKey: "output_tokens",
  },

  // OpenRouter / Kilo style
  prompt: {
    rawKey: "prompt",
    label: "Input tokens",
    order: 10,
    unit: "per_1M_tokens",
    sources: ["openrouter", "kilo"],
    isCharge: true,
    canonicalKey: "input_tokens",
  },
  completion: {
    rawKey: "completion",
    label: "Output tokens",
    order: 20,
    unit: "per_1M_tokens",
    sources: ["openrouter", "kilo"],
    isCharge: true,
    canonicalKey: "output_tokens",
  },
  // Cache-related
  input_cache_read: {
    rawKey: "input_cache_read",
    label: "Cached input read",
    order: 30,
    unit: "per_1M_tokens",
    sources: ["openrouter", "kilo"],
    isCharge: true,
    canonicalKey: "cached_input_read",
  },
  input_cache_write: {
    rawKey: "input_cache_write",
    label: "Cached input write",
    order: 40,
    unit: "per_1M_tokens",
    sources: ["openrouter", "kilo"],
    isCharge: true,
    canonicalKey: "cache_write",
  },
  input_cache_write_1h: {
    rawKey: "input_cache_write_1h",
    label: "Cached input write 1h",
    order: 41,
    unit: "per_1M_tokens",
    sources: ["openrouter", "kilo"],
    isCharge: true,
    canonicalKey: "cache_write_1h",
  },

  // Image / multimodal
  image: {
    rawKey: "image",
    label: "Image",
    order: 60,
    unit: "per_1M_tokens",
    sources: ["kilo"],
    isCharge: true,
    canonicalKey: "image",
  },

  // Audio
  audio: {
    rawKey: "audio",
    label: "Audio",
    order: 61,
    unit: "per_1M_tokens",
    sources: ["openrouter", "kilo"],
    isCharge: true,
    canonicalKey: "audio",
  },

  // Audio cache
  input_audio_cache: {
    rawKey: "input_audio_cache",
    label: "Cached audio input",
    order: 31,
    unit: "per_1M_tokens",
    sources: ["openrouter", "kilo"],
    isCharge: true,
    canonicalKey: "cached_audio_input",
  },

  // Web search
  web_search: {
    rawKey: "web_search",
    label: "Web search",
    order: 70,
    unit: "per_search",
    sources: ["openrouter", "kilo"],
    isCharge: true,
    canonicalKey: "web_search",
  },

  // Request-based
  request: {
    rawKey: "request",
    label: "Request",
    order: 50,
    unit: "per_request",
    sources: ["kilo"],
    isCharge: true,
    canonicalKey: "request",
  },

  // Internal reasoning
  internal_reasoning: {
    rawKey: "internal_reasoning",
    label: "Internal reasoning",
    order: 80,
    unit: "per_1M_tokens",
    sources: ["kilo"],
    isCharge: true,
    canonicalKey: "internal_reasoning",
  },

  // Discount / modifier
  discount: {
    rawKey: "discount",
    label: "Discount",
    order: 90,
    unit: "discount",
    sources: ["openrouter", "kilo"],
    isCharge: false,
    canonicalKey: "discount",
  },
};

/**
 * Alias mapping: map synonymous raw keys to canonical keys.
 * e.g., both "input" and "prompt" map to "input_tokens".
 */
export const FIELD_ALIASES: Record<string, string> = {
  input: "input_tokens",
  prompt: "input_tokens",
  output: "output_tokens",
  completion: "output_tokens",
};

/**
 * Get the canonical key for a raw field name.
 */
export function getCanonicalKey(rawKey: string): string {
  return FIELD_ALIASES[rawKey] ?? PRICING_FIELD_META[rawKey]?.canonicalKey ?? rawKey;
}

/**
 * Get field metadata for a raw key, or a default for unknown fields.
 */
export function getFieldMeta(rawKey: string, source?: string): PricingFieldMeta {
  const meta = PRICING_FIELD_META[rawKey];
  if (meta) {
    // If source is specified, verify this field applies to the source
    if (source && !meta.sources.includes(source)) {
      // Return a generic meta for this source
      return {
        rawKey,
        label: rawKey.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
        order: 100,
        unit: "unknown",
        sources: [source || "unknown"],
        isCharge: true,
        canonicalKey: getCanonicalKey(rawKey),
      };
    }
    return meta;
  }

  // Unknown field - return generic metadata
  return {
    rawKey,
    label: rawKey.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    order: 100,
    unit: "unknown",
    sources: source ? [source] : ["unknown"],
    isCharge: true,
    canonicalKey: getCanonicalKey(rawKey),
  };
}

/**
 * A normalized pricing entry ready for display.
 */
export interface NormalizedPricingEntry {
  /** Canonical field key (e.g., "input_tokens"). */
  key: string;
  /** Display label (e.g., "Input tokens"). */
  label: string;
  /** Formatted value string (e.g., "$0.000001 / 1M tokens"). */
  formatted: string;
  /** Raw numeric value for sorting/comparison. */
  value: number;
  /** Raw field name from source. */
  rawKey: string;
  /** Unit/type of the field. */
  unit: PricingFieldMeta["unit"];
  /** Source provider name. */
  source: string;
  /** Whether this is a charge (true) or modifier (false). */
  isCharge: boolean;
  /** Display order. */
  order: number;
}

/**
 * Sentinel value used by some providers (OpenRouter/Kilo) to indicate unknown pricing.
 */
export const UNKNOWN_SENTINEL = -1;

/**
 * Safely parse a pricing value from string or number.
 * Returns null for invalid, missing, or sentinel values.
 * Preserves genuine zero values.
 */
export function parsePricingValue(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return null;
    if (value === UNKNOWN_SENTINEL) return null; // -1 sentinel
    return value;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed === "") return null;
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) return null;
    if (parsed === UNKNOWN_SENTINEL) return null; // "-1" sentinel
    return parsed;
  }
  return null;
}
/**
 * Shared Intl.NumberFormat for pricing display.
 * - Always at least 2 fractional digits.
 * - Up to 20 fractional digits, trailing zeros stripped by Intl.
 * - No thousands grouping separators.
 */
const priceFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 20,
  useGrouping: false,
});

/**
 * Format a per-token price as USD per 1M tokens.
 *
 * The value is already normalized at the data layer (multiplied by 1M,
 * rounded to 4 decimals, trailing zeros truncated, stored as string).
 * Web layer only formats it for display — no further multiplication.
 */
export function formatPerTokenPrice(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return "$0.00 / 1M tokens";

  return `$${priceFormatter.format(value)} / 1M tokens`;
}

/**
 * Format a per-request/image/search price.
 */
export function formatPerUnitPrice(value: number, unit: string): string {
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return `$0.00 per ${unit}`;

  return `$${priceFormatter.format(value)} per ${unit}`;
}



/**
 * Format a discount value.
 * Since discount semantics are provider-specific, display conservatively.
 */
export function formatDiscount(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return "0%";
  // Display as percentage, but note it's provider-defined
  return `${(value * 100).toFixed(2)}% (provider-defined)`;
}

/**
 * Format a pricing value according to its unit policy.
 */
export function formatPricingValue(value: number, unit: PricingFieldMeta["unit"]): string {
  if (!Number.isFinite(value)) return "—";

  switch (unit) {
    case "per_1M_tokens":
      return formatPerTokenPrice(value);
    case "per_request":
      return formatPerUnitPrice(value, "request");
    case "per_image":
      return formatPerUnitPrice(value, "image");
    case "per_search":
      return formatPerUnitPrice(value, "search");
    case "percentage":
      return `${(value * 100).toFixed(2)}%`;
    case "discount":
      return formatDiscount(value);
    case "unknown":
    default:
      // Unknown unit - display raw value with note
      return `${value.toFixed(6)} (unit not specified)`;
  }
}

/**
 * Normalize a raw pricing dictionary into presentation-ready entries.
 * Handles alias normalization, sentinel filtering, and value formatting.
 */
export function normalizePricingEntries(
  pricing: Record<string, unknown> | null | undefined,
  source: string = "unknown",
): NormalizedPricingEntry[] {
  if (!pricing || typeof pricing !== "object") return [];

  const entries: NormalizedPricingEntry[] = [];
  const seenCanonical = new Set<string>();

  for (const [rawKey, rawValue] of Object.entries(pricing)) {
    const parsed = parsePricingValue(rawValue);
    if (parsed === null) continue; // Skip invalid/sentinel values

    const meta = getFieldMeta(rawKey);
    const canonicalKey = getCanonicalKey(rawKey);

    // Skip duplicate canonical keys (alias collision)
    if (seenCanonical.has(canonicalKey)) continue;
    seenCanonical.add(canonicalKey);

    const formatted = formatPricingValue(parsed, meta.unit);

    entries.push({
      key: canonicalKey,
      label: meta.label,
      formatted,
      value: parsed,
      rawKey,
      unit: meta.unit,
      source,
      isCharge: meta.isCharge,
      order: meta.order,
    });
  }

  // Sort by display order
  entries.sort((a, b) => a.order - b.order);
  return entries;
}

/**
 * Get the data source name from an endpoint for pricing display purposes.
 */
export function getPricingSource(endpoint: ModelEndpoint): string {
  // For Hugging Face, the provider is the actual inference provider
  if (endpoint.data_source === "huggingface") {
    return endpoint.provider;
  }
  return endpoint.data_source;
}

/**
 * Check if a pricing status indicates the endpoint has usable pricing details.
 */
export function hasPricingDetails(endpoint: ModelEndpoint): boolean {
  if (!endpoint.pricing || typeof endpoint.pricing !== "object") return false;
  const entries = normalizePricingEntries(endpoint.pricing, getPricingSource(endpoint));
  return entries.length > 0;
}

/**
 * Get display label for pricing status.
 */
export function getPricingStatusLabel(status: string | null | undefined): string {
  switch (status) {
    case "free":
      return "Free";
    case "priced":
      return "Pricing";
    case "unknown":
      return "Unknown";
    default:
      return "Unknown";
  }
}

/**
 * Get badge variant for pricing status.
 */
export function getPricingStatusVariant(status: string | null | undefined): "success" | "neutral" | "warning" | "accent" {
  switch (status) {
    case "free":
      return "success";
    case "priced":
      return "accent";
    case "unknown":
      return "neutral";
    default:
      return "neutral";
  }
}

/**
 * Get badge dot prop for pricing status.
 */
export function getPricingStatusDot(status: string | null | undefined): boolean {
  return status === "free";
}