// Tests for the /api/v1/models projection + filter + error
// helpers. Runs in Node via node --experimental-strip-types so we
// exercise the actual implementation, not a transpiled copy.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  toPublicModel,
  toPublicModels,
  PUBLIC_CAPABILITY_VOCABULARY,
  PUBLIC_MODALITY_VOCABULARY,
  PUBLIC_SUPPORTED_FEATURE_VOCABULARY,
  type PublicModel,
} from "../../functions/lib/projection.ts";
import {
  makeEtag,
  etagMatches,
  jsonResponse,
  textResponse,
} from "../../functions/lib/errors.ts";
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
  // owned_by must reflect the model creator, NOT the endpoint
  // provider — ``openai/gpt-oss-120b`` is owned by OpenAI even
  // though it's served on Groq here.
  assert.equal(out.owned_by, "openai");
  assert.equal(out.data_source, "groq");
  assert.equal(out.provider, "groq");
  assert.deepEqual(out.capabilities, ["chat", "reasoning", "tool_calling"]);
});

test("toPublicModel prefers canonical lab over model_id derivation", () => {
  // AMD/HF entries carry an explicit ``lab`` (publisher name). When
  // set, that wins over the model_id prefix derivation.
  const ep = makeEndpoint({
    model_id: "some-org/llama-3-8b-instruct",
    data_source: "huggingface",
    provider: "meta",
    lab: "meta-llama",
  });
  const out = toPublicModel(ep);
  assert.equal(out.owned_by, "meta-llama");
  assert.equal(out.provider, "meta");
  assert.equal(out.data_source, "huggingface");
});

test("toPublicModel omits owned_by when neither lab nor prefix is derivable", () => {
  // AMD entries without a publisher prefix land with no owner info.
  // We OMIT the field rather than fabricate it from data_source —
  // agents should treat absence as "unknown", not as an attribution
  // claim.
  const ep = makeEndpoint({
    model_id: "MiMo-V2.6-Flash",
    data_source: "amd",
    provider: "amd",
    lab: null,
  });
  const out = toPublicModel(ep);
  assert.equal("owned_by" in out, false);
  assert.equal(out.provider, "amd");
  assert.equal(out.data_source, "amd");
});

test("toPublicModel vocabulary surfaces unknown keys as a forward-compat shim", () => {
  // If a future data source emits a capability TFI doesn't yet
  // recognize, it appears after the canonical ones (preserving
  // backward-compatible ordering).
  const ep = makeEndpoint({
    model_id: "vendor/test",
    capabilities: {
      tool_calling: true,
      chat: true,
      // Future capability key — preserved.
      image_generation: true,
    },
  });
  const out = toPublicModel(ep);
  assert.deepEqual(out.capabilities, [
    "chat",
    "tool_calling",
    "image_generation",
  ]);
});

test("PUBLIC_CAPABILITY_VOCABULARY exposes the documented enum", () => {
  // The vocabulary is part of the API contract — adding a new key
  // requires a doc + test bump so consumers know.
  assert.deepEqual([...PUBLIC_CAPABILITY_VOCABULARY], [
    "chat",
    "vision",
    "speech",
    "embedding",
    "reasoning",
    "tool_calling",
    "structured_output",
    "decision",
  ]);
});

// ---------------------------------------------------------------------------
// supported_features projection + decision capability
// ---------------------------------------------------------------------------

test("toPublicModel projects decision capability in stable order", () => {
  const ep = makeEndpoint({
    capabilities: { chat: true, decision: true },
  });
  const out = toPublicModel(ep);
  assert.deepEqual(out.capabilities, ["chat", "decision"]);
});

test("toPublicModel omits supported_features when no endpoint confirms a feature", () => {
  const ep = makeEndpoint({});
  const out = toPublicModel(ep);
  assert.equal(out.supported_features, undefined);
});

test("toPublicModel unions supported_features across endpoints (model-level aggregate)", () => {
  const streaming = makeEndpoint({
    model_id: "vendor/multi",
    supported_features: ["streaming"],
  });
  const plain = makeEndpoint({
    model_id: "vendor/multi",
    data_source: "amd",
    provider: "amd",
  });
  const byModel = new Map([["vendor/multi", [streaming, plain]]]);
  const out = toPublicModel(streaming, { endpointsByModel: byModel });
  assert.deepEqual(out.supported_features, ["streaming"]);
});

test("toPublicModelEndpoint keeps supported_features endpoint-scoped", () => {
  // The model-level array is the documented UNION across the
  // model's endpoints (for filtering) — but the nested
  // ``endpoints[]`` records stay endpoint-scoped: a non-streaming
  // sibling never inherits the feature.
  const streaming = makeEndpoint({
    model_id: "vendor/multi",
    supported_features: ["streaming"],
  });
  const plain = makeEndpoint({
    model_id: "vendor/multi",
    data_source: "amd",
    provider: "amd",
  });
  const byModel = new Map([["vendor/multi", [streaming, plain]]]);
  const out = toPublicModel(plain, { endpointsByModel: byModel });
  // Model-level aggregate = union (any endpoint confirming).
  assert.deepEqual(out.supported_features, ["streaming"]);
  // Endpoint-level records stay scoped.
  const nestedStreaming = out.endpoints.find((e) => e.provider === "nvidia");
  const nestedPlain = out.endpoints.find((e) => e.provider === "amd");
  assert.deepEqual(nestedStreaming?.supported_features, ["streaming"]);
  assert.equal(nestedPlain?.supported_features, undefined);
});

test("PUBLIC_SUPPORTED_FEATURE_VOCABULARY exposes the documented enum", () => {
  assert.deepEqual([...PUBLIC_SUPPORTED_FEATURE_VOCABULARY], ["streaming"]);
});

test("parseFilters accepts decision as a capability filter", () => {
  const out = parseFilters(new URLSearchParams("capabilities=decision"));
  assert.deepEqual("error" in out ? out.error : out.capabilities, ["decision"]);
});

test("parseFilters accepts supported_features=streaming", () => {
  const out = parseFilters(new URLSearchParams("supported_features=streaming"));
  assert.deepEqual("error" in out ? out.error : out.supported_features, ["streaming"]);
});

test("parseFilters rejects unknown supported features with a 400 descriptor", () => {
  const out = parseFilters(new URLSearchParams("supported_features=quantum"));
  assert.ok("error" in out);
  if ("error" in out) {
    assert.equal(out.error.param, "supported_features");
    assert.equal(out.error.code, "invalid_supported_feature");
  }
});

test("filterEndpoints applies supported_features with AND-within-dimension semantics", () => {
  const streaming = makeEndpoint({ model_id: "a/s", supported_features: ["streaming"] });
  const plain = makeEndpoint({ model_id: "b/p" });
  const out = filterEndpoints([streaming, plain], { supported_features: ["streaming"] });
  assert.equal(out.length, 1);
  assert.equal(out[0].model_id, "a/s");
});

test("filterEndpoints treats missing supported_features as empty (historical records)", () => {
  const legacy = makeEndpoint({ model_id: "a/legacy" });
  const out = filterEndpoints([legacy], { supported_features: ["streaming"] });
  assert.equal(out.length, 0);
});

test("filterPublicModels applies supported_features to the model-level aggregate", () => {
  const m: PublicModel = {
    id: "vendor/test",
    object: "model",
    created: 0,
    data_source: "nvidia",
    provider: "nvidia",
    capabilities: ["chat"],
    supported_features: ["streaming"],
    endpoints: [],
  };
  assert.equal(filterPublicModels([m], { supported_features: ["streaming"] }).length, 1);
  assert.equal(filterPublicModels([m], { supported_features: [] }).length, 1);
});

test("PUBLIC_MODALITY_VOCABULARY exposes the documented enum", () => {
  assert.ok(PUBLIC_MODALITY_VOCABULARY.includes("text"));
  assert.ok(PUBLIC_MODALITY_VOCABULARY.includes("image"));
  assert.ok(PUBLIC_MODALITY_VOCABULARY.includes("audio"));
  assert.ok(PUBLIC_MODALITY_VOCABULARY.includes("video"));
  assert.ok(PUBLIC_MODALITY_VOCABULARY.includes("embedding"));
});

test("capabilities empty array means 'unavailable', not 'no capabilities'", () => {
  // Per doc §11 — an empty array is a signal that the data pipeline
  // didn't have capability info for this model, NOT that the model
  // itself has no capabilities. The vocabulary contract is tested
  // above; here we just confirm the shape stays ``[]`` (not null,
  // not omitted) so filter implementation can stay simple.
  const ep = makeEndpoint({
    model_id: "vendor/unknown",
    capabilities: {},
  });
  const out = toPublicModel(ep);
  assert.deepEqual(out.capabilities, []);
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
  // No model-level free — free status is endpoint-scoped only
  // (docs/tfi_model_and_endpoint_free_status_semantics.md §2.1).
  assert.equal("free" in out, false);
});

test("toPublicModels nests per-endpoint free/pricing without model-level free", () => {
  // Same canonical model served by two providers with DIFFERENT
  // free status — the exact case the semantics doc §3.1 mandates.
  const eps = [
    makeEndpoint({
      model_id: "Qwen/Qwen3-Next-80B-A3B-Instruct",
      provider: "together",
      free: false,
      pricing: { input: 0.2, output: 0.6 },
    }),
    makeEndpoint({
      model_id: "Qwen/Qwen3-Next-80B-A3B-Instruct",
      provider: "nvidia",
      free: true,
      pricing: null,
    }),
  ];
  const out = toPublicModels(eps);
  assert.equal(out.length, 1, "one PublicModel per canonical model");
  const model = out[0] as Record<string, unknown>;
  assert.equal("free" in model, false, "no model-level free");
  assert.equal(model.id, "Qwen/Qwen3-Next-80B-A3B-Instruct");
  const endpoints = model.endpoints as Array<Record<string, unknown>>;
  assert.equal(endpoints.length, 2);
  const nvidia = endpoints.find((e) => e.provider === "nvidia")!;
  const together = endpoints.find((e) => e.provider === "together")!;
  assert.equal(nvidia.free, true);
  assert.equal(nvidia.pricing, undefined, "null pricing omitted, not invented");
  assert.equal(together.free, false);
  assert.deepEqual(together.pricing, { input: 0.2, output: 0.6 });
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

// ---------------------------------------------------------------------------
// ETag — weak validator on response body for 304 revalidation
// ---------------------------------------------------------------------------

test("makeEtag is deterministic and strong (no W/ prefix)", () => {
  const a = makeEtag('{"a":1}');
  const b = makeEtag('{"a":1}');
  const c = makeEtag('{"a":2}');
  assert.equal(a, b);
  assert.notEqual(a, c);
  // Strong validator — bare quoted-string, no W/ prefix. Cloudflare's
  // edge strips weak ETags from cacheable responses; strong survives.
  assert.match(a, /^"tfi-[0-9a-f]{8}"$/);
});

test("etagMatches accepts bare / W-prefixed / comma-separated values", () => {
  const tag = makeEtag("hello");
  assert.equal(etagMatches(tag, tag), true);
  // W-prefixed form is also accepted (clients may receive either
  // depending on the proxy chain).
  const bareInsideQuotes = tag;
  assert.equal(etagMatches(`W/${bareInsideQuotes}`, tag), true);
  assert.equal(etagMatches(`*`, tag), true);
  assert.equal(etagMatches(`other, ${tag}, more`, tag), true);
  assert.equal(etagMatches("different", tag), false);
});

test("jsonResponse emits 304 + no body when If-None-Match matches", async () => {
  const body = { ok: 1 };
  const etag = makeEtag(JSON.stringify(body));
  const res = jsonResponse(body, {
    etag,
    ifNoneMatch: etag,
  });
  assert.equal(res.status, 304);
  // Per RFC 7232 §4.1, 304 responses MUST NOT include a message body
  // and the spec also strips most custom headers (we only see
  // Content-Length, which Cloudflare sets to 0). The validator
  // header is preserved on 304 for revalidation chains.
  const text = await res.text();
  assert.equal(text, "");
});

test("jsonResponse omits ETag header when no etag is passed", () => {
  const res = jsonResponse({ ok: 1 });
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("ETag"), null);
  // Cache-Control still present.
  assert.match(res.headers.get("Cache-Control") || "", /max-age=/);
});

test("textResponse also revalidates via ETag", async () => {
  const body = "# hello\n";
  const etag = makeEtag(body);
  const res = textResponse(body, "text/plain", {
    etag,
    ifNoneMatch: etag,
  });
  assert.equal(res.status, 304);
  // 304 has no body and most custom headers are stripped; just
  // verify the empty-body contract.
  const text = await res.text();
  assert.equal(text, "");
});

// ---------------------------------------------------------------------------
// source_url field (docs/tfi_model_source_url.md §6)
// ---------------------------------------------------------------------------

test("toPublicModel emits source_url when the canonical record has one", () => {
  const m = makeEndpoint();
  m.source_url = "https://build.nvidia.com/a/b";
  const pm = toPublicModel(m);
  assert.equal(pm.source_url, "https://build.nvidia.com/a/b");
});

test("toPublicModel omits source_url when the canonical record has none", () => {
  // Backward compat: older KV records do not carry the field.
  const m = makeEndpoint();
  // @ts-expect-error -- intentionally omitting source_url
  delete m.source_url;
  const pm = toPublicModel(m);
  assert.equal(pm.source_url, undefined);
});

test("toPublicModel omits source_url when canonical value is empty string", () => {
  // Defensive: the data pipeline should never stamp an empty string,
  // but the projection must be robust to it.
  const m = makeEndpoint();
  m.source_url = "";
  const pm = toPublicModel(m);
  assert.equal(pm.source_url, undefined);
});

test("toPublicModels forwards source_url on every projected model", () => {
  const m1 = makeEndpoint({ model_id: "m1", source_url: "https://a.com/m1" } as never);
  const m2 = makeEndpoint({ model_id: "m2", source_url: "https://a.com/m2" } as never);
  const out = toPublicModels([m1, m2]);
  assert.equal(out[0].source_url, "https://a.com/m1");
  assert.equal(out[1].source_url, "https://a.com/m2");
});
