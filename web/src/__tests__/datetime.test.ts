// Tests for the human-readable timestamp helpers used on the Browse
// page subhead (per-provider last-updated pills).
//
// The pipeline stamps each ``providers.{ds}.generated_at`` as ISO 8601.
// The web UI renders those timestamps in the user's locale + time zone
// when available, falling back to a placeholder when the value is
// missing or malformed.

// The web module is TypeScript — these tests run in Node via
// node --experimental-strip-types against the built-in Intl.
// Modern Node (>=18) ships full Intl so this is a belt-and-braces
// guard.

import { test } from "node:test";
import assert from "node:assert/strict";

if (typeof Intl === "undefined") {
  // @ts-expect-error - intentional polyfill for the test runtime
  globalThis.Intl = {};
}

const { formatTimestamp, formatProviderTimestamps, resolveTimeZone } =
  await import("../utils/datetime.ts");

test("formatTimestamp renders in the user's locale + time zone", () => {
  // 2026-10-05T01:24:17Z — UTC. In America/Los_Angeles this is
  // 2026-10-04T18:24 PDT (UTC-7 in October DST).
  const iso = "2026-10-05T01:24:17.512752+00:00";
  const utc = formatTimestamp(iso, "en-US", "UTC");
  assert.match(utc, /Oct/);
  assert.match(utc, /2026/);
  assert.match(utc, /01:24/);

  const pst = formatTimestamp(iso, "en-US", "America/Los_Angeles");
  assert.match(pst, /Oct/);
  // Different hour than UTC — proves the time zone was applied.
  assert.notEqual(pst, utc);
});

test("formatTimestamp returns placeholder when iso is null / malformed", () => {
  assert.equal(formatTimestamp(null, "en-US", "UTC"), "—");
  assert.equal(formatTimestamp(undefined, "en-US", "UTC"), "—");
  assert.equal(formatTimestamp("not-a-date", "en-US", "UTC"), "—");
});

test("formatTimestamp never throws on a malformed locale", () => {
  // BCP-47 reject path — fall back to UTC + en-US.
  const out = formatTimestamp(
    "2026-10-05T01:24:17+00:00",
    "not_a_real_locale!@#",
    "UTC",
  );
  assert.match(out, /2026/);
});

test("formatProviderTimestamps emits canonical order then alphabetical", () => {
  const m = {
    providers: {
      models_dev: { generated_at: "2026-10-05T01:24:19+00:00" },
      nvidia: { generated_at: "2026-10-05T01:24:19+00:00" },
      amd: { generated_at: "2026-10-05T01:24:17+00:00" },
      huggingface: { generated_at: "2026-10-05T01:24:18+00:00" },
      // An unknown ds — should land at the end, alphabetically.
      some_future_ds: { generated_at: "2026-10-05T02:00:00+00:00" },
    },
  };
  const out = formatProviderTimestamps(m, "en-US", "UTC");
  assert.deepEqual(
    out.map((e: { provider: string }) => e.provider),
    ["nvidia", "amd", "huggingface", "models_dev", "some_future_ds"],
  );
});

test("formatProviderTimestamps keeps providers with null timestamp", () => {
  const m = {
    providers: {
      amd: { generated_at: "2026-10-05T01:24:17+00:00" },
      huggingface: { generated_at: null },
    },
  };
  const out = formatProviderTimestamps(m, "en-US", "UTC");
  // ``huggingface`` is still listed — its entry surfaces a
  // placeholder timestamp so users know the ds is tracked but
  // publish never wrote it (e.g. fetch failed mid-run).
  assert.equal(out.length, 2);
  assert.equal(out[1].provider, "huggingface");
  assert.equal(out[1].timestamp, "—");
});

test("formatProviderTimestamps returns empty list when manifest has no providers", () => {
  assert.deepEqual(formatProviderTimestamps({}, "en-US", "UTC"), []);
  assert.deepEqual(
    formatProviderTimestamps({ providers: {} }, "en-US", "UTC"),
    [],
  );
});

test("resolveTimeZone falls back to UTC when Intl is unavailable", () => {
  // Even if Intl is fully absent the helper should not throw.
  assert.equal(typeof resolveTimeZone(), "string");
  assert.ok(resolveTimeZone().length > 0);
});

test("formatProviderTimestamps carries count and status per provider", () => {
  // The Browse hero subhead now also displays each provider's
  // endpoint count next to its timestamp. The pipeline writes the
  // count + status into the manifest; the formatter must surface
  // them verbatim so the React layer can render a count badge.
  const manifest = {
    providers: {
      nvidia: {
        count: 38,
        status: "success",
        generated_at: "2026-10-08T05:33:12.613378+00:00",
      },
      amd: {
        count: 8,
        status: "success",
        generated_at: "2026-10-08T05:33:10.510128+00:00",
      },
      huggingface: {
        count: 2,
        status: "partial",
        generated_at: "2026-10-08T05:33:11.061372+00:00",
      },
      models_dev: {
        count: 447,
        status: "success",
        generated_at: "2026-10-08T05:33:12.047371+00:00",
      },
      openrouter: {
        count: 467,
        status: "success",
        generated_at: "2026-10-08T05:33:13.372949+00:00",
      },
    },
  };
  const entries = formatProviderTimestamps(manifest, "en-US", "UTC");
  // Canonical order: nvidia, amd, huggingface, openrouter, models_dev.
  assert.equal(entries[0].provider, "nvidia");
  assert.equal(entries[0].count, 38);
  assert.equal(entries[0].status, "success");
  assert.equal(entries[1].provider, "amd");
  assert.equal(entries[1].count, 8);
  assert.equal(entries[2].provider, "huggingface");
  assert.equal(entries[2].count, 2);
  assert.equal(entries[2].status, "partial");
  assert.equal(entries[4].provider, "models_dev");
  assert.equal(entries[4].count, 447);
});

test("formatProviderTimestamps tolerates missing count / status", () => {
  // Legacy manifests (pre-provenance-rewrite) may omit count and
  // status. The formatter must not crash; both fields default to
  // null so the React layer can hide the badge.
  const manifest = {
    providers: {
      amd: { generated_at: "2026-10-05T01:24:17Z" },
    },
  };
  const entries = formatProviderTimestamps(manifest, "en-US", "UTC");
  assert.equal(entries.length, 1);
  assert.equal(entries[0].count, null);
  assert.equal(entries[0].status, null);
});

test("formatProviderTimestamps rejects unknown status strings", () => {
  // Defence-in-depth: if the manifest ever carries an unexpected
  // status literal, the formatter must not pass it through to the
  // React layer (where it would silently bypass the colour cue).
  const manifest = {
    providers: {
      amd: {
        count: 5,
        status: "garbage" as unknown as "success",
        generated_at: "2026-10-05T01:24:17Z",
      },
    },
  };
  const entries = formatProviderTimestamps(manifest, "en-US", "UTC");
  assert.equal(entries[0].status, null);
  assert.equal(entries[0].count, 5);
});
