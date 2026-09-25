// Small view helpers shared between pages.

import type { ModelEndpoint } from "../types";

/** True if the endpoint advertises vision / image inputs. */
export function hasVision(ep: ModelEndpoint): boolean {
  const caps = ep.capabilities || {};
  if (caps.vision) return true;
  const arch = ep.architecture;
  return !!(arch && Array.isArray(arch.input) && arch.input.includes("image"));
}

/** True if the endpoint advertises tool / function calling. */
export function hasToolCalling(ep: ModelEndpoint): boolean {
  const caps = ep.capabilities || {};
  if (caps.tool_calling || caps.toolCalling) return true;
  return false;
}

/** Map provider name → CSS class for the colored pill. */
export function providerClass(provider: string): string {
  const p = provider.toLowerCase();
  if (p === "nvidia") return "nvidia";
  if (p === "amd") return "amd";
  return "huggingface";
}

/** Format a context_length integer as "8K" / "128K" / "1M". */
export function fmtContext(ctx: number | null | undefined): string {
  if (ctx === null || ctx === undefined) return "?";
  if (ctx >= 1024 * 1024) return `${Math.round(ctx / (1024 * 1024))}M`;
  if (ctx >= 1024) return `${Math.round(ctx / 1024)}K`;
  return `${ctx}`;
}