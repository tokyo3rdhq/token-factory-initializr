import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ModelCard } from "../components/ModelCard";
import { useSelection } from "../components/SelectionContext";
import { postGenerate } from "../kv";

/**
 * Generate page.
 *
 * Shows the user's current picks, lets them remove individual entries
 * or clear all, then POSTs to /api/generate. On success, navigates to
 * the short-lived /generated/{id} URL where they can grab the config
 * or the agent prompt.
 */
export function GeneratePage() {
  const selection = useSelection();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onGenerate = async () => {
    if (selection.selected.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const resp = await postGenerate({
        model_ids: selection.selected.map((m) => ({
          provider: m.provider,
          model_id: m.model_id,
        })),
        format: "litellm",
      });
      selection.clear();
      navigate(`/generated/${resp.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="layout-stack">
      <header>
        <h1 style={{ margin: "0 0 4px 0", fontSize: 22 }}>
          Generate LiteLLM config
        </h1>
        <p className="muted" style={{ margin: 0 }}>
          Review your picks, then click Generate. The resulting config
          URL expires in 5 minutes.
        </p>
      </header>

      {selection.selected.length === 0 ? (
        <div className="empty">
          Nothing selected. Head to the{" "}
          <Link to="/">browse page</Link> and tap a model card to add
          it here.
        </div>
      ) : (
        <>
          <div className="row" style={{ gap: 8 }}>
            <button
              className="btn"
              onClick={() => selection.clear()}
              disabled={submitting}
            >
              Clear all ({selection.selected.length})
            </button>
            <button
              className="btn btn-primary"
              onClick={onGenerate}
              disabled={submitting || selection.selected.length === 0}
            >
              {submitting ? (
                <>
                  <span className="spinner" /> Generating…
                </>
              ) : (
                `Generate (${selection.selected.length} model${
                  selection.selected.length === 1 ? "" : "s"
                })`
              )}
            </button>
          </div>

          {error && <div className="banner error">{error}</div>}

          <div className="model-grid">
            {selection.selected.map((m) => (
              <ModelCard
                key={`${m.provider}::${m.model_id}`}
                endpoint={m}
                selected
                onToggle={(ep) => selection.toggle(ep)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}