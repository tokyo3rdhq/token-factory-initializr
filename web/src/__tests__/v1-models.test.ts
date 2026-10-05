// Tests for the /api/v1/models projection + filter + error
// helpers. Runs in Node via node --experimental-strip-types so we
// exercise the actual implementation, not a transpiled copy.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  toPublicModel,
  toPublicModels,
  type PublicModel,
} from "../../functions/lib/projection.ts";
import {
  filterEndpoints,
  filterPublicModels,
  parseFilters,
  publicListResponse,
  splitCsv,
  KNOWN_CAPABILITIES,
} from "../../functions/lib/filter.ts";
import type { ModelEndpoint } from "../../functions/lib/kv.ts";

function makeEndpoint(overrides: Partial<ModelEndpoint> = {}): ModelEndpoint {
  return {
    data_source: "nvidia",
    provider: "nvidia",
    model_id: "vendor/test",
    name: "Test Model",
    description: "Test description",
    free: true,
    capabilities: { chat: true },
    architecture: { input: ["text"], output: ["text"] },
    lab: null,
    metadata: {},
    fetched_at: "2026-10-05T01:24:17+00:00",
    context_length: 131072,
    pricing: null,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Projection
// ---------------------------------------------------------------------------

test("toPublicModel exposes only canonical public fields", () => {
  const ep = makeEndpoint({
    model_id: "openai/gpt-oss-120b",
    data_source: "groq",
    provider: "groq",
    capabilities: { chat: true, reasoning: true, tool_calling: true },
  });
  const out = toPublicModel(ep);
  assert.equal(out.id, "openai/gpt-oss-120b");
  assert.equal(out.object, "model");
  assert.equal(out.created, 0);
  assert.equal(out.owned_by, "groq");
  assert.equal(out.data_source, "groq");
  assert.equal(out.provider, "groq");
  assert.deepEqual(out.capabilities, ["chat", "reasoning", "tool_calling"]);
});

test("toPublicModel strips provenance + metadata + pricing + raw fields", () => {
  const ep = makeEndpoint({
    // Simulate a canonical model that ALSO carries internal fields
    // (the public projection must not surface them even when present).
    // @ts-expect-error - intentionally inject non-public fields
    provenance: { description: { source: "x" } },
    // @ts-expect-error
    raw_obj: { huge: "blob" },
  } as ModelEndpoint);
  const out = toPublicModel(ep) as Record<string, unknown>;
  assert.equal("provenance" in out, false);
  assert.equal("metadata" in out, false);
  assert.equal("pricing" in out, false);
  assert.equal("raw_obj" in out, false);
  assert.equal("fetched_at" in out, false);
});

test("toPublicModel emits capability order: chat/vision/.../tool_calling", () => {
  const ep = makeEndpoint({
    capabilities: {
      tool_calling: true,
      chat: true,
      vision: true,
      // Future capability key — preserved, surfaces after canonical
      // ones.
      some_future_cap: true,
    },
  });
  const out = toPublicModel(ep);
  // First three are canonical in declared order; future key trails.
  assert.deepEqual(out.capabilities, [
    "chat",
    "vision",
    "tool_calling",
    "some_future_cap",
  ]);
});

test("toPublicModels preserves order and count", () => {
  const eps = [
    makeEndpoint({ model_id: "a/x" }),
    makeEndpoint({ model_id: "a/y" }),
    makeEndpoint({ model_id: "a/z" }),
  ];
  const out = toPublicModels(eps);
  assert.equal(out.length, 3);
  assert.deepEqual(out.map((m) => m.id), ["a/x", "a/y", "a/z"]);
});

// ---------------------------------------------------------------------------
// splitCsv + parseFilters
// ---------------------------------------------------------------------------

test("splitCsv handles empty / whitespace / dedup", () => {
  assert.deepEqual(splitCsv(null), []);
  assert.deepEqual(splitCsv(""), []);
  assert.deepEqual(splitCsv("   "), []);
  assert.deepEqual(splitCsv("a,b,a"), ["a", "b"]);
  assert.deepEqual(splitCsv(" nvidia , amd "), ["nvidia", "amd"]);
});

test("parseFilters returns 400 on unknown capability", () => {
  const r = parseFilters(new URLSearchParams("capabilities=foo_bar"));
  assert.ok("error" in r);
  assert.equal(r.error.param, "capabilities");
  assert.equal(r.error.code, "invalid_capability");
  assert.match(r.error.message, /foo_bar/);
});

test("parseFilters returns 400 listing ALL unknown capabilities", () => {
  const r = parseFilters(
    new URLSearchParams("capabilities=chat,foo_bar,baz_quux")
  );
  assert.ok("error" in r);
  assert.match(r.error.message, /foo_bar/);
  assert.match(r.error.message, /baz_quux/);
});

test("parseFilters accepts every KNOWN_CAPABILITIES value", () => {
  for (const cap of KNOWN_CAPABILITIES) {
    const r = parseFilters(new URLSearchParams(`capabilities=${cap}`));
    assert.ok(!("error" in r), `expected no error for ${cap}`);
    assert.deepEqual(r.capabilities, [cap]);
  }
});

test("parseFilters ignores unknown data_source / provider — caller treats as empty", () => {
  const r = parseFilters(
    new URLSearchParams("data_source=does_not_exist&provider=ghost")
  );
  assert.ok(!("error" in r));
  assert.deepEqual(r.data_source, ["does_not_exist"]);
  assert.deepEqual(r.provider, ["ghost"]);
});

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------

test("filterEndpoints AND semantics for capabilities", () => {
  const eps = [
    makeEndpoint({ model_id: "a", capabilities: { chat: true, vision: true } }),
    makeEndpoint({ model_id: "b", capabilities: { chat: true } }),
    makeEndpoint({ model_id: "c", capabilities: { vision: true } }),
  ];
  const r = filterEndpoints(eps, { capabilities: ["chat", "vision"] });
  assert.deepEqual(r.map((e) => e.model_id), ["a"]);
});

test("filterEndpoints OR semantics within data_source dimension", () => {
  const eps = [
    makeEndpoint({ model_id: "n", data_source: "nvidia" }),
    makeEndpoint({ model_id: "a", data_source: "amd" }),
    makeEndpoint({ model_id: "h", data_source: "huggingface" }),
  ];
  const r = filterEndpoints(eps, { data_source: ["nvidia", "amd"] });
  assert.deepEqual(r.map((e) => e.model_id).sort(), ["a", "n"]);
});

test("filterEndpoints OR semantics within provider dimension", () => {
  const eps = [
    makeEndpoint({ model_id: "n", provider: "nvidia" }),
    makeEndpoint({ model_id: "t", provider: "together" }),
    makeEndpoint({ model_id: "z", provider: "zai-org" }),
  ];
  const r = filterEndpoints(eps, { provider: ["together", "zai-org"] });
  assert.deepEqual(r.map((e) => e.model_id).sort(), ["t", "z"]);
});

test("filterEndpoints combines dimensions with AND", () => {
  const eps = [
    makeEndpoint({
      model_id: "nvidia-chat",
      data_source: "nvidia",
      provider: "nvidia",
      capabilities: { chat: true },
    }),
    makeEndpoint({
      model_id: "nvidia-vision",
      data_source: "nvidia",
      provider: "nvidia",
      capabilities: { vision: true },
    }),
    makeEndpoint({
      model_id: "hf-chat",
      data_source: "huggingface",
      provider: "together",
      capabilities: { chat: true },
    }),
  ];
  const r = filterEndpoints(eps, {
    data_source: ["nvidia"],
    capabilities: ["chat"],
  });
  assert.deepEqual(r.map((e) => e.model_id), ["nvidia-chat"]);
});

test("filterPublicModels uses the same semantics on public list", () => {
  const publicList: PublicModel[] = [
    toPublicModel(
      makeEndpoint({
        model_id: "x",
        capabilities: { chat: true, vision: true },
      })
    ),
  ];
  const r = filterPublicModels(publicList, { capabilities: ["chat"] });
  assert.equal(r.length, 1);
  const empty = filterPublicModels(publicList, {
    capabilities: ["reasoning"],
  });
  assert.equal(empty.length, 0);
});

// ---------------------------------------------------------------------------
// publicListResponse envelope
// ---------------------------------------------------------------------------

test("publicListResponse uses OpenAI-compatible object/data envelope", () => {
  const list = publicListResponse([
    toPublicModel(makeEndpoint({ model_id: "a" })),
  ]);
  assert.equal(list.object, "list");
  assert.ok(Array.isArray(list.data));
  assert.equal(list.data.length, 1);
  assert.equal(list.data[0].id, "a");
});

// ---------------------------------------------------------------------------
// findEndpoint (model detail lookup)
// ---------------------------------------------------------------------------

import { findEndpoint, loadFullCatalog } from "../../functions/lib/catalog.ts";

test("findEndpoint returns the matching endpoint", () => {
  const eps = [makeEndpoint({ model_id: "openai/gpt-oss-120b" })];
  const r = findEndpoint(eps, "openai/gpt-oss-120b");
  assert.ok(r);
  assert.equal(r.model_id, "openai/gpt-oss-120b");
  assert.equal(findEndpoint(eps, "does/not/exist"), null);
});

test("findEndpoint handles ids containing multiple slashes", () => {
  const eps = [makeEndpoint({ model_id: "prism-ml/ternary-bonsai-2-27b" })];
  const r = findEndpoint(eps, "prism-ml/ternary-bonsai-2-27b");
  assert.ok(r);
});

// ---------------------------------------------------------------------------
// loadFullCatalog shape (sanity — KV is mocked by env flag below)
// ---------------------------------------------------------------------------

test("loadFullCatalog returns empty catalog when KV has no providers", async () => {
  // Stub a minimal Pages-compatible KV that returns null for every
  // key — exercises the "no providers published yet" path.
  const fakeKV = {
    get: async () => null,
    put: async () => {},
    list: async () => ({ keys: [], list_complete: true }),
    getWithMetadata: async () => ({ value: null, metadata: null }),
    delete: async () => {},
  } as never;
  const env = { TFI_KV: fakeKV } as never;
  const cat = await loadFullCatalog(env);
  assert.deepEqual(cat.endpoints, []);
  assert.deepEqual(cat.snapshots, []);
  assert.deepEqual(cat.pairs, []);
});
