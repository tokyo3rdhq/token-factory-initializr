// Bundled fixture data for offline / no-KV scenarios.
//
// When ``TFI_USE_LOCAL_FIXTURES=1`` is set in the Pages project
// environment (typically via the local ``.env`` file), every API
// endpoint that would otherwise read from KV falls back to the
// payloads in this file. The shape matches what the data pipeline
// writes to KV (``ProviderSnapshot``, ``Manifest``) so the UI
// behaves identically.
//
// Production deployments default to ``TFI_USE_LOCAL_FIXTURES=0`` so
// a missing KV is surfaced as a 404 rather than masked by stale
// data. The fallback is purely a developer / CI ergonomics layer.
//
// Refactor: fixtures follow the (data_source, provider) namespace
// — NVIDIA/AMD carry ``data_source=nvidia/amd`` and
// ``provider=nvidia/amd``. Hugging Face carries
// ``data_source=huggingface`` with multiple inference providers
// (novita, huggingface in this fixture) so the UI can render the
// HF multi-provider shape.

import type { ProviderSnapshot, Manifest } from "./kv";

const NVIDIA_FIXTURE: ProviderSnapshot = {
  data_source: "nvidia",
  provider: "nvidia",
  fetched_at: "2026-09-25T00:00:00Z",
  models: [
    {
      data_source: "nvidia",
      provider: "nvidia",
      model_id: "deepseek-ai/deepseek-v4.1-flash",
      name: "DeepSeek V4.1 Flash",
      description: null,
      free: true,
      capabilities: { chat: true, tool_calling: true },
      architecture: { input: ["text"], output: ["text", "tool_calls"] },
      lab: "deepseek-ai",
      metadata: {},
      fetched_at: "2026-09-25T00:00:00Z",
      context_length: 131072,
      pricing: null,
    },
    {
      data_source: "nvidia",
      provider: "nvidia",
      model_id: "google/gemma-4-31b-it",
      name: "Gemma 4 31B IT",
      description: null,
      free: true,
      capabilities: { chat: true },
      architecture: { input: ["text"], output: ["text"] },
      lab: "google",
      metadata: {},
      fetched_at: "2026-09-25T00:00:00Z",
      context_length: 131072,
      pricing: null,
    },
  ],
};

const AMD_FIXTURE: ProviderSnapshot = {
  data_source: "amd",
  provider: "amd",
  fetched_at: "2026-09-25T00:00:00Z",
  models: [
    {
      data_source: "amd",
      provider: "amd",
      model_id: "MiMo-V2.6-Flash",
      name: "MiMo V2.6 Flash",
      description: null,
      free: true,
      capabilities: { chat: true },
      architecture: { input: ["text"], output: ["text"] },
      lab: "Xiaomi",
      metadata: { original_id: "model_gateway:MiMo-V2.6-Flash" },
      fetched_at: "2026-09-25T00:00:00Z",
      context_length: 1048576,
      pricing: { prompt: "1.4e-7", completion: "2.8e-7" },
    },
  ],
};

const HF_FIXTURE: ProviderSnapshot = {
  data_source: "huggingface",
  provider: "novita",
  fetched_at: "2026-09-25T00:00:00Z",
  models: [
    {
      data_source: "huggingface",
      provider: "novita",
      model_id: "deepseek-ai/DeepSeek-V3.2-Exp",
      name: "DeepSeek V3.2 Exp",
      description: null,
      free: true,
      capabilities: { chat: true },
      architecture: { input: ["text"], output: ["text"] },
      lab: "deepseek-ai",
      metadata: { supports_tools: true },
      fetched_at: "2026-09-25T00:00:00Z",
      context_length: 65536,
      pricing: { input: 0, output: 0 },
    },
    {
      data_source: "huggingface",
      provider: "huggingface",
      model_id: "meta-llama/Llama-3.2-3B-Instruct",
      name: "Llama 3.2 3B Instruct",
      description: null,
      free: true,
      capabilities: { chat: true },
      architecture: { input: ["text"], output: ["text"] },
      lab: "meta-llama",
      metadata: { supports_tools: true },
      fetched_at: "2026-09-25T00:00:00Z",
      context_length: 131072,
      pricing: { input: 0, output: 0 },
    },
  ],
};

const FIXTURE_MANIFEST: Manifest = {
  version: "fixtures",
  generated_at: "2026-09-25T00:00:00Z",
  total:
    NVIDIA_FIXTURE.models.length +
    AMD_FIXTURE.models.length +
    HF_FIXTURE.models.length,
  providers: {
    nvidia: {
      data_source: "nvidia",
      count: NVIDIA_FIXTURE.models.length,
      status: "success",
      last_success: "2026-09-25T00:00:00Z",
    },
    amd: {
      data_source: "amd",
      count: AMD_FIXTURE.models.length,
      status: "success",
      last_success: "2026-09-25T00:00:00Z",
    },
    huggingface: {
      data_source: "huggingface",
      count: HF_FIXTURE.models.length,
      status: "success",
      last_success: "2026-09-25T00:00:00Z",
    },
  },
};

export const FIXTURE_PROVIDERS = [
  NVIDIA_FIXTURE,
  AMD_FIXTURE,
  HF_FIXTURE,
];
export const FIXTURE_MANIFEST_EXPORT = FIXTURE_MANIFEST;