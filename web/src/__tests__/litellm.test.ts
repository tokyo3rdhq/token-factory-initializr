// Litellm generator prefix tests — per data_source model prefix mapping.
//
// nvidia     -> nvidia_nim
// amd        -> openai
// huggingface -> huggingface

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { generateLiteLLM } from "../../functions/lib/litellm";
import type { ModelEndpoint } from "../../functions/lib/kv";

describe("litellm: model prefix per data source", () => {
  function makeEp(overrides: Partial<ModelEndpoint> & { data_source: string; provider: string }): ModelEndpoint {
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

  it("huggingface endpoint uses 'huggingface' prefix in model field", () => {
    const ep = makeEp({ data_source: "huggingface", provider: "huggingface", model_id: "prism-ml/Ternary-Bonsai-27B-gguf" });
    const yaml = generateLiteLLM({ models: [ep] });
    assert.match(yaml, /model:\s*'huggingface\/prism-ml\/Ternary-Bonsai-27B-gguf'/);
  });
});
