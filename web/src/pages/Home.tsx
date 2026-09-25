import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ModelCard } from "../components/ModelCard";
import { useSelection } from "../components/SelectionContext";
import {
  fetchManifest,
  fetchModels,
  FIXTURES,
  shouldUseLocalFixtures,
} from "../kv";
import type { Manifest, ModelEndpoint } from "../types";

/**
 * Home / Browse page.
 *
 * Loads the manifest + per-provider model snapshots from /api/*, lets
 * the user filter by provider, and lets them tap cards to add to
 * their Generate selection. The "Generate" pill in the top-right
 * carries the live count of selected endpoints.
 */
export function HomePage() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [models, setModels] = useState<ModelEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeProvider, setActiveProvider] = useState<string>("all");
  const [search, setSearch] = useState("");

  const selection = useSelection();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const m = await fetchManifest();
        const snap = await fetchModels();
        if (cancelled) return;
        setManifest(m);
        setModels(snap.flatMap((s) => s.models));
        setError(null);
      } catch (e) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const providers = manifest ? Object.keys(manifest.providers) : [];
  const providerCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const m of models) {
      counts[m.provider] = (counts[m.provider] ?? 0) + 1;
    }
    return counts;
  }, [models]);

  const filtered = useMemo(() => {
    const s = search.trim().toLowerCase();
    return models
      .filter((m) =>
        activeProvider === "all" ? true : m.provider === activeProvider
      )
      .filter((m) => {
        if (!s) return true;
        return (
          m.model_id.toLowerCase().includes(s) ||
          (m.name ?? "").toLowerCase().includes(s) ||
          (m.lab ?? "").toLowerCase().includes(s)
        );
      })
      .sort((a, b) => {
        // Free endpoints first; then alphabetical by name.
        if (a.free !== b.free) return a.free ? -1 : 1;
        const ax = a.name ?? a.model_id;
        const bx = b.name ?? b.model_id;
        return ax.localeCompare(bx);
      });
  }, [models, activeProvider, search]);

  const total = manifest?.total ?? filtered.length;
  const generatedAt = manifest?.generated_at;

  // Detect fallback mode (KV empty + local fixtures active).
  const usingFallback =
    !loading &&
    models.length === 0 &&
    shouldUseLocalFixtures(import.meta.env.VITE_USE_LOCAL_FIXTURES);

  // When the fetch above fails AND local fixtures are explicitly opted-in
  // (env var set in wrangler.toml vars), fall back to FIXTURES so the
  // UI still renders something useful (e.g. fresh clone before the
  // data pipeline has run).
  useEffect(() => {
    if (!usingFallback) return;
    setManifest(FIXTURES.manifest);
    setModels(FIXTURES.models.flatMap((s) => s.models));
  }, [usingFallback]);

  return (
    <div className="layout-stack">
      <header>
        <h1 style={{ margin: "0 0 4px 0", fontSize: 22 }}>
          Free model endpoints
        </h1>
        <p className="muted" style={{ margin: 0 }}>
          {total} endpoints across {providers.length} providers.
          {generatedAt && (
            <>
              {" "}Last refreshed:{" "}
              <code>{generatedAt}</code>.
            </>
          )}
          {" "}
          <Link to="/generate" className="muted">
            {selection.selected.length > 0
              ? `→ ${selection.selected.length} selected`
              : "select endpoints →"}
          </Link>
        </p>
      </header>

      {error && !usingFallback && (
        <div className="banner error">
          Could not load KV catalog: {error}. If this persists, run{" "}
          <code>python -m data.main</code> against the namespace, or set{" "}
          <code>TFI_USE_LOCAL_FIXTURES=1</code> for offline-mode browsing.
        </div>
      )}

      {usingFallback && (
        <div className="banner">
          Showing local fixture data (TFI_USE_LOCAL_FIXTURES=1). The live
          KV is empty; run the data pipeline to populate the real catalog.
        </div>
      )}

      <div className="card">
        <div className="layout-stack" style={{ gap: 12 }}>
          <input
            type="search"
            placeholder="Search by name, id, or lab…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="btn"
            style={{ width: "100%" }}
          />

          <div className="tabs">
            <button
              className={`tab ${activeProvider === "all" ? "active" : ""}`}
              onClick={() => setActiveProvider("all")}
            >
              all <span className="count">{models.length}</span>
            </button>
            {providers.map((p) => (
              <button
                key={p}
                className={`tab ${activeProvider === p ? "active" : ""}`}
                onClick={() => setActiveProvider(p)}
              >
                {p}{" "}
                <span className="count">{providerCounts[p] ?? 0}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="empty">
          <span className="spinner" /> Loading…
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty">No models match this filter.</div>
      ) : (
        <div className="model-grid">
          {filtered.map((m) => (
            <ModelCard
              key={`${m.provider}::${m.model_id}`}
              endpoint={m}
              selected={selection.isSelected(m)}
              onToggle={selection.toggle}
            />
          ))}
        </div>
      )}
    </div>
  );
}