// LiteLLM Token Factory generator.
//
// Implements the TokenFactoryGenerator contract for the LiteLLM
// gateway. Per docs/tfi_phase_1_initializr_core_workflow.md §11 —
// LiteLLM is the first fully working generator.
//
// Produces a YAML fragment shaped per the example in AGENTS.md §18:
//
//   model_list:
//     - model_name: <provider>-<slug>
//       litellm_params:
//         model: <provider>/<model_id>
//         api_key: os.environ/<PROVIDER>_API_KEY
//
// Real API keys are NEVER stored — we always reference env vars.
// Provider-specific auth is hard-coded for the three supported
// providers; future providers should extend the API_KEY_ENV table.

import type { ModelEndpoint } from "../kv";
import { GeneratorError, type GenerationContext, type GeneratedConfig, type TokenFactoryGenerator, type TokenFactoryMeta } from "./types";

/** API key env var name keyed by data source (not provider — the
 *  same data source may host multiple inference providers under one
 *  gateway, e.g. Hugging Face routing to together, openrouter, etc.). */
const API_KEY_ENV: Record<string, string> = {
  nvidia: "NVIDIA_API_KEY",
  amd: "AMD_API_KEY",
  huggingface: "HUGGING_FACE_API_KEY",
};
/** LiteLLM model-field prefix keyed by data source. */
const DATA_SOURCE_PREFIX: Record<string, string> = {
  nvidia: "nvidia_nim",
  amd: "openai",
  huggingface: "huggingface",
};
function litellmModelPrefix(ep: ModelEndpoint): string {
  const prefix = DATA_SOURCE_PREFIX[ep.data_source] ?? ep.data_source;
  // The Hugging Face router requires the inference provider in the
  // path: huggingface/<provider>/<model_id> (e.g. huggingface/together/…).
  return ep.data_source === "huggingface"
    ? `${prefix}/${ep.provider}`
    : prefix;
}
const META: TokenFactoryMeta = {
  id: "litellm",
  name: "LiteLLM",
  description:
    "Open-source Python SDK + proxy that unifies 100+ LLM APIs behind the OpenAI interface.",
  formatLabel: "LiteLLM model_list",
};

function slugFromModelId(modelId: string): string {
  // ``google/gemma-4-31b-it`` -> ``gemma-4-31b-it``
  // ``owner/some-model-v2`` -> ``some-model-v2``
  // ``no-slash``           -> ``no-slash``
  const slash = modelId.indexOf("/");
  return slash >= 0 ? modelId.slice(slash + 1) : modelId;
}

function yamlEscape(value: string): string {
  // Defence-in-depth hardening per security audit finding F4.
  //
  // 1. Reject ASCII control characters outright. A model_id with a
  //    literal newline would otherwise break the YAML line and let
  //    an attacker inject adjacent `model_list:` entries. Provider
  //    fetchers already strip / reject such inputs upstream, but
  //    we re-check here so a future provider that bypasses
  //    validation cannot reach this function with unsafe input.
  //
  // 2. Keep single-quoted YAML (vulnerable to a lone trailing `'`
  //    if the doubling logic ever regresses; the doubling is
  //    preserved below).
  if (/[\x00-\x1f\x7f]/.test(value)) {
    throw new Error(
      "yamlEscape: refusing to render value containing ASCII control character",
    );
  }
  return `'${value.replace(/'/g, "''")}'`;
}

/** Render a ``model_list:`` YAML fragment. Empty → empty model_list. */
function renderLiteLLMYaml(
  models: ModelEndpoint[],
  includeApiKey = true,
): string {
  if (models.length === 0) {
    return "model_list: []\n";
  }
  const lines: string[] = ["model_list:"];
  for (const ep of models) {
    const slug = slugFromModelId(ep.model_id);
    const modelName = `${ep.provider}-${slug}`;
    const apiKeyEnv = API_KEY_ENV[ep.data_source] ?? `${ep.data_source.toUpperCase()}_API_KEY`;
    lines.push(`  - model_name: ${yamlEscape(modelName)}`);
    lines.push(`    litellm_params:`);
    lines.push(`      model: ${yamlEscape(`${litellmModelPrefix(ep)}/${ep.model_id}`)}`);
    if (includeApiKey) {
      lines.push(`      api_key: os.environ/${apiKeyEnv}`);
    }
  }
  return lines.join("\n") + "\n";
}

export const litellmGenerator: TokenFactoryGenerator = {
  id: "litellm",
  meta: META,
  generate(models: ModelEndpoint[], _ctx: GenerationContext): GeneratedConfig {
    if (models.length === 0) {
      // Per doc §9 + §19 — generation is unavailable when no models
      // are selected. We throw here so the caller maps to a 4xx
      // rather than silently emitting an empty config.
      throw new GeneratorError(
        "No models selected. Select one or more models before generating.",
        400,
      );
    }
    return {
      format: "litellm",
      content: renderLiteLLMYaml(models),
      filename: "config-litellm.yaml",
    };
  },
};

/** Re-export the legacy function for the rest of the codebase
 *  (the existing /api/generate endpoint imports `generateLiteLLM`
 *  directly). Once the API endpoint has been migrated to dispatch
 *  via {@link getGenerator}, this re-export can be removed. */
export function generateLiteLLM({
  models,
  includeApiKey = true,
}: {
  models: ModelEndpoint[];
  includeApiKey?: boolean;
}): string {
  return renderLiteLLMYaml(models, includeApiKey);
}