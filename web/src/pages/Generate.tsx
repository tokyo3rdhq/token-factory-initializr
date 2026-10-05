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
  Segmented,
  Stack,
} from "@tokyo3rdhq/magi-design-system";

import { useInitializr } from "../initializr/InitializrContext";
import { postGenerate, type GenerateResponse } from "../kv";
import { useI18n } from "../I18nProvider";
import { SUPPORTED_TOKEN_FACTORIES } from "../../functions/lib/generators";

/**
 * Generate page — the second half of the Initializr core workflow
 * (per docs/tfi_phase_1_initializr_core_workflow.md §10).
 *
 * The page drives the explicit InitializrState held in
 * InitializrContext:
 *
 *   selectedModels     ← from Browse (selection-only role)
 *   tokenFactory       ← Token Factory picker on this page
 *
 * Validation (§9) happens at two layers:
 *   1. {@link InitializrContext.computeReadiness} computes the
 *      readiness flag from selectedModels + tokenFactory.
 *   2. The Generate API endpoint validates server-side
 *      (returns 400 / 404 with an actionable error string).
 *
 * The page reads readiness from context and surfaces it as:
 *   - Generate button disabled when not ready
 *   - Inline Banner showing the reason (validated at domain level,
 *     not just inferred from the disabled button)
 *
 * The Token Factory picker iterates SUPPORTED_TOKEN_FACTORIES (the
 * server-authoritative list of registered generators) — so adding a
 * new factory automatically extends the picker UI.
 */
export function GeneratePage() {
  const navigate = useNavigate();
  const initializr = useInitializr();
  const { ts, dict } = useI18n();

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [copied, setCopied] = useState<"yaml" | "url" | "prompt" | null>(null);

  const onInitialize = async () => {
    if (!initializr.readiness.ready || initializr.tokenFactory === null) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const resp = await postGenerate({
        model_ids: initializr.selectedModels.map((m) => ({
          data_source: m.data_source,
          provider: m.provider,
          model_id: m.model_id,
        })),
        format: initializr.tokenFactory,
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

  const factoryMeta =
    initializr.tokenFactory === null
      ? null
      : dict.initializr.factories[initializr.tokenFactory];

  return (
    <Section spacing="lg">
      <Container size="md">
        {/* Hero — left-aligned, ~720px content block to match magi-portal's
         * per-page hero rhythm (was centered; reverting). */}
        <Stack gap="3" className="tfi-page-hero">
          <span className="magi-eyebrow">{ts("generate.eyebrow")}</span>
          <h1 className="magi-h1">{ts("generate.headline")}</h1>
          <p className="magi-body-lg tfi-page-hero-subhead">
            {initializr.selectedModels.length > 0
              ? dict.generate.subheadWithSelectionTemplate(
                  initializr.selectedModels.length,
                )
              : ts("generate.subheadNoSelection")}
          </p>
        </Stack>

        {initializr.selectedModels.length === 0 ? (
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
                {initializr.selectedModels.map((m) => (
                  <div
                    className="tfi-candidate-row"
                    key={`${m.data_source}::${m.provider}::${m.model_id}`}
                  >
                    <div className="tfi-meta-grid">
                      <span className="tfi-meta-key">{ts("generate.fieldModel")}</span>
                      <span className="tfi-meta-value">{m.name || m.model_id}</span>
                      <span className="tfi-meta-key">{ts("generate.fieldProvider")}</span>
                      <span className="tfi-meta-value">{m.provider}</span>
                      <span className="tfi-meta-key">{ts("generate.fieldId")}</span>
                      <span className="tfi-meta-value">{m.model_id}</span>
                    </div>
                    <div className="tfi-candidate-row-action">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => initializr.removeModel(m)}
                        aria-label="Remove"
                      >
                        ✕
                      </Button>
                    </div>
                  </div>
                ))}
              </Stack>
            </Card>

            {/* Token Factory picker — iterates the server-authoritative
                list. The action is driven entirely by InitializrState. */}
            <Card>
              <FormField
                label={ts("initializr.pickerHeading")}
                helper={ts("initializr.pickerDescription")}
              >
                <Segmented
                  value={initializr.tokenFactory ?? SUPPORTED_TOKEN_FACTORIES[0]}
                  options={SUPPORTED_TOKEN_FACTORIES.map((id) => ({
                    value: id,
                    label: dict.initializr.factories[id].name,
                  }))}
                  onChange={(v) => initializr.setTokenFactory(v as never)}
                  accent
                />
              </FormField>
              {factoryMeta && (
                <p
                  className="magi-caption tfi-caption-secondary tfi-factory-description"
                >
                  {factoryMeta.description}
                </p>
              )}
            </Card>

            {/* Generation preconditions + action (§9). */}
            <Card>
              <Stack gap="4">
                <Stack direction="row" align="center" gap="4">
                  <span className="magi-caption tfi-caption-secondary">
                    {dict.initializr.selectionCountTemplate(
                      initializr.selectedModels.length,
                    )}
                  </span>
                  <Button
                    variant="primary"
                    onClick={onInitialize}
                    disabled={!initializr.readiness.ready || submitting}
                    loading={submitting}
                  >
                    {submitting ? ts("generate.btnInitializing") : ts("generate.btnInitialize")}
                  </Button>
                </Stack>
                {!initializr.readiness.ready && initializr.readiness.reason && (
                  <Banner variant="info">
                    {ts(initializr.readiness.reason)}
                  </Banner>
                )}
              </Stack>
            </Card>

            {error && (
              <Banner variant="error">
                {ts("initializr.errorPrefix")} {error}
              </Banner>
            )}

            {!result ? (
              <EmptyState>
                {error
                  ? ""
                  : initializr.readiness.ready
                    ? ts("generate.emptyClick")
                    : ""}
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