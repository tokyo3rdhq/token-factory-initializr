// Tests for the /api/v1/providers + /api/v1/endpoints projection,
// filter parsing, and redaction. Runs in Node via
// node --experimental-strip-types so we exercise the actual TS
// implementation, not a transpiled copy.

import { test } from "node:test";
import assert from "node:assert/strict";

const { toPublicProvider, toPublicEndpoint, redactEndpoint, findCredentialString, FORBIDDEN_SUBSTRINGS } =
  await import("../../functions/lib/projection.ts");
const { buildIndexes } = await import("../../functions/lib/endpoints.ts");
const { filterPublicProviders, filterPublicEndpoints, parseProviderFilters, parseEndpointFilters } =
  await import("../../functions/lib/filter.ts");
import type { ModelEndpoint } from "../../functions/lib/kv.ts";

function makeEndpoint(overrides: Partial<ModelEndpoint> = {}): ModelEndpoint {
  return {
    data_source: "huggingface",
    provider: "together",
    model_id: "meta-llama/Llama-3.3-70B-Instruct",
    name: null,
    description: null,
    free: true,
    capabilities: { chat: true },
    architecture: null,
    lab: null,
    metadata: {},
    fetched_at: "2026-10-08T00:00:00Z",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Provider projection
// ---------------------------------------------------------------------------

test("toPublicProvider carries id, name, data_source, protocols", () => {
  const p = toPublicProvider("huggingface", "together");
  assert.equal(p.id, "together");
  assert.equal(p.data_source, "huggingface");
  assert.ok(Array.isArray(p.protocols));
  assert.ok(p.protocols.length > 0, "registry should map together to a protocol");
  // Documentation URL is surface-stable.
  assert.ok(typeof p.documentation_url === "string" || p.documentation_url === undefined);
});

test("toPublicProvider is stable across repeated calls (idempotent)", () => {
  const a = toPublicProvider("nvidia", "nvidia");
  const b = toPublicProvider("nvidia", "nvidia");
  assert.deepEqual(a, b);
});

test("toPublicProvider protocols are sorted in a stable canonical order", () => {
  const p = toPublicProvider("huggingface", "huggingface");
  // Always begins with the canonical first protocol.
  assert.equal(p.protocols[0], "huggingface");
});

test("toPublicProvider does NOT include model-specific data", () => {
  // The provider object must not embed models[] or any per-model field.
  const p = toPublicProvider("huggingface", "together") as Record<string, unknown>;
  assert.equal(p.models, undefined);
  assert.equal(p.base_url, undefined);
  assert.equal(p.capabilities, undefined);
  assert.equal(p.limits, undefined);
  assert.equal(p.status, undefined);
});

test("toPublicProvider on an unknown provider still produces a valid object", () => {
  // Unknown providers must NOT throw. They surface minimal info
  // (id + data_source) and omit the registry-only fields.
  const p = toPublicProvider("huggingface", "totally-fake-provider-xyz");
  assert.equal(p.id, "totally-fake-provider-xyz");
  assert.equal(p.data_source, "huggingface");
  // protocols: from registry (empty), so the array is empty — the
  // field is still present per the schema (always emit).
  assert.deepEqual(p.protocols, []);
  // name + documentation_url omitted.
  assert.equal(p.name, undefined);
  assert.equal(p.documentation_url, undefined);
});

// ---------------------------------------------------------------------------
// Endpoint projection
// ---------------------------------------------------------------------------

test("toPublicEndpoint id format is {provider}:{endpoint_name}", () => {
  const ep = toPublicEndpoint("huggingface", "together", ["m1", "m2"]);
  assert.equal(ep.id, "together:default");
});

test("toPublicEndpoint carries protocol + base_url + authentication + status + models", () => {
  const ep = toPublicEndpoint("huggingface", "together", ["m1"]);
  assert.equal(ep.provider, "together");
  assert.equal(ep.data_source, "huggingface");
  assert.ok(ep.protocol);
  assert.ok(ep.base_url);
  assert.equal(ep.authentication?.type, "bearer");
  assert.equal(ep.authentication?.credential_required, true);
  assert.equal(ep.status, "active");
  assert.deepEqual(ep.models, ["m1"]);
});

test("toPublicEndpoint drops models when the catalog slice is empty", () => {
  const ep = toPublicEndpoint("huggingface", "together", []);
  assert.equal(ep.models, undefined, "empty models[] must be omitted per §10");
});

test("toPublicEndpoint models are sorted for diff-friendly output", () => {
  const ep = toPublicEndpoint("huggingface", "together", ["z", "a", "m"]);
  assert.deepEqual(ep.models, ["a", "m", "z"]);
});

test("toPublicEndpoint honours endpointName override", () => {
  const ep = toPublicEndpoint("huggingface", "together", ["m1"], {
    endpointName: "region-eu",
  });
  assert.equal(ep.id, "together:region-eu");
});

test("toPublicEndpoint status can be overridden", () => {
  const ep = toPublicEndpoint("huggingface", "together", ["m1"], {
    status: "deprecated",
  });
  assert.equal(ep.status, "deprecated");
});

test("toPublicEndpoint never carries credentials, tokens, or auth headers", () => {
  // Build an endpoint from the public registry (the only legal
  // input) and assert no credential-shaped substring leaks through
  // the projection.
  const ep = toPublicEndpoint("huggingface", "together", ["m1"]);
  const hit = findCredentialString(ep);
  assert.equal(hit, null, `unexpected credential-shaped substring: ${hit}`);
});

test("redactEndpoint is idempotent", () => {
  const ep = toPublicEndpoint("nvidia", "nvidia", ["m1"]);
  const a = redactEndpoint(ep);
  const b = redactEndpoint(redactEndpoint(ep));
  assert.deepEqual(a, b);
});

test("redactEndpoint keeps only the documented public fields", () => {
  const ep = toPublicEndpoint("nvidia", "nvidia", ["m1"]) as Record<string, unknown>;
  const redacted = redactEndpoint(ep) as Record<string, unknown>;
  const allowed = new Set([
    "id", "provider", "data_source", "protocol", "base_url",
    "authentication", "status", "limits", "models",
  ]);
  for (const k of Object.keys(redacted)) {
    assert.ok(allowed.has(k), `unexpected field in redacted endpoint: ${k}`);
  }
});

test("FORBIDDEN_SUBSTRINGS covers the obvious credential shapes", () => {
  // Defence-in-depth — if this list is ever trimmed we want the
  // regression test to fail loudly so we can update the projection
  // before the leak lands in prod.
  for (const s of [
    "Authorization: Bearer abc",
    "api_key=secret-123",
    "password=hunter2",
    "X-Auth-Token: 9f3...",
  ]) {
    const hit = FORBIDDEN_SUBSTRINGS.find((bad) => s.toLowerCase().includes(bad));
    assert.ok(hit, `expected ${s} to match a forbidden substring`);
  }
});

// ---------------------------------------------------------------------------
// buildIndexes
// ---------------------------------------------------------------------------

test("buildIndexes dedupes endpoints by (data_source, provider) pair", () => {
  const cat = {
    endpoints: [
      makeEndpoint({ model_id: "m1" }),
      makeEndpoint({ model_id: "m2" }),
      makeEndpoint({ model_id: "m3" }),
    ],
    snapshots: [],
    pairs: [],
  };
  const idx = buildIndexes(cat);
  assert.equal(idx.endpoints.length, 1, "3 models on same pair -> 1 endpoint");
  assert.equal(idx.endpoints[0].provider, "together");
  assert.equal(idx.endpoints[0].id, "together:default");
  assert.equal(idx.providers.length, 1);
  assert.equal(idx.providers[0].id, "together");
});

test("buildIndexes creates one endpoint per (data_source, provider) pair", () => {
  const cat = {
    endpoints: [
      makeEndpoint({ data_source: "huggingface", provider: "together", model_id: "m1" }),
      makeEndpoint({ data_source: "huggingface", provider: "novita", model_id: "m2" }),
      makeEndpoint({ data_source: "nvidia", provider: "nvidia", model_id: "m3" }),
    ],
    snapshots: [],
    pairs: [],
  };
  const idx = buildIndexes(cat);
  // 2 huggingface providers + 1 nvidia = 3 endpoints.
  assert.equal(idx.endpoints.length, 3);
  assert.equal(idx.providers.length, 3);
  // Lookup maps.
  assert.equal(idx.endpointById.get("together:default")?.provider, "together");
  assert.equal(idx.providerById.get("nvidia")?.id, "nvidia");
});

test("buildIndexes model_id -> endpoint ids index is correct", () => {
  const cat = {
    endpoints: [
      makeEndpoint({ data_source: "huggingface", provider: "together", model_id: "shared" }),
      makeEndpoint({ data_source: "huggingface", provider: "novita", model_id: "shared" }),
      makeEndpoint({ data_source: "nvidia", provider: "nvidia", model_id: "nvidia-only" }),
    ],
    snapshots: [],
    pairs: [],
  };
  const idx = buildIndexes(cat);
  const shared = idx.modelsByEndpoint.get("shared")!.sort();
  assert.deepEqual(shared, ["novita:default", "together:default"]);
  assert.deepEqual(idx.modelsByEndpoint.get("nvidia-only"), ["nvidia:default"]);
});

test("buildIndexes is deterministic across repeated calls", () => {
  const cat = {
    endpoints: [
      makeEndpoint({ data_source: "huggingface", provider: "together", model_id: "z" }),
      makeEndpoint({ data_source: "huggingface", provider: "novita", model_id: "a" }),
      makeEndpoint({ data_source: "nvidia", provider: "nvidia", model_id: "m" }),
    ],
    snapshots: [],
    pairs: [],
  };
  const a = buildIndexes(cat);
  const b = buildIndexes(cat);
  assert.deepEqual(a, b);
});

// ---------------------------------------------------------------------------
// filterPublicProviders
// ---------------------------------------------------------------------------

test("filterPublicProviders no filters = passthrough", () => {
  const providers = [
    toPublicProvider("huggingface", "together"),
    toPublicProvider("nvidia", "nvidia"),
  ];
  assert.equal(filterPublicProviders(providers, {}).length, 2);
});

test("filterPublicProviders data_source OR semantics", () => {
  const providers = [
    toPublicProvider("huggingface", "together"),
    toPublicProvider("nvidia", "nvidia"),
    toPublicProvider("amd", "amd"),
  ];
  const out = filterPublicProviders(providers, { data_source: ["huggingface", "amd"] });
  assert.equal(out.length, 2);
  assert.deepEqual(out.map((p) => p.id).sort(), ["amd", "together"]);
});

test("filterPublicProviders unknown data_source returns empty", () => {
  const providers = [toPublicProvider("huggingface", "together")];
  const out = filterPublicProviders(providers, { data_source: ["nope"] });
  assert.equal(out.length, 0);
});

// ---------------------------------------------------------------------------
// filterPublicEndpoints
// ---------------------------------------------------------------------------

test("filterPublicEndpoints provider filter OR semantics", () => {
  const endpoints = [
    toPublicEndpoint("huggingface", "together", ["m1"]),
    toPublicEndpoint("huggingface", "novita", ["m2"]),
    toPublicEndpoint("nvidia", "nvidia", ["m3"]),
  ];
  const out = filterPublicEndpoints(endpoints, { provider: ["together", "nvidia"] });
  assert.equal(out.length, 2);
  assert.deepEqual(out.map((e) => e.provider).sort(), ["nvidia", "together"]);
});

test("filterPublicEndpoints combined dimensions = AND across", () => {
  const endpoints = [
    toPublicEndpoint("huggingface", "together", ["m1"]),
    toPublicEndpoint("huggingface", "novita", ["m2"]),
    toPublicEndpoint("nvidia", "nvidia", ["m3"]),
  ];
  const out = filterPublicEndpoints(endpoints, {
    provider: ["together", "novita"],
    data_source: ["nvidia"],
  });
  // provider in (together, novita) AND data_source = nvidia -> empty.
  assert.equal(out.length, 0);
});

test("filterPublicEndpoints protocol filter", () => {
  const endpoints = [
    toPublicEndpoint("huggingface", "together", ["m1"]),  // openai-compatible
    toPublicEndpoint("huggingface", "huggingface", ["m2"]), // huggingface
  ];
  const out = filterPublicEndpoints(endpoints, { protocol: ["huggingface"] });
  assert.equal(out.length, 1);
  assert.equal(out[0].provider, "huggingface");
});

test("filterPublicEndpoints status filter", () => {
  const endpoints = [
    toPublicEndpoint("huggingface", "together", ["m1"], { status: "active" }),
    toPublicEndpoint("huggingface", "novita", ["m2"], { status: "deprecated" }),
  ];
  const out = filterPublicEndpoints(endpoints, { status: ["deprecated"] });
  assert.equal(out.length, 1);
  assert.equal(out[0].provider, "novita");
});

test("filterPublicEndpoints model_id filter matches endpoints serving the model", () => {
  const endpoints = [
    toPublicEndpoint("huggingface", "together", ["m1", "m2"]),
    toPublicEndpoint("huggingface", "novita", ["m3"]),
    toPublicEndpoint("nvidia", "nvidia", ["m2"]),
  ];
  const out = filterPublicEndpoints(endpoints, { model_id: ["m2"] });
  // m2 is on together + nvidia — OR-within-dimension means any
  // endpoint serving m2 matches.
  assert.equal(out.length, 2);
  assert.deepEqual(out.map((e) => e.id).sort(), ["nvidia:default", "together:default"]);
});

test("filterPublicEndpoints model_id with no matches returns empty", () => {
  const endpoints = [toPublicEndpoint("huggingface", "together", ["m1"])];
  const out = filterPublicEndpoints(endpoints, { model_id: ["nope"] });
  assert.equal(out.length, 0);
});

// ---------------------------------------------------------------------------
// parseProviderFilters / parseEndpointFilters
// ---------------------------------------------------------------------------

test("parseProviderFilters empty params = empty filters", () => {
  const r = parseProviderFilters(new URLSearchParams(""));
  assert.equal(r.ok, true);
  if (r.ok) assert.deepEqual(r.filters, {});
});

test("parseProviderFilters data_source=groq,nvidia -> {data_source: [...]}", () => {
  const r = parseProviderFilters(new URLSearchParams("data_source=groq,nvidia"));
  assert.equal(r.ok, true);
  if (r.ok) {
    assert.deepEqual(r.filters.data_source, ["groq", "nvidia"]);
  }
});

test("parseProviderFilters empty data_source= silently treats as no filter", () => {
  // Empty CSV means "user passed the param but provided no values".
  // The handler treats this as "no filter on this dimension" — same
  // as omitting the param entirely. This is intentional lenience for
  // browser query-string behaviour; the strict 400 path is reserved
  // for explicit bad capability values via the existing models
  // filter contract.
  const r = parseProviderFilters(new URLSearchParams("data_source="));
  assert.equal(r.ok, true);
  if (r.ok) assert.deepEqual(r.filters, {});
});

test("parseEndpointFilters accepts all 5 dimensions", () => {
  const r = parseEndpointFilters(new URLSearchParams(
    "provider=together,novita&data_source=huggingface&protocol=openai-compatible&status=active&model_id=meta-llama/Llama-3.3-70B-Instruct"
  ));
  assert.equal(r.ok, true);
  if (r.ok) {
    assert.deepEqual(r.filters.provider, ["together", "novita"]);
    assert.deepEqual(r.filters.data_source, ["huggingface"]);
    assert.deepEqual(r.filters.protocol, ["openai-compatible"]);
    assert.deepEqual(r.filters.status, ["active"]);
    assert.deepEqual(r.filters.model_id, ["meta-llama/Llama-3.3-70B-Instruct"]);
  }
});

test("parseEndpointFilters rejects empty value", () => {
  const r = parseEndpointFilters(new URLSearchParams("status="));
  assert.equal(r.ok, false);
  if (!r.ok) assert.equal(r.param, "status");
});

// ---------------------------------------------------------------------------
// Model backref wiring
// ---------------------------------------------------------------------------

const { toPublicModel, toPublicModels } = await import("../../functions/lib/projection.ts");

test("toPublicModel without endpointsByModel omits endpoints field", () => {
  const m = makeEndpoint();
  const pm = toPublicModel(m);
  assert.equal(pm.endpoints, undefined);
});

test("toPublicModel with endpointsByModel attaches the matching endpoint ids", () => {
  const m = makeEndpoint({ model_id: "m1" });
  const idx = new Map<string, string[]>([["m1", ["together:default", "nvidia:default"]]]);
  const pm = toPublicModel(m, { endpointsByModel: idx });
  assert.deepEqual(pm.endpoints, ["nvidia:default", "together:default"]);
});

test("toPublicModel with endpointsByModel but no match omits endpoints field", () => {
  const m = makeEndpoint({ model_id: "m1" });
  const idx = new Map<string, string[]>([["other-model", ["x:default"]]]);
  const pm = toPublicModel(m, { endpointsByModel: idx });
  assert.equal(pm.endpoints, undefined);
});

test("toPublicModels forwards endpointsByModel to every per-model projection", () => {
  const idx = new Map<string, string[]>([
    ["m1", ["together:default"]],
    ["m2", ["nvidia:default"]],
  ]);
  const out = toPublicModels(
    [makeEndpoint({ model_id: "m1" }), makeEndpoint({ model_id: "m2" })],
    { endpointsByModel: idx },
  );
  assert.deepEqual(out[0].endpoints, ["together:default"]);
  assert.deepEqual(out[1].endpoints, ["nvidia:default"]);
});
