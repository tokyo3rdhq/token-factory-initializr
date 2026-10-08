// Internal (cross-source) vs. consumer-facing (primary) data sources.
//
// "Internal" data sources do not surface their own model catalogs to
// the public API or the Browse UI. The data pipeline still fetches
// them, but only as observation inputs that flow into the normalize
// stage's cross-source enrichment of the primary providers
// (nvidia / amd / huggingface).
//
// Adding a new internal data source is one line; adding a new
// primary source means it shows up in /api/models default listings,
// /api/v1/models listings, and the Browse hero subhead.

export const INTERNAL_DATA_SOURCES: ReadonlySet<string> = new Set([
  "openrouter",  // cross-source enrichment only; provider = openrouter
  "models_dev",  // cross-source enrichment only; provider = models_dev
]);

export function isInternalDataSource(ds: string): boolean {
  return INTERNAL_DATA_SOURCES.has(ds);
}
