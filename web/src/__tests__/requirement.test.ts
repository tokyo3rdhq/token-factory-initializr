/**
 * Unit tests for :func:`matchesRequirement` (web/src/types.ts).
 *
 * Verifies each sub-rule of the ModelRequirement contract against a
 * realistic set of endpoints spanning the three providers.
 *
 * Run with:  cd web && npx tsx src/__tests__/requirement.test.ts
 * or:        cd web && npm run build  (also runs tsc --noEmit which
 *                                     type-checks this file)
 */

import assert from "node:assert/strict";

// Tiny inline test runner — keeps the test file free of `node:test`
// (which `@types/node@22` doesn't ship). Each `suite()` block is a
// closure, and `check()` records a pass/fail in counters. The script
// exits non-zero on any failure via the final `assert.equal(failed, 0)`.
let passed = 0;
let failed = 0;
let failedLabels: string[] = [];

import {
  matchesRequirement,
  type ModelEndpoint,
  type ModelRequirement,
} from "../types";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

function ep(overrides: Partial<ModelEndpoint>): ModelEndpoint {
  return {
    provider: "nvidia",
    model_id: "x/y",
    name: "Y",
    description: null,
    free: true,
    capabilities: {},
    architecture: null,
    lab: null,
    metadata: {},
    fetched_at: new Date().toISOString(),
    context_length: null,
    pricing: null,
    ...overrides,
  };
}

const NV_TEXT = ep({
  provider: "nvidia",
  model_id: "nvidia/text-8b",
  name: "Text 8B",
  capabilities: { chat: true, tool_calling: true },
  architecture: { input: ["text"], output: ["text"] },
  context_length: 131072,
});

const NV_VISION = ep({
  provider: "nvidia",
  model_id: "nvidia/cosmos3-nano",
  name: "Cosmos 3 Nano",
  capabilities: { vision: true },
  architecture: { input: ["text", "image"], output: ["text"] },
  context_length: 65536,
});

const AMD_MM = ep({
  provider: "amd",
  model_id: "MiMo-V2.6-Flash",
  capabilities: { chat: true },
  architecture: { input: ["text", "image"], output: ["text"] },
  metadata: {
    original_id: "model_gateway:MiMo-V2.6-Flash",
    context_length: 1048576,
    free_status: "free_endpoint",
  },
  context_length: 1048576,
  pricing: { prompt: "1.4e-7", completion: "2.8e-7" },
});

const HF_FREE = ep({
  provider: "huggingface",
  model_id: "meta-llama/Llama-3.2-3B-Instruct",
  capabilities: { chat: true },
  architecture: { input: ["text"], output: ["text"] },
  context_length: 131072,
  pricing: { input: 0, output: 0 },
});

const HF_PAID = ep({
  provider: "novita",
  model_id: "novita/some-paid-model",
  free: false,
  capabilities: { chat: true },
  architecture: { input: ["text"], output: ["text"] },
  context_length: 65536,
  pricing: { input: 0.27, output: 1.1 },
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

function check(label: string, actual: boolean, expected: boolean): void {
  if (actual === expected) {
    passed++;
    console.log(`  ok  ${label}`);
  } else {
    failed++;
    failedLabels.push(`${label}: expected ${expected}, got ${actual}`);
    console.error(`  FAIL ${label}: expected ${expected}, got ${actual}`);
  }
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

// -- empty requirement --
suite("empty requirement", () => {
  const req: ModelRequirement = {};
  check("NV_TEXT matches empty", matchesRequirement(NV_TEXT, req), true);
  check("AMD_MM matches empty", matchesRequirement(AMD_MM, req), true);
  check("HF_PAID matches empty", matchesRequirement(HF_PAID, req), true);
});

// -- capabilities --
suite("capabilities.vision", () => {
  const req: ModelRequirement = { capabilities: { vision: true } };
  check("NV_VISION matches", matchesRequirement(NV_VISION, req), true);
  check("NV_TEXT does not match", matchesRequirement(NV_TEXT, req), false);
});

suite("capabilities.toolCalling", () => {
  const req: ModelRequirement = { capabilities: { toolCalling: true } };
  check("NV_TEXT matches", matchesRequirement(NV_TEXT, req), true);
  check("NV_VISION does not match", matchesRequirement(NV_VISION, req), false);
});

suite("capabilities.structuredOutput", () => {
  // No endpoint in fixtures has structured_output, so both should fail.
  const req: ModelRequirement = { capabilities: { structuredOutput: true } };
  check("HF_FREE does not match", matchesRequirement(HF_FREE, req), false);
  check("NV_TEXT does not match", matchesRequirement(NV_TEXT, req), false);
});

suite("capabilities.reasoning (reserved)", () => {
  const req: ModelRequirement = { capabilities: { reasoning: true } };
  // Per schema, reasoning flag isn't set by any provider today, so
  // no endpoint should match.
  check("NV_TEXT does not match", matchesRequirement(NV_TEXT, req), false);
});

suite("capabilities flags AND-combine", () => {
  const req: ModelRequirement = {
    capabilities: { vision: true, toolCalling: true },
  };
  check("NV_TEXT does not match (no vision)", matchesRequirement(NV_TEXT, req), false);
  check("NV_VISION does not match (no tool_calling)", matchesRequirement(NV_VISION, req), false);
});

// -- contextWindow --
suite("contextWindow.min", () => {
  const req1: ModelRequirement = { contextWindow: { min: 100000 } };
  check("NV_TEXT (131072) passes", matchesRequirement(NV_TEXT, req1), true);
  check("AMD_MM (1048576) passes", matchesRequirement(AMD_MM, req1), true);
  check("HF_FREE (131072) passes", matchesRequirement(HF_FREE, req1), true);

  const req2: ModelRequirement = { contextWindow: { min: 200000 } };
  check("NV_TEXT (131072) fails", matchesRequirement(NV_TEXT, req2), false);
  check("AMD_MM (1048576) passes", matchesRequirement(AMD_MM, req2), true);
  check("HF_FREE (131072) fails", matchesRequirement(HF_FREE, req2), false);
});

suite("contextWindow.min treats null/unknown as pass", () => {
  const unknown = ep({ context_length: null });
  const req: ModelRequirement = { contextWindow: { min: 1 } };
  check("null context_length passes", matchesRequirement(unknown, req), true);
});

// -- pricing --
suite("pricing.free=true rejects paid", () => {
  const req: ModelRequirement = { pricing: { free: true } };
  check("NV_TEXT passes", matchesRequirement(NV_TEXT, req), true);
  check("HF_FREE passes", matchesRequirement(HF_FREE, req), true);
  check("HF_PAID fails", matchesRequirement(HF_PAID, req), false);
});

suite("pricing.free=false accepts only paid", () => {
  const req: ModelRequirement = { pricing: { free: false } };
  check("HF_PAID passes", matchesRequirement(HF_PAID, req), true);
  check("NV_TEXT rejected (free=true)", matchesRequirement(NV_TEXT, req), false);
});

suite("pricing.input filters by max input price", () => {
  const req: ModelRequirement = { pricing: { input: 0.5 } };
  check("AMD_MM (~0) passes", matchesRequirement(AMD_MM, req), true);
  check("HF_FREE (0) passes", matchesRequirement(HF_FREE, req), true);
  check("HF_PAID (0.27) passes", matchesRequirement(HF_PAID, req), true);

  const tight: ModelRequirement = { pricing: { input: 0.1 } };
  check("HF_PAID (0.27) fails tight", matchesRequirement(HF_PAID, tight), false);
  check("AMD_MM (~0) passes tight", matchesRequirement(AMD_MM, tight), true);
});

suite("pricing treats missing pricing dict as pass", () => {
  const req: ModelRequirement = { pricing: { input: 0.0001 } };
  // NV_TEXT has pricing: null — should not be filtered out on price.
  check("NV_TEXT (null pricing) passes", matchesRequirement(NV_TEXT, req), true);
});

// -- providers --
suite("providers whitelist", () => {
  const req: ModelRequirement = { providers: ["huggingface"] };
  check("NV_TEXT fails (not in list)", matchesRequirement(NV_TEXT, req), false);
  check("HF_FREE passes", matchesRequirement(HF_FREE, req), true);
  check("AMD_MM fails (not in list)", matchesRequirement(AMD_MM, req), false);
});

suite("providers empty array means all", () => {
  const req: ModelRequirement = { providers: [] };
  check("NV_TEXT passes", matchesRequirement(NV_TEXT, req), true);
  check("HF_FREE passes", matchesRequirement(HF_FREE, req), true);
});

// -- combined --
suite("combined requirements AND-compose", () => {
  const req: ModelRequirement = {
    pricing: { free: true },
    capabilities: { vision: true },
    providers: ["amd"],
  };
  check("AMD_MM (amd + vision + free) passes", matchesRequirement(AMD_MM, req), true);
  check("NV_VISION fails (not amd)", matchesRequirement(NV_VISION, req), false);
  check("HF_FREE fails (no vision)", matchesRequirement(HF_FREE, req), false);
  check("NV_TEXT fails (neither)", matchesRequirement(NV_TEXT, req), false);
});

// -- reserved fields --
suite("useCases is reserved — currently no-op", () => {
  const req: ModelRequirement = { useCases: ["chat", "rag"] };
  check("NV_TEXT passes (no-op)", matchesRequirement(NV_TEXT, req), true);
});

suite("endpointCount is reserved — currently no-op", () => {
  const req: ModelRequirement = { endpointCount: 1 };
  check("NV_TEXT passes (no-op)", matchesRequirement(NV_TEXT, req), true);
});

suite("constraints are reserved — currently no-op", () => {
  const req: ModelRequirement = { constraints: { latency: 200 } };
  check("NV_TEXT passes (no-op)", matchesRequirement(NV_TEXT, req), true);
});

// -- summary --
console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  console.error("Failures:\n  " + failedLabels.join("\n  "));
}
assert.equal(failed, 0, `${failed} test(s) failed`);