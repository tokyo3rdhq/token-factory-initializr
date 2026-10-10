import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Copy, User, Bot } from "lucide-react";

import {
  Container,
  Section,
  Stack,
  Button,
  Segmented,
} from "@tokyo3rdhq/magi-design-system";

import { useI18n } from "../I18nProvider";
import { useSeo } from "../seo/useSeo";

/**
 * Home — the entry point.
 *
 * Layout:
 *   [Left: eyebrow + headline + subhead]
 *   [Right: sidebar card with tabs + doc links]
 */
export function HomePage() {
  const navigate = useNavigate();
  const { ts, dict } = useI18n();
  useSeo("/");

  const [tab, setTab] = useState<"human" | "agent">("human");
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(dict.home.agentPromptInline);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API may be blocked; fallback to manual selection.
    }
  };

  const renderTab = (opt: { value: string; label: string }, _state: { active: boolean; disabled: boolean }) => (
    <div style={{ display: "flex", alignItems: "center", gap: "6px", width: "100%" }}>
      {opt.value === "human" ? <User size={14} aria-hidden="true" /> : <Bot size={14} aria-hidden="true" />}
      <span>{opt.label}</span>
    </div>
  );

  return (
    <Section className="tfi-home-section">
      <Container>
        {/* Left-aligned intro block */}
        <Stack gap="4" className="tfi-home-intro">
          <span className="magi-eyebrow">{ts("home.eyebrow")}</span>
          <h1 className="magi-display tfi-home-headline">{ts("home.headline")}</h1>
          <p className="magi-body-lg tfi-home-subhead">{ts("home.subhead")}</p>
        </Stack>

        {/* Right sidebar card */}
        <div className="tfi-home-sidebar">
          {/* Tab switcher */}
          <Segmented
            value={tab}
            onChange={(v) => setTab(v as "human" | "agent")}
            options={[
              { value: "human", label: ts("home.humanTab") },
              { value: "agent", label: ts("home.agentTab") },
            ]}
            children={renderTab}
            className="tfi-home-tabs"
          />

          {/* Content panel based on tab */}
          <div className="tfi-home-panel">
            {tab === "human" && (
              <div className="tfi-home-human-panel" data-testid="home-human-panel">
                <ol className="tfi-home-steps">
                  <li className="tfi-home-step">
                    <span className="tfi-home-step-title">{ts("home.step1Title")}</span>
                  </li>
                  <li className="tfi-home-step">
                    <span className="tfi-home-step-title">{ts("home.step2Title")}</span>
                  </li>
                  <li className="tfi-home-step">
                    <span className="tfi-home-step-title">{ts("home.step3Title")}</span>
                  </li>
                </ol>
                <div className="tfi-home-cta">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => navigate("/browse")}
                    className="tfi-home-browse-btn"
                  >
                    {ts("home.browseModelsButton")}
                  </Button>
                </div>
              </div>
            )}

            {tab === "agent" && (
              <div className="tfi-home-agent-panel" data-testid="home-agent-panel">
                <div className="tfi-home-agent-instruction">
                  <pre
                    className="magi-code tfi-home-agent-prompt"
                    data-testid="home-agent-prompt"
                    aria-label="Agent bootstrap prompt"
                  >
                    <code>{dict.home.agentPromptInline}</code>
                  </pre>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={onCopy}
                    data-testid="home-agent-copy"
                    aria-label={ts("home.agentCopyButton")}
                    className="tfi-home-agent-copy-btn"
                  >
                    {copied ? (
                      <>
                        <Copy size={14} aria-hidden="true" className="tfi-home-copied-icon" />
                        <span>{ts("home.agentCopiedLabel")}</span>
                      </>
                    ) : (
                      <>
                        <Copy size={14} aria-hidden="true" />
                        <span>{ts("home.agentCopyButton")}</span>
                      </>
                    )}
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Shared doc links */}
          <div className="tfi-home-links">
            <a href="/llms.txt" target="_blank" rel="noreferrer" className="tfi-home-link">llms.txt</a>
            <span className="tfi-home-separator" aria-hidden="true">·</span>
            <a href="/agents.md" target="_blank" rel="noreferrer" className="tfi-home-link">agents.md</a>
          </div>
        </div>
      </Container>
    </Section>
  );
}
