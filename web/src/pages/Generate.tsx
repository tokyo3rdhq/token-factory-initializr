import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useSelection } from "../components/SelectionContext";
import { postGenerate } from "../kv";

/**
 * Token Factory — Generate page (replaces the old Generate + Generated
 * pair with a single in-page flow).
 *
 * Flow:
 *   1. User picks models on /browse (carried in selection state).
 *   2. User selects a config format on /generate.
 *   3. User clicks Initialize → POST /api/generate → renders the YAML
 *      inline below with Copy / Download / Agent Prompt actions.
 *
 * The artifact is still stored in KV with a 5-min TTL; the page can
 * share the public URL via "Open shareable URL" if the user wants to
 * revisit it later (and an agent can curl the same URL to fetch the
 * YAML).
 */
export function GeneratePage() {
  const selection = useSelection();
  const navigate = useNavigate();

  const [format, setFormat] = useState<"litellm">("litellm");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    yaml: string;
    url: string;
    id: string;
    agent_prompt?: string;
    expires_at: number;
  } | null>(null);
  const [copied, setCopied] = useState<"yaml" | "url" | "prompt" | null>(null);

  const onInitialize = async () => {
    if (selection.selected.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const resp = await postGenerate({
        model_ids: selection.selected.map((m) => ({
          provider: m.provider,
          model_id: m.model_id,
        })),
        format,
      });
      setResult(resp);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const copy = async (text: string, key: "yaml" | "url" | "prompt") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      window.setTimeout(() => setCopied(null), 1500);
    } catch {
      // Clipboard API blocked (e.g. insecure context) — silently no-op.
    }
  };

  const downloadYaml = () => {
    if (!result) return;
    const blob = new Blob([result.yaml], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `litellm_config_${result.id}.yaml`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="layout-stack" style={{ maxWidth: 720, margin: "0 auto" }}>
      <header>
        <h1 style={{ margin: "0 0 4px 0", fontSize: 22 }}>Token Factory</h1>
        <p className="muted" style={{ margin: 0 }}>
          {selection.selected.length > 0 ? (
            <>
              {selection.selected.length} selected model
              {selection.selected.length === 1 ? "" : "s"} ready to
              initialize.
            </>
          ) : (
            <>No models selected.</>
          )}
        </p>
      </header>

      {selection.selected.length === 0 ? (
        <div className="empty">
          Nothing selected yet. Head to{" "}
          <Link to="/">the requirements form</Link>, then{" "}
          <Link to="/browse">browse</Link> to pick models.
        </div>
      ) : (
        <>
          <section className="card layout-stack" style={{ gap: 16 }}>
            <div className="row" style={{ alignItems: "center", gap: 12 }}>
              <span style={{ fontWeight: 600, fontSize: 15 }}>
                {selection.selected.length} model
                {selection.selected.length === 1 ? "" : "s"}
              </span>
              <div style={{ flex: 1 }} />
              <FormatSelect value={format} onChange={setFormat} />
              <button
                className="btn btn-primary"
                onClick={onInitialize}
                disabled={submitting}
              >
                {submitting ? (
                  <>
                    <span className="spinner" /> Initializing…
                  </>
                ) : (
                  "Initialize"
                )}
              </button>
            </div>

            <div
              className="muted"
              style={{ fontSize: 12, textAlign: "center", margin: "8px 0" }}
            >
              ↓
            </div>

            {error && <div className="banner error">{error}</div>}

            {!result ? (
              <div className="empty">
                {error ? "" : "Click Initialize to generate the config."}
              </div>
            ) : (
              <ResultPanel
                yaml={result.yaml}
                url={result.url}
                id={result.id}
                agentPrompt={result.agent_prompt}
                copied={copied}
                onCopy={copy}
                onDownload={downloadYaml}
              />
            )}
          </section>

          <div style={{ display: "flex", gap: 8 }}>
            <Link to="/browse" className="btn">
              ← Back to picks
            </Link>
            {result && (
              <button
                className="btn"
                onClick={() => {
                  selection.clear();
                  navigate("/");
                }}
              >
                Start over
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function FormatSelect({
  value,
  onChange,
}: {
  value: "litellm";
  onChange: (v: "litellm") => void;
}) {
  return (
    <label className="row" style={{ alignItems: "center", gap: 8 }}>
      <span className="muted" style={{ fontSize: 12 }}>Format</span>
      <select
        className="btn"
        value={value}
        onChange={(e) => onChange(e.target.value as "litellm")}
        style={{ padding: "6px 10px" }}
      >
        <option value="litellm">LiteLLM</option>
      </select>
    </label>
  );
}

function ResultPanel({
  yaml,
  url,
  id,
  agentPrompt,
  copied,
  onCopy,
  onDownload,
}: {
  yaml: string;
  url: string;
  id: string;
  agentPrompt?: string;
  copied: "yaml" | "url" | "prompt" | null;
  onCopy: (text: string, key: "yaml" | "url" | "prompt") => void;
  onDownload: () => void;
}) {
  return (
    <div className="layout-stack" style={{ gap: 12 }}>
      <div className="row" style={{ alignItems: "center", gap: 8 }}>
        <span className="muted" style={{ fontSize: 13 }}>
          <code>{id}.yaml</code>
        </span>
        <div style={{ flex: 1 }} />
        <button className="btn" onClick={() => onCopy(yaml, "yaml")}>
          {copied === "yaml" ? "Copied!" : "Copy"}
        </button>
        <button className="btn" onClick={onDownload}>
          Download
        </button>
        <button
          className="btn"
          onClick={() => onCopy(agentPrompt ?? "", "prompt")}
        >
          {copied === "prompt" ? "Copied!" : "Agent Prompt"}
        </button>
      </div>
      <pre className="code" data-testid="yaml">
        {yaml}
      </pre>
      <div className="row" style={{ alignItems: "center", gap: 8 }}>
        <span className="muted" style={{ fontSize: 12 }}>
          Shareable URL (5-min TTL):
        </span>
        <input
          className="btn"
          style={{ flex: 1, fontFamily: "ui-monospace, monospace", fontSize: 12 }}
          readOnly
          value={url}
        />
        <button className="btn" onClick={() => onCopy(url, "url")}>
          {copied === "url" ? "Copied!" : "Copy URL"}
        </button>
      </div>
    </div>
  );
}