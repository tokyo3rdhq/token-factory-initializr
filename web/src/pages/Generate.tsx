import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Container, Section, Stack, Button, Card } from "@tokyo3rdhq/magi-design-system";

import { useSelection } from "../components/SelectionContext";
import { postGenerate } from "../kv";

/**
 * Token Factory — Generate page.
 *
 * Layout:
 *   - developer-infrastructure summary (MODEL / PROVIDER / ID)
 *   - format selector + Initialize button
 *   - terminal-style code surface for the YAML
 *   - copy / download / agent-prompt actions
 *   - shareable URL as a small machine-friendly meta row
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
      /* clipboard unavailable in this context */
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
    <Section spacing="lg">
      <Container size="md">
        <Stack gap="3" style={{ marginBottom: "var(--magi-space-10)" }}>
          <span className="magi-eyebrow">Generate</span>
          <h1 className="magi-h1">Token Factory</h1>
          <p className="magi-body-lg" style={{ color: "var(--magi-text-secondary)" }}>
            {selection.selected.length > 0
              ? `${selection.selected.length} model${
                  selection.selected.length === 1 ? "" : "s"
                } ready to initialize.`
              : "No models selected yet."}
          </p>
        </Stack>

        {selection.selected.length === 0 ? (
          <div className="tfi-empty">
            Nothing selected. Head to{" "}
            <Link to="/">the requirements form</Link>, then{" "}
            <Link to="/browse">browse</Link> to pick models.
          </div>
        ) : (
          <Stack gap="6">
            {/* Selected models summary */}
            <Card>
              <span
                className="magi-eyebrow"
                style={{ display: "block", marginBottom: "var(--magi-space-4)" }}
              >
                Selection
              </span>
              <Stack gap="4">
                {selection.selected.map((m) => (
                  <div
                    className="tfi-meta-grid"
                    key={`${m.provider}::${m.model_id}`}
                  >
                    <span className="tfi-meta-key">Model</span>
                    <span className="tfi-meta-value">{m.name || m.model_id}</span>
                    <span className="tfi-meta-key">Provider</span>
                    <span className="tfi-meta-value">{m.provider}</span>
                    <span className="tfi-meta-key">ID</span>
                    <span className="tfi-meta-value">{m.model_id}</span>
                  </div>
                ))}
              </Stack>
            </Card>

            {/* Format + Initialize */}
            <Card>
              <Stack direction="row" gap="4" align="center">
                <div className="tfi-field" style={{ flex: 1 }}>
                  <label className="tfi-field-label" htmlFor="format-select">
                    Format
                  </label>
                  <select
                    id="format-select"
                    className="tfi-select"
                    value={format}
                    onChange={(e) => setFormat(e.target.value as "litellm")}
                  >
                    <option value="litellm">LiteLLM</option>
                  </select>
                </div>
                <Button
                  variant="primary"
                  onClick={onInitialize}
                  disabled={submitting}
                  loading={submitting}
                >
                  {submitting ? "Initializing…" : "Initialize"}
                </Button>
              </Stack>
            </Card>

            {error && (
              <div className="tfi-banner error">{error}</div>
            )}

            {!result ? (
              <div className="tfi-empty">
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

            <div className="tfi-action-bar">
              <Link to="/browse" className="tfi-nav-link" style={{ paddingLeft: 0 }}>
                ← Back to picks
              </Link>
              <div style={{ flex: 1 }} />
              {result && (
                <Button
                  variant="secondary"
                  onClick={() => {
                    selection.clear();
                    navigate("/");
                  }}
                >
                  Start over
                </Button>
              )}
            </div>
          </Stack>
        )}
      </Container>
    </Section>
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
    <Stack gap="4">
      <div className="tfi-code-chrome">
        <span className="tfi-code-filename">{id}.yaml</span>
        <span className="tfi-code-status">Ready</span>
        <div style={{ flex: 1 }} />
        <Button size="sm" variant="secondary" onClick={() => onCopy(yaml, "yaml")}>
          {copied === "yaml" ? "Copied" : "Copy"}
        </Button>
        <Button size="sm" variant="secondary" onClick={onDownload}>
          Download
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => onCopy(agentPrompt ?? "", "prompt")}
        >
          {copied === "prompt" ? "Copied" : "Agent Prompt"}
        </Button>
      </div>
      <pre className="magi-code tfi-code-surface" data-testid="yaml">
        {yaml}
      </pre>

      <div className="tfi-meta-grid">
        <span className="tfi-meta-key">URL</span>
        <span className="tfi-meta-value">
          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>{url}</span>
          <Button size="sm" variant="secondary" onClick={() => onCopy(url, "url")}>
            {copied === "url" ? "Copied" : "Copy"}
          </Button>
        </span>
        <span className="tfi-meta-key">TTL</span>
        <span className="tfi-meta-value">5 minutes — by design</span>
      </div>
    </Stack>
  );
}
