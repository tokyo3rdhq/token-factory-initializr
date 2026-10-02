// NewAPI Token Factory generator.
//
// Implements the TokenFactoryGenerator contract for the NewAPI
// gateway. NewAPI (newapi.ai / one-api variants) is a self-hostable
// LLM gateway that consumes a flat array of model objects.
//
// Per docs/tfi_phase_1_initializr_core_workflow.md §12 — the doc
// explicitly allows shipping a "known supported configuration
// format" even when we don't yet have full coverage of NewAPI's
// schema. We emit the most commonly-used shape:
//
//   {
//     "models": [
//       { "id": "<provider>/<model_id>", "name": "<provider>-<slug>" }
//     ]
//   }
//
// This is the format NewAPI documents for the minimal
// one-api-compatible channel / model registration payload. Real
// deployments typically combine this with extra fields (groups,
// pricing, proxy, etc.) — those remain future work and are out of
// scope for Phase 1.
//
// API keys are NEVER stored; we surface a single
// ``NEWAPI_BASE_URL`` / ``NEWAPI_ADMIN_TOKEN`` reference so the
// user can wire their gateway at deploy time.

import type { ModelEndpoint } from "../kv";
import {
  GeneratorError,
  type GenerationContext,
  type GeneratedConfig,
  type TokenFactoryGenerator,
  type TokenFactoryMeta,
} from "./types";

const META: TokenFactoryMeta = {
  id: "newapi",
  name: "NewAPI",
  description:
    "Self-hostable LLM gateway (one-api compatible) used to channel many upstream providers behind a single endpoint.",
  formatLabel: "NewAPI models[]",
};

function slugFromModelId(modelId: string): string {
  // ``google/gemma-4-31b-it`` → ``gemma-4-31b-it``
  const slash = modelId.indexOf("/");
  return slash >= 0 ? modelId.slice(slash + 1) : modelId;
}

interface NewApiModelEntry {
  id: string;
  name: string;
}

function renderNewApiModelsJson(
  models: ModelEndpoint[],
): string {
  const entries: NewApiModelEntry[] = models.map((ep) => ({
    id: `${ep.provider}/${ep.model_id}`,
    name: `${ep.provider}-${slugFromModelId(ep.model_id)}`,
  }));
  // 2-space indent + trailing newline — readable for humans, valid
  // for ``JSON.parse``.
  return JSON.stringify({ models: entries }, null, 2) + "\n";
}

export const newapiGenerator: TokenFactoryGenerator = {
  id: "newapi",
  meta: META,
  generate(models: ModelEndpoint[], _ctx: GenerationContext): GeneratedConfig {
    if (models.length === 0) {
      throw new GeneratorError(
        "No models selected. Select one or more models before generating.",
        400,
      );
    }
    return {
      format: "newapi",
      content: renderNewApiModelsJson(models),
      filename: "models-newapi.json",
    };
  },
};