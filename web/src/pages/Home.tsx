import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Container, Section, Stack, Button, Card } from "@tokyo3rdhq/magi-design-system";

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
 * Layout primitives come from @tokyo3rdhq/magi-design-system
 * (Container, Section, Stack, Button). Color and accent come from
 * CSS custom properties via <ProductTheme accent="cyan">.
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
        <Stack gap="6" style={{ maxWidth: 720 }}>
          <span className="magi-eyebrow">Token Factory Initializr</span>
          <h1 className="magi-display" style={{ maxWidth: 720 }}>
            Initialize your token factory.
          </h1>
          <p className="magi-body-lg">
            Pick the free AI endpoints that fit your project. We generate
            ready-to-use configuration for LiteLLM.
          </p>
        </Stack>

        <div style={{ marginTop: "var(--magi-space-10)", maxWidth: 720 }}>
          <Card>
            <Stack gap="8">
              {/* Free-text project */}
              <Stack gap="2">
                <label className="tfi-field-label" htmlFor="req-project">
                  Project
                </label>
                <input
                  id="req-project"
                  className="tfi-input"
                  placeholder="e.g. Coding assistant"
                  value={useCase}
                  onChange={(e) => setUseCase(e.target.value)}
                />
              </Stack>

              <div style={{height: 1, background: "var(--magi-border)", margin: "var(--magi-space-7) 0"}} />

              {/* Two-column requirements grid */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "var(--magi-space-6)",
                }}
              >
                <Field label="Context">
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
                </Field>

                <Field label="Models">
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
                </Field>

                <Field label="Tool Calling">
                  <Segmented
                    value={toolCalling}
                    options={[
                      { value: "yes", label: "Yes" },
                      { value: "no", label: "No" },
                    ]}
                    onChange={(v) => setToolCalling(v as typeof toolCalling)}
                  />
                </Field>

                <Field label="Vision">
                  <Segmented
                    value={vision}
                    options={[
                      { value: "yes", label: "Yes" },
                      { value: "no", label: "No" },
                    ]}
                    onChange={(v) => setVision(v as typeof vision)}
                  />
                </Field>

                <Field label="Cost">
                  <Segmented
                    value={cost}
                    options={[
                      { value: "free", label: "Free only" },
                      { value: "any", label: "Any" },
                    ]}
                    onChange={(v) => setCost(v as typeof cost)}
                    accent
                  />
                </Field>

                <Field label="Providers">
                  <Stack direction="row" gap="2" wrap>
                    {(["nvidia", "amd", "huggingface"] as const).map((p) => (
                      <Segmented
                        key={p}
                        value={providers.includes(p) ? p : ""}
                        options={[{ value: p, label: p }]}
                        onChange={() => toggleProvider(p)}
                        accent
                        multi
                      />
                    ))}
                  </Stack>
                </Field>
              </div>

              <div style={{height: 1, background: "var(--magi-border)", margin: "var(--magi-space-7) 0"}} />

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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Stack gap="2">
      <span className="tfi-field-label">{label}</span>
      <div>{children}</div>
    </Stack>
  );
}

function Segmented({
  value,
  options,
  onChange,
  accent = false,
  multi = false,
}: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
  accent?: boolean;
  multi?: boolean;
}) {
  return (
    <div className="tfi-segmented">
      {options.map((opt) => {
        const active = multi ? true : value === opt.value;
        const className = `tfi-segmented-item${active ? " active" : ""}${accent ? " accent" : ""}`;
        return (
          <button
            key={opt.value}
            type="button"
            className={className}
            onClick={() => {
              if (multi) onChange(opt.value);
              else if (value !== opt.value) onChange(opt.value);
            }}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}


