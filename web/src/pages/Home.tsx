import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bot, X } from "lucide-react";
import {
  Container,
  Section,
  Stack,
  Button,
  Card,
  Checkbox,
  FormField,
  Input,
  Segmented,
} from "@tokyo3rdhq/magi-design-system";

import type { ModelRequirement } from "../types";
import { useI18n } from "../I18nProvider";
import { useSeo } from "../seo/useSeo";

/**
 * Home — the entry point.
 *
 * Structure follows the MAGI hero pattern:
 *   [eyebrow]
 *   display headline
 *   subhead
 *   [primary CTA: Browse]
 *   [secondary CTA: I'm an Agent] → opens AgentDialog
 *   [requirements card]
 *
 * All primitives (FormField / Input / Segmented / Checkbox) come from
 * @tokyo3rdhq/magi-design-system. Accent propagates via
 * <AppTheme accent="cyan">. Strings are routed through the i18n
 * provider so the same component tree serves both English and
 * Chinese visitors.
 *
 * Agent Access entry (§2 / §3 / §4 of tfi_homepage_agent_access.md):
 * the "I'm an Agent" button is a secondary CTA, visually quieter
 * than the primary "Browse models" CTA, and opens a lightweight
 * inline dialog with the canonical bootstrap prompt + Copy button +
 * a secondary link to /agents.md.
 */
export function HomePage() {
  const navigate = useNavigate();
  const { ts, dict } = useI18n();
  // Per docs/tfi_seo_optimization.md §6 — bind the route's metadata
  // (title, description, canonical, og:*, twitter:*) to document.head
  // on mount + on every route change. Static <head> in index.html
  // still carries the homepage baseline for crawlers that don't run
  // JavaScript at all.
  useSeo("/");

  const [useCase, setUseCase] = useState("");
  const [contextMin, setContextMin] = useState<'128k' | '32k' | '8k' | 'any'>(
    '128k',
  );
  const [toolCalling, setToolCalling] = useState<'yes' | 'no'>('yes');
  const [vision, setVision] = useState<'yes' | 'no'>('no');
  const [cost, setCost] = useState<'free' | 'any'>('free');
  const [providers, setProviders] = useState<string[]>(["nvidia", "amd", "huggingface"]);
  const [endpointCount, setEndpointCount] = useState<number>(5);

  // Agent Access dialog state. Local to HomePage (not a global modal
  // system per doc §4) — when the spec asks for a dialog primitive
  // we promote it.
  const [agentOpen, setAgentOpen] = useState(false);
  const [agentCopied, setAgentCopied] = useState(false);

  const toggleProvider = (p: string) => {
    setProviders((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p],
    );
  };

  const onContinue = () => {
    const req: ModelRequirement = {
      useCases: useCase ? [useCase] : undefined,
      contextWindow: contextMin === "any" ? undefined : { min: parseInt(contextMin) * 1024 },
      capabilities: {
        toolCalling: toolCalling === "yes" ? true : undefined,
        vision: vision === "yes" ? true : undefined,
      },
      pricing: cost === "free" ? { free: true } : undefined,
      providers,
      endpointCount,
    };
    navigate("/browse", { state: { requirement: req } });
  };

  const onReset = () => {
    setUseCase("");
    setContextMin('128k');
    setToolCalling('yes');
    setVision('no');
    setCost('free');
    setProviders(["nvidia", "amd", "huggingface"]);
    setEndpointCount(5);
  };

  return (
    <Section spacing="lg">
      <Container>
        <Stack gap="6" className="tfi-page-hero">
          <span className="magi-eyebrow">{ts("home.eyebrow")}</span>
          <h1 className="magi-display">{ts("home.headline")}</h1>
          <p className="magi-body-lg tfi-page-hero-subhead">
            {ts("home.subhead")}
          </p>
          <Stack direction="row" gap="4" align="center" className="tfi-page-cta-row">
            <Button variant="primary" onClick={onContinue}>
              {ts("home.ctaBrowse")}
            </Button>
            {/* §3 — secondary access path. Visually quieter than the
             * primary CTA per spec; variant="secondary" already does
             * that, and we sit it alongside (not below) Browse so the
             * primary action still leads. */}
            <Button
              variant="secondary"
              onClick={() => setAgentOpen(true)}
              aria-haspopup="dialog"
              data-testid="home-agent-entry"
            >
              <Bot size={16} aria-hidden="true" />
              {ts("home.ctaAgent")}
            </Button>
            <Button variant="ghost" onClick={onReset}>
              {ts("home.ctaReset")}
            </Button>
          </Stack>
        </Stack>

        <Card className="tfi-page-requirements-card">
          <Stack gap="6">
            <FormField label={ts("home.fields.project")}>
              <Input
                value={useCase}
                onChange={(e) => setUseCase(e.target.value)}
                placeholder={ts("home.fields.projectPlaceholder")}
              />
            </FormField>

            <div className="tfi-form-grid-2col">
              <FormField label={ts("home.fields.context")}>
                <Segmented
                  value={contextMin}
                  options={[
                    { value: "128k", label: ts("home.fields.contextMin128k") },
                    { value: "32k", label: ts("home.fields.contextMin32k") },
                    { value: "8k", label: ts("home.fields.contextMin8k") },
                    { value: "any", label: ts("home.fields.contextMinAny") },
                  ]}
                  onChange={(v) => setContextMin(v as typeof contextMin)}
                />
              </FormField>

              <FormField label={ts("home.fields.maxModels")} helper={ts("home.fields.maxModelsHelper")}>
                <Segmented
                  value={String(endpointCount)}
                  options={[
                    { value: "1", label: "1" },
                    { value: "3", label: "3" },
                    { value: "5", label: "5" },
                    { value: "10", label: "10" },
                  ]}
                  onChange={(v) => setEndpointCount(Number(v))}
                />
              </FormField>
            </div>

            <div className="tfi-form-grid-3col">
              <FormField label={ts("home.fields.toolCalling")}>
                <Segmented
                  value={toolCalling}
                  options={[
                    { value: "yes", label: ts("home.fields.toolCallingYes") },
                    { value: "no", label: ts("home.fields.toolCallingNo") },
                  ]}
                  onChange={(v) => setToolCalling(v as typeof toolCalling)}
                />
              </FormField>

              <FormField label={ts("home.fields.vision")}>
                <Segmented
                  value={vision}
                  options={[
                    { value: "yes", label: ts("home.fields.visionYes") },
                    { value: "no", label: ts("home.fields.visionNo") },
                  ]}
                  onChange={(v) => setVision(v as typeof vision)}
                />
              </FormField>

              <FormField label={ts("home.fields.cost")}>
                <Segmented
                  value={cost}
                  options={[
                    { value: "free", label: ts("home.fields.costFree") },
                    { value: "any", label: ts("home.fields.costAny") },
                  ]}
                  onChange={(v) => setCost(v as typeof cost)}
                  accent
                />
              </FormField>
            </div>

            <FormField
              label={ts("home.fields.providers")}
              helper={ts("home.fields.providersHelper")}
            >
              <Stack direction="row" gap="6">
                {(["nvidia", "amd", "huggingface"] as const).map((p) => (
                  <Checkbox
                    key={p}
                    checked={providers.includes(p)}
                    onChange={() => toggleProvider(p)}
                  >
                    {p}
                  </Checkbox>
                ))}
              </Stack>
            </FormField>

            <Stack
              direction="row"
              align="center"
              gap="3"
              className="tfi-bottom-row"
            >
              <span className="magi-caption tfi-caption-secondary">
                {dict.home.summaryTemplate(endpointCount, providers.length)}
              </span>
              <Button variant="primary" onClick={onContinue}>
                {ts("home.ctaBrowse")}
              </Button>
            </Stack>
          </Stack>
        </Card>
      </Container>

      {agentOpen && (
        <AgentDialog
          blurb={ts("home.agentBlurb")}
          heading={ts("home.agentHeading")}
          prompt={ts("home.agentPrompt")}
          copyLabel={ts("home.agentCopy")}
          copiedLabel={ts("home.agentCopied")}
          readGuideLabel={ts("home.agentReadGuide")}
          closeLabel={ts("home.agentClose")}
          copiedFlag={agentCopied}
          onCopied={() => {
            setAgentCopied(true);
            window.setTimeout(() => setAgentCopied(false), 1500);
          }}
          onClose={() => setAgentOpen(false)}
        />
      )}
    </Section>
  );
}

// ---------------------------------------------------------------------------
// AgentDialog — local modal built on existing primitives (Card + Stack +
// design-system tokens). No new global modal system per doc §4 — this is
// the only consumer in the app.
//
// Structure:
//   [backdrop]
//     [Card dialog]
//       [header: heading + close]
//       [blurb]
//       [code block: prompt (selectable, monospace)]
//       [footer: Read Agent Guide link + Copy Prompt button]
//
// a11y per doc §18:
//   - role="dialog" + aria-modal="true" + aria-labelledby
//   - focus moves to dialog on open
//   - Esc closes
//   - close button has accessible name
//   - backdrop click closes
// ---------------------------------------------------------------------------

interface AgentDialogProps {
  heading: string;
  blurb: string;
  prompt: string;
  copyLabel: string;
  copiedLabel: string;
  readGuideLabel: string;
  closeLabel: string;
  copiedFlag: boolean;
  onCopied: () => void;
  onClose: () => void;
}

function AgentDialog({
  heading,
  blurb,
  prompt,
  copyLabel,
  copiedLabel,
  readGuideLabel,
  closeLabel,
  copiedFlag,
  onCopied,
  onClose,
}: AgentDialogProps) {
  // Esc to close — doc §18.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Move focus into the dialog on open so keyboard users land in
  // the right place. The close button is the natural first stop —
  // it's a destructive-by-default interaction, putting it first
  // would be wrong. We focus the prompt container instead so Tab
  // walks into Copy → Read Guide → Close.
  const dialogRef = useDialogFocus();

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(prompt);
      onCopied();
    } catch {
      // Clipboard API may be blocked (insecure context / permission
      // denied). Leave copiedFlag false so the user knows nothing
      // happened. They can still select the prompt body manually.
    }
  };

  return (
    <div
      className="tfi-agent-backdrop"
      onClick={onClose}
      data-testid="home-agent-backdrop"
    >
      <Card
        className="tfi-agent-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tfi-agent-heading"
        ref={dialogRef as never}
        onClick={(e: { stopPropagation: () => void }) => e.stopPropagation()}
      >
        <Stack gap="4">
          <Stack
            direction="row"
            align="center"
            gap="3"
            style={{ justifyContent: "space-between" }}
          >
            <h2 id="tfi-agent-heading" className="magi-h3">
              {heading}
            </h2>
            <Button
              size="sm"
              variant="ghost"
              onClick={onClose}
              aria-label={closeLabel}
              data-testid="home-agent-close"
            >
              <X size={16} aria-hidden="true" />
            </Button>
          </Stack>
          <p className="magi-body-md tfi-agent-blurb">{blurb}</p>

          {/*
            The prompt block uses a real <pre>/<code> pair so screen
            readers announce it as preformatted text AND the content
            remains selectable for the rare cases where the user copies
            by hand. Per doc §9 — "must remain selectable".
          */}
          <pre
            className="magi-code tfi-agent-prompt"
            data-testid="home-agent-prompt"
            aria-label="Agent bootstrap prompt"
          >
            <code>{prompt}</code>
          </pre>

          <Stack
            direction="row"
            align="center"
            gap="3"
            style={{ justifyContent: "flex-end" }}
            className="tfi-agent-footer"
          >
            {/* §11 — secondary link to the canonical Agent guide.
                    Doesn't compete with Copy Prompt visually. */}
            <a
              className="tfi-agent-guide-link"
              href="/agents.md"
              target="_blank"
              rel="noreferrer"
            >
              {readGuideLabel}
            </a>
            <Button
              variant="primary"
              onClick={onCopy}
              data-testid="home-agent-copy"
            >
              {copiedFlag ? copiedLabel : copyLabel}
            </Button>
          </Stack>
        </Stack>
      </Card>
    </div>
  );
}

/**
 * Tiny focus-into-dialog helper. Returns a ref the consumer attaches
 * to the dialog container. On mount we focus the first focusable
 * element inside; on unmount we restore focus to whatever was
 * focused before (typically the "I'm an Agent" trigger button).
 */
function useDialogFocus() {
  const [node, setNode] = useState<HTMLElement | null>(null);
  useEffect(() => {
    if (!node) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const firstFocusable = node.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    firstFocusable?.focus();
    return () => {
      // Restore focus to the opener so keyboard users don't get
      // stranded after the dialog disappears.
      previouslyFocused?.focus?.();
    };
  }, [node]);
  return { ref: setNode };
}