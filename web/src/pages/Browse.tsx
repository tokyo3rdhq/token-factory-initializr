import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Badge, Banner, Button, Checkbox, Container, EmptyState, Section, Stack } from "@tokyo3rdhq/magi-design-system";

import { fmtContext, hasVision } from "../components/format";
import { useSelection } from "../components/SelectionContext";
import { fetchModels, FIXTURES, shouldUseLocalFixtures } from "../kv";
import { matchesRequirement, type ModelEndpoint, type ModelRequirement } from "../types";
import { useI18n } from "../I18nProvider";

/**
 * Browse — model selection page.
 *
 * Uses the developer-infrastructure row pattern (MODEL / PROVIDER /
 * CONTEXT · tools · vision). Layout primitives come from the design
 * system; colors come from CSS custom properties via ProductTheme.
 * Strings are routed through the i18n provider.
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

  const target = requirement?.endpointCount ?? 3;
  const matching = useMemo(
    () => models.filter((m) => matchesRequirement(m, requirement ?? {})),
    [models, requirement],
  );

  const sorted = useMemo(() => {
    return [...matching].sort((a, b) => {
      const ctxA = a.context_length ?? 0;
      const ctxB = b.context_length ?? 0;
      return ctxB - ctxA;
    });
  }, [matching]);

  const recommended = sorted.slice(0, target);
  const others = sorted.slice(target);

  return (
    <Section spacing="lg">
      <Container>
        {/* Hero — left-aligned, ~720px content block to match magi-portal's
         * per-page hero rhythm (was centered; reverting). */}
<Stack gap="3" className="tfi-page-hero">
          <span className="magi-eyebrow">{ts("browse.eyebrow")}</span>
          <h1 className="magi-h1">
            {requirement ? ts("browse.headingWithReq") : ts("browse.headingNoReq")}
          </h1>
          <p className="magi-body-lg tfi-page-hero-subhead">
            {requirement
              ? dict.browse.countWithReqTemplate(matching.length)
              : dict.browse.countNoReqTemplate(matching.length)}
          </p>
        </Stack>

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
            {ts("browse.emptyBefore")}
            <Link to="/">{ts("browse.emptyAfter")}</Link>.
          </EmptyState>
        ) : (
          <Stack gap="10">
            <BrowseSection
              heading={ts("browse.sectionRecommended")}
              hint={dict.browse.hintRecommendedTemplate(recommended.length)}
            >
              <ModelList>
                {recommended.length === 0 ? (
                  <div className="tfi-empty-muted">
                    Nothing in this bucket.
                  </div>
                ) : (
                  recommended.map((m) => (
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

            {others.length > 0 && (
              <BrowseSection heading={ts("browse.sectionOther")} hint={ts("browse.hintOther")} muted>
                <ModelList>
                  {others.map((m) => (
                    <ModelRow
                      key={`${m.data_source}::${m.provider}::${m.model_id}`}
                      endpoint={m}
                      selected={selection.isSelected(m)}
                      onToggle={selection.toggle}
                    />
                  ))}
                </ModelList>
              </BrowseSection>
            )}

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
      </span>
      <span className="tfi-model-meta">
        {ctx && <Badge variant="neutral">{ctx}</Badge>}
        {hasTools && <Badge variant="accent">tools</Badge>}
        {hasVisionCap && <Badge variant="accent">vision</Badge>}
        {endpoint.free && <Badge variant="success" dot>free</Badge>}
      </span>
    </label>
  );
}