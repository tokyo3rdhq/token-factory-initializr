import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { fetchGenerated } from "../kv";

/**
 * Generated page — shown at /generated/{id}.
 *
 * Loads the artifact body (the rendered LiteLLM YAML) plus the
 * agent prompt from the same artifact metadata endpoint. Renders
 * the YAML in a code block with a Copy button; below it, an
 * "agent prompt" snippet the user can hand to an AI agent.
 *
 * Falls back to "expired or not found" if the artifact TTL has
 * elapsed — the 5-minute window is enforced server-side, so the
 * client only knows after a 404.
 */
export function GeneratedPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<{
    yaml: string;
    format: string;
    expires_at: number;
    model_count: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<"yaml" | "url" | "prompt" | null>(
    null
  );
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetchGenerated(id);
        if (cancelled) return;
        setData({
          yaml: resp.config_yaml,
          format: resp.format,
          expires_at: resp.expires_at,
          model_count: resp.model_count,
        });
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  const expiresIn = data
    ? Math.max(0, Math.round((data.expires_at - now) / 1000))
    : 0;
  const expired = data ? expiresIn === 0 : false;

  const fullUrl = useMemo(() => {
    if (typeof window === "undefined" || !id) return "";
    return `${window.location.origin}/generated/${id}`;
  }, [id]);

  const agentPrompt = useMemo(() => {
    if (!data) return "";
    return [
      "You are integrating a Token Factory Initializr generated config.",
      "Fetch this URL and merge the LiteLLM `model_list` entries into",
      "the user's existing litellm config:",
      "",
      `  ${fullUrl}`,
      "",
      "Rules:",
      "  1. Preserve every model already in the user's config.",
      "  2. Add only entries whose `model_name` is not already present.",
      `  3. Do not overwrite unrelated keys (router_settings, litellm_settings, etc.).`,
      `  4. Treat this URL as short-lived; do not cache the response.`,
    ].join("\n");
  }, [data, fullUrl]);

  const copy = async (text: string, key: "yaml" | "url" | "prompt") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      window.setTimeout(() => setCopied(null), 1500);
    } catch {
      setCopied(null);
    }
  };

  if (error) {
    return (
      <div className="layout-stack">
        <header>
          <h1 style={{ margin: "0 0 4px 0", fontSize: 22 }}>
            Generated config
          </h1>
        </header>
        <div className="banner error">
          This URL has expired or was never valid. Generated configs are
          kept in KV for 5 minutes.{" "}
          <Link to="/generate">Generate a new one</Link>.
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="empty">
        <span className="spinner" /> Loading generated config…
      </div>
    );
  }

  return (
    <div className="layout-stack">
      <header>
        <h1 style={{ margin: "0 0 4px 0", fontSize: 22 }}>
          Generated config <code style={{ fontSize: 14 }}>{id}</code>
        </h1>
        <p className="muted" style={{ margin: 0 }}>
          {data.model_count} model{data.model_count === 1 ? "" : "s"} ·{" "}
          format: {data.format}
          {expired ? (
            <>
              {" "}· <span style={{ color: "var(--bad)" }}>expired</span>
            </>
          ) : (
            <>
              {" "}· expires in{" "}
              <strong>
                {Math.floor(expiresIn / 60)}m {expiresIn % 60}s
              </strong>
            </>
          )}
        </p>
      </header>

      {expired && (
        <div className="banner error">
          This URL has expired. The config has been evicted from KV;{" "}
          <Link to="/generate">generate a new one</Link>.
        </div>
      )}

      <section className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 className="section-title">LiteLLM config</h2>
          <button className="btn" onClick={() => copy(data.yaml, "yaml")}>
            {copied === "yaml" ? "Copied!" : "Copy YAML"}
          </button>
        </div>
        <pre className="code" data-testid="yaml">
          {data.yaml}
        </pre>
      </section>

      <section className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 className="section-title">Share URL</h2>
          <button className="btn" onClick={() => copy(fullUrl, "url")}>
            {copied === "url" ? "Copied!" : "Copy URL"}
          </button>
        </div>
        <pre className="code">{fullUrl}</pre>
        <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>
          Anyone with this URL can fetch the raw config for the next 5
          minutes. After that it's gone.
        </p>
      </section>

      <section className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 className="section-title">Agent prompt</h2>
          <button className="btn" onClick={() => copy(agentPrompt, "prompt")}>
            {copied === "prompt" ? "Copied!" : "Copy prompt"}
          </button>
        </div>
        <pre className="code">{agentPrompt}</pre>
        <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>
          Hand this to an AI agent to merge the generated config into
          an existing LiteLLM setup. The prompt is short on purpose so
          it survives context-window truncation.
        </p>
      </section>
    </div>
  );
}