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

/** OpenAI-compatible public model shape returned by /api/v1/models. */
export interface PublicModel {
  /** OpenAI: model identifier. We use the canonical model_id. */
  id: string;
  /** OpenAI: always "model". */
  object: "model";
  /** OpenAI: unix epoch seconds. We don't have a reliable release
   *  timestamp for every endpoint — use 0 (the documented "unknown"
   *  sentinel) rather than fabricate a value. */
  created: number;
  /** OpenAI: owner string. We surface the data_source as the
   *  human-readable owner label; e.g. nvidia, huggingface. */
  owned_by: string;
  /** TFI extension: data source (nvidia / amd / huggingface /
   *  openrouter / models_dev). */
  data_source: string;
  /** TFI extension: provider (nvidia / together / novita / etc.). */
  provider: string;
  /** Canonical normalized capabilities — see doc §12 for the
   *  fixed vocabulary. Order is stable for diff-friendly output. */
  capabilities: string[];
  /** Optional public detail fields. Always omitted when null/empty
   *  so the list endpoint stays compact. */
  name?: string;
  description?: string;
  architecture?: { input: string[]; output: string[] };
  context_length?: number;
  free?: boolean;
  lab?: string;
}

/** Stable capability sort order — keeps list responses diff-friendly. */
const CAPABILITY_ORDER = [
  "chat",
  "vision",
  "speech",
  "embedding",
  "reasoning",
  "tool_calling",
  "structured_output",
] as const;

/**
 * Project a canonical ``ModelEndpoint`` into the public API shape.
 *
 * Strips (by construction — we never read these fields):
 *   - provenance
 *   - metadata (raw source payload / pipeline internals)
 *   - pricing
 *   - endpoint_url / region / status / limits / score
 *   - fetched_at / canonical_model_id / model_family / organization /
 *     version / quantization
 */
export function toPublicModel(model: ModelEndpoint): PublicModel {
  const caps: string[] = [];
  for (const key of CAPABILITY_ORDER) {
    if (model.capabilities && model.capabilities[key] === true) {
      caps.push(key);
    }
  }
  // Surface any non-standard True capability keys too (forward compat).
  if (model.capabilities) {
    for (const [key, value] of Object.entries(model.capabilities)) {
      if (
        value === true &&
        !CAPABILITY_ORDER.includes(key as (typeof CAPABILITY_ORDER)[number])
      ) {
        caps.push(key);
      }
    }
  }

  const publicModel: PublicModel = {
    id: model.model_id,
    object: "model",
    created: 0,
    owned_by: model.data_source || model.provider || "unknown",
    data_source: model.data_source,
    provider: model.provider,
    capabilities: caps,
  };

  if (typeof model.name === "string" && model.name.length > 0) {
    publicModel.name = model.name;
  }
  if (typeof model.description === "string" && model.description.length > 0) {
    publicModel.description = model.description;
  }
  if (model.architecture) {
    publicModel.architecture = {
      input: Array.isArray(model.architecture.input)
        ? model.architecture.input.slice()
        : [],
      output: Array.isArray(model.architecture.output)
        ? model.architecture.output.slice()
        : [],
    };
  }
  if (typeof model.context_length === "number" && model.context_length > 0) {
    publicModel.context_length = model.context_length;
  }
  if (typeof model.free === "boolean") {
    publicModel.free = model.free;
  }
  if (typeof model.lab === "string" && model.lab.length > 0) {
    publicModel.lab = model.lab;
  }

  return publicModel;
}

/** Project a list of canonical endpoints (detail view keeps all fields). */
export function toPublicModels(models: ModelEndpoint[]): PublicModel[] {
  return models.map(toPublicModel);
}
