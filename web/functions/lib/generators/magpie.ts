// Magpie Token Factory generator.
//
// Implements the TokenFactoryGenerator contract for the Magpie AI
// gateway configuration. Produces a strict-JSON provider configuration
// shaped per the canonical Magpie template at
// /tmp/providers.json (see docs/tfi_add_support_for_magpie_configuration_generation.md
// §3).
//
// Per §2, each provider entry exposes four dynamic fields and keeps
// every static template field:
//
//   - key      → always "" (the user enters the API key in Magpie)
//   - pickedFrom → every model ID currently available in TFI for the
//     corresponding data source — not merely the selected models
//   - models   → only the model IDs the user selected for that source
//   - chat     → the selected model endpoint's base URL
//
// The transformation is pure: given the selected models, the full
// catalog (for pickedFrom), and the read-only template, it produces
// deterministic output. Missing or conflicting endpoint data throws
// GeneratorError so the UI surfaces an actionable message
// (per doc §8).

import type { ModelEndpoint } from "../kv";
import { resolveBaseUrl } from "../projection";
import {
  GeneratorError,
  type GenerationContext,
  type GeneratedConfig,
  type TokenFactoryGenerator,
  type TokenFactoryMeta,
} from "./types";

/** Canonical Magpie provider template (static fields only). */
const MAGPIE_TEMPLATE = {
  nvidia: {
    id: "nvidia",
    name: "NVIDIA NIM",
    icon: "nvidia-color",
    preset: "nvidia",
    catalog: "nvidia",
    website: "https://build.nvidia.com",
    keysUrl: "https://build.nvidia.com/settings/api-keys",
  },
  openrouter: {
    id: "openrouter",
    name: "OpenRouter",
    icon: "openrouter",
    preset: "openrouter",
    catalog: "openrouter",
    website: "https://openrouter.ai",
    keysUrl: "https://openrouter.ai/keys",
    anthropic: "https://openrouter.ai/api",
    decide: "https://openrouter.ai/api/v1",
  },
  kilo: {
    id: "kilo",
    name: "Kilo Gateway",
    icon: "kilo",
    preset: "kilo",
    website: "https://kilo.ai/docs/gateway",
    keysUrl: "https://app.kilo.ai",
  },
  amd: {
    id: "amd",
    name: "AMD Radeon Cloud",
    icon: "amd",
    catalog: "amd",
    website: "https://developer.amd.com.cn/radeon/tokenfactory",
    keysUrl: "https://developer.amd.com.cn/radeon/profile",
    baseAPI: "chat",
  },
  "ollama-cloud": {
    id: "ollama-cloud",
    name: "Ollama Cloud",
    icon: "ollama",
    preset: "ollama-cloud",
    catalog: "ollama-cloud",
    website: "https://docs.ollama.com/cloud",
    keysUrl: "https://ollama.com/settings/keys",
    anthropic: "https://ollama.com",
    decide: "https://ollama.com/v1",
  },
  huggingface: {
    id: "huggingface",
    name: "huggingface",
    icon: "huggingface-color",
    website: "https://huggingface.co/inference/models",
    keysUrl: "https://huggingface.co/settings/tokens",
    baseAPI: "chat",
    proxy: "http://127.0.0.1:7897",
  },
} as const;

const MAGPIE_PROVIDER_ORDER = [
  "nvidia",
  "openrouter",
  "kilo",
  "amd",
  "ollama-cloud",
  "huggingface",
] as const;

/** TFI data_source → Magpie provider id. Explicit mapping layer
 *  (doc §3 §5 — never assume the identifiers already coincide). */
const DATA_SOURCE_TO_MAGPIE_PROVIDER: Readonly<Record<string, string>> = {
  nvidia: "nvidia",
  openrouter: "openrouter",
  kilo: "kilo",
  amd: "amd",
  ollama: "ollama-cloud",
  huggingface: "huggingface",
} as const;

/** Reverse map: Magpie provider id → TFI data_source. */
const MAGPIE_PROVIDER_TO_DATA_SOURCE: Readonly<Record<string, string>> = {
  nvidia: "nvidia",
  openrouter: "openrouter",
  kilo: "kilo",
  amd: "amd",
  "ollama-cloud": "ollama",
  huggingface: "huggingface",
} as const;

interface MagpieProviderEntry {
  id: string;
  name: string;
  icon?: string;
  preset?: string;
  catalog?: string;
  website?: string;
  keysUrl?: string;
  anthropic?: string;
  decide?: string;
  baseAPI?: string;
  proxy?: string;
  key: string;
  chat: string;
  models: string[];
  pickedFrom: string[];
}

interface MagpieConfig {
  providers: MagpieProviderEntry[];
}

const META: TokenFactoryMeta = {
  id: "magpie",
  name: "Magpie",
  description:
    "Magpie AI gateway — strict-JSON provider configuration with per-provider model catalogs and endpoint base URLs.",
  formatLabel: "Magpie providers[]",
};

/** Stable, readable JSON output (2-space indent, trailing newline). */
function stableJson(obj: unknown): string {
  return JSON.stringify(obj, null, 2) + "\n";
}

export const magpieGenerator: TokenFactoryGenerator = {
  id: "magpie",
  meta: META,
  generate(
    models: ModelEndpoint[],
    context: GenerationContext,
  ): GeneratedConfig {
    if (models.length === 0) {
      throw new GeneratorError(
        "No models selected. Select one or more models before generating.",
        400,
      );
    }

    // Full catalog (needed for pickedFrom). context.catalog is the
    // current catalog the generator validates against.
    const catalog = context.catalog ?? [];

    // Group selected models by data source, preserving selection order.
    const selectedByDs = new Map<string, ModelEndpoint[]>();
    for (const ep of models) {
      const list = selectedByDs.get(ep.data_source) ?? [];
      list.push(ep);
      selectedByDs.set(ep.data_source, list);
    }

    // Catalog model IDs per data source — deduped, sorted.
    const catalogByDs = new Map<string, string[]>();
    for (const ep of catalog) {
      const ds = ep.data_source;
      const list = catalogByDs.get(ds) ?? [];
      if (!list.includes(ep.model_id)) {
        list.push(ep.model_id);
      }
      catalogByDs.set(ds, list);
    }
    for (const list of catalogByDs.values()) {
      list.sort();
    }

    const providers: MagpieProviderEntry[] = [];

    for (const magpieProviderId of MAGPIE_PROVIDER_ORDER) {
      const dataSource = MAGPIE_PROVIDER_TO_DATA_SOURCE[magpieProviderId];
      const selected = selectedByDs.get(dataSource);
      if (!selected || selected.length === 0) {
        continue; // no selection for this source → not emitted
      }

      const pickedFrom = catalogByDs.get(dataSource) ?? [];
      const pickedSet = new Set(pickedFrom);
      for (const ep of selected) {
        if (!pickedSet.has(ep.model_id)) {
          throw new GeneratorError(
            `Magpie: selected model ${ep.model_id} (data source ${dataSource}) ` +
              `is not present in the current catalog for provider ${magpieProviderId}.`,
            400,
          );
        }
      }

      // Resolve chat from the selected endpoints' base URLs; detect
      // conflicts explicitly (doc §2.4 §6).
      let chat: string | null = null;
      for (const ep of selected) {
        const baseUrl = resolveBaseUrl(ep.data_source, ep.provider);
        if (!baseUrl) {
          throw new GeneratorError(
            `Magpie: no usable endpoint base URL for ${ep.data_source}/${ep.model_id}. ` +
              `Select a model whose data source exposes a base URL, or exclude it from the selection.`,
            400,
          );
        }
        const normalizedUrl = baseUrl.trim().replace(/\/+$/, "");
        if (chat === null) {
          chat = normalizedUrl;
        } else if (chat !== normalizedUrl) {
          throw new GeneratorError(
            `Magpie: conflicting endpoint base URLs for provider ${magpieProviderId} ` +
              `(${chat} vs ${normalizedUrl}). Select models served by a single endpoint base URL.`,
            400,
          );
        }
      }

      const template = MAGPIE_TEMPLATE[magpieProviderId];
      if (!template) {
        throw new GeneratorError(
          `Magpie: no template definition for provider ${magpieProviderId}.`,
          400,
        );
      }

      providers.push({
        ...template,
        key: "",
        chat: chat!,
        models: selected.map((ep) => ep.model_id),
        pickedFrom,
      });
    }

    if (providers.length === 0) {
      throw new GeneratorError(
        "No selected models map to a supported Magpie provider. " +
          `Supported sources: ${Object.values(DATA_SOURCE_TO_MAGPIE_PROVIDER).join(", ")}.`,
        400,
      );
    }

    const config: MagpieConfig = { providers };
    return {
      format: "magpie",
      content: stableJson(config),
      filename: "config.json",
    };
  },
};
