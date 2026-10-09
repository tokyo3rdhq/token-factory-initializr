import { useEffect, useMemo, useState } from "react";
import { Copy, ExternalLink } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Badge, Banner, Button, Checkbox, Container, EmptyState, Input, Section, Stack } from "@tokyo3rdhq/magi-design-system";

import { fmtContext, hasVision } from "../components/format";
import { useSelection } from "../components/SelectionContext";
import { fetchManifest, fetchModels, FIXTURES, shouldUseLocalFixtures } from "../kv";
import { matchesRequirement, type Manifest, type ModelEndpoint, type ModelRequirement } from "../types";
import { useI18n } from "../I18nProvider";
import { useSeo } from "../seo/useSeo";
import { formatProviderTimestamps, resolveTimeZone } from "../utils/datetime";
import { isInternalDataSource } from "../kv";

/**
 * Tag filter taxonomy for the Browse page.
 *
 * Each tag is a (id, predicate, color) triple. The predicate is a
 * pure function over a ModelEndpoint; the color is one of the
 * DS Badge variants (accent / success / warning / neutral).
 *
 * Tags are pure metadata — adding a new one is one new entry below.
 * No magic string lookups anywhere else.
 */
export type TagId =
  | "chat"
  | "vision"
  | "tools"
  | "reasoning"
  | "speech"
  | "structured_output"
  | "free"
  | "longCtx";

interface TagDef {
  id: TagId;
  /** i18n key suffix — the lookup is ts("browse.tags." + id + ".label"). */
  variant: "accent" | "success" | "warning" | "neutral";
}

export const TAGS: TagDef[] = [
  { id: "chat",              variant: "accent"  },
  { id: "vision",            variant: "accent"  },
  { id: "tools",             variant: "accent"  },
  { id: "reasoning",         variant: "accent"  },
  { id: "speech",            variant: "accent"  },
  { id: "structured_output", variant: "accent"  },
  { id: "free",              variant: "success" },
  { id: "longCtx",           variant: "warning" },
];

/** Pure predicate — given an endpoint and a tag id, return whether
 *  the endpoint has the tag. Centralized so the filter UI and the
 *  per-row badge rendering stay in sync (single source of truth). */
function hasTag(ep: ModelEndpoint, tag: TagId): boolean {
  switch (tag) {
    case "chat":
      return !!ep.capabilities?.chat;
    case "vision":
      return hasVision(ep);
    case "tools":
      return !!ep.capabilities?.tool_calling;
    case "reasoning":
      return !!ep.capabilities?.reasoning;
    case "speech": {
      if (ep.capabilities?.speech === true) return true;
      // Forward-compat: a provider whose adapter omits the speech
      // capability flag but exposes 'audio' in architecture.output
      // (e.g. an OpenAI TTS-style endpoint) should still surface
      // the speech tag.
      if (Array.isArray(ep.architecture?.output)) {
        return ep.architecture!.output.includes("audio");
      }
      return false;
    }
    case "structured_output":
      return !!ep.capabilities?.structured_output;
    case "free":
      return ep.free === true;
    case "longCtx":
      return (ep.context_length ?? 0) >= 128_000;
  }
}

/** Pure filter — keyword + active tag set. Returns the visible
 *  subset. The Browse page applies this BEFORE matching against
 *  the requirement so the requirement filter is applied on top of
 *  the user's free-text + tag choices. */
function applyFilters(
  models: ModelEndpoint[],
  query: string,
  activeTags: ReadonlySet<TagId>,
): ModelEndpoint[] {
  const q = query.trim().toLowerCase();
  return models.filter((m) => {
    if (activeTags.size > 0) {
      // AND — every selected tag must match.
      for (const tag of activeTags) {
        if (!hasTag(m, tag)) return false;
      }
    }
    if (q) {
      const hay =
        (m.name ?? "").toLowerCase() +
        " " + m.model_id.toLowerCase() +
        " " + m.provider.toLowerCase() +
        " " + m.data_source.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

/**
 * Browse — model selection page.
 *
 * Filter row (above the list):
 *   [keyword input] [tag toggles] [select-all visible] [reset]
 *
 * Lists split into Recommended (top N by context length) + Other
 * matching, same as before. The recommendation is by requirement
 * only; tag/keyword filters narrow the user's view BEFORE the
 * recommendation split is computed.
 */
export function BrowsePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const selection = useSelection();
  const { ts, dict, locale } = useI18n();
  // See docs/tfi_seo_optimization.md §5 — /browse has its own
  // discoverable metadata so it doesn't inherit the homepage copy.
  useSeo("/browse");

  const requirement: ModelRequirement | null =
    (location.state as { requirement?: ModelRequirement } | null)?.requirement ?? null;

  const [models, setModels] = useState<ModelEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Manifest fetched in parallel with the model list. Used to surface
  // each provider's last successful catalog fetch time under the
  // catalog-count subhead. Optional — older / failed fetches leave
  // this null and the timestamps line stays hidden.
  const [manifest, setManifest] = useState<Manifest | null>(null);

  /** Free-text keyword — matches name, model_id, provider, data_source. */
  const [query, setQuery] = useState("");

  /** Active tag filter set. Empty = no tag filter (show everything
   *  that matches the other criteria). */
  const [activeTags, setActiveTags] = useState<ReadonlySet<TagId>>(
    () => new Set(),
  );

  const toggleTag = (tag: TagId) => {
    setActiveTags((prev) => {
      const next = new Set(prev);
      if (next.has(tag)) next.delete(tag);
      else next.add(tag);
      return next;
    });
  };

  useEffect(() => {
    if (!shouldUseLocalFixtures(import.meta.env.VITE_USE_LOCAL_FIXTURES)) {
      fetchModels()
        .then((snaps) => {
          setModels(snaps.flatMap((s) => s.models));
          setLoading(false);
        })
        .catch((e) => {
          setError(e instanceof Error ? e.message : String(e));
          setLoading(false);
        });
      // Fire-and-forget: the manifest powers a non-essential
      // subhead line so we don't block catalog rendering on it.
      fetchManifest()
        .then(setManifest)
        .catch(() => setManifest(null));
    } else {
      setModels(FIXTURES.models.flatMap((s) => s.models));
      // Use the bundled fixture as the manifest source so local dev
      // also gets the per-provider timestamp pills (with the
      // fixture's static timestamp).
      setManifest(FIXTURES.manifest as Manifest);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!loading && models.length === 0 && !error) {
      navigate("/", { replace: true });
    }
  }, [loading, models.length, error, navigate]);

  // Filter (query + tags) applies first, THEN the requirement.
  // The result is a single ordered list — sorted by context length
  // descending so the most capable models surface at the top of the
  // user's view. Per doc §26 ("TFI is not yet an AI model
  // recommender"), we don't pre-select a subset: every model that
  // passes the filters is presented with equal weight, and the user
  // opts in to as many as they want via the filter row's Select-all
  // button.
  const filtered = useMemo(
    () => applyFilters(models, query, activeTags),
    [models, query, activeTags],
  );
  const matching = useMemo(
    () => filtered.filter((m) => matchesRequirement(m, requirement ?? {})),
    [filtered, requirement],
  );

  const sorted = useMemo(() => {
    return [...matching].sort((a, b) => {
      const ctxA = a.context_length ?? 0;
      const ctxB = b.context_length ?? 0;
      return ctxB - ctxA;
    });
  }, [matching]);

  // Single visible list — no Recommended / Other matching split.
  const visible = sorted;

  const filtersActive = query.trim().length > 0 || activeTags.size > 0;
  const resetFilters = () => {
    setQuery("");
    setActiveTags(new Set());
  };

  const selectAllVisible = () => {
    if (visible.length === 0) return;
    // Idempotent — only adds models that aren't already selected.
    // selection.toggle is a no-op on already-selected items.
    visible.forEach((m) => {
      if (!selection.isSelected(m)) selection.toggle(m);
    });
  };

  // Per-provider last-updated timestamps for the subhead line. Built
  // from the manifest fetched in parallel with the catalog so the
  // count line + timestamp pills update together when the pipeline
  // re-runs. ``null`` (no manifest yet / fetch failed) → line hidden.
  //
  // Internal cross-source data sources (openrouter, models_dev) are
  // filtered out: they're not consumer-facing model catalogs, just
  // enrichment inputs that flow into the normalize stage for the
  // primary providers (nvidia / amd / huggingface). Surfacing them
  // on the Browse page would imply they offer end-user models,
  // which they don't. The data pipeline still fetches them; they're
  // just hidden from this view.
  const providerTimestamps = useMemo(() => {
    if (!manifest) return [];
    const all = formatProviderTimestamps(manifest, locale, resolveTimeZone());
    return all.filter((entry) => !isInternalDataSource(entry.provider));
  }, [manifest, locale]);

  return (
    <Section spacing="lg">
      <Container>
        {/* Hero — left-aligned, ~720px content block. */}
        <Stack gap="3" className="tfi-page-hero">
          <span className="magi-eyebrow">{ts("browse.eyebrow")}</span>
          <h1 className="magi-h1">
            {requirement ? ts("browse.headingWithReq") : ts("browse.headingNoReq")}
          </h1>
          <p className="magi-body-lg tfi-page-hero-subhead">
            {filtersActive
              ? dict.browse.countFilteredTemplate(matching.length, filtered.length)
              : requirement
                ? dict.browse.countWithReqTemplate(matching.length)
                : dict.browse.countNoReqTemplate(matching.length)}
          </p>
          {providerTimestamps.length > 0 && (
            <p
              className="magi-caption tfi-page-hero-timestamps"
              title={ts("browse.providerTimestampsTitle")}
              data-testid="provider-timestamps"
            >
              {providerTimestamps.map((entry, idx) => (
                <span key={entry.provider} className="tfi-provider-timestamp">
                  <strong className="tfi-provider-timestamp-label">
                    {entry.label}
                  </strong>
                  {entry.count !== null && (
                    <span
                      className={`tfi-provider-timestamp-count tfi-provider-timestamp-count--${entry.status ?? "unknown"}`}
                      title={dict.browse.providerCountTitle(
                        entry.count,
                        entry.label,
                      )}
                    >
                      {entry.count.toLocaleString(locale)}
                    </span>
                  )}
                  <span className="tfi-provider-timestamp-value">
                    {entry.timestamp}
                  </span>
                  {idx < providerTimestamps.length - 1
                    ? dict.browse.providerTimestampsSeparator
                    : null}
                </span>
              ))}
            </p>
          )}
        </Stack>

        {/* Filter row — keyword input, tag toggles, select-all + reset. */}
        <div className="tfi-filter-row">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={ts("browse.filters.searchPlaceholder")}
            aria-label={ts("browse.filters.searchPlaceholder")}
            className="tfi-filter-search"
          />
          <div className="tfi-tag-row">
            {TAGS.map((tag) => {
              const active = activeTags.has(tag.id);
              return (
                <button
                  key={tag.id}
                  type="button"
                  className={`tfi-tag-chip tfi-tag-chip-${tag.id}${active ? " active" : ""}`}
                  aria-pressed={active}
                  onClick={() => toggleTag(tag.id)}
                  title={ts(`browse.tags.${tag.id}.description` as never)}
                >
                  <span className="tfi-tag-chip-dot" aria-hidden="true" />
                  {ts(`browse.tags.${tag.id}.label` as never)}
                </button>
              );
            })}
          </div>
          <div className="tfi-filter-actions">
            <Button
              size="sm"
              variant="primary"
              onClick={selectAllVisible}
              disabled={visible.length === 0}
            >
              {dict.browse.selectAllVisibleTemplate(visible.length)}
            </Button>
            {selection.selected.length > 0 && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => selection.clear()}
              >
                {dict.browse.clearAllTemplate(selection.selected.length)}
              </Button>
            )}
            {filtersActive && (
              <Button size="sm" variant="ghost" onClick={resetFilters}>
                {ts("browse.filters.reset")}
              </Button>
            )}
          </div>
        </div>

        {error && (
          <Banner
            variant="error"
            role="alert"
            className="tfi-banner-spacer"
          >
            {ts("browse.fallbackPrefix")}
            {error}.{" "}
            {shouldUseLocalFixtures(import.meta.env.VITE_USE_LOCAL_FIXTURES)
              ? ts("browse.fallbackFixture")
              : ts("browse.fallbackHelp")}
          </Banner>
        )}

        {!requirement && (
          <Banner variant="info" className="tfi-banner-spacer">
            {ts("browse.noReqBannerBefore")}
            <Link to="/">{ts("nav.start")}</Link>
            {ts("browse.noReqBannerAfter")}
          </Banner>
        )}

        {loading ? (
          <EmptyState>
            <span className="tfi-spinner" /> {ts("browse.loading")}
          </EmptyState>
        ) : matching.length === 0 ? (
          <EmptyState>
            {filtersActive
              ? ts("browse.emptyFiltered")
              : ts("browse.emptyBefore")}
            <Link to="/">{ts("browse.emptyAfter")}</Link>.
          </EmptyState>
        ) : (
          <Stack gap="10">
            <BrowseSection
              heading={ts("browse.sectionAll")}
              hint={dict.browse.hintAllTemplate(visible.length)}
            >
              <ModelList>
                {visible.length === 0 ? (
                  <div className="tfi-empty-muted">
                    Nothing in this bucket.
                  </div>
                ) : (
                  visible.map((m) => (
                    <ModelRow
                      key={`${m.data_source}::${m.provider}::${m.model_id}`}
                      endpoint={m}
                      selected={selection.isSelected(m)}
                      onToggle={selection.toggle}
                    />
                  ))
                )}
              </ModelList>
            </BrowseSection>

            <Stack
              direction="row"
              align="center"
              gap="3"
              className="tfi-bottom-row"
            >
              <span className="magi-caption tfi-caption-secondary">
                {dict.browse.selectedCountTemplate(selection.selected.length)}
              </span>
              <Button variant="primary" onClick={() => navigate("/generate")}>
                {ts("nav.generate")} →
              </Button>
            </Stack>
          </Stack>
        )}
      </Container>
    </Section>
  );
}

function BrowseSection({
  heading,
  hint,
  muted,
  children,
}: {
  heading: string;
  hint?: string;
  muted?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Stack gap="4">
      <div className="tfi-section-header">
        <h2 className={`magi-eyebrow ${muted ? "tfi-section-heading-muted" : "tfi-section-heading-accent"}`}>
          {heading}
        </h2>
        {hint && (
          <span className="magi-caption tfi-caption-secondary">{hint}</span>
        )}
      </div>
      {children}
    </Stack>
  );
}

function ModelList({ children }: { children: React.ReactNode }) {
  return <div className="tfi-model-list">{children}</div>;
}

function ModelRow({
  endpoint,
  selected,
  onToggle,
}: {
  endpoint: ModelEndpoint;
  selected: boolean;
  onToggle: (ep: ModelEndpoint) => void;
}) {
  const { dict } = useI18n();
  const ctx = fmtContext(endpoint.context_length);
  const hasTools = !!endpoint.capabilities?.tool_calling;
  const hasVisionCap = hasVision(endpoint);
  const [copied, setCopied] = useState<"copy" | null>(null);
  const onCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied("copy");
      window.setTimeout(() => setCopied(null), 1500);
    } catch {
      // Clipboard API may be blocked; do nothing.
    }
  };
  // Row badges mirror the Browse tag-filter chips for the capabilities
  // a user is most likely to scan for in the row. ``chat`` is the most
  // common capability so it's surfaced as an ``accent`` badge whenever
  // the canonical normalize shape flags it. The full set lives in
  // ``ep.capabilities``; this is a curation, not the whole set.
  const hasChat = !!endpoint.capabilities?.chat;
  const hasSpeech = !!endpoint.capabilities?.speech;
  const hasEmbedding = !!endpoint.capabilities?.embedding;
  const hasReasoningBadge = !!endpoint.capabilities?.reasoning;
  const hasStructuredOutputBadge = !!endpoint.capabilities?.structured_output;
  return (
    <label className={`tfi-model-row${selected ? " selected" : ""}`}>
      <Checkbox
        checked={selected}
        onChange={() => onToggle(endpoint)}
        aria-label={`Select ${endpoint.model_id}`}
      />
      <Badge variant="neutral">{endpoint.provider}</Badge>
      <span>
        <span className="tfi-model-name-row">
          <span className="tfi-model-name">{endpoint.model_id}</span>
          {endpoint.source_url && (
            <a
              className="tfi-model-source-link"
              href={endpoint.source_url}
              target="_blank"
              rel="noopener noreferrer"
              // Stop the <label> wrapper from intercepting the click
              // as a model-selection toggle. The link's own click
              // handler is the browser's default (open in new tab).
              onClick={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
              // Accessible name per docs/tfi_model_source_url.md §7.
              // Magnifying the model_id makes the screen reader
              // announce "View source for <model_id>" instead of
              // reading the URL aloud.
              aria-label={dict.browse.viewSourceLabel(endpoint.model_id)}
              title={dict.browse.viewSourceLabel(endpoint.model_id)}
            >
              <ExternalLink size={12} aria-hidden="true" />
            </a>
          )}
          <button
            type="button"
            className="tfi-model-source-link tfi-model-copy-btn"
            onClick={(e) => {
              e.stopPropagation();
              onCopy(endpoint.model_id);
            }}
            onMouseDown={(e) => e.stopPropagation()}
            aria-label={copied ? dict.browse.copyCopied : dict.browse.copy}
            title={copied ? dict.browse.copyCopied : dict.browse.copy}
          >
            <Copy size={12} aria-hidden="true" />
          </button>
        </span>
        {endpoint.description && (
          <div className="tfi-model-desc">{endpoint.description}</div>
        )}
      </span>
      <span className="tfi-model-meta">
        {ctx && <Badge variant="accent">{ctx}</Badge>}
        {hasChat && <Badge variant="accent">chat</Badge>}
        {hasTools && <Badge variant="accent">tools</Badge>}
        {hasVisionCap && <Badge variant="accent">vision</Badge>}
        {hasSpeech && <Badge variant="accent">speech</Badge>}
        {hasReasoningBadge && <Badge variant="accent">reasoning</Badge>}
        {hasStructuredOutputBadge && <Badge variant="accent">json</Badge>}
        {hasEmbedding && <Badge variant="warning">embed</Badge>}
        {endpoint.free && <Badge variant="success" dot>free</Badge>}
      </span>
    </label>
  );
}

// Re-export pure helpers so unit tests can exercise the filter logic
// without rendering React. See web/src/__tests__/browse-filters.test.ts.
export const __browseFilters = { hasTag, applyFilters };
