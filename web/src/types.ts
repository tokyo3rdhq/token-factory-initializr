// ModelEndpoint types — mirror of shared/schema/model.schema.json
// and data/models/schema.py. This file is the TS-side hand-rolled
// counterpart to the JSON schema; keep them in sync.

export interface ModelEndpoint {
  /** Provider identifier (e.g. "nvidia", "amd", "huggingface"). */
  provider: string;

  /** Provider-specific model id (e.g. "deepseek-ai/deepseek-v4.1-flash"). */
  model_id: string;

  /** Human-readable model name. */
  name: string | null;

  /** Optional longer description. */
  description: string | null;

  /** True iff the upstream provider offers free access. */
  free: boolean;

  /** Capability flags (chat, tool_calling, vision, speech, embedding, ...). */
  capabilities: Record<string, unknown>;

  /** Input / output modalities — null when upstream doesn't expose them. */
  architecture: { input: string[]; output: string[] } | null;

  /** Lab / organization (HF: owned_by, AMD: token_factory.publisher.name). */
  lab: string | null;

  /** Per-provider metadata — fields differ by provider; not canonicalized. */
  metadata: Record<string, unknown>;

  /** ISO 8601 timestamp when this endpoint was fetched. */
  fetched_at: string;

  /** Optional top-level context window length. */
  context_length?: number | null;

  /** Optional per-token pricing. */
  pricing?: Record<string, unknown> | null;
}

export interface ProviderSnapshot {
  provider: string;
  /** All endpoints for this provider (free + paid; UI filters client-side). */
  models: ModelEndpoint[];
  fetched_at: string;
}

export interface ManifestProvider {
  provider: string;
  count: number;
  status: "success" | "partial" | "failed" | "invalid";
  last_success?: string;
  error?: string;
}

export interface Manifest {
  version: string;
  generated_at: string;
  total: number;
  providers: Record<string, ManifestProvider>;
}

export interface GeneratedArtifact {
  /** Random 8-char id used in the public URL ``/generated/{id}``. */
  id: string;
  /** UTC epoch ms when this artifact was created. */
  created_at: number;
  /** UTC epoch ms when the artifact becomes unreachable. */
  expires_at: number;
  /** Source provider endpoints (selected by the user). */
  models: ModelEndpoint[];
  /** Rendered LiteLLM config (YAML). */
  config_yaml: string;
  /** Config format key (currently only "litellm"). */
  format: string;
}

/** Lifted to the top level because both KV and Functions use it. */
export const TTL_SECONDS = 300;