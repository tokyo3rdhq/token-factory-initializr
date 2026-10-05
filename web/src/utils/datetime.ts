/** Human-readable timestamp formatting for the manifest providers line.

The pipeline stores each provider's last successful KV write as an
ISO 8601 string under ``providers.{ds}.generated_at``. On the
Browse page we surface those timestamps next to the catalog count so
users can tell at a glance when each upstream feed was last refreshed.

Time zones:
* If the browser exposes ``Intl.DateTimeFormat().resolvedOptions().timeZone``
  we render in the user's local zone so a PST user sees PST.
* Otherwise we fall back to ``"UTC"`` so the format is unambiguous.

Locales:
* The current i18n locale (``en`` / ``zh``) is used so English users
  see "Oct 5, 2026, 1:24 AM" and Chinese users see "2026/10/5 1:24".

The formatter never throws — a malformed or missing timestamp degrades
to a placeholder string so a single bad provider row never takes the
whole providers line down.
*/

const MISSING_TIMESTAMP = "—";

/** Pick the time zone string for the user, falling back to "UTC". */
export function resolveTimeZone(): string {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (typeof tz === "string" && tz.length > 0) {
      return tz;
    }
  } catch {
    /* Intl not available (very old browser) — fall through. */
  }
  return "UTC";
}

/** Format an ISO 8601 timestamp in the user's locale + time zone. */
export function formatTimestamp(
  iso: string | null | undefined,
  locale: string,
  timeZone: string,
): string {
  if (!iso) return MISSING_TIMESTAMP;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return MISSING_TIMESTAMP;
  try {
    return new Intl.DateTimeFormat(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone,
    }).format(d);
  } catch {
    // Locale was rejected (e.g. malformed BCP-47) — drop to UTC + en-US.
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
      timeZoneName: "short",
    }).format(d);
  }
}

export interface ProviderTimestampEntry {
  /** Provider / data_source id as it appears in the manifest (e.g. "amd"). */
  provider: string;
  /** Display label (uppercase). */
  label: string;
  /** Format the timestamp for this provider, given the user's locale. */
  timestamp: string;
  /** Raw ISO string for tooltips / debugging. */
  raw: string | null;
}

/**
 * Build the per-provider timestamp entries for the manifest.
 *
 * Skips providers with no ``generated_at`` (publish never wrote them)
 * and sorts the result in the canonical data-source order so the
 * displayed line is stable across renders.
 */
export function formatProviderTimestamps(
  manifest: { providers?: Record<string, { generated_at?: string | null }> },
  locale: string,
  timeZone: string = resolveTimeZone(),
): ProviderTimestampEntry[] {
  const providers = manifest.providers || {};
  // Stable, human-familiar order — primary providers first, then the
  // cross-source enrichers. Anything not in this list falls to the end.
  const ORDER = ["nvidia", "amd", "huggingface", "openrouter", "models_dev"];
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const k of ORDER) {
    if (k in providers) {
      ordered.push(k);
      seen.add(k);
    }
  }
  for (const k of Object.keys(providers).sort()) {
    if (!seen.has(k)) {
      ordered.push(k);
    }
  }

  return ordered.map((ds) => {
    const raw = providers[ds]?.generated_at ?? null;
    return {
      provider: ds,
      label: ds.toUpperCase(),
      timestamp: formatTimestamp(raw, locale, timeZone),
      raw,
    };
  });
}
