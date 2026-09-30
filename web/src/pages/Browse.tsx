import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Badge, Banner, Button, Checkbox, Container, EmptyState, Section, Stack } from "@tokyo3rdhq/magi-design-system";

import { fmtContext, hasVision } from "../components/format";
import { useSelection } from "../components/SelectionContext";
import { fetchModels, FIXTURES, shouldUseLocalFixtures } from "../kv";
import { matchesRequirement, type ModelEndpoint, type ModelRequirement } from "../types";

/**
 * Browse — model selection page.
 *
 * Uses the developer-infrastructure row pattern (MODEL / PROVIDER /
 * CONTEXT · tools · vision). Layout primitives come from the design
 * system; colors come from CSS custom properties via ProductTheme.
 */
export function BrowsePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const selection = useSelection();

  const requirement: ModelRequirement | null =
    (location.state as { requirement?: ModelRequirement } | null)?.requirement ?? null;

  const [models, setModels] = useState<ModelEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const snap = await fetchModels();
        if (cancelled) return;
        setModels(snap.flatMap((s) => s.models));
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (loading || models.length > 0) return;
    if (!shouldUseLocalFixtures(import.meta.env.VITE_USE_LOCAL_FIXTURES)) return;
    setModels(FIXTURES.models.flatMap((s) => s.models));
  }, [loading, models.length]);

  const target = requirement?.endpointCount ?? 3;
  const matching = useMemo(
    () => models.filter((m) => matchesRequirement(m, requirement ?? {})),
    [models, requirement],
  );

  const sorted = useMemo(() => {
    return [...matching].sort((a, b) => {
      if (a.free !== b.free) return a.free ? -1 : 1;
      const aCtx = a.context_length ?? 0;
      const bCtx = b.context_length ?? 0;
      return bCtx - aCtx;
    });
  }, [matching]);

  const recommended = sorted.slice(0, target);
  const others = sorted.slice(target);

  return (
    <Section spacing="lg">
      <Container>
        <Stack
          gap="3"
          align="center"
          style={{ marginBottom: "var(--magi-space-10)", textAlign: "center", margin: "0 auto var(--magi-space-10)" }}
        >
          <span className="magi-eyebrow">Browse</span>
          <h1 className="magi-h1" style={{ textAlign: "center" }}>
            {requirement ? "Recommended models" : "All endpoints"}
          </h1>
          <p className="magi-body-lg" style={{ textAlign: "center" }}>
            {matching.length} model{matching.length === 1 ? "" : "s"} match
            {requirement ? " your requirements." : " the catalog."}
          </p>
        </Stack>

        {error && (
          <Banner variant="error" style={{ marginBottom: "var(--magi-space-6)" }}>
            Could not load KV catalog: {error}.{" "}
            {shouldUseLocalFixtures(import.meta.env.VITE_USE_LOCAL_FIXTURES)
              ? "Falling back to bundled fixtures."
              : "Set TFI_USE_LOCAL_FIXTURES=1 to browse offline."}
          </Banner>
        )}

        {!requirement && (
          <Banner variant="info" style={{ marginBottom: "var(--magi-space-6)" }}>
            No requirements set.{" "}
            <Link to="/">Go back</Link> to specify what you're building —
            we'll pick the right models for you.
          </Banner>
        )}

        {loading ? (
          <EmptyState>
            <span className="tfi-spinner" /> Loading catalog…
          </EmptyState>
        ) : matching.length === 0 ? (
          <EmptyState>
            No models match. Try loosening the constraints —{" "}
            <Link to="/">edit requirements</Link>.
          </EmptyState>
        ) : (
          <Stack gap="10">
            <BrowseSection heading="Recommended" hint={`Top ${recommended.length} matching`}>
              <ModelList>
                {recommended.length === 0 ? (
                  <div
                    className="magi-body-sm"
                    style={{
                      padding: "var(--magi-space-6)",
                      textAlign: "center",
                      color: "var(--magi-text-tertiary)",
                    }}
                  >
                    Nothing in this bucket.
                  </div>
                ) : (
                  recommended.map((m) => (
                    <ModelRow
                      key={`${m.provider}::${m.model_id}`}
                      endpoint={m}
                      selected={selection.isSelected(m)}
                      onToggle={selection.toggle}
                    />
                  ))
                )}
              </ModelList>
            </BrowseSection>

            {others.length > 0 && (
              <BrowseSection heading="Other matching" hint="match — pick if useful" muted>
                <ModelList>
                  {others.map((m) => (
                    <ModelRow
                      key={`${m.provider}::${m.model_id}`}
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
              style={{
                marginTop: "var(--magi-space-10)",
                paddingTop: "var(--magi-space-7)",
                borderTop: "1px solid var(--magi-border)",
              }}
            >
              <Link to="/" className="tfi-nav-link" style={{ paddingLeft: 0 }}>
                ← Edit requirements
              </Link>
              <div style={{ flex: 1 }} />
              <Button
                variant="primary"
                onClick={() => navigate("/generate")}
                disabled={selection.selected.length === 0}
              >
                Continue to generate ({selection.selected.length})
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
    <section>
      <Stack
        direction="row"
        align="center"
        style={{ justifyContent: "space-between", marginBottom: "var(--magi-space-4)" }}
      >
        <h2 className="magi-eyebrow" style={{ margin: 0 }}>
          {heading}
        </h2>
        {hint && (
          <span className="magi-caption">
            {hint}
          </span>
        )}
      </Stack>
      <div style={{ opacity: muted ? 0.7 : 1 }}>{children}</div>
    </section>
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
