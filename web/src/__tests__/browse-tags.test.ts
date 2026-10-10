// Tests for the Browse page tag taxonomy — specifically the three
// new capabilities added in the source_url implementation:
// reasoning / speech / structured_output.
//
// The Browse UI surfaces 8 tags (chat / vision / tools / reasoning
// / speech / structured_output / free / longCtx). The first three
// were already tested by the existing browse-filters suite; this
// file pins the contract for the new three so a future
// normalization regression surfaces immediately.

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
  // Tag count: 10 total (9 legacy + embedding).
  assert.equal(ids.length, 10, "TAGS array must have 10 entries (9 legacy + embedding)");
});

// ---------------------------------------------------------------------------
// hasTag predicates — capability → tag axis
// ---------------------------------------------------------------------------

test("hasTag reasoning is true when capabilities.reasoning is true", () => {
  const ep = makeEndpoint({ capabilities: { reasoning: true } });
  assert.equal(hasTag(ep, "reasoning"), true);
});

test("hasTag reasoning is false when capability is missing or false", () => {
  assert.equal(hasTag(makeEndpoint(), "reasoning"), false);
  assert.equal(hasTag(makeEndpoint({ capabilities: { reasoning: false } }), "reasoning"), false);
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

test("hasTag structured_output is true when capabilities.structured_output is true", () => {
  const ep = makeEndpoint({ capabilities: { structured_output: true } });
  assert.equal(hasTag(ep, "structured_output"), true);
});

test("hasTag structured_output is false when capability is missing or false", () => {
  assert.equal(hasTag(makeEndpoint(), "structured_output"), false);
  assert.equal(
    hasTag(makeEndpoint({ capabilities: { structured_output: false } }), "structured_output"),
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
  const modelA = makeEndpoint({ model_id: "m/with-reasoning", capabilities: { reasoning: true } });
  const modelB = makeEndpoint({ model_id: "m/no-reasoning", capabilities: {} });

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
  const epA = makeEndpoint({ model_id: "m/chat+reasoning", capabilities: { chat: true, reasoning: true } });
  const epB = makeEndpoint({ model_id: "m/chat-only", capabilities: { chat: true } });
  const epC = makeEndpoint({ model_id: "m/reasoning-only", capabilities: { reasoning: true } });

  const out = applyFilters(
    [epA, epB, epC],
    "",
    new Set(["chat", "reasoning"]),
  );
  assert.equal(out.length, 1);
  assert.equal(out[0].model_id, "m/chat+reasoning");
});

test("applyFilters AND across dimensions (legacy tag + new tag)", () => {
  // The user can combine chat (legacy) with reasoning (new). Both
  // must hold for a model to pass.
  const epA = makeEndpoint({ model_id: "m/chat+reasoning", capabilities: { chat: true, reasoning: true } });
  const epB = makeEndpoint({ model_id: "m/chat-only", capabilities: { chat: true } });
  const epC = makeEndpoint({ model_id: "m/reasoning-only", capabilities: { reasoning: true } });

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
    makeEndpoint({ capabilities: { reasoning: true } }),
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
  const ep = makeEndpoint({ capabilities: { reasoning: false } });
  assert.equal(matchesRequirement(ep, { capabilities: { reasoning: true } }), false);
  const ep2 = makeEndpoint({ capabilities: { reasoning: true } });
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
  const ep2 = makeEndpoint({ capabilities: { structured_output: true } });
  assert.equal(matchesRequirement(ep2, { capabilities: { structuredOutput: true } }), true);
});

// Exported helpers re-export check (regression — the existing
// browse-filters suite pins this same contract).
assert.equal(typeof __browseFilters, "object");
assert.equal(typeof __browseFilters.hasTag, "function");
assert.equal(typeof __browseFilters.applyFilters, "function");
