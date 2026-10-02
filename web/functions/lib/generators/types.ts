// Token Factory generator abstraction — types.
//
// Per docs/tfi_phase_1_initializr_core_workflow.md §4 — Model selection
// must be independent from Token Factory implementation. The
// architecture allows:
//
//   SelectedModels           →   LiteLLMGenerator   → GeneratedConfig
//                          →   NewAPIGenerator    → GeneratedConfig
//                          →   FutureGenerator    → GeneratedConfig
//
// rather than baking LiteLLM-specific logic into the UI / shared
// code. Each implementation owns its own output format.

import type { ModelEndpoint } from "../kv";

/**
 * Identifier for a Token Factory implementation. New values are added
 * by implementing the {@link TokenFactoryGenerator} interface and
 * registering the implementation in {@link getGenerator}.
 */
export type TokenFactoryId = "litellm" | "newapi";

/**
 * Display metadata for a Token Factory — what the picker UI renders
 * and what the result panel headers show. Defined alongside the
 * generators in {@link GENERATORS} so the source of truth is one
 * place.
 */
export interface TokenFactoryMeta {
  id: TokenFactoryId;
  /** Endonym label shown in the picker / header. */
  name: string;
  /** Single-line or sentence for the picker subtitle. */
  description: string;
  /** Human-readable format identifier shown in the result header. */
  formatLabel: string;
}

/**
 * Canonical generated artifact. Copy + download must consume this
 * exact payload (per doc §14 / §15). ``filename`` is used by the
 * download action; ``content`` is the raw configuration text.
 */
export interface GeneratedConfig {
  format: TokenFactoryId;
  content: string;
  filename: string;
}

/**
 * Generation context the caller passes to the generator. Currently
 * just the human-readable URL for the agent-prompt template, but
 * reserved as the expansion surface for future context inputs
 * (project name, env-var prefix override, etc.) per doc §10.
 */
export interface GenerationContext {
  /** Public URL pointing at the generated artifact (used by the
   *  agent-prompt template — server-generated, never embedded in
   *  the artifact itself). */
  generatedUrl: string;
}

/**
 * Token Factory generator contract.
 *
 * Implementations MUST be deterministic: same models + same context
 * → same content. They MUST NOT silently substitute values, drop
 * models, or invent fake data when required metadata is missing
 * (per doc §20). Missing-metadata cases throw
 * {@link GeneratorError} which the caller maps to a 4xx response.
 */
export interface TokenFactoryGenerator {
  readonly id: TokenFactoryId;
  readonly meta: TokenFactoryMeta;

  /**
   * Transform ``models`` into a Token-Factory-specific configuration.
   * Returns the raw artifact text + a suggested filename.
   */
  generate(
    models: ModelEndpoint[],
    context: GenerationContext,
  ): GeneratedConfig;
}

/**
 * Thrown by a generator when a required input is missing or the
 * configuration cannot be produced safely. The /api/generate
 * handler maps this to a 4xx response with the message; the UI
 * renders it verbatim so the user sees the actionable cause
 * (per doc §20).
 */
export class GeneratorError extends Error {
  readonly status: number;
  constructor(message: string, status = 400) {
    super(message);
    this.name = "GeneratorError";
    this.status = status;
  }
}