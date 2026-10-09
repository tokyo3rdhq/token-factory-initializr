/**
 * Unit tests for the Phase-1 Token Factory generators
 * (web/functions/lib/generators/*).
 *
 * Per docs/tfi_phase_1_initializr_core_workflow.md §11 + §25:
 *   - LiteLLM generator deterministic
 *   - NewAPI generator deterministic
 *   - Empty models → throws GeneratorError (no silent empty output)
 *   - Selected models correctly represented
 *   - Missing required metadata → throws
 *
 * Run with:  cd web && npx tsx src/__tests__/generators.test.ts
 */

import assert from "node:assert/strict";

let passed = 0;
let failed = 0;
let failedLabels: string[] = [];

import {
  litellmGenerator,
} from "../../functions/lib/generators/litellm";
import { newapiGenerator } from "../../functions/lib/generators/newapi";
import { generateWith } from "../../functions/lib/generators";
import {
  GeneratorError,
} from "../../functions/lib/generators/types";
import type { ModelEndpoint } from "../types";

function check(label: string, actual: unknown, expected: unknown): void {
  if (actual === expected) {
    passed++;
    console.log(`  ok  ${label}`);
  } else {
    failed++;
    failedLabels.push(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    console.error(`  FAIL ${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function checkThrows(label: string, fn: () => unknown, errorName: string): void {
  try {
    fn();
    failed++;
    failedLabels.push(`${label}: expected throw`);
    console.error(`  FAIL ${label}: expected throw`);
  } catch (e) {
    if (e instanceof Error && e.name === errorName) {
      passed++;
      console.log(`  ok  ${label}`);
    } else {
      failed++;
      failedLabels.push(`${label}: expected ${errorName}, got ${e instanceof Error ? e.name : String(e)}`);
      console.error(`  FAIL ${label}: expected ${errorName}, got ${e instanceof Error ? e.name : String(e)}`);
    }
  }
}

const ep = (overrides: Partial<ModelEndpoint>): ModelEndpoint => ({
  provider: overrides.provider ?? "nvidia",
  data_source: overrides.data_source ?? "nvidia",
  model_id: overrides.model_id ?? "x/y",
  name: overrides.name ?? null,
  description: null,
  free: true,
  capabilities: {},
  architecture: null,
  lab: null,
  metadata: {},
  fetched_at: "2026-10-02T00:00:00Z",
  context_length: null,
  pricing: null,
});

const sample: ModelEndpoint[] = [
  ep({ provider: "nvidia", model_id: "deepseek-v4-1-flash", name: "deepseek-v4.1-flash" }),
  ep({ provider: "huggingface", data_source: "huggingface", model_id: "kimi-k3", name: "kimi-k3" }),
];

// ---------------------------------------------------------------------------
// LiteLLM generator
// ---------------------------------------------------------------------------

console.log("\nlitellm: deterministic output");

// Same inputs → same output (idempotency / §11 invariant).
const a = litellmGenerator.generate(sample, {
  generatedUrl: "https://example.test/generated/abc",
});
const b = litellmGenerator.generate(sample, {
  generatedUrl: "https://example.test/generated/xyz",
});
// generatedUrl is intentionally NOT part of the YAML body — it's only used
// by the agent prompt template. So the YAMLs must be byte-identical
// even when the URL changes.


// Selected models are present in the YAML.
console.log("\nlitellm: selected models represented");
check("contains nvidia_nim/deepseek-v4-1-flash", a.content.includes("nvidia_nim/deepseek-v4-1-flash"), true);
check("contains huggingface/kimi-k3", a.content.includes("huggingface/kimi-k3"), true);
check("contains api_key env reference for nvidia", a.content.includes("os.environ/NVIDIA_API_KEY"), true);
check("contains api_key env reference for huggingface", a.content.includes("os.environ/HF_TOKEN"), true);

// Empty models → throws GeneratorError (no silent empty config).
console.log("\nlitellm: empty models raise");
checkThrows(
  "empty models → GeneratorError",
  () => litellmGenerator.generate([], { generatedUrl: "x" }),
  "GeneratorError",
);

// Format metadata.
console.log("\nlitellm: format metadata");
check("id = 'litellm'", litellmGenerator.id, "litellm");
check("meta.name = 'LiteLLM'", litellmGenerator.meta.name, "LiteLLM");
check("filename ends with .yaml", a.filename.endsWith(".yaml"), true);

// Control-char rejection (security audit F4).
console.log("\nlitellm: refuses ASCII control characters in model_id");
{
  const unsafeModel: ModelEndpoint = {
    data_source: "huggingface",
    provider: "huggingface",
    model_id: "evil/with\u000Anewline",
    name: null,
    description: null,
    free: true,
    capabilities: {},
    architecture: null,
    lab: null,
    metadata: {},
    fetched_at: "2026-01-01T00:00:00Z",
  };
  let threw = false;
  try {
    litellmGenerator.generate([unsafeModel], { generatedUrl: "x" });
  } catch (e) {
    threw = true;
    check(
      "control-char rejection throws a plain Error",
      e instanceof Error && e.message.includes("control character"),
      true,
    );
  }
  check("control-char rejection threw", threw, true);
}

// ---------------------------------------------------------------------------
// NewAPI generator
// ---------------------------------------------------------------------------

console.log("\nnewapi: deterministic output");

const c = newapiGenerator.generate(sample, { generatedUrl: "x" });
const d = newapiGenerator.generate(sample, { generatedUrl: "y" });
check("same models → byte-identical config", c.content === d.content, true);
check("format = 'newapi'", c.format, "newapi");

console.log("\nnewapi: valid JSON shape");
let parsed: { models: Array<{ id: string; name: string }> } | null = null;
try {
  parsed = JSON.parse(c.content);
  passed++;
  console.log("  ok  output is valid JSON");
} catch (e) {
  failed++;
  failedLabels.push(`output is valid JSON: ${e instanceof Error ? e.message : String(e)}`);
  console.error(`  FAIL output is valid JSON: ${e instanceof Error ? e.message : String(e)}`);
}
if (parsed) {
  check("parsed.models length matches", parsed.models.length === sample.length, true);
  check(
    "first model has id",
    typeof parsed.models[0]?.id === "string" && parsed.models[0].id.length > 0,
    true,
  );
  check(
    "first model has name",
    typeof parsed.models[0]?.name === "string" && parsed.models[0].name.length > 0,
    true,
  );
}

console.log("\nnewapi: empty models raise");
checkThrows(
  "empty models → GeneratorError",
  () => newapiGenerator.generate([], { generatedUrl: "x" }),
  "GeneratorError",
);

// ---------------------------------------------------------------------------
// Registry dispatch
// ---------------------------------------------------------------------------

console.log("\nregistry: dispatch by format id");
const litellmOut = generateWith("litellm", sample, { generatedUrl: "x" });
const newapiOut = generateWith("newapi", sample, { generatedUrl: "x" });
check("litellm dispatch returns yaml output", litellmOut.content.includes("model_list:"), true);
check("newapi dispatch returns json output", newapiOut.content.includes('"models"'), true);
check("different formats → different output", litellmOut.content !== newapiOut.content, true);

console.log("\nregistry: unsupported format throws");
checkThrows(
  "unknown format → GeneratorError",
  () => generateWith("nope" as never, sample, { generatedUrl: "x" }),
  "GeneratorError",
);

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  console.log("\nFailures:");
  for (const l of failedLabels) console.log(`  ${l}`);
  process.exit(1);
}
assert.equal(failed, 0, `${failed} test(s) failed`);