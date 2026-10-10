import { useState } from "react";
import { useNavigate } from "react-router-dom";

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
    <Section spacing="lg">
      <Container>
        <Stack gap="6" className="tfi-home-hero">
          <span className="magi-eyebrow">{ts("home.eyebrow")}</span>
          <h1 className="magi-display">{ts("home.headline")}</h1>
          <p className="magi-body-lg tfi-home-hero-subhead">{ts("home.subhead")}</p>

          {/* Tab switcher - Agent vs Human */}
          <Segmented
            value={tab}
            onChange={(v) => setTab(v as "agent" | "human")}
            options={[
              { value: "agent", label: ts("home.agentTab") },
              { value: "human", label: ts("home.humanTab") },
            ]}
            className="tfi-home-tabs"
          />

          {/* Agent tab panel */}
          {tab === "agent" && (
            <Stack gap="4" className="tfi-home-agent-panel">
              <pre
                className="magi-code tfi-home-prompt"
                data-testid="home-agent-prompt"
                aria-label="Agent bootstrap prompt"
              >
                <code>{dict.home.agentPromptInline}</code>
              </pre>

              <Stack
                direction="row"
                align="center"
                gap="3"
                className="tfi-home-agent-actions"
              >
                <Button
                  variant="primary"
                  onClick={onCopy}
                  data-testid="home-agent-copy"
                  aria-label={ts("home.agentCopyButton")}
                >
                  {copied ? ts("home.agentCopiedLabel") : ts("home.agentCopyButton")}
                </Button>
              </Stack>
            </Stack>
          )}

          {/* Human tab panel */}
          {tab === "human" && (
            <div className="tfi-home-steps">
              <ol>
                <li className="tfi-home-step">
                  <h3 className="magi-h4">{ts("home.step1Title")}</h3>
                  <p className="magi-body-md">{ts("home.step1Desc")}</p>
                </li>
                <li className="tfi-home-step">
                  <h3 className="magi-h4">{ts("home.step2Title")}</h3>
                  <p className="magi-body-md">{ts("home.step2Desc")}</p>
                </li>
                <li className="tfi-home-step">
                  <h3 className="magi-h4">{ts("home.step3Title")}</h3>
                  <p className="magi-body-md">{ts("home.step3Desc")}</p>
                </li>
              </ol>
              <div className="tfi-home-cta">
                <Button
                  variant="primary"
                  onClick={() => navigate("/browse")}
                >
                  {ts("home.browseModelsButton")}
                </Button>
              </div>
            </div>
          )}
        </Stack>
      </Container>

      {/* Shared footer links */}
      <div className="tfi-home-footer">
        <Stack direction="row" gap="6" align="center">
          <a
            href="/llms.txt"
            target="_blank"
            rel="noreferrer"
            className="magi-caption tfi-footer-link"
          >
            llms.txt
          </a>
          <span className="magi-caption tfi-footer-separator">|</span>
          <a
            href="/agents.md"
            target="_blank"
            rel="noreferrer"
            className="magi-caption tfi-footer-link"
          >
            agents.md
          </a>
        </Stack>
      </div>
    </Section>
  );
}
