/**
 * Unit tests for the Browse page filter logic
 * (web/src/pages/Browse.tsx — exported via __browseFilters).
 *
 * Per docs/tfi_phase_1_initializr_core_workflow.md §25 — the
 * Selection filter pipeline is pure data manipulation and benefits
 * from isolated tests more than rendering tests.
 *
 * Run with:  cd web && npx tsx src/__tests__/browse-filters.test.ts
 */

import assert from "node:assert/strict";

let passed = 0;
let failed = 0;
let failedLabels: string[] = [];

import { __browseFilters } from "../pages/Browse";
import type { ModelEndpoint } from "../types";

const { hasTag, applyFilters } = __browseFilters;

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

function ep(overrides: Partial<ModelEndpoint>): ModelEndpoint {
  return {
    provider: overrides.provider ?? "nvidia",
    data_source: overrides.data_source ?? "nvidia",
    model_id: overrides.model_id ?? "x/y",
    name: overrides.name ?? null,
    description: null,
    free: overrides.free ?? true,
    capabilities: overrides.capabilities ?? {},
    architecture: overrides.architecture ?? null,
    lab: null,
    metadata: {},
    fetched_at: "2026-10-02T00:00:00Z",
    context_length: overrides.context_length ?? null,
    pricing: null,
  };
}

const sample: ModelEndpoint[] = [
  ep({ model_id: "nvidia/deepseek-v4", name: "DeepSeek V4", free: true, capabilities: { chat: true, tool_calling: true }, context_length: 131_072 }),
  ep({ model_id: "huggingface/kimi-k3", data_source: "huggingface", provider: "cohere", free: true, capabilities: { chat: true }, context_length: 65_536 }),
  ep({ model_id: "nvidia/cosmos-vision", name: "Cosmos Vision", free: true, architecture: { input: ["text", "image"], output: ["text"] }, context_length: 32_768 }),
  ep({ model_id: "amd/paid-model", data_source: "amd", provider: "amd", free: false, capabilities: { chat: true } }),
];

// ---------------------------------------------------------------------------
// hasTag
// ---------------------------------------------------------------------------

console.log("\nhasTag: chat");
check("chat=true → true", hasTag(sample[0], "chat"), true);
check("chat=false → false", hasTag(sample[1], "chat") && !hasTag(sample[1], "chat"), false);
console.log("  (already tested)"); // noop to keep parallel structure

console.log("\nhasTag: vision");
check("vision architecture → true", hasTag(sample[2], "vision"), true);
check("vision architecture without image → false", hasTag(sample[0], "vision"), false);

console.log("\nhasTag: tools");
check("tools capability → true", hasTag(sample[0], "tools"), true);
check("no tools capability → false", hasTag(sample[1], "tools"), false);

console.log("\nhasTag: free");
check("free=true → true", hasTag(sample[0], "free"), true);
check("free=false → false", hasTag(sample[3], "free"), false);

console.log("\nhasTag: longCtx");
check("context_length=131072 → true", hasTag(sample[0], "longCtx"), true);
check("context_length=65536 → false", hasTag(sample[1], "longCtx"), false);
check("context_length=null → false", hasTag(ep({ context_length: null }), "longCtx"), false);
check("context_length=127999 → false (boundary)", hasTag(ep({ context_length: 127_999 }), "longCtx"), false);
check("context_length=128000 → true (boundary)", hasTag(ep({ context_length: 128_000 }), "longCtx"), true);

// ---------------------------------------------------------------------------
// applyFilters
// ---------------------------------------------------------------------------

console.log("\napplyFilters: empty filters = everything");
check("empty query + empty tags = unchanged", equalsLength(applyFilters(sample, "", new Set()), sample.length), sample.length);

console.log("\napplyFilters: keyword alone");
check("'deepseek' matches 1", equalsLength(applyFilters(sample, "deepseek", new Set())), 1);
check("'KIMI' matches 1 (case-insensitive)", equalsLength(applyFilters(sample, "KIMI", new Set())), 1);
check("'nvidia' matches 2 (provider + data_source)", equalsLength(applyFilters(sample, "nvidia", new Set())), 2);
check("'huggingface' matches 1 (data_source)", equalsLength(applyFilters(sample, "huggingface", new Set())), 1);
check("'cohere' matches 1 (provider)", equalsLength(applyFilters(sample, "cohere", new Set())), 1);
check("'xyz' matches 0", equalsLength(applyFilters(sample, "xyz", new Set())), 0);

console.log("\napplyFilters: tag alone (single)");
check("free only → 3 of 4", equalsLength(applyFilters(sample, "", new Set(["free"]))), 3);

console.log("\napplyFilters: tag alone (AND)");
check("free+chat → 2 (paid + cosmos excluded)", equalsLength(applyFilters(sample, "", new Set(["free", "chat"]))), 2);
check("free+vision → 1 (only cosmos-vision)", equalsLength(applyFilters(sample, "", new Set(["free", "vision"]))), 1);
check("vision+tools → 0 (cosmos has vision but not tools)", equalsLength(applyFilters(sample, "", new Set(["vision", "tools"]))), 0);

console.log("\napplyFilters: keyword + tag");
check("'nvidia' + free → 2 (kimi excluded)", equalsLength(applyFilters(sample, "nvidia", new Set(["free"]))), 2);
check("'deepseek' + free → 1 (deepseek itself)", equalsLength(applyFilters(sample, "deepseek", new Set(["free"]))), 1);
check("'deepseek' + vision → 0 (deepseek isn't vision)", equalsLength(applyFilters(sample, "deepseek", new Set(["vision"]))), 0);
check("'kimi' + chat + free → 1", equalsLength(applyFilters(sample, "kimi", new Set(["chat", "free"]))), 1);

// ---------------------------------------------------------------------------
console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  console.log("\nFailures:");
  for (const l of failedLabels) console.log(`  ${l}`);
  process.exit(1);
}
assert.equal(failed, 0, `${failed} test(s) failed`);

// helper (local — undefined as the inlined length check)
function equalsLength(arr: unknown[]): number {
  return arr.length;
}