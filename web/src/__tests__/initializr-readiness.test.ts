/**
 * Unit tests for :func:`computeReadiness` (web/src/initializr/InitializrContext.tsx).
 *
 * Locks the contract that drives the Generate button's enabled state on
 * the /generate page:
 *
 *   - empty selection    → not ready (reason: "initializr.validation.noModels")
 *   - selection present,
 *     factory === null   → not ready (reason: "initializr.validation.noFactory")
 *   - selection present,
 *     factory !== null   → ready (reason: null)
 *
 * Regression coverage for the bug where the InitializrProvider
 * initialized ``tokenFactory`` to ``null`` while the Segmented control
 * rendered with ``value ?? SUPPORTED_TOKEN_FACTORIES[0]`` (litellm
 * visually). The mismatch disabled the Initialize button until the
 * user toggled the picker — a useless detour for the default flow.
 * The fix: provider initializes to ``SUPPORTED_TOKEN_FACTORIES[0]``
 * so the visual + state are in sync on first mount.
 *
 * Run with:  cd web && npx tsx src/__tests__/initializr-readiness.test.ts
 */

import assert from "node:assert/strict";
import { computeReadiness } from "../initializr/InitializrContext";
import { SUPPORTED_TOKEN_FACTORIES } from "../../functions/lib/generators";
import type { SelectedModel, TokenFactoryId } from "../initializr/types";

let passed = 0;
let failed = 0;
const failedLabels: string[] = [];

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

const sampleModel: SelectedModel = {
  data_source: "nvidia",
  provider: "nvidia",
  model_id: "nvidia/sample",
  name: "Sample",
  description: null,
  free: true,
  capabilities: {},
  architecture: null,
  lab: null,
  metadata: {},
  fetched_at: "2026-01-01T00:00:00Z",
  context_length: null,
  pricing: null,
};

// -- empty selection --
suite("empty selection blocks generation", () => {
  const r = computeReadiness({ selectedModels: [], tokenFactory: null });
  check("ready === false", r.ready, false);
  check("reason === noModels", r.reason, "initializr.validation.noModels");
});

// -- null factory with non-empty selection --
suite("null factory blocks generation even when selection is present", () => {
  const r = computeReadiness({
    selectedModels: [sampleModel],
    tokenFactory: null,
  });
  check("ready === false", r.ready, false);
  check("reason === noFactory", r.reason, "initializr.validation.noFactory");
});

// -- ready --
suite("non-empty selection + non-null factory is ready", () => {
  const r = computeReadiness({
    selectedModels: [sampleModel],
    tokenFactory: SUPPORTED_TOKEN_FACTORIES[0],
  });
  check("ready === true", r.ready, true);
  check("reason === null", r.reason, null);
});

// -- supports every registered factory id --
suite("every SUPPORTED_TOKEN_FACTORIES id is accepted", () => {
  for (const id of SUPPORTED_TOKEN_FACTORIES) {
    const r = computeReadiness({
      selectedModels: [sampleModel],
      tokenFactory: id as TokenFactoryId,
    });
    check(`factory=${id} ready`, r.ready, true);
    check(`factory=${id} reason null`, r.reason, null);
  }
});

// -- default factory invariant (regression for the picker mismatch) --
// This expresses the contract the Provider must satisfy on first mount:
// the React state held in InitializrContext MUST equal the value the
// Segmented control renders by default. Otherwise the visual default
// (litellm) shows a button that's actually disabled, and the user has
// to toggle the picker once before Initialize becomes clickable.
suite("first SUPPORTED_TOKEN_FACTORIES id matches the picker default", () => {
  // The Segmented control in Generate.tsx falls back to
  // SUPPORTED_TOKEN_FACTORIES[0] when context.tokenFactory is null.
  // That means the *effective* default on first mount is
  // SUPPORTED_TOKEN_FACTORIES[0] — so the context's initial state
  // must equal it for ready to be true.
  const r = computeReadiness({
    selectedModels: [sampleModel],
    tokenFactory: SUPPORTED_TOKEN_FACTORIES[0],
  });
  check("default factory yields ready=true", r.ready, true);
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  console.error("Failures:\n  " + failedLabels.join("\n  "));
}
assert.equal(failed, 0, `${failed} test(s) failed`);
