// Tests for pricing field metadata changes (ollama sources + cached field).

import { test } from "node:test";
import assert from "node:assert/strict";

import { PRICING_FIELD_META } from "../lib/pricing.ts";

test("input pricing meta includes ollama as source", () => {
  const meta = PRICING_FIELD_META["input"];
  assert.ok(meta);
  assert.ok(meta.sources.includes("ollama"));
});

test("output pricing meta includes ollama as source", () => {
  const meta = PRICING_FIELD_META["output"];
  assert.ok(meta);
  assert.ok(meta.sources.includes("ollama"));
});

test("cached pricing field meta exists with per_1M_tokens unit", () => {
  const meta = PRICING_FIELD_META["cached"];
  assert.ok(meta);
  assert.equal(meta.rawKey, "cached");
  assert.equal(meta.unit, "per_1M_tokens");
  assert.deepEqual(meta.sources, ["ollama"]);
  assert.equal(meta.canonicalKey, "cached_input_read");
});
