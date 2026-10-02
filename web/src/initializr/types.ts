// Initializr domain model.
//
// Per docs/tfi_phase_1_initializr_core_workflow.md §3 the React
// component state must NOT become the domain model — instead the
// app maintains an explicit InitializrState:
//
//   selectedModels:  SelectedModel[]
//   tokenFactory:    TokenFactoryId | null
//
// Selection happens in the Browse page; Token Factory choice is
// made on the Generate page. They live in the same context so the
// generator always sees both inputs together and can validate them
// as a single artifact (per doc §9 — generation preconditions
// require BOTH conditions to be true).

import type { ModelEndpoint } from "../types";

/** A single model the user has marked as a candidate. */
export interface SelectedModel extends ModelEndpoint {}

/**
 * Token Factory implementation identifiers. Mirrors the server-side
 * definition in ``web/functions/lib/generators/types.ts``. Adding
 * a new factory = extend this union AND register a generator on
 * the server.
 */
export type TokenFactoryId = "litellm" | "newapi";

/**
 * The complete session state. ``tokenFactory === null`` means the user
 * has not yet chosen (per doc §9 the Generate action is unavailable
 * in this state). ``selectedModels === []`` likewise blocks
 * generation with an actionable message rather than silently
 * emitting an empty config.
 */
export interface InitializrState {
  selectedModels: SelectedModel[];
  tokenFactory: TokenFactoryId | null;
}

/** Validation result used by the Generate UI to drive disabled state. */
export interface InitializrReadiness {
  ready: boolean;
  /** Reason for not-ready (i18n key the UI maps via ts()). */
  reason: "initializr.validation.noModels" | "initializr.validation.noFactory" | null;
}