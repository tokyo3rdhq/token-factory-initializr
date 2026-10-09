// LiteLLM config generator.
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

import type { ModelEndpoint } from "./kv";

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

function slugFromModelId(modelId: string): string {
  // ``google/gemma-4-31b-it`` -> ``gemma-4-31b-it``
  // ``owner/some-model-v2`` -> ``some-model-v2``
  // ``no-slash``           -> ``no-slash``
  const slash = modelId.indexOf("/");
  return slash >= 0 ? modelId.slice(slash + 1) : modelId;
}

function yamlEscape(value: string): string {
  // Single-quoted YAML; double single-quotes to escape.
  return `'${value.replace(/'/g, "''")}'`;
}

export interface GenerateLiteLLMArgs {
  models: ModelEndpoint[];
  /** When true (default), emit ``api_key: os.environ/<KEY>``. */
  includeApiKey?: boolean;
}

/**
 * Render a ``model_list:`` YAML fragment for the given endpoints.
 * Empty input produces an empty model_list.
 */
export function generateLiteLLM({
  models,
  includeApiKey = true,
}: GenerateLiteLLMArgs): string {
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

/**
 * Render an agent-friendly instruction block that asks the agent
 * to fetch a generated config URL and merge it into the user's
 * existing LiteLLM config. Kept short on purpose so the prompt
 * survives context-window truncation when relayed between
 * different LLM clients.
 */
export function generateAgentPrompt(generatedUrl: string): string {
  return [
    "You are integrating a Token Factory Initializr generated config.",
    "Fetch this URL and merge the LiteLLM `model_list` entries into",
    "the user's existing litellm config:",
    "",
    `  ${generatedUrl}`,
    "",
    "Rules:",
    "  1. Preserve every model already in the user's config.",
    "  2. Add only entries whose `model_name` is not already present.",
    "  3. Do not overwrite unrelated keys (router_settings,",
    "     litellm_settings, general_settings, etc.).",
    "  4. Treat this URL as short-lived; do not cache the response.",
  ].join("\n");
}

/** Random 8-character URL-safe id. Used by /api/generate. */
export function generateId(): string {
  const alphabet =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  let out = "";
  for (const b of bytes) {
    out += alphabet[b % alphabet.length];
  }
  return out;
}