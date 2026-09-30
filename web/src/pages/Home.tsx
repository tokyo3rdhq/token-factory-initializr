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
 * @tokyo3rdhq/magi-design-system@^0.2.0. Accent propagates via
 * <ProductTheme accent="cyan">.
 */
export function HomePage() {
  const navigate = useNavigate();

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
      capabilities: {
        toolCalling: toolCalling === "yes",
        vision: vision === "yes",
      },
      contextWindow: {
        min: contextMin === "128k" ? 131072 : contextMin === "32k" ? 32768 : 8192,
      },
      pricing: { free: cost === "free" },
      providers,
      endpointCount,
    };
    if (useCase.trim()) {
      req.useCases = [useCase.trim()];
    }
    navigate("/browse", { state: { requirement: req } });
  };

  return (
    <Section spacing="lg">
      <Container>
        {/* Hero — left-aligned, narrower content block (~720px) to match
         * magi-portal's hero rhythm. The main site uses a left-aligned
         * hero on a wider page, with the content block constrained to
         * ~720px and left-aligned. tfi was previously centered at 1024px
         * which felt "too wide" relative to the main site.
         *
         * Accent stays cyan per spec §5 ("Token Factory Initializr = cyan
         * accent"); only spacing + alignment follow the main site. */}
        <Stack gap="6" style={{ maxWidth: 720, textAlign: "left" }}>
          <span className="magi-eyebrow">Token Factory Initializr</span>
          <h1 className="magi-display">
            Initialize your token factory.
          </h1>
          <p className="magi-body-lg" style={{ maxWidth: 600 }}>
            Pick the free AI endpoints that fit your project. We generate
            ready-to-use configuration for LiteLLM.
          </p>
          <Stack
            direction="row"
            gap="4"
            align="center"
            style={{ marginTop: "var(--magi-space-3)" }}
          >
            <Button variant="primary" onClick={onContinue}>
              Browse models →
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                // Reset to default requirements and scroll to form
                setUseCase("");
                setContextMin("128k");
                setToolCalling("yes");
                setVision("no");
                setCost("free");
                setProviders(["nvidia", "huggingface"]);
                setEndpointCount(3);
              }}
            >
              Reset
            </Button>
          </Stack>
        </Stack>

        <div
          style={{
            margin: "var(--magi-space-10) auto 0",
            maxWidth: 720,
          }}
        >
          <Card>
            <Stack gap="8">
              {/* Free-text project */}
              <FormField label="Project">
                <Input
                  id="req-project"
                  placeholder="e.g. Coding assistant"
                  value={useCase}
                  onChange={(e) => setUseCase(e.target.value)}
                />
              </FormField>

              <div style={{height: 1, background: "var(--magi-border)", margin: "var(--magi-space-6) 0"}} />

              {/* Two-column requirements grid */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "var(--magi-space-6)",
                }}
              >
                <FormField label="Context">
                  <Segmented
                    value={contextMin}
                    options={[
                      { value: "128k", label: "128K+" },
                      { value: "32k", label: "32K+" },
                      { value: "8k", label: "8K+" },
                      { value: "any", label: "Any" },
                    ]}
                    onChange={(v) => setContextMin(v as typeof contextMin)}
                  />
                </FormField>

                <FormField
                  label="Max models"
                  helper="How many models to include in the recommended bucket (1–10)."
                >
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

                <FormField label="Tool Calling">
                  <Segmented
                    value={toolCalling}
                    options={[
                      { value: "yes", label: "Yes" },
                      { value: "no", label: "No" },
                    ]}
                    onChange={(v) => setToolCalling(v as typeof toolCalling)}
                  />
                </FormField>

                <FormField label="Vision">
                  <Segmented
                    value={vision}
                    options={[
                      { value: "yes", label: "Yes" },
                      { value: "no", label: "No" },
                    ]}
                    onChange={(v) => setVision(v as typeof vision)}
                  />
                </FormField>

                <FormField label="Cost">
                  <Segmented
                    value={cost}
                    options={[
                      { value: "free", label: "Free only" },
                      { value: "any", label: "Any" },
                    ]}
                    onChange={(v) => setCost(v as typeof cost)}
                    accent
                  />
                </FormField>

                <FormField
                  label="Providers"
                  helper="Tick the providers whose endpoints you want included."
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
              </div>

              <div style={{height: 1, background: "var(--magi-border)", margin: "var(--magi-space-6) 0"}} />

              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: "var(--magi-space-4)",
                }}
              >
                <span className="magi-body-sm">
                  We'll match {endpointCount} model
                  {endpointCount === 1 ? "" : "s"} from {providers.length} provider
                  {providers.length === 1 ? "" : "s"}.
                </span>
                <Button variant="primary" onClick={onContinue}>
                  Browse models →
                </Button>
              </div>
            </Stack>
          </Card>
        </div>
      </Container>
    </Section>
  );
}

