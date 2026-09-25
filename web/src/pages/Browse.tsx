import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { fmtContext, hasVision, providerClass } from "../components/format";
import { useSelection } from "../components/SelectionContext";
import {
  fetchModels,
  FIXTURES,
  shouldUseLocalFixtures,
} from "../kv";
import {
  matchesRequirement,
  type ModelEndpoint,
  type ModelRequirement,
} from "../types";

/**
 * Browse page — split into "Recommended Models" (top N matching the
 * requirement) and "Other matching models" (the rest that match).
 *
 * The user picks models by toggling checkboxes; the count next to
 * "Generate" reflects the live selection. The requirement comes in
 * via router state (set by the Home form). If no requirement is
 * provided (e.g. user hit the URL directly), all endpoints are
 * considered matches.
 */
export function BrowsePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const selection = useSelection();

  const requirement: ModelRequirement | null =
    (location.state as { requirement?: ModelRequirement } | null)?.requirement ??
    null;

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

  // Local-fixture fallback when KV is empty (TFI_USE_LOCAL_FIXTURES=1).
  useEffect(() => {
    if (loading || models.length > 0) return;
    if (!shouldUseLocalFixtures(import.meta.env.VITE_USE_LOCAL_FIXTURES)) return;
    setModels(FIXTURES.models.flatMap((s) => s.models));
  }, [loading, models.length]);

  // Split into Recommended (top N matching) and Other (rest matching).
  const target = requirement?.endpointCount ?? 3;
  const matching = useMemo(() => {
    return models.filter((m) => matchesRequirement(m, requirement ?? {}));
  }, [models, requirement]);

  // Sort: free first, then by context length desc.
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
    <div className="layout-stack">
      <header>
        <h1 style={{ margin: "0 0 4px 0", fontSize: 22 }}>
          {requirement ? "Recommended Models" : "Browse"}
        </h1>
        <p className="muted" style={{ margin: 0 }}>
          {matching.length} model{matching.length === 1 ? "" : "s"} match your
          requirements.{" "}
          <Link to="/generate" className="muted">
            {selection.selected.length > 0
              ? `→ ${selection.selected.length} selected`
              : "select models →"}
          </Link>
        </p>
      </header>

      {error && (
        <div className="banner error">
          Could not load KV catalog: {error}.{" "}
          {shouldUseLocalFixtures(import.meta.env.VITE_USE_LOCAL_FIXTURES)
            ? "Falling back to bundled fixtures."
            : "Set TFI_USE_LOCAL_FIXTURES=1 to browse offline."}
        </div>
      )}

      {!requirement && (
        <div className="banner">
          No requirements set. <Link to="/">Go back</Link> to specify what
          you're building — we'll pick the right models for you.
        </div>
      )}

      {loading ? (
        <div className="empty">
          <span className="spinner" /> Loading…
        </div>
      ) : matching.length === 0 ? (
        <div className="empty">
          No models match. Try loosening the constraints —{" "}
          <Link to="/">edit requirements</Link>.
        </div>
      ) : (
        <>
          <Section
            title="Recommended Models"
            empty={recommended.length === 0}
          >
            {recommended.map((m) => (
              <PickRow
                key={`${m.provider}::${m.model_id}`}
                endpoint={m}
                selected={selection.isSelected(m)}
                onToggle={selection.toggle}
              />
            ))}
          </Section>

          {others.length > 0 && (
            <Section title="Other matching models" muted>
              {others.map((m) => (
                <PickRow
                  key={`${m.provider}::${m.model_id}`}
                  endpoint={m}
                  selected={selection.isSelected(m)}
                  onToggle={selection.toggle}
                />
              ))}
            </Section>
          )}

          <div style={{ display: "flex", gap: 8 }}>
            <Link to="/" className="btn">
              ← Edit requirements
            </Link>
            <button
              className="btn btn-primary"
              onClick={() => navigate("/generate")}
              disabled={selection.selected.length === 0}
            >
              Generate ({selection.selected.length})
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function Section({
  title,
  children,
  empty,
  muted,
}: {
  title: string;
  children: React.ReactNode;
  empty?: boolean;
  muted?: boolean;
}) {
  return (
    <section className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 className="section-title">{title}</h2>
        {muted && <span className="muted" style={{ fontSize: 12 }}>match — pick if useful</span>}
      </div>
      {empty ? (
        <div className="muted" style={{ padding: "8px 0", fontSize: 13 }}>
          Nothing in this bucket.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
          {children}
        </div>
      )}
    </section>
  );
}

function PickRow({
  endpoint,
  selected,
  onToggle,
}: {
  endpoint: ModelEndpoint;
  selected: boolean;
  onToggle: (ep: ModelEndpoint) => void;
}) {
  const ctx = fmtContext(endpoint.context_length);
  const tools = endpoint.capabilities?.tool_calling ? " · tools" : "";
  const vision = hasVision(endpoint) ? " · vision" : "";
  return (
    <label
      className="card"
      style={{
        cursor: "pointer",
        padding: "8px 12px",
        background: selected ? "rgba(77, 142, 255, 0.08)" : undefined,
        borderColor: selected ? "var(--accent)" : undefined,
      }}
    >
      <div className="row" style={{ alignItems: "center", gap: 12 }}>
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggle(endpoint)}
          aria-label={`Select ${endpoint.model_id}`}
        />
        <span className={`provider-pill ${providerClass(endpoint.provider)}`}>
          {endpoint.provider}
        </span>
        <span style={{ flex: 1 }}>
          <span style={{ fontWeight: 600 }}>{endpoint.name || endpoint.model_id}</span>
          <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>
            {endpoint.model_id}
          </span>
        </span>
        <span className="muted" style={{ fontSize: 12, whiteSpace: "nowrap" }}>
          {ctx}{tools}{vision}
        </span>
      </div>
    </label>
  );
}