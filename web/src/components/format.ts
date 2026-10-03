// Small view helpers shared between pages.
//
// All predicates read the canonical snake_case keys that the normalize
// stage (``data.process.normalize.normalize_capabilities``) writes into
// every endpoint's ``capabilities`` field. There is no dual-key fallback
// — every nvidia / huggingface / amd endpoint reaches the consumer in
// the same shape.

import type { ModelEndpoint } from "../types";

/** True if the endpoint advertises vision / image inputs. */
export function hasVision(ep: ModelEndpoint): boolean {
  if (ep.capabilities?.vision) return true;
  const arch = ep.architecture;
  return !!(arch && Array.isArray(arch.input) && arch.input.includes("image"));
}

/** True if the endpoint advertises tool / function calling. */
export function hasToolCalling(ep: ModelEndpoint): boolean {
  return ep.capabilities?.tool_calling === true;
}

/** Map provider name → CSS class for the colored pill. */
export function providerClass(provider: string): string {
  const p = provider.toLowerCase();
  if (p === "nvidia") return "nvidia";
  if (p === "amd") return "amd";
  return "huggingface";
}

/** Format a context_length integer as "8K" / "128K" / "1M".
 *  Returns null when the context is missing — callers should hide
 *  the badge rather than render "?" (negative space is more honest). */
export function fmtContext(ctx: number | null | undefined): string | null {
  if (ctx === null || ctx === undefined) return null;
  if (ctx >= 1024 * 1024) return `${Math.round(ctx / (1024 * 1024))}M`;
  if (ctx >= 1024) return `${Math.round(ctx / 1024)}K`;
  return `${ctx}`;
}