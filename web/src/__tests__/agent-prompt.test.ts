/**
 * Unit tests for :func:`buildAgentPrompt`
 * (web/functions/lib/generators/agentPrompt.ts).
 *
 * The Generate page's result panel surfaces the per-selection agent
 * prompt via an "Agent Prompt" copy button. The button copies the
 * generated URL plus the prompt in a single clipboard payload.
 *
 * This test pins the prompt contract:
 *
 *   1. The generated URL is embedded as a concrete example.
 *   2. The selection manifest lists every (data_source, provider,
 *      model_id) the user picked.
 *   3. The factory name in the header reflects the chosen Token
 *      Factory implementation (LiteLLM / NewAPI).
 *   4. The Merge Strategy section names the factory's merge
 *      semantics (model_list / models[]).
 *   5. The factory-agnostic workflow steps (1-10) always render.
 *   6. An unsupported factory id throws (exhaustive guard).
 *
 * Run with:  cd web && npx tsx src/__tests__/agent-prompt.test.ts
 */

import assert from "node:assert/strict";

let passed = 0;
let failed = 0;
const failedLabels: string[] = [];

function check(label: string, actual: unknown, expected: unknown): void {
  if (actual === expected) {
    passed++;
    console.log(`  ok  ${label}`);
  } else {
    failed++;
    failedLabels.push(
      `${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
    );
    console.error(
      `  FAIL ${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
    );
  }
}

function checkContains(label: string, haystack: string, needle: string): void {
  check(`${label} (contains)`, haystack.includes(needle), true);
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

import { buildAgentPrompt } from "../../functions/lib/generators";
import type { ModelEndpoint } from "../types";

const ep = (overrides: Partial<ModelEndpoint>): ModelEndpoint => ({
  data_source: "nvidia",
  provider: "nvidia",
  model_id: "x/y",
  name: "Y",
  description: null,
  free: true,
  capabilities: {},
  architecture: null,
  lab: null,
  metadata: {},
  fetched_at: "2026-01-01T00:00:00Z",
  context_length: null,
  pricing: null,
  ...overrides,
});

const samples: ModelEndpoint[] = [
  ep({
    data_source: "nvidia",
    provider: "nvidia",
    model_id: "deepseek-ai/deepseek-v4.1-flash",
  }),
  ep({
    data_source: "huggingface",
    provider: "huggingface",
    model_id: "meta-llama/Llama-3.2-3B-Instruct",
  }),
  ep({
    data_source: "amd",
    provider: "amd",
    model_id: "MiMo-V2.6-Flash",
  }),
];

const URL = "https://start.magi.website/generated/EsXHtLvI";

// ---------------------------------------------------------------------------
// LiteLLM prompt
// ---------------------------------------------------------------------------

suite("litellm: factory-specific naming", () => {
  const p = buildAgentPrompt("litellm", URL, samples);
  checkContains("header mentions LiteLLM", p, "LiteLLM configuration");
  checkContains(
    "merge strategy references litellm_yaml semantics indirectly",
    p,
    "Existing configuration",
  );
});

suite("litellm: selection manifest includes every model", () => {
  const p = buildAgentPrompt("litellm", URL, samples);
  for (const m of samples) {
    checkContains(
      `manifest lists ${m.data_source} :: ${m.provider} :: ${m.model_id}`,
      p,
      `${m.data_source} :: ${m.provider} :: ${m.model_id}`,
    );
  }
});

suite("litellm: URL rendered as concrete example", () => {
  const p = buildAgentPrompt("litellm", URL, samples);
  checkContains("URL appears as concrete example", p, URL);
});

suite("litellm: factory-agnostic workflow steps render", () => {
  const p = buildAgentPrompt("litellm", URL, samples);
  // Spot-check a handful of section headings from the common
  // skeleton — they must render for every factory.
  checkContains("step 1 heading", p, "## 1. Inspect the Current Project");
  checkContains("step 6 heading", p, "## 6. Preserve Secrets");
  checkContains("step 10 heading", p, "## 10. Final Report");
  checkContains("important principle heading", p, "## Important Principle");
});

// ---------------------------------------------------------------------------
// NewAPI prompt
// ---------------------------------------------------------------------------

suite("newapi: factory-specific naming", () => {
  const p = buildAgentPrompt("newapi", URL, samples);
  checkContains("header mentions NewAPI", p, "NewAPI");
  checkContains(
    "factory-specific merge strategy names models[] semantics",
    p,
    "models[]",
  );
});

suite("newapi: selection manifest still included", () => {
  const p = buildAgentPrompt("newapi", URL, samples);
  for (const m of samples) {
    checkContains(
      `manifest lists ${m.model_id}`,
      p,
      `${m.data_source} :: ${m.provider} :: ${m.model_id}`,
    );
  }
});

suite("newapi: URL rendered as concrete example", () => {
  const p = buildAgentPrompt("newapi", URL, samples);
  checkContains("URL appears as concrete example", p, URL);
});

suite("newapi: factory-agnostic workflow steps render", () => {
  const p = buildAgentPrompt("newapi", URL, samples);
  checkContains("step 1 heading", p, "## 1. Inspect the Current Project");
  checkContains("step 6 heading", p, "## 6. Preserve Secrets");
  checkContains("step 10 heading", p, "## 10. Final Report");
});

suite("newapi: differs from litellm prompt", () => {
  const a = buildAgentPrompt("litellm", URL, samples);
  const b = buildAgentPrompt("newapi", URL, samples);
  check("different factory → different prompt body", a !== b, true);
});

// ---------------------------------------------------------------------------
// Cross-cutting invariants
// ---------------------------------------------------------------------------

suite("never embeds the placeholder <GENERATED_URL> unresolved", () => {
  // The header carries an instructional "<GENERATED_URL>" placeholder
  // explaining the URL's role — that one is intentional. The URL
  // itself is rendered as the concrete example on the next line. This
  // test guards against accidental expansion of the placeholder
  // elsewhere in the body (e.g. inside a YAML snippet).
  const p = buildAgentPrompt("litellm", URL, samples);
  const occurrences = p.split("<GENERATED_URL>").length - 1;
  // Exactly one: in the header. If a future edit accidentally leaves
  // a stray placeholder, this fails.
  check("exactly one <GENERATED_URL> placeholder", occurrences, 1);
});

suite("empty selection still renders a usable prompt", () => {
  // The API rejects empty model_ids, so this case never reaches
  // production. The builder must not crash on [] anyway — if a
  // future caller forgets the upstream check, the agent should still
  // get a coherent prompt that names the missing selection.
  const p = buildAgentPrompt("litellm", URL, []);
  checkContains("URL still embedded", p, URL);
  checkContains("selection section header still rendered", p, "## User Selection");
});

suite("unsupported factory id throws", () => {
  let thrown = false;
  let message = "";
  try {
    buildAgentPrompt("bogus" as never, URL, samples);
  } catch (e) {
    thrown = true;
    message = e instanceof Error ? e.message : String(e);
  }
  check("buildAgentPrompt threw", thrown, true);
  check(
    "error mentions the unsupported id",
    message.includes("bogus") || message.includes("unsupported"),
    true,
  );
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  console.error("Failures:\n  " + failedLabels.join("\n  "));
}
assert.equal(failed, 0, `${failed} test(s) failed`);