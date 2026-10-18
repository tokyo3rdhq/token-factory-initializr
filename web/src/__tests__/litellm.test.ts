// Litellm generator prefix tests — per data_source model prefix mapping.
//
// nvidia      -> nvidia_nim
// amd         -> openai
// huggingface -> huggingface
//
// Decision-model rule per docs/tfi_litellm_configuration_generation_rules.md:
// architecture.output containing "decision" -> hosted_vllm/<model_id>,
// overriding the data-source mapping.

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { generateLiteLLM } from "../../functions/lib/litellm";
import type { ModelEndpoint } from "../../functions/lib/kv";

function makeEp(
  overrides: Partial<ModelEndpoint> & { data_source: string; provider: string },
): ModelEndpoint {
  return {
    model_id: overrides.model_id ?? "deepseek-ai/deepseek-v4.1-flash",
    name: null,
    description: null,
    free: true,
    capabilities: {},
    architecture: null,
    lab: null,
    metadata: {},
    fetched_at: new Date().toISOString(),
    ...overrides,
  } satisfies ModelEndpoint;
}

describe("litellm: model prefix per data source", () => {
  it("nvidia endpoint uses 'nvidia_nim' prefix in model field", () => {
    const ep = makeEp({ data_source: "nvidia", provider: "nvidia", model_id: "deepseek-ai/deepseek-v4.1-flash" });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.match(yaml, /model:\s*'nvidia_nim\/deepseek-ai\/deepseek-v4.1-flash'/);
  });

  it("amd endpoint uses 'openai' prefix in model field", () => {
    const ep = makeEp({ data_source: "amd", provider: "amd", model_id: "MiMo-V2.6-Flash" });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.match(yaml, /model:\s*'openai\/MiMo-V2.6-Flash'/);
  });

  it("huggingface data source prefixes with the inference provider", () => {
    const ep = makeEp({ data_source: "huggingface", provider: "together", model_id: "prism-ml/Ternary-Bonsai-27B-gguf" });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.match(yaml, /model:\s*'huggingface\/together\/prism-ml\/Ternary-Bonsai-27B-gguf'/);
  });

  it("huggingface data source with same provider still includes provider in path", () => {
    const ep = makeEp({ data_source: "huggingface", provider: "huggingface", model_id: "deepseek-ai/deepseek-v4.1-flash" });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.match(yaml, /model:\s*'huggingface\/huggingface\/deepseek-ai\/deepseek-v4.1-flash'/);
  });

  it("kilo endpoint uses 'openai' prefix in model field", () => {
    const ep = makeEp({ data_source: "kilo", provider: "kilo", model_id: "kilo-auto/glm-5-3" });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.match(yaml, /model:\s*'openai\/kilo-auto\/glm-5-3'/);
  });

  it("openrouter endpoint uses 'openrouter' prefix in model field", () => {
    const ep = makeEp({ data_source: "openrouter", provider: "openrouter", model_id: "deepseek/deepseek-r1" });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.match(yaml, /model:\s*'openrouter\/deepseek\/deepseek-r1'/);
  });
});

describe("litellm: decision model rule (docs/tfi_litellm_configuration_generation_rules.md)", () => {
  it("decision model uses 'hosted_vllm' prefix regardless of data source", () => {
    const ep = makeEp({
      data_source: "amd",
      provider: "amd",
      model_id: "Clef",
      architecture: { input: ["text"], output: ["decision"] },
    });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.match(yaml, /model:\s*'hosted_vllm\/Clef'/);
  });

  it("decision rule overrides data-source mapping (huggingface decision model)", () => {
    const ep = makeEp({
      data_source: "huggingface",
      provider: "together",
      model_id: "some/decision-model",
      architecture: { input: ["text"], output: ["text", "decision"] },
    });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.match(yaml, /model:\s*'hosted_vllm\/some\/decision-model'/);
  });

  it("non-decision model with reasoning/tool capabilities stays on regular mapping", () => {
    const ep = makeEp({
      data_source: "nvidia",
      provider: "nvidia",
      model_id: "some/reasoning-model",
      architecture: { input: ["text"], output: ["text"] },
      capabilities: { reasoning: true, tools: true, structured_output: true },
    });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.match(yaml, /model:\s*'nvidia_nim\/some\/reasoning-model'/);
  });

  it("missing architecture falls back to regular mapping", () => {
    const ep = makeEp({ data_source: "nvidia", provider: "nvidia" });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.match(yaml, /model:\s*'nvidia_nim\/deepseek-ai\/deepseek-v4.1-flash'/);
  });

  it("model name containing 'decision' does not trigger decision mapping", () => {
    const ep = makeEp({
      data_source: "amd",
      provider: "amd",
      model_id: "decision-finder-v2",
      architecture: { input: ["text"], output: ["text"] },
    });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.match(yaml, /model:\s*'openai\/decision-finder-v2'/);
  });

  it("decision model does not emit api_base (doc §3 forbids modifying api_base)", () => {
    const ep = makeEp({
      data_source: "amd",
      provider: "amd",
      model_id: "Clef",
      architecture: { input: ["text"], output: ["decision"] },
    });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.doesNotMatch(yaml, /api_base/);
  });
});
