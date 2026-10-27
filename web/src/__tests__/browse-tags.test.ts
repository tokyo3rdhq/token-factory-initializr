// Tests for the Browse page tag taxonomy — capability chips,
// the migrated interface/parameter tags (tools / reasoning /
// structured_output / streaming, moved to supported_parameters on
// 2026-10-19), and the decision capability.

import { test } from "node:test";
import assert from "node:assert/strict";

import { __browseFilters, TAGS } from "../pages/Browse";
const { hasTag, applyFilters } = __browseFilters;
import type { ModelEndpoint } from "../../functions/lib/kv.ts";

function makeEndpoint(overrides: Partial<ModelEndpoint> = {}): ModelEndpoint {
  return {
    data_source: "huggingface",
    provider: "together",
    model_id: "sample/model",
    name: null,
    description: null,
    free: true,
    capabilities: {},
    architecture: null,
    lab: null,
    metadata: {},
    fetched_at: "2026-10-08T00:00:00Z",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// TAGS array — taxonomy surface area
// ---------------------------------------------------------------------------

test("TAGS exposes the new reasoning / speech / structured_output ids", () => {
  const ids = TAGS.map((t) => t.id);
  // The three new tags are wired into the public taxonomy.
  assert.ok(ids.includes("reasoning"), "TAGS must include 'reasoning'");
  assert.ok(ids.includes("speech"), "TAGS must include 'speech'");
  assert.ok(ids.includes("structured_output"), "TAGS must include 'structured_output'");
  // Tag count: 13 total (6 capabilities + 4 parameters + 1 pricing tier + longCtx + longCtxM + decision capability).
  assert.equal(ids.length, 13, "TAGS array must have 13 entries");
  // decision capability is wired in too.
  assert.ok(ids.includes("decision"), "TAGS must include 'decision'");
});

// ---------------------------------------------------------------------------
// hasTag predicates — supported_parameters axis (streaming)
// ---------------------------------------------------------------------------

test("hasTag streaming is true when supported_parameters contains streaming", () => {
  const ep = makeEndpoint({ supported_parameters: ["streaming"] });
  assert.equal(hasTag(ep, "streaming"), true);
});

test("hasTag streaming is false when supported_parameters is missing (historical records)", () => {
  const ep = makeEndpoint({});
  assert.equal(hasTag(ep, "streaming"), false);
});

test("hasTag streaming is false when supported_parameters is empty or lists other features", () => {
  assert.equal(hasTag(makeEndpoint({ supported_parameters: [] }), "streaming"), false);
  assert.equal(hasTag(makeEndpoint({ supported_parameters: ["other"] }), "streaming"), false);
});

test("hasTag streaming never infers from metadata or capability flags", () => {
  const ep = makeEndpoint({
    capabilities: { chat: true },
    supported_parameters: ["reasoning"],
    metadata: { streaming: true },
  });
  assert.equal(hasTag(ep, "streaming"), false);
});

test("streaming tag is positioned after capability tags and after free/longCtx", () => {
  const ids = TAGS.map((t) => t.id);
  const streamingIdx = ids.indexOf("streaming");
  const structuredIdx = ids.indexOf("structured_output");
  const freeIdx = ids.indexOf("free");
  const longCtxIdx = ids.indexOf("longCtx");
  // Badge order: Free → longCtx → capabilities → supported_parameters,
  // so streaming lands at the very end, after free/longCtx/capabilities.
  assert.ok(streamingIdx > structuredIdx, "streaming must come after the last capability tag");
  assert.ok(streamingIdx > freeIdx, "streaming must come after free");
  assert.ok(streamingIdx > longCtxIdx, "streaming must come after longCtx");
});

test("streaming tag uses the neutral (gray) variant", () => {
  const streaming = TAGS.find((t) => t.id === "streaming");
  assert.ok(streaming, "TAGS must include 'streaming'");
  assert.equal(streaming?.variant, "neutral");
});

test("applyFilters filters by the streaming tag", () => {
  const eps = [
    makeEndpoint({ model_id: "a/streaming-model", supported_parameters: ["streaming"] }),
    makeEndpoint({ model_id: "b/plain-model" }),
  ];
  const out = applyFilters(eps, "", new Set(["streaming"]));
  assert.equal(out.length, 1);
  assert.equal(out[0].model_id, "a/streaming-model");
});

// ---------------------------------------------------------------------------
// hasTag predicates — capability → tag axis
// ---------------------------------------------------------------------------

test("hasTag reasoning is true when supported_parameters contains reasoning", () => {
  const ep = makeEndpoint({ supported_parameters: ["reasoning"] });
  assert.equal(hasTag(ep, "reasoning"), true);
});

test("hasTag reasoning is false when the parameter is missing or absent", () => {
  assert.equal(hasTag(makeEndpoint(), "reasoning"), false);
  assert.equal(hasTag(makeEndpoint({ supported_parameters: ["tool_calling"] }), "reasoning"), false);
  // Legacy shape (reasoning under capabilities) must NOT match.
  assert.equal(hasTag(makeEndpoint({ capabilities: { reasoning: true } }), "reasoning"), false);
});

test("hasTag speech is true when capabilities.speech is true", () => {
  const ep = makeEndpoint({ capabilities: { speech: true } });
  assert.equal(hasTag(ep, "speech"), true);
});

test("hasTag speech falls back to architecture.output containing 'audio'", () => {
  // Forward-compat path: a provider whose adapter omits the speech
  // capability flag but exposes 'audio' in architecture.output
  // (e.g. an OpenAI TTS-style endpoint) should still surface
  // the speech tag.
  const ep = makeEndpoint({
    capabilities: { speech: undefined },
    architecture: { input: ["text"], output: ["audio"] },
  });
  assert.equal(hasTag(ep, "speech"), true);
});

test("hasTag structured_output is true when supported_parameters contains it", () => {
  const ep = makeEndpoint({ supported_parameters: ["structured_output"] });
  assert.equal(hasTag(ep, "structured_output"), true);
});

test("hasTag structured_output is false when the parameter is missing or absent", () => {
  assert.equal(hasTag(makeEndpoint(), "structured_output"), false);
  assert.equal(
    hasTag(makeEndpoint({ supported_parameters: ["streaming"] }), "structured_output"),
    false,
  );
  // Legacy shape must NOT match.
  assert.equal(
    hasTag(makeEndpoint({ capabilities: { structured_output: true } }), "structured_output"),
    false,
  );
});

// ---------------------------------------------------------------------------
// applyFilters — multi-axis composition
// ---------------------------------------------------------------------------

test("applyFilters accepts the three new tag ids in the activeTags set", () => {
  // Regression: the type for activeTags was widened to include the
  // three new ids. Filtering with the new ids as the only active tag
  // must work.
  const modelA = makeEndpoint({ model_id: "m/with-reasoning", supported_parameters: ["reasoning"] });
  const modelB = makeEndpoint({ model_id: "m/no-reasoning", supported_parameters: [] });

  const out = applyFilters([modelA, modelB], "", new Set(["reasoning"]));
  assert.equal(out.length, 1);
  assert.equal(out[0].model_id, "m/with-reasoning");
});

test("applyFilters AND semantics across the new tag axes (active set = chat+reasoning)", () => {
  // The Browse filter is currently strict-AND within the active
  // tag set: every selected tag must hold. This is a pre-existing
  // implementation choice that differs from the public API filter
  // semantics (which is OR-within-dimension per the model filter
  // spec). The test below pins the current AND behaviour so the
  // contract is explicit and any future change is intentional.
  const epA = makeEndpoint({ model_id: "m/chat+reasoning", capabilities: { chat: true }, supported_parameters: ["reasoning"] });
  const epB = makeEndpoint({ model_id: "m/chat-only", capabilities: { chat: true } });
  const epC = makeEndpoint({ model_id: "m/reasoning-only", supported_parameters: ["reasoning"] });

  const out = applyFilters(
    [epA, epB, epC],
    "",
    new Set(["chat", "reasoning"]),
  );
  assert.equal(out.length, 1);
  assert.equal(out[0].model_id, "m/chat+reasoning");
});

test("applyFilters AND across dimensions (capability tag + parameter tag)", () => {
  // The user can combine chat (capability) with reasoning
  // (parameter). Both must hold for a model to pass.
  const epA = makeEndpoint({ model_id: "m/chat+reasoning", capabilities: { chat: true }, supported_parameters: ["reasoning"] });
  const epB = makeEndpoint({ model_id: "m/chat-only", capabilities: { chat: true } });
  const epC = makeEndpoint({ model_id: "m/reasoning-only", supported_parameters: ["reasoning"] });

  const out = applyFilters(
    [epA, epB, epC],
    "",
    new Set(["chat", "reasoning"]),
  );
  assert.equal(out.length, 1);
  assert.equal(out[0].model_id, "m/chat+reasoning");
});

test("applyFilters with no activeTags is the identity pass-through", () => {
  const eps = [
    makeEndpoint({ capabilities: { chat: true } }),
    makeEndpoint({ supported_parameters: ["reasoning"] }),
    makeEndpoint({ capabilities: { speech: true } }),
  ];
  const out = applyFilters(eps, "", new Set());
  assert.equal(out.length, 3);
});

// ---------------------------------------------------------------------------
// matchesRequirement — Home page requirement → Browse filter wiring
// ---------------------------------------------------------------------------

const { matchesRequirement } = await import("../../src/types.ts");

test("matchesRequirement: capability.reasoning=true filters out non-reasoning models", () => {
  const ep = makeEndpoint({ supported_parameters: [] });
  assert.equal(matchesRequirement(ep, { capabilities: { reasoning: true } }), false);
  const ep2 = makeEndpoint({ supported_parameters: ["reasoning"] });
  assert.equal(matchesRequirement(ep2, { capabilities: { reasoning: true } }), true);
});

test("matchesRequirement: capability.speech=true filters out non-speech models", () => {
  const ep = makeEndpoint({ capabilities: { speech: false } });
  assert.equal(matchesRequirement(ep, { capabilities: { speech: true } }), false);
  const ep2 = makeEndpoint({ capabilities: { speech: true } });
  assert.equal(matchesRequirement(ep2, { capabilities: { speech: true } }), true);
});

test("matchesRequirement: capability.speech falls back to architecture.output=audio", () => {
  // Forward-compat: a provider whose adapter omits the speech flag
  // but exposes 'audio' in architecture.output should still satisfy
  // capability.speech=true. This is the same fallback that
  // hasSpeech() applies; matchesRequirement should agree.
  const ep = makeEndpoint({
    capabilities: {},
    architecture: { input: ["text"], output: ["audio"] },
  });
  assert.equal(matchesRequirement(ep, { capabilities: { speech: true } }), true);
});

test("matchesRequirement: capability.structuredOutput=true filters out non-structured models", () => {
  const ep = makeEndpoint({ capabilities: {} });
  assert.equal(matchesRequirement(ep, { capabilities: { structuredOutput: true } }), false);
  const ep2 = makeEndpoint({ supported_parameters: ["structured_output"] });
  assert.equal(matchesRequirement(ep2, { capabilities: { structuredOutput: true } }), true);
});

// Exported helpers re-export check (regression — the existing
// browse-filters suite pins this same contract).
assert.equal(typeof __browseFilters, "object");
assert.equal(typeof __browseFilters.hasTag, "function");
assert.equal(typeof __browseFilters.applyFilters, "function");
