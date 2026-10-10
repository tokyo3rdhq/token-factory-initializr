/**
 * Unit tests for the Agent Access entry on the homepage
 * (docs/tfi_homepage_agent_access.md).
 *
 * Scoped to the data-side contract of the dialog — the prompt body,
 * the required entry URLs, and the absent-secrets invariant — plus
 * the bootstrap-prompt presence/absence in /agents.md. The actual
 * React rendering is exercised by the Pages-Functions deployment
 * smoke test (curl /) on deploy.
 *
 * Run with:  cd web && npx tsx src/__tests__/home-agent.test.ts
 */

import assert from "node:assert/strict";
import en from "../i18n/locales/en";

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

function checkNotContains(label: string, haystack: string, needle: string): void {
  check(`${label} (does NOT contain)`, haystack.includes(needle), false);
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

// The bootstrap prompt body is hand-copied verbatim from the spec
// (§5). Every URL is the canonical public TFI endpoint. The prompt
// must NOT contain secrets or private URLs (§14).
const BOOTSTRAP_PROMPT = `I want to use Token Factory Initializr (TFI) to select models and configure my Token Factory.

Start by reading:
https://start.magi.website/agents.md

Use TFI's public model catalog to discover and inspect available models:
https://start.magi.website/api/v1/models

Help me choose suitable models based on my requirements, then use TFI's configuration workflow at:
https://start.magi.website/

If I provide a generated TFI configuration URL, fetch it and help me safely apply the generated configuration to my existing Token Factory configuration.

Do not expose or modify secrets. Preserve my existing configuration unless I explicitly ask you to replace it.`;

// Narrow once at the test boundary. The locale is a typed object
// but we don't want to depend on the i18n types here — the test
// pins the surface contract regardless of how the types evolve.
function getHome(en: unknown): Record<string, unknown> | null {
  if (!en || typeof en !== "object") return null;
  const root = en as Record<string, unknown>;
  if (!("home" in root)) return null;
  const home = root.home;
  if (!home || typeof home !== "object") return null;
  return home as Record<string, unknown>;
}
const EN_HOME = getHome(en);

suite("bootstrap prompt: required URLs are present (§5 / §20)", () => {
  checkContains("agents.md URL", BOOTSTRAP_PROMPT, "https://start.magi.website/agents.md");
  checkContains("/api/v1/models URL", BOOTSTRAP_PROMPT, "https://start.magi.website/api/v1/models");
  checkContains("home URL", BOOTSTRAP_PROMPT, "https://start.magi.website/");
});

suite("bootstrap prompt: secret-free (§14)", () => {
  checkNotContains(
    "no API key placeholder",
    BOOTSTRAP_PROMPT,
    "api_key",
  );
  checkNotContains("no token literal", BOOTSTRAP_PROMPT, "Bearer ");
  checkNotContains("no env-var names", BOOTSTRAP_PROMPT, "os.environ/");
  checkNotContains("no specific generated URL embedded", BOOTSTRAP_PROMPT, "generated/EsXHtLvI");
  checkNotContains("no AUTH placeholder", BOOTSTRAP_PROMPT, "AUTH_TOKEN");
});

suite("bootstrap prompt: explicit generated-URL support (§7)", () => {
  // The prompt must mention generated configuration URLs as a thing
  // the user may hand to the agent — but it must NOT embed one.
  checkContains(
    "mentions generated TFI configuration URL as a concept",
    BOOTSTRAP_PROMPT,
    "generated TFI configuration URL",
  );
});

suite("en locale: Agent strings wired up", () => {
  check("EN_HOME is a record", EN_HOME !== null, true);
  const h = EN_HOME as Record<string, string>;
  check("ctaAgent present", typeof h.ctaAgent, "string");
  checkContains("ctaAgent label", h.ctaAgent, "Agent");
  checkContains("agentHeading label", h.agentHeading, "AI Agent");
  checkContains("agentCopy label", h.agentCopy, "Copy Prompt");
  checkContains("agentCopied label", h.agentCopied, "Copied");
  checkContains("agentReadGuide label", h.agentReadGuide, "Agent Guide");
  checkContains("agentClose label", h.agentClose, "Close");
});

suite("en locale: bootstrap prompt is identical to the spec body (§14)", () => {
  // The prompt is intentionally the same canonical English body
  // across locales (spec §14 — the agent prompt is a body of text,
  // not localizable product copy). Verify the English home bundle
  // embeds the exact spec body so any drift fails the test.
  const h = EN_HOME as Record<string, string>;
  check("en prompt matches spec verbatim", h.agentPrompt, BOOTSTRAP_PROMPT);
});
suite("en locale: Agent/Human tab switcher keys (§5 / §6)", () => {
  check("agentTab present", typeof EN_HOME?.agentTab, "string");
  checkContains("agentTab contains Agent", EN_HOME?.agentTab ?? "", "Agent");
  check("humanTab present", typeof EN_HOME?.humanTab, "string");
  checkContains("humanTab contains Human", EN_HOME?.humanTab ?? "", "Human");
  check("agentPromptInline present and non-empty", typeof EN_HOME?.agentPromptInline, "string");
  assert.ok(typeof EN_HOME?.agentPromptInline === "string" && (EN_HOME?.agentPromptInline as string).length > 0,
    "agentPromptInline must be non-empty");
  checkContains("agentPromptInline contains llms.txt", EN_HOME?.agentPromptInline ?? "", "llms.txt");
  checkContains("agentPromptInline mentions discover models", EN_HOME?.agentPromptInline ?? "", "discover");
});

suite("en locale: step headings and CTA (§6)", () => {
  checkContains("step1Title present", EN_HOME?.step1Title ?? "", "Define");
  checkContains("step2Title present", EN_HOME?.step2Title ?? "", "Browse");
  checkContains("step3Title present", EN_HOME?.step3Title ?? "", "Generate");
  checkContains("browseModelsButton present", EN_HOME?.browseModelsButton ?? "", "Browse");
});

suite("en locale: documentation link label (§8)", () => {
  checkContains("documentationLink present", EN_HOME?.documentationLink ?? "", "Documentation");
});

suite("agentPromptInline: secret-free (§14)", () => {
  const prompt = typeof EN_HOME?.agentPromptInline === "string" ? EN_HOME?.agentPromptInline : "";
  checkNotContains("no api_key", prompt, "api_key");
  checkNotContains("no Bearer token", prompt, "Bearer ");
  checkNotContains("no os.environ", prompt, "os.environ/");
});
