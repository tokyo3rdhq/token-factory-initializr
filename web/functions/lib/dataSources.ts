// Unified Data Source Registry — Single Source of Truth
//
// This file is the AUTHORITATIVE registry for all data source and provider
// metadata in TFI. All other modules (projection, generators, KV, docs)
// MUST import from here rather than duplicating definitions.
//
// When adding a new data source:
// 1. Add an entry to `DATA_SOURCE_REGISTRY`
// 2. Add any provider-specific entries to `PROVIDER_REGISTRY`
// 3. Run `npm run build` — type system will catch missing references
// 4. Run `npm test` — tests will validate the registry

// ============================================================================
// CORE TYPE DEFINITIONS
// ============================================================================

/** All known data source identifiers. */
export type DataSourceId =
  | "nvidia"
  | "amd"
  | "huggingface"
  | "openrouter"
  | "kilo"
  | "ollama"
  | "models_dev"; // internal enrichment source, never surfaced to UI

/** All known provider identifiers (including upstream providers within a data source). */
export type ProviderId =
  | "nvidia"
  | "amd"
  | "huggingface"
  | "openrouter"
  | "kilo"
  | "ollama"
  | "together"
  | "deepinfra"
  | "cerebras"
  | "novita"
  | "cohere"
  | "fireworks"
  | "baseten"
  | "scaleway"
  | "nscale"
  | "ovhcloud"
  | "publicai"
  | "featherless"
  | "groq"
  | "cloudflare"
  | "zai-org"
  | "fireworks-ai"
  | "featherless-ai"
  | "deepinfra"
  | "ovhcloud"
  | "nscale"
  | "publicai"
  | "scaleway"
  | "prism-ml"
  | "zai-org";

/** All Token Factory implementation identifiers. */
export type TokenFactoryId =
  | "litellm"
  | "newapi"
  | "bifrost"
  | "magpie";

/** Protocol vocabulary used across the platform. */
export type Protocol =
  | "openai-compatible"
  | "anthropic"
  | "native"
  | "huggingface"
  | "nim";

/** Model capability vocabulary (canonical normalized capabilities). */
export type Capability =
  | "chat"
  | "vision"
  | "speech"
  | "embedding"
  | "translation"
  | "decision";

/** Supported parameter vocabulary (endpoint-level interface/runtime params). */
export type SupportedParameter =
  | "tool_calling"
  | "reasoning"
  | "structured_output"
  | "streaming";

// ============================================================================
// DATA SOURCE REGISTRY — Core data source definitions
// ============================================================================

export interface DataSourceConfig {
  displayName: string;
  description: string;
  isConsumerFacing: boolean;
  baseUrl: string;
  documentationUrl?: string;
  icon: string;
  preset?: string;
  catalog?: string;
  website?: string;
  keysUrl?: string;
  apiKeyEnv?: string;
  protocol: Protocol;
  isRouterSource: boolean;
  baseApi?: string;
  proxy?: string;
  order: number;
  anthropic?: string;
  decide?: string;
}

/** Canonical data source registry — single source of truth. */
const DATA_SOURCE_REGISTRY_OBJ = {
  nvidia: {
    displayName: "NVIDIA NIM",
    description: "NVIDIA NIM microservices for optimized inference",
    isConsumerFacing: true,
    baseUrl: "https://integrate.api.nvidia.com/v1",
    documentationUrl: "https://docs.nvidia.com/nim/",
    icon: "nvidia-color",
    preset: "nvidia",
    catalog: "nvidia",
    website: "https://build.nvidia.com",
    keysUrl: "https://build.nvidia.com/settings/api-keys",
    apiKeyEnv: "NVIDIA_API_KEY",
    protocol: "nim" as Protocol,
    isRouterSource: false,
    order: 1,
  },
  amd: {
    displayName: "AMD Radeon Cloud",
    description: "AMD Radeon AI Platform model endpoints",
    isConsumerFacing: true,
    baseUrl: "https://developer.amd.com.cn/radeon/api/v1",
    documentationUrl: "https://amd-aim.github.io/radeon-cloud-docs/",
    icon: "amd",
    preset: "amd",
    catalog: "amd",
    website: "https://developer.amd.com.cn/radeon/tokenfactory",
    keysUrl: "https://developer.amd.com.cn/radeon/profile",
    apiKeyEnv: "AMD_API_KEY",
    protocol: "openai-compatible" as Protocol,
    isRouterSource: false,
    baseApi: "chat",
    order: 2,
  },
  huggingface: {
    displayName: "Hugging Face",
    description: "Hugging Face Inference Router (multi-provider router)",
    isConsumerFacing: true,
    baseUrl: "https://router.huggingface.co/v1",
    documentationUrl: "https://huggingface.co/docs/api-inference/",
    icon: "huggingface-color",
    catalog: "huggingface",
    website: "https://huggingface.co/inference/models",
    keysUrl: "https://huggingface.co/settings/tokens",
    apiKeyEnv: "HUGGING_FACE_API_KEY",
    protocol: "huggingface" as Protocol,
    isRouterSource: true,
    baseApi: "chat",
    proxy: "http://127.0.0.1:7897",
    order: 3,
  },
  openrouter: {
    displayName: "OpenRouter",
    description: "OpenRouter unified API gateway",
    isConsumerFacing: true,
    baseUrl: "https://openrouter.ai/api/v1",
    documentationUrl: "https://openrouter.ai/docs",
    icon: "openrouter",
    preset: "openrouter",
    catalog: "openrouter",
    website: "https://openrouter.ai",
    keysUrl: "https://openrouter.ai/keys",
    apiKeyEnv: "OPENROUTER_API_KEY",
    protocol: "openai-compatible" as Protocol,
    isRouterSource: false,
    anthropic: "https://openrouter.ai/api",
    decide: "https://openrouter.ai/api/v1",
    order: 4,
  },
  kilo: {
    displayName: "Kilo Gateway",
    description: "Kilo AI gateway",
    isConsumerFacing: true,
    baseUrl: "https://api.kilo.ai/api/gateway",
    documentationUrl: "https://kilo.ai/docs/gateway",
    icon: "kilo",
    preset: "kilo",
    catalog: "kilo",
    website: "https://kilo.ai/docs/gateway",
    keysUrl: "https://app.kilo.ai/profile",
    apiKeyEnv: "KILO_API_KEY",
    protocol: "openai-compatible" as Protocol,
    isRouterSource: false,
    order: 5,
  },
  ollama: {
    displayName: "Ollama Cloud",
    description: "Ollama Cloud hosted models",
    isConsumerFacing: true,
    baseUrl: "https://ollama.com/v1",
    documentationUrl: "https://docs.ollama.com/cloud",
    icon: "ollama",
    preset: "ollama-cloud",
    catalog: "ollama-cloud",
    website: "https://docs.ollama.com/cloud",
    keysUrl: "https://ollama.com/settings/keys",
    apiKeyEnv: "OLLAMA_API_KEY",
    protocol: "openai-compatible" as Protocol,
    isRouterSource: false,
    anthropic: "https://ollama.com",
    decide: "https://ollama.com/v1",
    order: 6,
  },
  models_dev: {
    displayName: "Models.dev",
    description: "Cross-source enrichment from models.dev (internal)",
    isConsumerFacing: false,
    baseUrl: "",
    icon: "database",
    isRouterSource: false,
    protocol: "openai-compatible" as Protocol,
    order: 99,
  },
} as const;

export const DATA_SOURCE_REGISTRY: Record<string, {
  displayName: string;
  description: string;
  isConsumerFacing: boolean;
  baseUrl: string;
  documentationUrl?: string;
  icon: string;
  preset?: string;
  catalog?: string;
  website?: string;
  keysUrl?: string;
  apiKeyEnv?: string;
  protocol: Protocol;
  isRouterSource: boolean;
  baseApi?: string;
  proxy?: string;
  order: number;
  anthropic?: string;
  decide?: string;
}> = DATA_SOURCE_REGISTRY_OBJ as Record<string, {
  displayName: string;
  description: string;
  isConsumerFacing: boolean;
  baseUrl: string;
  documentationUrl?: string;
  icon: string;
  preset?: string;
  catalog?: string;
  website?: string;
  keysUrl?: string;
  apiKeyEnv?: string;
  protocol: Protocol;
  isRouterSource: boolean;
  baseApi?: string;
  proxy?: string;
  order: number;
  anthropic?: string;
  decide?: string;
}>;

// ============================================================================
// PROVIDER REGISTRY — Upstream provider details (for HF router fanout, etc.)
// ============================================================================

interface ProviderConfig {
  displayName: string;
  protocols: Protocol[];
  nativeBaseUrl?: string;
  documentationUrl?: string;
  apiKeyEnv?: string;
  protocol: Protocol;
  order: number;
}

/** Upstream provider registry — used for HF router fanout, Bifrost native providers, etc. */
export const PROVIDER_REGISTRY: Record<string, ProviderConfig> = {
  // First-party / gateway providers
  nvidia: {
    displayName: "NVIDIA NIM",
    protocols: ["nim"],
    nativeBaseUrl: "https://integrate.api.nvidia.com/v1",
    documentationUrl: "https://docs.nvidia.com/nim/",
    apiKeyEnv: "NVIDIA_API_KEY",
    protocol: "nim",
    order: 1,
  },
  amd: {
    displayName: "AMD Radeon Cloud",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://developer.amd.com.cn/radeon/api/v1",
    documentationUrl: "https://amd-aim.github.io/radeon-cloud-docs/",
    apiKeyEnv: "AMD_API_KEY",
    protocol: "openai-compatible" as Protocol,
    order: 2,
  },
  huggingface: {
    displayName: "Hugging Face",
    protocols: ["huggingface"],
    documentationUrl: "https://huggingface.co/docs/api-inference/",
    protocol: "huggingface" as Protocol,
    order: 3,
  },
  openrouter: {
    displayName: "OpenRouter",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://openrouter.ai/api/v1",
    documentationUrl: "https://openrouter.ai/docs",
    apiKeyEnv: "OPENROUTER_API_KEY",
    protocol: "openai-compatible" as Protocol,
    order: 4,
  },
  kilo: {
    displayName: "Kilo AI",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.kilo.ai/api/gateway",
    documentationUrl: "https://kilo.ai/docs/gateway",
    apiKeyEnv: "KILO_API_KEY",
    protocol: "openai-compatible" as Protocol,
    order: 5,
  },
  ollama: {
    displayName: "Ollama Cloud",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://ollama.com/v1",
    documentationUrl: "https://docs.ollama.com/cloud",
    apiKeyEnv: "OLLAMA_API_KEY",
    protocol: "openai-compatible" as Protocol,
    order: 6,
  },
  together: {
    displayName: "Together AI",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.together.xyz/v1",
    documentationUrl: "https://docs.together.ai/docs/openai-api",
    protocol: "openai-compatible" as Protocol,
    order: 10,
  },
  deepinfra: {
    displayName: "DeepInfra",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.deepinfra.com/v1/openai",
    documentationUrl: "https://deepinfra.com/docs/openai_api",
    protocol: "openai-compatible" as Protocol,
    order: 11,
  },
  cerebras: {
    displayName: "Cerebras",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.cerebras.ai/v1",
    documentationUrl: "https://inference.cerebras.ai",
    protocol: "openai-compatible" as Protocol,
    order: 12,
  },
  novita: {
    displayName: "Novita AI",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.novita.ai/v3/openai",
    documentationUrl: "https://novita.ai/docs",
    protocol: "openai-compatible" as Protocol,
    order: 13,
  },
  cohere: {
    displayName: "Cohere",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.cohere.ai/v1",
    documentationUrl: "https://docs.cohere.com",
    protocol: "openai-compatible" as Protocol,
    order: 13,
  },
  fireworks: {
    displayName: "Fireworks AI",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.fireworks.ai/inference/v1",
    documentationUrl: "https://docs.fireworks.ai",
    protocol: "openai-compatible" as Protocol,
    order: 14,
  },
  baseten: {
    displayName: "Baseten",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.baseten.co/v1",
    documentationUrl: "https://docs.baseten.co",
    protocol: "openai-compatible" as Protocol,
    order: 15,
  },
  scaleway: {
    displayName: "Scaleway",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.scaleway.ai/v1",
    documentationUrl: "https://www.scaleway.com/en/docs",
    protocol: "openai-compatible" as Protocol,
    order: 17,
  },
  nscale: {
    displayName: "Nscale",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.nscale.com/v1",
    documentationUrl: "https://docs.nscale.com",
    protocol: "openai-compatible" as Protocol,
    order: 18,
  },
  ovhcloud: {
    displayName: "OVHcloud AI Endpoints",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
    documentationUrl: "https://endpoints.ovhcloud.com",
    protocol: "openai-compatible" as Protocol,
    order: 18,
  },
  publicai: {
    displayName: "PublicAI",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.publicai.co/v1",
    documentationUrl: "https://publicai.co",
    protocol: "openai-compatible" as Protocol,
    order: 19,
  },
  featherless: {
    displayName: "Featherless",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.featherless.ai/v1",
    documentationUrl: "https://featherless.ai",
    protocol: "openai-compatible" as Protocol,
    order: 19,
  },
  groq: {
    displayName: "Groq",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.groq.com/openai/v1",
    documentationUrl: "https://console.groq.com/docs/openai",
    protocol: "openai-compatible" as Protocol,
    order: 20,
  },
  cloudflare: {
    displayName: "Cloudflare Workers AI",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.cloudflare.com/client/v4/accounts",
    documentationUrl: "https://developers.cloudflare.com/workers-ai/",
    protocol: "openai-compatible" as Protocol,
    order: 21,
  },
  "zai-org": {
    displayName: "Z.ai",
    protocols: ["openai-compatible"],
    nativeBaseUrl: "https://api.z.ai/v1",
    documentationUrl: "https://z.ai/docs",
    protocol: "openai-compatible" as Protocol,
    order: 22,
  },
} as const;

// ============================================================================
// MAGPIE GENERATOR MAPPINGS
// ============================================================================


/** Magpie provider template (static fields from reference template). */
export const MAGPIE_TEMPLATE: Readonly<Record<string, {
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
}>> = {
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
    keysUrl: "https://app.kilo.ai/profile",
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

/** Magpie provider output order (matches reference template). */
export const MAGPIE_PROVIDER_ORDER = [
  "nvidia",
  "openrouter",
  "kilo",
  "amd",
  "ollama-cloud",
  "huggingface",
] as const;

/** TFI data_source → Magpie provider id. */
export const DATA_SOURCE_TO_MAGPIE_PROVIDER: Readonly<Record<string, string>> = {
  nvidia: "nvidia",
  openrouter: "openrouter",
  kilo: "kilo",
  amd: "amd",
  ollama: "ollama-cloud",
  huggingface: "huggingface",
  models_dev: "huggingface",
} as const;

/** Reverse map: Magpie provider id → TFI data_source. */
export const MAGPIE_PROVIDER_TO_DATA_SOURCE: Readonly<Record<string, string>> = {
  nvidia: "nvidia",
  openrouter: "openrouter",
  kilo: "kilo",
  amd: "amd",
  "ollama-cloud": "ollama",
  huggingface: "huggingface",
} as const;

/** Magpie provider output order for stable iteration. */
export const MAGPIE_PROVIDER_ORDER_LIST = MAGPIE_PROVIDER_ORDER;

// ============================================================================
// BIFROST GENERATOR MAPPINGS
// ============================================================================

/** Environment variable name Bifrost expects per provider. */
export const BIFROST_API_KEY_ENV: Readonly<Record<string, string>> = {
  huggingface: "HUGGING_FACE_API_KEY",
  amd: "AMD_API_KEY",
  nvidia: "NVIDIA_API_KEY",
  kilo: "KILO_API_KEY",
  ollama: "OLLAMA_API_KEY",
};

/** Providers Bifrost has a built-in type for. */
export const BIFROST_NATIVE_PROVIDERS = new Set([
  "huggingface",
  "groq",
  "openrouter",
]);

/** Custom OpenAI-compatible providers Bifrost supports explicitly. */
export const BIFROST_CUSTOM_OPENAI_BASE_URLS: Readonly<Record<string, string>> = {
  nvidia: "https://integrate.api.nvidia.com/v1",
  amd: "https://developer.amd.com.cn/radeon/api/v1",
  kilo: "https://api.kilo.ai/api/gateway",
  ollama: "https://ollama.com/v1",
};

/** Bifrost provider output order (deterministic). */
export const BIFROST_PROVIDER_ORDER = [
  "nvidia",
  "amd",
  "kilo",
  "ollama",
  "huggingface",
  "groq",
  "openrouter",
] as const;

// ============================================================================
// LITELLM GENERATOR MAPPINGS
// ============================================================================

/** LiteLLM API key env var per data source. */
export const LITELLM_API_KEY_ENV: Readonly<Record<string, string>> = {
  nvidia: "NVIDIA_API_KEY",
  amd: "AMD_API_KEY",
  huggingface: "HUGGING_FACE_API_KEY",
  openrouter: "OPENROUTER_API_KEY",
  kilo: "KILO_API_KEY",
  ollama: "OLLAMA_API_KEY",
  models_dev: "HUGGING_FACE_API_KEY",
};

/** LiteLLM model-field prefix per data source. */
export const LITELLM_DATA_SOURCE_PREFIX: Readonly<Record<string, string>> = {
  nvidia: "nvidia_nim",
  amd: "openai",
  huggingface: "huggingface",
  openrouter: "openrouter",
  kilo: "openai",
  ollama: "ollama_chat",
  models_dev: "huggingface",
};

/** LiteLLM decision model prefix. */
export const LITELLM_DECISION_PREFIX = "hosted_vllm";

// ============================================================================
// DATA SOURCE ORDERING — Deterministic sort order
// ============================================================================

/** Canonical data source order for deterministic output. */
export const DATA_SOURCE_ORDER: readonly string[] = [
  "nvidia",
  "amd",
  "huggingface",
  "openrouter",
  "kilo",
  "ollama",
  "models_dev",
] as const;

/** Sort data sources by canonical order. */
export function sortDataSources(sources: readonly string[]): string[] {
  const order = new Map(DATA_SOURCE_ORDER.map((ds, i) => [ds, i]));
  return [...sources].sort((a, b) => (order.get(a) ?? 99) - (order.get(b) ?? 99));
}

/** Sort providers by deterministic order. */
export function sortProviders(providers: readonly string[]): string[] {
  const providerOrder = new Map([
    ["nvidia", 0], ["amd", 1], ["kilo", 2], ["ollama", 2], ["huggingface", 3], ["openrouter", 4],
    ["groq", 5], ["together", 10], ["deepinfra", 11], ["cerebras", 12], ["novita", 13],
    ["cohere", 14], ["fireworks", 15], ["baseten", 16], ["scaleway", 17], ["nscale", 18],
    ["ovhcloud", 19], ["publicai", 20], ["featherless", 21], ["groq", 22], ["cloudflare", 23], ["zai-org", 24],
  ]);
  return [...providers].sort((a, b) => (providerOrder.get(a) ?? 99) - (providerOrder.get(b) ?? 99));
}

// ============================================================================
// DATA SOURCE BASE URLS — Consumer-facing entry points
// ============================================================================

/** Per-data-source entry-point URL (router/gateway endpoint). */
export const DATA_SOURCE_BASE_URLS: Readonly<Record<string, string>> = {
  nvidia: "https://integrate.api.nvidia.com/v1",
  amd: "https://developer.amd.com.cn/radeon/api/v1",
  huggingface: "https://router.huggingface.co/v1",
  openrouter: "https://openrouter.ai/api/v1",
  kilo: "https://api.kilo.ai/api/gateway",
  ollama: "https://ollama.com/v1",
  models_dev: "",
} as const;

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/** Check if a data source is consumer-facing (appears in Browse, Generate, etc.). */
export function isConsumerDataSource(ds: string): boolean {
  const config = DATA_SOURCE_REGISTRY[ds];
  return config?.isConsumerFacing ?? false;
}

/** Check if a data source is internal (enrichment only). */
export function isInternalDataSource(ds: string): boolean {
  return ds === "models_dev";
}

/** Get all consumer-facing data sources. */
export function getConsumerDataSources(): readonly string[] {
  return Object.values(DATA_SOURCE_REGISTRY)
    .filter((ds: any) => ds.isConsumerFacing)
    .map((ds: any) => ds.id as string)
    .sort((a, b) => (DATA_SOURCE_REGISTRY[a].order ?? 99) - (DATA_SOURCE_REGISTRY[b].order ?? 99));
}

/** Get all data source IDs (including internal). */
export function getAllDataSourceIds(): string[] {
  return Object.keys(DATA_SOURCE_REGISTRY);
}

/** Get consumer-facing data source count. */
export function getConsumerDataSourceCount(): number {
  return getConsumerDataSources().length;
}

/** Resolve consumer-facing base URL for a (data_source, provider) pair. */
export function resolveBaseUrl(dataSource: string, provider: string): string | undefined {
  const dsUrl = DATA_SOURCE_BASE_URLS[dataSource];
  if (dsUrl) return dsUrl;

  const providerMeta = PROVIDER_REGISTRY[provider];
  if (providerMeta?.nativeBaseUrl) return providerMeta.nativeBaseUrl;

  return undefined;
}

/** Get provider metadata by provider ID. */
export function getProviderMetadata(providerId: string) {
  return PROVIDER_REGISTRY[providerId] ?? null;
}

/** Get API key env var for a data source (for generators). */
export function getApiKeyEnv(dataSource: string): string {
  const config = DATA_SOURCE_REGISTRY[dataSource];
  return config?.apiKeyEnv ?? `${dataSource.toUpperCase()}_API_KEY`;
}

/** Get Magpie provider ID for a data source. */
export function getMagpieProviderId(dataSource: string): string {
  return DATA_SOURCE_TO_MAGPIE_PROVIDER[dataSource] ?? dataSource;
}

/** Get Bifrost API key env var for a provider. */
export function getBifrostApiKeyEnv(provider: string): string {
  return BIFROST_API_KEY_ENV[provider] ?? `${provider.toUpperCase()}_API_KEY`;
}

/** Get Bifrost custom base URL for a provider. */
export function getBifrostBaseUrl(provider: string): string | undefined {
  return BIFROST_CUSTOM_OPENAI_BASE_URLS[provider];
}

/** Check if Bifrost has native support for a provider. */
export function isBifrostNativeProvider(provider: string): boolean {
  return BIFROST_NATIVE_PROVIDERS.has(provider);
}

/** Get LiteLLM model prefix for a data source. */
export function getLitellmPrefix(dataSource: string): string {
  return LITELLM_DATA_SOURCE_PREFIX[dataSource] ?? dataSource;
}

/** Get LiteLLM API key env for a data source. */
export function getLitellmApiKeyEnv(dataSource: string): string {
  return LITELLM_API_KEY_ENV[dataSource] ?? `${dataSource.toUpperCase()}_API_KEY`;
}


/** Validate that all consumer data sources have required fields. */
export function validateRegistry(): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  for (const [id, config] of Object.entries(DATA_SOURCE_REGISTRY)) {
    const configAny = config as any;
    if (configAny.isConsumerFacing) {
      if (!configAny.baseUrl) errors.push(`${id}: missing baseUrl`);
      if (!configAny.displayName) errors.push(`${id}: missing displayName`);
      if (!configAny.apiKeyEnv) errors.push(`${id}: missing apiKeyEnv`);
      if (!configAny.protocol) errors.push(`${id}: missing protocol`);
      if (!configAny.icon) errors.push(`${id}: missing icon`);
    }
    if (configAny.isRouterSource && !configAny.proxy) {
      errors.push(`${id}: router source missing proxy`);
    }
  }

  return { valid: errors.length === 0, errors };
}

/** Get all KNOWN_DATA_SOURCES as array (for Python parity). */
export function getKnownDataSources(): string[] {
  return Object.keys(DATA_SOURCE_REGISTRY).filter((k) => k !== "models_dev");
}

// All exports are inline via `export const`/`export function`/`export type` above.