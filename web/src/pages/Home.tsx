import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ModelRequirement } from "../types";

/**
 * Requirements form — the first page in the new flow.
 *
 * Replaces the previous "browse + click-to-select" home with a single
 * form that captures the user's intent as a ``ModelRequirement``
 * shape. On submit, the requirement is pushed to the next route
 * (``/browse``), which evaluates it against the live catalog and
 * presents a Recommended / Other split.
 *
 * Field shapes map 1:1 to ``shared/schema/model_requirement.schema.json``.
 */
export function HomePage() {
  const navigate = useNavigate();

  // --- form state ---
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
      pricing: {
        free: cost === "free",
      },
      providers,
      endpointCount,
    };
    if (useCase.trim()) {
      req.useCases = [useCase.trim()];
    }
    navigate("/browse", { state: { requirement: req } });
  };

  return (
    <div className="layout-stack" style={{ maxWidth: 560, margin: "0 auto" }}>
      <header>
        <h1 style={{ margin: "0 0 4px 0", fontSize: 22 }}>What are you building?</h1>
        <p className="muted" style={{ margin: 0 }}>
          Tell us what you're building. We'll pick the right free models for you.
        </p>
      </header>

      <section className="card layout-stack" style={{ gap: 16 }}>
        {/* Free-text use case */}
        <label className="layout-stack" style={{ gap: 6 }}>
          <span className="section-title">Project</span>
          <input
            className="btn"
            style={{ width: "100%", textAlign: "left" }}
            placeholder="e.g. Coding assistant"
            value={useCase}
            onChange={(e) => setUseCase(e.target.value)}
          />
        </label>

        <div className="muted" style={{ fontSize: 12, margin: "8px 0 0 0" }}>
          Requirements
        </div>

        {/* Context Window */}
        <Field label="Context">
          <div className="tabs">
            {(["128k+", "32k+", "8k+", "any"] as const).map((opt) => (
              <button
                key={opt}
                className={`tab ${
                  contextMin ===
                  (opt === "128k+" ? "128k" : opt === "32k+" ? "32k" : opt === "8k+" ? "8k" : "any")
                    ? "active"
                    : ""
                }`}
                onClick={() =>
                  setContextMin(
                    opt === "128k+" ? "128k" : opt === "32k+" ? "32k" : opt === "8k+" ? "8k" : "any",
                  )
                }
              >
                {opt}
              </button>
            ))}
          </div>
        </Field>

        {/* Tool Calling */}
        <Field label="Tool Calling">
          <div className="tabs">
            {(["yes", "no"] as const).map((opt) => (
              <button
                key={opt}
                className={`tab ${toolCalling === opt ? "active" : ""}`}
                onClick={() => setToolCalling(opt)}
              >
                {opt}
              </button>
            ))}
          </div>
        </Field>

        {/* Vision */}
        <Field label="Vision">
          <div className="tabs">
            {(["yes", "no"] as const).map((opt) => (
              <button
                key={opt}
                className={`tab ${vision === opt ? "active" : ""}`}
                onClick={() => setVision(opt)}
              >
                {opt}
              </button>
            ))}
          </div>
        </Field>

        {/* Cost */}
        <Field label="Cost">
          <div className="tabs">
            {(["free", "any"] as const).map((opt) => (
              <button
                key={opt}
                className={`tab ${cost === opt ? "active" : ""}`}
                onClick={() => setCost(opt)}
              >
                {opt}
              </button>
            ))}
          </div>
        </Field>

        {/* Providers */}
        <Field label="Providers">
          <div className="tabs">
            {["nvidia", "amd", "huggingface"].map((p) => (
              <button
                key={p}
                className={`tab ${providers.includes(p) ? "active" : ""}`}
                onClick={() => toggleProvider(p)}
              >
                {p}
              </button>
            ))}
          </div>
        </Field>

        {/* Number of models */}
        <Field label="Models">
          <div className="tabs">
            {[1, 3, 5, 10].map((n) => (
              <button
                key={n}
                className={`tab ${endpointCount === n ? "active" : ""}`}
                onClick={() => setEndpointCount(n)}
              >
                {n}
              </button>
            ))}
          </div>
        </Field>

        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
          <button className="btn btn-primary" onClick={onContinue}>
            Continue →
          </button>
        </div>
      </section>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "110px 1fr",
        gap: 12,
        alignItems: "center",
      }}
    >
      <span className="muted" style={{ fontSize: 13 }}>
        {label}
      </span>
      <div>{children}</div>
    </div>
  );
}