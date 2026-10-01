import { useState } from "react";
import { useNavigate } from "react-router-dom";
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

/**
 * Home — the entry point.
 *
 * Structure follows the MAGI hero pattern:
 *   [eyebrow]
 *   display headline
 *   subhead
 *   [requirements card]
 *
 * All primitives (FormField / Input / Segmented / Checkbox) come from
 * @tokyo3rdhq/magi-design-system. Accent propagates via
 * <AppTheme accent="cyan">. Strings are routed through the i18n
 * provider so the same component tree serves both English and
 * Chinese visitors.
 */
export function HomePage() {
  const navigate = useNavigate();
  const { ts, dict } = useI18n();

  const [useCase, setUseCase] = useState("");
  const [contextMin, setContextMin] = useState<'128k' | '32k' | '8k' | 'any'>(
    '128k',
  );
  const [toolCalling, setToolCalling] = useState<'yes' | 'no'>('yes');
  const [vision, setVision] = useState<'yes' | 'no'>('no');
  const [cost, setCost] = useState<'free' | 'any'>('free');
  const [providers, setProviders] = useState<string[]>(["nvidia", "huggingface"]);
  const [endpointCount, setEndpointCount] = useState<number>(3);

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
    setProviders(["nvidia", "huggingface"]);
    setEndpointCount(3);
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
            <Button variant="secondary" onClick={onReset}>
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
    </Section>
  );
}