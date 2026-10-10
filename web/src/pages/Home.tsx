import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Copy } from "lucide-react";

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
 * Structure follows the MAGI hero pattern with Agent/Human tab switcher
 * (docs/tfi_homepage_redesign_for_human_and_agent.md):
 *   [eyebrow]
 *   display headline
 *   subhead
 *   [tab switcher: Agent / Human]
 *   [active panel]
 *   [shared footer: llms.txt + agents.md]
 *
 * Two tabs serve different visitor types:
 *   - Agent: copy prompt + API documentation links
 *   - Human: 3-step workflow + Browse models CTA
 */
export function HomePage() {
  const navigate = useNavigate();
  const { ts, dict } = useI18n();
  useSeo("/");

  const [tab, setTab] = useState<"agent" | "human">("agent");
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

  return (
    <Section className="tfi-home-section">
      <Container>
        {/* Compact introductory block */}
        <Stack gap="4" className="tfi-home-intro">
          <span className="magi-eyebrow">{ts("home.eyebrow")}</span>
          <h1 className="magi-display tfi-home-headline">{ts("home.headline")}</h1>
          <p className="magi-body-lg tfi-home-subhead">{ts("home.subhead")}</p>

          {/* Two-option audience switcher */}
          <div className="tfi-home-tabs-wrapper">
            <Segmented
              value={tab}
              onChange={(v) => setTab(v as "agent" | "human")}
              options={[
                { value: "agent", label: ts("home.agentTab") },
                { value: "human", label: ts("home.humanTab") },
              ]}
              className="tfi-home-tabs"
            />
          </div>

          {/* One content panel whose content depends on the selected audience */}
          {tab === "agent" && (
            <div className="tfi-home-agent-panel" data-testid="home-agent-panel">
              <h2 className="magi-h4 tfi-home-agent-heading">{ts("home.agentHeading")}</h2>
              <p className="magi-body-md tfi-home-agent-desc">{ts("home.agentDesc")}</p>
              
              {/* Instruction surface with copy action */}
              <div className="tfi-home-agent-instruction-container">
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
                      <span className="tfi-home-copied-text">{ts("home.agentCopiedLabel")}</span>
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
          
          {tab === "human" && (
            <div className="tfi-home-human-panel">
              <h2 className="magi-h4 tfi-home-human-heading">{ts("home.humanHeading")}</h2>
              <p className="magi-body-md tfi-home-human-desc">{ts("home.humanDesc")}</p>
              
              {/* Three vertically aligned steps */}
              <ol className="tfi-home-steps">
                <li className="tfi-home-step">
                  <div className="tfi-home-step-marker">01</div>
                  <div className="tfi-home-step-content">
                    <h3 className="magi-h4">{ts("home.step1Title")}</h3>
                    <p className="magi-body-md">{ts("home.step1Desc")}</p>
                  </div>
                </li>
                <li className="tfi-home-step">
                  <div className="tfi-home-step-marker">02</div>
                  <div className="tfi-home-step-content">
                    <h3 className="magi-h4">{ts("home.step2Title")}</h3>
                    <p className="magi-body-md">{ts("home.step2Desc")}</p>
                  </div>
                </li>
                <li className="tfi-home-step">
                  <div className="tfi-home-step-marker">03</div>
                  <div className="tfi-home-step-content">
                    <h3 className="magi-h4">{ts("home.step3Title")}</h3>
                    <p className="magi-body-md">{ts("home.step3Desc")}</p>
                  </div>
                </li>
              </ol>
              
              {/* Primary action after the three steps */}
              <div className="tfi-home-cta">
                <Button
                  variant="primary"
                  size="lg"
                  onClick={() => navigate("/browse")}
                  className="tfi-home-browse-btn"
                >
                  {ts("home.browseModelsButton")}
                </Button>
              </div>
            </div>
          )}
        </Stack>
      </Container>

      {/* Shared documentation links for llms.txt and agents.md */}
      <footer className="tfi-home-footer">
        <Container>
          <div className="tfi-home-footer-links">
            <a
              href="/llms.txt"
              target="_blank"
              rel="noreferrer"
              className="tfi-home-footer-link"
            >
              llms.txt
            </a>
            <span className="tfi-home-footer-separator" aria-hidden="true">·</span>
            <a
              href="/agents.md"
              target="_blank"
              rel="noreferrer"
              className="tfi-home-footer-link"
            >
              agents.md
            </a>
          </div>
        </Container>
      </footer>
    </Section>
  );
}
