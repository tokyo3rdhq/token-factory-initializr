// Bifrost Token Factory generator.
//
// Implements the TokenFactoryGenerator contract for the Bifrost LLM
// gateway (https://docs.getbifrost.ai — Maxim AI).
//
// Bifrost consumes a single declarative `config.json` (or a UI/API
// equivalent). The relevant top-level keys for TFI's first cut are:
//
//   {
//     "$schema": "https://www.getbifrost.ai/schema",
//     "providers": {
//       "<provider_name>": {
//         "keys": [
//           {
//             "name":        "<key-name>",
//             "value":       "env.<PROVIDER_API_KEY>",
//             "models":      ["<model_id>", ...],
//             "weight":      1.0
//           }
//         ],
//         // For OpenAI-compatible endpoints Bifrost does NOT have a
//         // built-in provider for, use `custom_provider_config` with
//         // `base_provider_type: "openai"` + `network_config.base_url`.
//         "custom_provider_config": { ... },
//         "network_config": { ... }
//       }
//     }
//   }
//
// Per docs/tfi_add_bifrost_implementation.md §4 — schema source of
// truth is the official Bifrost docs at
// https://docs.getbifrost.ai/deployment-guides/config-json/providers.
// TFI targets the `config.json` shape (declarative, GitOps-friendly,
// supports any provider Bifrost can talk to). We deliberately do NOT
// emit governance / observability / clustering / MCP / virtual keys
// sections — those are out of Phase-1 scope (per spec §18).
//
// Per §5: secrets are NEVER embedded — we reference env vars via
// the `env.` prefix Bifrost documents explicitly.
//
// Per §6: model IDs are preserved EXACTLY (e.g.
// `meta-llama/Llama-3.3-70B-Instruct` is passed verbatim to Bifrost
// `keys[].models[]`). Bifrost's models array accepts arbitrary
// strings, so no URL-encoding or `/` substitution is needed.
//
// Per §7: capabilities (chat / vision / tool_calling / etc.) are
// NOT mapped into Bifrost config — Bifrost does not have a capability
// dimension in its config schema; routing is done at request time
// from the model_id. Carrying capability-shaped fields would invent
// unsupported Bifrost configuration.
//
// Per §12: providers Bifrost does NOT currently support (in this
// TFI first-cut) throw an explicit `GeneratorError`. Supported
// providers today:
//
//   * `huggingface` — Bifrost native provider
//   * `groq`        — Bifrost native provider
//   * `openrouter`  — Bifrost native provider
//   * `nvidia`      — Bifrost custom OpenAI-compatible provider
//                     (NVIDIA NIM uses the OpenAI-compatible API)
//                    baseURL = https://integrate.api.nvidia.com/v1
//   * `amd`         — Bifrost custom OpenAI-compatible provider
//                     (AMD Radeon Cloud exposes an OpenAI-compatible
//                     chat completions endpoint per the AMD Radeon Cloud
//                     docs at amd-aim.github.io/radeon-cloud-docs)
//                    baseURL = https://developer.amd.com.cn/radeon/api/v1
//
// Providers that need a fixed public base URL but Bifrost has no
// first-class type for (e.g. AMD Radeon Cloud, whose endpoint URL
// is dynamic and per-model) are NOT supported in this iteration;
// the generator throws GeneratorError so the UI surfaces an
// actionable error rather than silently producing a broken config.

import type { ModelEndpoint } from "../kv";
import {
  GeneratorError,
  type GenerationContext,
  type GeneratedConfig,
  type TokenFactoryGenerator,
  type TokenFactoryMeta,
} from "./types";

const META: TokenFactoryMeta = {
  id: "bifrost",
  name: "Bifrost",
  description:
    "A high-performance LLM gateway for routing and serving multiple model providers behind an OpenAI-compatible API.",
  formatLabel: "Bifrost providers[]",
};

/** Environment-variable name Bifrost expects per provider.
 *
 *  Bifrost's docs explicitly recommend the `env.<VAR>` prefix — we
 *  never inline a literal key. Adding a new Bifrost-native provider
 *  is a one-line change here. */
const PROVIDER_API_KEY_ENV: Record<string, string> = {
  huggingface: "HF_TOKEN",
  groq: "GROQ_API_KEY",
  openrouter: "OPENROUTER_API_KEY",
  nvidia: "NVIDIA_API_KEY",
  amd: "RADEON_API_KEY",
};

/** Providers Bifrost has a built-in type for. Anything outside this
 *  list goes through `custom_provider_config` (or errors). */
const NATIVE_PROVIDERS = new Set([
  "huggingface",
  "groq",
  "openrouter",
]);

/** Custom OpenAI-compatible providers we explicitly support in TFI's
 *  first iteration. Each carries a documented public base URL the
 *  user can sanity-check against their own deployment. */
const CUSTOM_OPENAI_BASE_URLS: Record<string, string> = {
  nvidia: "https://integrate.api.nvidia.com/v1",
  // AMD Radeon Cloud — OpenAI-compatible chat completions per the
  // official AMD Radeon Cloud docs (amd-aim.github.io/radeon-cloud-docs
  // Quickstart). The Authorization header carries the bearer token
  // (RADEON_API_KEY), which Bifrost passes through unchanged when
  // the upstream is OpenAI-compatible.
  amd: "https://developer.amd.com.cn/radeon/api/v1",
};

/** Per-provider ordering for stable JSON output. Bifrost doesn't
 *  mandate ordering, but a stable order keeps the generated config
 *  diff-friendly across runs. */
const PROVIDER_ORDER = [
  "nvidia",
  "amd",
  "huggingface",
  "groq",
  "openrouter",
];

interface BifrostProviderConfig {
  keys: Array<{
    name: string;
    value: string;
    models: string[];
    weight: number;
  }>;
  /** Only set for custom OpenAI-compatible providers. */
  custom_provider_config?: {
    base_provider_type: "openai";
  };
  /** Network config — required for custom providers (base_url); optional otherwise. */
  network_config?: {
    base_url?: string;
  };
}

interface BifrostConfig {
  $schema: string;
  providers: Record<string, BifrostProviderConfig>;
}

/** Stable JSON.stringify with sorted keys (deep). */
function stableJson(obj: unknown): string {
  return JSON.stringify(obj, (_key, value: unknown) => {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const sorted: Record<string, unknown> = {};
      for (const k of Object.keys(value as Record<string, unknown>).sort()) {
        sorted[k] = (value as Record<string, unknown>)[k];
      }
      return sorted;
    }
    return value;
  }, 2);
}

function resolveApiKeyEnv(provider: string): string {
  return (
    PROVIDER_API_KEY_ENV[provider] ?? `${provider.toUpperCase()}_API_KEY`
  );
}

function renderBifrostConfig(models: ModelEndpoint[]): string {
  // Group models by provider — Bifrost's config keys are per-provider.
  // Preserve input order within each provider for diff-friendly output.
  const grouped = new Map<string, ModelEndpoint[]>();
  for (const ep of models) {
    const list = grouped.get(ep.provider);
    if (list) {
      list.push(ep);
    } else {
      grouped.set(ep.provider, [ep]);
    }
  }

  const providers: Record<string, BifrostProviderConfig> = {};

  // Iterate providers in stable order so the JSON output is
  // deterministic regardless of input map insertion order.
  const orderedProviders = Array.from(grouped.keys()).sort((a, b) => {
    const ai = PROVIDER_ORDER.indexOf(a);
    const bi = PROVIDER_ORDER.indexOf(b);
    if (ai === -1 && bi === -1) return a.localeCompare(b);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });

  for (const provider of orderedProviders) {
    const providerModels = grouped.get(provider) ?? [];

    if (NATIVE_PROVIDERS.has(provider)) {
      // Bifrost has a built-in provider type — just emit keys[].
      providers[provider] = {
        keys: [
          {
            name: `${provider}-primary`,
            value: `env.${resolveApiKeyEnv(provider)}`,
            // model_ids preserved verbatim per §6 (e.g.
            // `meta-llama/Llama-3.3-70B-Instruct`).
            models: providerModels.map((m) => m.model_id),
            weight: 1.0,
          },
        ],
      };
    } else if (provider in CUSTOM_OPENAI_BASE_URLS) {
      // OpenAI-compatible provider — Bifrost needs the base URL
      // baked into network_config + custom_provider_config declaring
      // the base protocol as `openai`.
      const baseUrl = CUSTOM_OPENAI_BASE_URLS[provider];
      providers[provider] = {
        keys: [
          {
            name: `${provider}-primary`,
            value: `env.${resolveApiKeyEnv(provider)}`,
            models: providerModels.map((m) => m.model_id),
            weight: 1.0,
          },
        ],
        custom_provider_config: {
          base_provider_type: "openai",
        },
        network_config: {
          base_url: baseUrl,
        },
      };
    } else {
      // Unsupported provider per §12 — surface an actionable error
      // so the UI tells them why their selection can't be expressed
      // in Bifrost config yet.
      throw new GeneratorError(
        `Bifrost config does not support provider "${provider}" in this iteration. ` +
          `Supported providers: ${[...NATIVE_PROVIDERS, ...Object.keys(CUSTOM_OPENAI_BASE_URLS)].join(", ")}. ` +
          `Pick only models whose provider is in that set.`,
        400,
      );
    }
  }

  const config: BifrostConfig = {
    $schema: "https://www.getbifrost.ai/schema",
    providers,
  };

  return stableJson(config) + "\n";
}

export const bifrostGenerator: TokenFactoryGenerator = {
  id: "bifrost",
  meta: META,
  generate(models: ModelEndpoint[], _ctx: GenerationContext): GeneratedConfig {
    if (models.length === 0) {
      throw new GeneratorError(
        "No models selected. Select one or more models before generating.",
        400,
      );
    }
    return {
      format: "bifrost",
      content: renderBifrostConfig(models),
      filename: "config.json",
    };
  },
};