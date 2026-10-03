import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Badge, Banner, Button, Checkbox, Container, EmptyState, Input, Section, Stack } from "@tokyo3rdhq/magi-design-system";

import { fmtContext, hasVision } from "../components/format";
import { useSelection } from "../components/SelectionContext";
import { fetchModels, FIXTURES, shouldUseLocalFixtures } from "../kv";
import { matchesRequirement, type ModelEndpoint, type ModelRequirement } from "../types";
import { useI18n } from "../I18nProvider";

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
export type TagId = "chat" | "vision" | "tools" | "free" | "longCtx";

interface TagDef {
  id: TagId;
  /** i18n key suffix — the lookup is ts("browse.tags." + id + ".label"). */
  variant: "accent" | "success" | "warning" | "neutral";
}

export const TAGS: TagDef[] = [
  { id: "chat",    variant: "accent"  },
  { id: "vision",  variant: "accent"  },
  { id: "tools",   variant: "accent"  },
  { id: "free",    variant: "success" },
  { id: "longCtx", variant: "warning" },
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
  const { ts, dict } = useI18n();

  const requirement: ModelRequirement | null =
    (location.state as { requirement?: ModelRequirement } | null)?.requirement ?? null;

  const [models, setModels] = useState<ModelEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    } else {
      setModels(FIXTURES.models.flatMap((s) => s.models));
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
  const ctx = fmtContext(endpoint.context_length);
  const hasTools = !!endpoint.capabilities?.tool_calling;
  const hasVisionCap = hasVision(endpoint);
  // Row badges mirror the Browse tag-filter chips for the capabilities
  // a user is most likely to scan for in the row. ``chat`` is the most
  // common capability so it's surfaced as an ``accent`` badge whenever
  // the canonical normalize shape flags it. The full set lives in
  // ``ep.capabilities``; this is a curation, not the whole set.
  const hasChat = !!endpoint.capabilities?.chat;
  const hasSpeech = !!endpoint.capabilities?.speech;
  const hasEmbedding = !!endpoint.capabilities?.embedding;
  return (
    <label className={`tfi-model-row${selected ? " selected" : ""}`}>
      <Checkbox
        checked={selected}
        onChange={() => onToggle(endpoint)}
        aria-label={`Select ${endpoint.model_id}`}
      />
      <Badge variant="neutral">{endpoint.provider}</Badge>
      <span>
        <span className="tfi-model-name">{endpoint.name || endpoint.model_id}</span>
        <div className="tfi-model-id">{endpoint.model_id}</div>
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
        {hasEmbedding && <Badge variant="warning">embed</Badge>}
        {endpoint.free && <Badge variant="success" dot>free</Badge>}
      </span>
    </label>
  );
}

// Re-export pure helpers so unit tests can exercise the filter logic
// without rendering React. See web/src/__tests__/browse-filters.test.ts.
export const __browseFilters = { hasTag, applyFilters };
