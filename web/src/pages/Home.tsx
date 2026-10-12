import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Copy, User, Bot } from "lucide-react";

import {
  Container,
  Section,
  Stack,
  Segmented,
} from "@tokyo3rdhq/magi-design-system";

import { useI18n } from "../I18nProvider";
import "../gtag";
import { useSeo } from "../seo/useSeo";

/**
 * Home — the entry point.
 *
 * Layout (lobehub-icons inspired):
 *   [Left: eyebrow + headline + subhead, left-aligned]
 *   [Right: sidebar card ~280px, top-aligned with the headline]
 *     └── Tab switcher (Human / Agent with icons, full-width)
 *         ├── Human panel: numbered steps 1/2/3 + Start button below
 *         └── Agent panel: intro line + single-line prompt row + copy icon
 *     └── Doc links (llms.txt · agents.md)
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
      // Clipboard API may be blocked.
    }
  };

  const renderTab = (
    opt: { value: string; label: string },
    state: { active: boolean; disabled: boolean; onSelect: () => void }
  ) => (
    <button
      type="button"
      role="radio"
      aria-checked={state.active}
      disabled={state.disabled}
      tabIndex={state.active ? 0 : -1}
      onClick={state.onSelect}
      className={`magi-segmented-item ${state.active ? "magi-segmented-item--active" : ""}`}
      style={{ display: "flex", alignItems: "center", gap: "6px", width: "100%" }}
    >
      {opt.value === "human" ? <User size={14} aria-hidden="true" /> : <Bot size={14} aria-hidden="true" />}
      <span>{opt.label}</span>
    </button>
  );

  return (
    <Section className="tfi-home-section">
      <Container>
        <div className="tfi-home-columns">
          {/* Left-aligned intro block */}
          <div className="tfi-home-intro-wrap">
            <Stack gap="4" className="tfi-home-intro">
              <span className="magi-eyebrow">{ts("home.eyebrow")}</span>
              <h1 className="magi-display tfi-home-headline">{ts("home.headline")}</h1>
              <p className="magi-body-lg tfi-home-subhead">{ts("home.subhead")}</p>
            </Stack>
          </div>

          {/* Right sidebar card — top edge aligned with the headline */}
          <div className="tfi-home-sidebar">
            {/* Tab switcher — full sidebar width */}
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

            {/* Content panel */}
            <div className="tfi-home-panel">
              {tab === "human" && (
                <>
                  <div className="tfi-home-human-panel" data-testid="home-human-panel">
                    <ol className="tfi-home-steps">
                      <li className="tfi-home-step">
                        <div className="tfi-home-step-row">
                          <span className="tfi-home-step-num">1</span>
                          <span className="tfi-home-step-title">{ts("home.step1Title")}</span>
                        </div>
                        <span className="tfi-home-step-desc">{ts("home.step1Desc")}</span>
                      </li>
                      <li className="tfi-home-step">
                        <div className="tfi-home-step-row">
                          <span className="tfi-home-step-num">2</span>
                          <span className="tfi-home-step-title">{ts("home.step2Title")}</span>
                        </div>
                        <span className="tfi-home-step-desc">{ts("home.step2Desc")}</span>
                      </li>
                      <li className="tfi-home-step">
                        <div className="tfi-home-step-row">
                          <span className="tfi-home-step-num">3</span>
                          <span className="tfi-home-step-title">{ts("home.step3Title")}</span>
                        </div>
                        <span className="tfi-home-step-desc">{ts("home.step3Desc")}</span>
                      </li>
                    </ol>
                  </div>
                  <div className="tfi-home-cta">
                    <button
                      type="button"
                      className="tfi-home-browse-btn"
                      onClick={() => {
                        navigate("/browse");
                        gtag('event', 'browse_models_clicked', {
                          event_category: 'Human Onboarding',
                          event_label: 'Browse models CTA',
                          non_interaction: false,
                        });
                      }}
                    >
                      {ts("home.browseModelsButton")}
                    </button>
                  </div>
                </>
              )}

              {tab === "agent" && (
                <div className="tfi-home-agent-panel" data-testid="home-agent-panel">
                  <p className="tfi-home-agent-intro">{ts("home.agentPanelIntro")}</p>
                  <div className="tfi-home-agent-row">
                    <code className="tfi-home-agent-prompt" data-testid="home-agent-prompt">
                      {dict.home.agentPromptInline}
                    </code>
                    <button
                      type="button"
                      aria-label={ts("home.agentCopyButton")}
                      data-testid="home-agent-copy"
                      className={`tfi-home-copy-btn ${copied ? "tfi-home-copied" : ""}`}
                      onClick={onCopy}
                    >
                      <Copy size={14} aria-hidden="true" />
                    </button>
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
        </div>
      </Container>
    </Section>
  );
}
