// Token Factory generator registry.
//
// Single source of truth for "which Token Factory implementations
// does TFI support, in what order, and what metadata is shown to
// the user". New generators register here and (optionally) ship a
// client-side preview config so the picker can render description +
// format label without duplicating that text into the React layer.
//
// Per docs/tfi_phase_1_initializr_core_workflow.md §8 — the picker
// should iterate real product capabilities rather than arbitrary UI
// strings. Adding a Token Factory is one new file + one line here.

import type { ModelEndpoint } from "../kv";
import { litellmGenerator } from "./litellm";
import { newapiGenerator } from "./newapi";
import { GeneratorError, type GenerationContext, type GeneratedConfig, type TokenFactoryGenerator, type TokenFactoryId, type TokenFactoryMeta } from "./types";

/**
 * Authoritative list of Token Factories. The order here drives:
 *   - the picker UI order (Generate.tsx iterates this list)
 *   - the API dispatch order (validated-id-token → format mapping)
 *
 * Adding a Token Factory = add an implementation in
 * generators/<id>.ts + register it here.
 */
export const GENERATORS: Record<TokenFactoryId, TokenFactoryGenerator> = {
  litellm: litellmGenerator,
  newapi: newapiGenerator,
};

/** Token Factory metadata in picker-display order. */
export const TOKEN_FACTORY_META: TokenFactoryMeta[] = Object.values(
  GENERATORS,
).map((g) => g.meta);

/**
 * Dispatch a generation request to the right Token Factory by id.
 *
 * Throws {@link GeneratorError} with ``status: 400`` when the id is
 * not registered — the API handler maps that to a 4xx response so
 * the caller sees an actionable error rather than a server crash.
 */
export function generateWith(
  format: TokenFactoryId,
  models: ModelEndpoint[],
  context: GenerationContext,
): GeneratedConfig {
  const gen = GENERATORS[format];
  if (!gen) {
    throw new GeneratorError(
      `unsupported Token Factory: ${format}`,
      400,
    );
  }
  return gen.generate(models, context);
}

/** All supported Token Factory ids — single source for client + server. */
export const SUPPORTED_TOKEN_FACTORIES = Object.keys(GENERATORS) as TokenFactoryId[];

// Re-exports for consumers — flatten the public surface of the
// generators module.
export type { TokenFactoryId, TokenFactoryMeta, GeneratedConfig } from "./types";
export { GeneratorError } from "./types";
export { litellmGenerator } from "./litellm";
export { newapiGenerator } from "./newapi";