/**
 * Unit tests for the Bifrost Token Factory generator
 * (web/functions/lib/generators/bifrost.ts).
 *
 * Per docs/tfi_add_bifrost_implementation.md §14 — these tests pin
 * the Bifrost output contract:
 *
 *   - shape matches the official Bifrost `config.json` schema
 *     (providers.<id>.keys[].{name,value,models,weight})
 *   - `$schema` is included so IDEs validate the file
 *   - secrets are referenced via env.<VAR> (never literal)
 *   - model IDs containing `/` are preserved verbatim
 *   - native providers (huggingface, openrouter) emit clean keys
 *   - custom OpenAI-compatible providers (nvidia) emit
 *     custom_provider_config + network_config.base_url
 *   - unsupported providers (amd) throw GeneratorError
 *   - empty models throw GeneratorError
 *   - output is deterministic across runs
 *   - output is valid JSON
 *
 * Run with:  cd web && npx tsx src/__tests__/bifrost.test.ts
 */

import assert from "node:assert/strict";

let passed = 0;
let failed = 0;
const failedLabels: string[] = [];

function check(label: string, actual: unknown, expected: unknown): void {
  if (actual === expected) {
    passed++;
    console.log(`  ok  ${label}`);
  } else {
    failed++;
    failedLabels.push(
      `${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
    );
    console.error(
      `  FAIL ${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
    );
  }
}

function checkContains(label: string, haystack: string, needle: string): void {
  check(`${label} (contains)`, haystack.includes(needle), true);
}

function checkThrows(label: string, fn: () => unknown, errorName: string): void {
  let thrown = false;
  let name = "";
  try {
    fn();
  } catch (e) {
    thrown = true;
    name = e instanceof Error ? e.constructor.name : "";
  }
  check(`${label} (threw)`, thrown, true);
  check(`${label} (error name = ${errorName})`, name, errorName);
}

function suite(name: string, fn: () => void): void {
  console.log(`\n${name}`);
  try {
    fn();
  } catch (e) {
    failed++;
    failedLabels.push(`${name}: ${e instanceof Error ? e.message : String(e)}`);
    console.error(`  EXCEPTION: ${e instanceof Error ? e.message : String(e)}`);
  }
}

import {
  bifrostGenerator,
  GENERATORS,
  SUPPORTED_TOKEN_FACTORIES,
  type TokenFactoryId,
} from "../../functions/lib/generators";
import {
  NATIVE_PROVIDERS,
  PROVIDER_API_KEY_ENV,
} from "../../functions/lib/generators/bifrost";
import type { ModelEndpoint } from "../types";

const ep = (overrides: Partial<ModelEndpoint>): ModelEndpoint => ({
  data_source: "nvidia",
  provider: "nvidia",
  model_id: "x/y",
  name: "Y",
  description: null,
  free: true,
  capabilities: {},
  architecture: null,
  lab: null,
  metadata: {},
  fetched_at: "2026-01-01T00:00:00Z",
  context_length: null,
  pricing: null,
  ...overrides,
});

const URL = "https://example.test/generated/abc";

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

suite("registration: bifrost is a registered Token Factory", () => {
  check("SUPPORTED_TOKEN_FACTORIES includes bifrost", SUPPORTED_TOKEN_FACTORIES.includes("bifrost" as TokenFactoryId), true);
  check("GENERATORS.bifrost exists", "bifrost" in GENERATORS, true);
  check("bifrostGenerator.id === 'bifrost'", bifrostGenerator.id, "bifrost");
  check("bifrostGenerator.meta.name === 'Bifrost'", bifrostGenerator.meta.name, "Bifrost");
  check("bifrostGenerator filename ends with .json", bifrostGenerator.generate([ep({ data_source: "nvidia", provider: "nvidia", model_id: "x/y" })], { generatedUrl: URL }).filename.endsWith(".json"), true);
});

// ---------------------------------------------------------------------------
// Determinism + JSON validity
// ---------------------------------------------------------------------------

suite("output: deterministic across runs", () => {
  const models = [
    ep({ data_source: "nvidia", provider: "nvidia", model_id: "deepseek-ai/deepseek-v4.1-flash" }),
    ep({ data_source: "huggingface", provider: "together", model_id: "meta-llama/Llama-3.3-70B-Instruct" }),
  ];
  const a = bifrostGenerator.generate(models, { generatedUrl: "x" });
  const b = bifrostGenerator.generate(models, { generatedUrl: "y" });
  check("same models → byte-identical content", a.content === b.content, true);
});

suite("output: valid JSON", () => {
  const out = bifrostGenerator.generate(
    [ep({ data_source: "huggingface", provider: "together", model_id: "meta-llama/Llama-3.3-70B-Instruct" })],
    { generatedUrl: URL },
  );
  let parsed: unknown = null;
  let parseErr = "";
  try {
    parsed = JSON.parse(out.content);
  } catch (e) {
    parseErr = e instanceof Error ? e.message : String(e);
  }
  check("JSON.parse succeeded", parseErr, "");
  check(
    "top-level keys present",
    parsed !== null && typeof parsed === "object" && "$schema" in parsed && "providers" in parsed,
    true,
  );
});

suite("output: $schema is the official Bifrost schema URL", () => {
  const out = bifrostGenerator.generate(
    [ep({ data_source: "nvidia", provider: "nvidia", model_id: "x" })],
    { generatedUrl: URL },
  );
  const parsed = JSON.parse(out.content);
  check("schema URL matches", parsed.$schema, "https://www.getbifrost.ai/schema");
});

// ---------------------------------------------------------------------------
// Native Bifrost providers
// ---------------------------------------------------------------------------

suite("native provider: huggingface emits bare keys[] (no custom_provider_config)", () => {
  const out = bifrostGenerator.generate(
    [
      ep({ data_source: "huggingface", provider: "together", model_id: "meta-llama/Llama-3.3-70B-Instruct" }),
    ],
    { generatedUrl: URL },
  );
  const parsed = JSON.parse(out.content);
  const p = parsed.providers.huggingface;
  check("huggingface provider exists", p !== undefined, true);
  check("has exactly one key", p.keys.length, 1);
  check("key name is '<provider>-primary'", p.keys[0].name, "huggingface-primary");
  check("key value references HUGGING_FACE_API_KEY env", p.keys[0].value, "env.HUGGING_FACE_API_KEY");
  check("models array has 1 entry", p.keys[0].models.length, 1);
  check("weight = 1.0", p.keys[0].weight, 1.0);
  check("no custom_provider_config", p.custom_provider_config, undefined);
  check("no network_config", p.network_config, undefined);
});

suite("native provider: openrouter emits bare keys[]", () => {
  const out = bifrostGenerator.generate(
    [ep({ data_source: "openrouter", provider: "openrouter", model_id: "openai/gpt-4o-mini" })],
    { generatedUrl: URL },
  );
  const parsed = JSON.parse(out.content);
  const p = parsed.providers.openrouter;
  check("openrouter provider exists", p !== undefined, true);
  check("key value references OPENROUTER_API_KEY", p.keys[0].value, "env.OPENROUTER_API_KEY");
  check("no custom_provider_config", p.custom_provider_config, undefined);
});

// ---------------------------------------------------------------------------
// Custom OpenAI-compatible providers
// ---------------------------------------------------------------------------

suite("custom provider: nvidia emits custom_provider_config + network_config.base_url", () => {
  const out = bifrostGenerator.generate(
    [ep({ data_source: "nvidia", provider: "nvidia", model_id: "deepseek-ai/deepseek-v4.1-flash" })],
    { generatedUrl: URL },
  );
  const parsed = JSON.parse(out.content);
  const p = parsed.providers.nvidia;
  check("nvidia provider exists", p !== undefined, true);
  check("custom_provider_config.base_provider_type = 'openai'", p.custom_provider_config?.base_provider_type, "openai");
  check("network_config.base_url is NVIDIA NIM", p.network_config?.base_url, "https://integrate.api.nvidia.com/v1");
  check("key value references NVIDIA_API_KEY", p.keys[0].value, "env.NVIDIA_API_KEY");
});

suite("custom provider: amd emits custom_provider_config + network_config.base_url", () => {
  const out = bifrostGenerator.generate(
    [ep({ data_source: "amd", provider: "amd", model_id: "MiMo-V2.6-Flash" })],
    { generatedUrl: URL },
  );
  const parsed = JSON.parse(out.content);
  const p = parsed.providers.amd;
  check("amd provider exists", p !== undefined, true);
  check("custom_provider_config.base_provider_type = 'openai'", p.custom_provider_config?.base_provider_type, "openai");
  check("network_config.base_url is AMD Radeon Cloud", p.network_config?.base_url, "https://developer.amd.com.cn/radeon/api/v1");
  check("key value references AMD_API_KEY", p.keys[0].value, "env.AMD_API_KEY");
  check("key name is 'amd-primary'", p.keys[0].name, "amd-primary");
});

suite("custom provider: together routed under huggingface native provider", () => {
  // Together AI is a HuggingFace router upstream. In current code it's
  // grouped under data_source "huggingface" with provider "together", producing
  // composite model ID "huggingface/together/...".
  const out = bifrostGenerator.generate(
    [ep({ data_source: "huggingface", provider: "together", model_id: "meta-llama/Llama-3-70b" })],
    { generatedUrl: URL },
  );
  const parsed = JSON.parse(out.content);
  const hf = parsed.providers.huggingface;
  check("huggingface provider exists", hf !== undefined, true);
  check("model id is composite (huggingface/<provider>/<model_id>)", hf.keys[0].models[0], "huggingface/together/meta-llama/Llama-3-70b");
  check("no separate 'together' provider block", !!parsed.providers.together, false);
});
suite("model IDs containing '/' are preserved verbatim", () => {
  const models = [
    ep({ data_source: "huggingface", provider: "together", model_id: "meta-llama/Llama-3.3-70B-Instruct" }),
    ep({ data_source: "nvidia", provider: "nvidia", model_id: "deepseek-ai/deepseek-v4.1-flash" }),
    ep({ data_source: "openrouter", provider: "openrouter", model_id: "openai/gpt-4o-mini" }),
  ];
  const out = bifrostGenerator.generate(models, { generatedUrl: URL });
  const parsed = JSON.parse(out.content);
  const hf = parsed.providers.huggingface.keys[0].models;
  check("HF model id verbatim", hf[0], "huggingface/together/meta-llama/Llama-3.3-70B-Instruct");
  const nv = parsed.providers.nvidia.keys[0].models;
  check("NVIDIA model id verbatim", nv[0], "deepseek-ai/deepseek-v4.1-flash");
  check("no URL-encoded slashes in output", out.content.includes("%2F"), false);
});

// ---------------------------------------------------------------------------
// Secrets
// ---------------------------------------------------------------------------

suite("secrets: never embedded as literals", () => {
  const out = bifrostGenerator.generate(
    [
      ep({ data_source: "nvidia", provider: "nvidia", model_id: "x" }),
      ep({ data_source: "amd", provider: "amd", model_id: "y" }),
      ep({ data_source: "huggingface", provider: "together", model_id: "z" }),
      ep({ data_source: "openrouter", provider: "openrouter", model_id: "w" }),
    ],
    { generatedUrl: URL },
  );
  checkContains("references HUGGING_FACE_API_KEY via env.", out.content, "env.HUGGING_FACE_API_KEY");
  checkContains("references NVIDIA_API_KEY via env.", out.content, "env.NVIDIA_API_KEY");
  checkContains("references AMD_API_KEY via env.", out.content, "env.AMD_API_KEY");
  checkContains("references OPENROUTER_API_KEY via env.", out.content, "env.OPENROUTER_API_KEY");
  check("no literal 'sk-' key fragment", out.content.includes("sk-"), false);
});

// ---------------------------------------------------------------------------
// Multiple providers grouped
// ---------------------------------------------------------------------------

suite("multi-provider: separate providers keyed by provider field", () => {
  const models = [
    ep({ data_source: "nvidia", provider: "nvidia", model_id: "m1" }),
    ep({ data_source: "huggingface", provider: "together", model_id: "m2" }),
    ep({ data_source: "huggingface", provider: "together", model_id: "m3" }), // second HF model
  ];
  const out = bifrostGenerator.generate(models, { generatedUrl: URL });
  const parsed = JSON.parse(out.content);
  const providers = Object.keys(parsed.providers).sort();
  check("providers: huggingface + nvidia", JSON.stringify(providers), JSON.stringify(["huggingface", "nvidia"]));
  check("huggingface has 2 models", parsed.providers.huggingface.keys[0].models.length, 2);
  check("nvidia has 1 model", parsed.providers.nvidia.keys[0].models.length, 1);
});

// ---------------------------------------------------------------------------
// Unsupported providers throw explicit error
// ---------------------------------------------------------------------------

suite("unsupported provider: amd now supported via custom_provider_config (regression)", () => {
  // AMD Radeon Cloud exposes a documented OpenAI-compatible chat
  // completions endpoint. Bifrost handles it via
  // custom_provider_config + network_config.base_url.
  const out = bifrostGenerator.generate(
    [ep({ data_source: "amd", provider: "amd", model_id: "MiMo-V2.6-Flash" })],
    { generatedUrl: URL },
  );
  const parsed = JSON.parse(out.content);
  const p = parsed.providers.amd;
  check("amd provider exists", p !== undefined, true);
  check("no error thrown", !!p, true);
});


// ---------------------------------------------------------------------------
// Empty input
// ---------------------------------------------------------------------------

suite("empty selection: throws GeneratorError", () => {
  checkThrows(
    "empty models → GeneratorError",
    () => bifrostGenerator.generate([], { generatedUrl: "x" }),
    "GeneratorError",
  );
});

// ---------------------------------------------------------------------------
// Capabilities are NOT mapped into Bifrost config (per spec §7)
// ---------------------------------------------------------------------------

suite("capabilities: chat/vision/tool_calling are NOT mapped into Bifrost config", () => {
  const out = bifrostGenerator.generate(
    [
      ep({
        provider: "nvidia",
        model_id: "x",
        capabilities: { chat: true, vision: true, tool_calling: true, reasoning: true },
      }),
    ],
    { generatedUrl: URL },
  );
  check("no 'chat' key in output", out.content.includes("chat"), false);
  check("no 'tool_calling' key in output", out.content.includes("tool_calling"), false);
  check("no 'reasoning' key in output", out.content.includes("reasoning"), false);
});

// ---------------------------------------------------------------------------
// Existing implementations still work
// ---------------------------------------------------------------------------

suite("regression: existing litellm + newapi are unchanged", () => {
  check(
    "litellm in SUPPORTED_TOKEN_FACTORIES",
    SUPPORTED_TOKEN_FACTORIES.includes("litellm" as TokenFactoryId),
    true,
  );
  check(
    "newapi in SUPPORTED_TOKEN_FACTORIES",
    SUPPORTED_TOKEN_FACTORIES.includes("newapi" as TokenFactoryId),
    true,
  );
  check("GENERATORS.litellm unchanged", GENERATORS.litellm.id, "litellm");
  check("GENERATORS.newapi unchanged", GENERATORS.newapi.id, "newapi");
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  console.error("Failures:\n  " + failedLabels.join("\n  "));
}
assert.equal(failed, 0, `${failed} test(s) failed`);
