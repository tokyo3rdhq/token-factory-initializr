import type { ModelEndpoint } from "../types";

interface ModelCardProps {
  endpoint: ModelEndpoint;
  selected?: boolean;
  onToggle?: (ep: ModelEndpoint) => void;
}

/**
 * Card for one ModelEndpoint. Renders provider, model id, name, and
 * a short list of modality tags + capabilities. When `onToggle` is
 * provided, the entire card is clickable (used by the Generate flow).
 */
export function ModelCard({ endpoint, selected, onToggle }: ModelCardProps) {
  const clickable = Boolean(onToggle);
  const architecture = endpoint.architecture;
  const modalities = architecture
    ? [
        ...architecture.input.map((m) => `in: ${m}`),
        ...architecture.output.map((m) => `out: ${m}`),
      ]
    : [];
  const capabilityKeys = Object.keys(endpoint.capabilities || {});

  const className = `model-card ${selected ? "selected" : ""}`;

  return (
    <div
      className={className}
      onClick={clickable ? () => onToggle!(endpoint) : undefined}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={
        clickable
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onToggle!(endpoint);
              }
            }
          : undefined
      }
    >
      <div className="row">
        <span className={`provider-pill ${providerClass(endpoint.provider)}`}>
          {endpoint.provider}
        </span>
        {!endpoint.free && <span className="tag">paid</span>}
      </div>
      <div className="name">{endpoint.name || endpoint.model_id}</div>
      <div className="id">{endpoint.model_id}</div>
      {endpoint.lab && <div className="muted">via {endpoint.lab}</div>}
      <div className="row">
        {modalities.map((m) => (
          <span key={m} className="tag">
            {m}
          </span>
        ))}
        {capabilityKeys.map((k) => (
          <span key={k} className="tag">
            {k}
          </span>
        ))}
        {endpoint.context_length && (
          <span className="tag">{fmtCtx(endpoint.context_length)}</span>
        )}
      </div>
    </div>
  );
}

function providerClass(provider: string): string {
  const p = provider.toLowerCase();
  if (p === "nvidia") return "nvidia";
  if (p === "amd") return "amd";
  return "huggingface";
}

function fmtCtx(n: number): string {
  if (n >= 1024 * 1024) return `${Math.round(n / (1024 * 1024))}M ctx`;
  if (n >= 1024) return `${Math.round(n / 1024)}K ctx`;
  return `${n} ctx`;
}