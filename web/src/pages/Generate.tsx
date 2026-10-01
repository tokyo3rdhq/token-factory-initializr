import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Banner,
  Button,
  Card,
  Container,
  EmptyState,
  FormField,
  Section,
  Stack,
} from "@tokyo3rdhq/magi-design-system";

import { useSelection } from "../components/SelectionContext";
import { postGenerate, type GenerateResponse } from "../kv";
import { useI18n } from "../I18nProvider";

/**
 * Generate page.
 *
 * Flow:
 *   - format selector + Initialize button
 *   - server returns a YAML + shareable URL (5-minute TTL)
 *   - shareable URL as a small machine-friendly meta row
 *
 * All user-visible strings are routed through the i18n provider.
 */
export function GeneratePage() {
  const navigate = useNavigate();
  const selection = useSelection();
  const { ts, dict } = useI18n();

  const [format, setFormat] = useState<"litellm">("litellm");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [copied, setCopied] = useState<"yaml" | "url" | "prompt" | null>(null);

  const onInitialize = async () => {
    if (selection.selected.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const resp = await postGenerate({
        model_ids: selection.selected.map((m) => ({
          data_source: m.data_source,
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
      // Clipboard API may be blocked; do nothing.
    }
  };

  const download = () => {
    if (!result) return;
    const blob = new Blob([result.yaml], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "config.yaml";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Section spacing="lg">
      <Container size="md">
        {/* Hero — left-aligned, ~720px content block to match magi-portal's
         * per-page hero rhythm (was centered; reverting). */}
<Stack gap="3" className="tfi-page-hero">
          <span className="magi-eyebrow">{ts("generate.eyebrow")}</span>
          <h1 className="magi-h1">{ts("generate.headline")}</h1>
          <p className="magi-body-lg tfi-page-hero-subhead">
            {selection.selected.length > 0
              ? dict.generate.subheadWithSelectionTemplate(selection.selected.length)
              : ts("generate.subheadNoSelection")}
          </p>
        </Stack>

        {selection.selected.length === 0 ? (
          <EmptyState>
            {ts("generate.emptyBefore")}
            <Link to="/">{ts("nav.start")}</Link>
            {ts("generate.emptyForm")}
            <Link to="/browse">{ts("nav.browse")}</Link>
            {ts("generate.emptyBrowse")}
          </EmptyState>
        ) : (
          <Stack gap="6">
            {/* Selected models summary */}
            <Card>
              <span className="magi-eyebrow tfi-selection-header">
                {ts("generate.selectionHeader")}
              </span>
              <Stack gap="4">
                {selection.selected.map((m) => (
                  <div
                    className="tfi-meta-grid"
                    key={`${m.data_source}::${m.provider}::${m.model_id}`}
                  >
                    <span className="tfi-meta-key">{ts("generate.fieldModel")}</span>
                    <span className="tfi-meta-value">{m.name || m.model_id}</span>
                    <span className="tfi-meta-key">{ts("generate.fieldProvider")}</span>
                    <span className="tfi-meta-value">{m.provider}</span>
                    <span className="tfi-meta-key">{ts("generate.fieldId")}</span>
                    <span className="tfi-meta-value">{m.model_id}</span>
                  </div>
                ))}
              </Stack>
            </Card>

            {/* Format + Initialize */}
            <Card>
              <Stack direction="row" gap="4" align="center">
                <FormField label={ts("generate.fieldFormat")}>
                  <select
                    id="format-select"
                    className="tfi-select"
                    value={format}
                    onChange={(e) => setFormat(e.target.value as "litellm")}
                  >
                    <option value="litellm">{ts("generate.optionLitellm")}</option>
                  </select>
                </FormField>
                <Button
                  variant="primary"
                  onClick={onInitialize}
                  disabled={submitting}
                  loading={submitting}
                >
                  {submitting ? ts("generate.btnInitializing") : ts("generate.btnInitialize")}
                </Button>
              </Stack>
            </Card>

            {error && (
              <Banner variant="error">{error}</Banner>
            )}

            {!result ? (
              <EmptyState>
                {error ? "" : ts("generate.emptyClick")}
              </EmptyState>
            ) : (
              <ResultPanel
                yaml={result.yaml}
                url={result.url}
                id={result.id}
                agentPrompt={result.agent_prompt}
                copied={copied}
                onCopy={copy}
                onDownload={download}
              />
            )}
          </Stack>
        )}

        <div className="tfi-back-button-wrap">
          <Button variant="secondary" onClick={() => navigate("/browse")}>
            ← {ts("nav.browse")}
          </Button>
        </div>
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
  const { ts } = useI18n();
  return (
    <Stack gap="4">
      <div className="tfi-code-chrome">
        <span className="tfi-code-filename">{id}.yaml</span>
        <span className="magi-caption tfi-result-ready">
          {ts("generate.yamlReady")}
        </span>
        <div className="tfi-result-spacer" />
        <Button size="sm" variant="secondary" onClick={() => onCopy(yaml, "yaml")}>
          {copied === "yaml" ? ts("generate.yamlCopied") : ts("generate.yamlCopy")}
        </Button>
        <Button size="sm" variant="secondary" onClick={onDownload}>
          {ts("generate.yamlDownload")}
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => onCopy(agentPrompt ?? "", "prompt")}
        >
          {copied === "prompt" ? ts("generate.yamlCopied") : ts("generate.yamlAgentPrompt")}
        </Button>
      </div>
      <pre className="magi-code tfi-code-surface" data-testid="yaml">
        {yaml}
      </pre>

      <div className="tfi-meta-grid">
        <span className="tfi-meta-key">{ts("generate.fieldUrl")}</span>
        <span className="tfi-meta-value">
          <span className="tfi-result-url-cell">{url}</span>
          <Button size="sm" variant="secondary" onClick={() => onCopy(url, "url")}>
            {copied === "url" ? ts("generate.yamlCopied") : ts("generate.yamlCopy")}
          </Button>
        </span>
        <span className="tfi-meta-key">{ts("generate.fieldTtl")}</span>
        <span className="tfi-meta-value">{ts("generate.ttlValue")}</span>
      </div>
    </Stack>
  );
}