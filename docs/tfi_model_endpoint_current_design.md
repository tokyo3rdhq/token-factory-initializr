# TFI Model & Endpoint Data Structure Design (Current)

> **Status**: Current as of 2026-10-26  
> **Scope**: Canonical model/endpoint schema, public API projection, and generator mappings

---

## 1. Canonical ModelEndpoint (Internal / KV)

Defined in `data/models/schema.py` (Python) and `web/functions/lib/kv.ts` (TypeScript). This is the **source of truth** stored in Cloudflare KV.

### 1.1 Core Identity Fields (Required)

| Field | Type | Description |
|-------|------|-------------|
| `provider` | `string` | Provider name (e.g., `nvidia`, `amd`, `novita`, `together`, `huggingface`, `ollama`). **Not** the data source — a single data source can fan out to multiple providers. |
| `model_id` | `string` | Provider-specific model identifier (e.g., `deepseek-ai/deepseek-v4.1-flash`). |
| `free` | `bool` | **Endpoint-level** free status. There is NO model-level free flag. |
| `fetched_at` | `datetime` / ISO string | When this endpoint record was created/updated. |

### 1.2 Source Attribution (Required)

| Field | Type | Description |
|-------|------|-------------|
| `data_source` | `string` | The catalog TFI discovered this through (`nvidia`, `amd`, `huggingface`, `openrouter`, `kilo`, `ollama`, `models_dev`). **Not** derived from provider — e.g., HF router models have `data_source="huggingface"` but `provider="novita"`. |

### 1.3 Optional Human Metadata

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string \| null` | Human-readable name (e.g., "DeepSeek V4.1 Flash"). |
| `description` | `string \| null` | Free-text description. |
| `lab` | `string \| null` | Creator organization (HF: `owned_by`, AMD: `token_factory.publisher.name`, NVIDIA: empty). |

### 1.4 Capabilities & Architecture

| Field | Type | Description |
|-------|------|-------------|
| `capabilities` | `Record<string, unknown>` | Canonical normalized capabilities: `chat`, `vision`, `speech`, `embedding`, `translation`, `decision`. Object with boolean flags. |
| `architecture` | `{ input: string[], output: string[] } \| null` | Input/output modalities. HF router shape: `architecture.{input,output}_modalities`. NVIDIA derives from capabilities. |
| `supported_parameters` | `string[]` | Endpoint-level runtime params: `tool_calling`, `reasoning`, `structured_output`, `streaming`. **Endpoint-scoped** — never promoted to siblings. Populated only from explicit source signals. |

### 1.5 Provider-Specific Metadata (Opaque)

| Field | Type | Description |
|-------|------|-------------|
| `metadata` | `Record<string, unknown>` | Per-provider opaque bag. **Consumers MUST branch on `provider` first.** Examples:<br/>• AMD: `{family, context_length, free_status, original_id}`<br/>• HF: `{router_provider, context_length, supports_tools, first_token_latency_ms, throughput}`<br/>• NVIDIA: `{raw_obj?, attributes?, labels?}` |

### 1.6 Future / Enrichment Fields (Optional)

| Field | Type | Description |
|-------|------|-------------|
| `canonical_model_id` | `string \| null` | Future: unified model identity across sources. |
| `model_family` | `string \| null` | Model family grouping. |
| `organization` | `string \| null` | Publisher org. |
| `version` | `string \| null` | Model version. |
| `context_length` | `number \| null` | Context window (tokens). Lifted from HF `architecture` / AMD `provider_pricing`. |
| `license` | `string \| null` | License string. |
| `quantization` | `string \| null` | Quantization format (e.g., `AWQ-4bit`). |
| `pricing` | `dict \| null` | Per-token prices (string-encoded scientific notation). AMD: `provider_pricing[0].pricing`. HF/NVIDIA: `null`. **`free` flag is the cost signal — non-null pricing ≠ paid.** |
| `endpoint_url` | `string \| null` | Endpoint base URL (rarely populated). |
| `region` | `string \| null` | Geographic region. |
| `source_url` | `string \| null` | Human-readable source page (e.g., `https://build.nvidia.com/...`). Normalized via `normalize_source_url`. |
| `status` | `string \| null` | Endpoint lifecycle status. |
| `limits` | `dict \| null` | Rate/quota limits (`{scope, subject, rpm, rpd, tpm}`). |
| `score` | `float \| null` | Quality/ranking score. |

### 1.7 Provenance Tracking

| Field | Type | Description |
|-------|------|-------------|
| `provenance` | `dict<field_path, FieldProvenance>` | Per-field audit trail. Key = dotted path (e.g., `capabilities.input_modalities`). Value = `FieldProvenance{source, source_id, source_field, method, confidence, observed_at}`. Method ∈ {`native`, `enriched`, `normalized`, `inferred`, `derived`}. |

---

## 2. Public API Projection (`/api/v1/models`)

Defined in `web/functions/lib/projection.ts`. This is the **public API contract** — strict subset of canonical fields, never provenance or raw payloads.

### 2.1 `PublicModel` (List Item)

```typescript
interface PublicModel {
  id: string;                          // Canonical model_id (e.g., "deepseek-ai/deepseek-v4")
  object: "model";
  created: number;                      // Unix epoch (0 when unknown)
  owned_by?: string;                    // Derived from `lab` or model_id prefix
  data_source: string;                  // TFI data source of FIRST endpoint
  provider: string;                     // Provider of FIRST endpoint
  capabilities: string[];               // Normalized capability keys
  supported_parameters?: string[];      // Union of params across ALL endpoints
  name?: string;
  description?: string;
  architecture?: { input: string[]; output: string[] };
  context_length?: number;
  lab?: string;
  source_url?: string;
  endpoints: PublicModelEndpoint[];     // One per provider endpoint
}
```

**Key Design**: 
- `free` is **NOT** at model level — endpoint-specific only.
- `data_source` / `provider` reflect the **first** endpoint only.
- `endpoints[]` carries per-endpoint details.

### 2.2 `PublicModelEndpoint` (Nested)

```typescript
interface PublicModelEndpoint {
  id: string;                    // "{provider}:{endpoint_name}" e.g. "huggingface:together"
  provider: string;              // e.g., "together"
  model_id: string;              // Provider-specific model_id
  free: boolean;                 // ENDPOINT-specific free status
  pricing?: Record<string, unknown> | null;
  limits?: Record<string, unknown> | null;
  supported_parameters?: string[]; // Endpoint-scoped, never promoted
}
```

**Key Design**: 
- `free` is **endpoint-scoped** — same model can be free on one provider, paid on another.
- `pricing` / `limits` are endpoint-scoped.
- `supported_parameters` never promoted to siblings.

### 2.3 `PublicEndpoint` (Separate Endpoint Catalog)

```typescript
interface PublicEndpoint {
  id: string;                    // "{provider}:{endpoint_name}" e.g., "huggingface:together"
  provider: string;
  data_source: string;
  protocol?: string;
  base_url?: string;             // Public API base URL
  authentication?: {
    type: string;                // "none" | "bearer" | "api_key" | "oauth2" | "custom" | "unknown"
    credential_required?: boolean;
  };
  status?: string;               // "active" | "degraded" | "temporarily_unavailable" | "deprecated" | "unknown"
  limits?: { scope?, subject?, rpm?, rpd?, tpm? };
  models?: string[];             // Model IDs served by this endpoint
}
```

---

## 3. Generator Output Formats

### 3.1 LiteLLM (`web/functions/lib/generators/litellm.ts`)

**Output**: YAML with `model_list: [{ model_name, litellm_params: { model, api_key, api_base? } }]`

**Model ID Mapping** (per `LITELLM_DATA_SOURCE_PREFIX`):

| Data Source | Prefix | Example |
|-------------|--------|---------|
| `nvidia` | `nvidia_nim/` | `nvidia_nim/deepseek-ai/deepseek-v4.1-flash` |
| `amd` | `openai/` | `openai/Meta-Llama-3.1-8B-Instruct` |
| `huggingface` | `huggingface/<provider>/` | `huggingface/together/meta-llama/Llama-3.3-70B-Instruct` |
| `openrouter` | `openrouter/` | `openrouter/deepseek/deepseek-r1` |
| `kilo` | `openai/` | `openai/kilo-auto/glm-5-3` |
| `ollama` | `ollama_chat/` | `ollama_chat/minimax-m3.1-flash` |

**Decision Models** (output modality contains `decision`):  
Prefix `hosted_vllm/` regardless of data source. e.g., `hosted_vllm/Clef`.

**API Key**: Always `os.environ/<PROVIDER>_API_KEY` (never literal keys).

### 3.2 NewAPI (`web/functions/lib/generators/newapi.ts`)

**Output**: JSON `{ models: [{ id: "<provider>/<model_id>", name: "<provider>-<slug>" }] }`

### 3.3 Bifrost (`web/functions/lib/generators/bifrost.ts`)

**Output**: JSON `{ $schema, providers: { <provider>: { keys: [...], custom_provider_config?, network_config? } } }`

- Native providers (built-in): `huggingface`, `groq`, `openrouter` → only `keys[]`
- Custom OpenAI-compatible: `nvidia`, `amd`, `kilo`, `ollama` → `custom_provider_config: { base_provider_type: "openai" }` + `network_config.base_url`

### 3.4 Magpie (`web/functions/lib/generators/magpie.ts`)

**Output**: JSON `{ providers: [{ id, name, icon?, preset?, catalog?, website?, keysUrl?, key, chat, models[], pickedFrom[] }] }`

| Field | Source |
|-------|--------|
| `key` | Always `""` (user fills in Magpie) |
| `pickedFrom` | **All** model IDs currently available in TFI for that data source (full catalog) |
| `models` | Only user-selected models for that source |
| `chat` | From `resolveBaseUrl(data_source, provider)` via `dataSources.ts` |

---

## 4. Data Source Registry (Single Source of Truth)

Defined in `web/functions/lib/dataSources.ts`.

### Data Source Registry (`DATA_SOURCE_REGISTRY`)

| Data Source | `baseUrl` | `protocol` | `isRouterSource` | `proxy` | `apiKeyEnv` | `isConsumerFacing` |
|-------------|-----------|------------|------------------|---------|-------------|-------------------|
| `nvidia` | `https://integrate.api.nvidia.com/v1` | `nim` | false | — | `NVIDIA_API_KEY` | true |
| `amd` | `https://developer.amd.com.cn/radeon/api/v1` | `openai-compatible` | false | — | `AMD_API_KEY` | true |
| `huggingface` | `https://router.huggingface.co/v1` | `huggingface` | **true** | `http://127.0.0.1:7897` | `HUGGING_FACE_API_KEY` | true |
| `openrouter` | `https://openrouter.ai/api/v1` | `openai-compatible` | false | — | `OPENROUTER_API_KEY` | true |
| `kilo` | `https://api.kilo.ai/api/gateway` | `openai-compatible` | false | — | `KILO_API_KEY` | true |
| `ollama` | `https://ollama.com/v1` | `openai-compatible` | false | — | `OLLAMA_API_KEY` | true |
| `models_dev` | `""` | `openai-compatible` | false | — | — | **false** (internal) |

### Provider Registry (Upstream Providers)

Used for HF router fanout, Bifrost native providers, etc.

| Provider | `nativeBaseUrl` | `protocol` | `apiKeyEnv` |
|----------|-----------------|------------|-------------|
| `nvidia` | `https://integrate.api.nvidia.com/v1` | `nim` | `NVIDIA_API_KEY` |
| `amd` | `https://developer.amd.com.cn/radeon/api/v1` | `openai-compatible` | `AMD_API_KEY` |
| `huggingface` | — | `huggingface` | `HUGGING_FACE_API_KEY` |
| `openrouter` | `https://openrouter.ai/api/v1` | `openai-compatible` | `OPENROUTER_API_KEY` |
| `kilo` | `https://api.kilo.ai/api/gateway` | `openai-compatible` | `KILO_API_KEY` |
| `ollama` | `https://ollama.com/v1` | `openai-compatible` | `OLLAMA_API_KEY` |
| `together`, `deepinfra`, `cerebras`, `novita`, `cohere`, `fireworks`, `baseten`, `scaleway`, `nscale`, `ovhcloud`, `publicai`, `featherless`, `groq`, `cloudflare`, `zai-org` | various | `openai-compatible` | various |

---

## 5. Key Invariants & Semantics

### 5.1 Endpoint Identity ≠ Model Identity ≠ Quota Identity

> The same model exposed by two providers produces **two distinct endpoints** in the catalog, each with its own auth, latency, and rate limits.

- `ModelEndpoint` identity = `(data_source, provider, model_id)`
- `free` is **endpoint-scoped** — not model-level
- Same model (e.g., `deepseek-ai/deepseek-v4.1-flash`) on NVIDIA and AMD = two endpoints, different `free`/pricing/limits

### 5.2 Free Status Semantics

- `free: true` = confirmed free under data source's stated conditions
- `free: false` = confirmed paid
- **Absence of `pricing` ≠ free** — pricing missing means unknown, not free
- No model-level `free` field exists (by design)

### 5.3 Data Source vs Provider vs Endpoint

| Concept | Example | Scope |
|---------|---------|-------|
| **Data Source** | `huggingface` | Catalog TFI used to discover |
| **Provider** | `together` | Upstream provider within data source |
| **Endpoint** | `huggingface:together` | Runtime access point (`{provider}:{endpoint_name}`) |

### 5.4 Free Filter

`free_filter.py` runs after normalization — drops non-free endpoints per source-specific rules:
- NVIDIA/AMD: `free` flag from source
- HF: `is_free` from router payload
- OpenRouter/Ollama: `free` from source

### 5.5 Deduplication

Cross-source merge (same canonical model_id across sources) produces multiple endpoints under same model_id with different `provider`/`data_source`. No endpoint merging — each retains its own auth/limits.

---

## 6. Data Flow Summary

```
Free Model APIs (NVIDIA, AMD, HF, OpenRouter, Ollama, Kilo)
        ↓
Fetch & Parse (per-source adapters)
        ↓
Normalize → Canonical ModelEndpoint (data_source, provider, model_id, free, ...)
        ↓
Validate (schema + free filter)
        ↓
Enrich (models_dev cross-source enrichment)
        ↓
Deduplicate (cross-source merge by canonical model_id)
        ↓
Snapshot → KV (tfi:models:<ds>:<provider>:latest, tfi:manifest:latest)
        ↓
        ├─→ /api/v1/models (PublicModel + PublicModelEndpoint[])
        ├─→ /api/v1/endpoints (PublicEndpoint[])
        ├─→ /api/generate → Magpie / LiteLLM / NewAPI / Bifrost config
        └─→ Feishu notification
```

---

## 7. Key Type Definitions (TypeScript)

```typescript
// Canonical internal record
interface ModelEndpoint {
  data_source: string;
  provider: string;
  model_id: string;
  name: string | null;
  description: string | null;
  free: boolean;
  capabilities: Record<string, unknown>;
  architecture: { input: string[]; output: string[] } | null;
  lab: string | null;
  metadata: Record<string, unknown>;
  fetched_at: string;
  context_length?: number | null;
  pricing?: Record<string, unknown> | null;
  endpoint_url?: string | null;
  source_url?: string | null;
  supported_parameters?: string[];
}

// Public API model (list item)
interface PublicModel {
  id: string;
  object: "model";
  created: number;
  owned_by?: string;
  data_source: string;
  provider: string;
  capabilities: string[];
  supported_parameters?: string[];
  name?: string;
  description?: string;
  architecture?: { input: string[]; output: string[] };
  context_length?: number;
  lab?: string;
  source_url?: string;
  endpoints: PublicModelEndpoint[];
}

// Per-endpoint inside PublicModel
interface PublicModelEndpoint {
  id: string;                    // "provider:endpoint_name"
  provider: string;
  model_id: string;
  free: boolean;
  pricing?: Record<string, unknown> | null;
  limits?: Record<string, unknown> | null;
  supported_parameters?: string[];
}

// Endpoint catalog (separate endpoint)
interface PublicEndpoint {
  id: string;                    // "provider:endpoint_name"
  provider: string;
  data_source: string;
  protocol?: string;
  base_url?: string;
  authentication?: { type: string; credential_required?: boolean };
  status?: string;
  limits?: { scope?, subject?, rpm?, rpd?, tpm? };
  models?: string[];
}
```

---

## 7. Key Files Reference

| File | Purpose |
|------|---------|
| `data/models/schema.py` | Canonical `ModelEndpoint` + `FieldProvenance` (Python) |
| `web/functions/lib/kv.ts` | `ModelEndpoint` TypeScript interface |
| `web/functions/lib/projection.ts` | `PublicModel`, `PublicModelEndpoint`, `PublicEndpoint`, `resolveBaseUrl`, `toPublicModel` |
| `web/functions/lib/dataSources.ts` | **Unified registry** (source of truth for all generators) |
| `web/functions/lib/generators/*.ts` | Generator implementations (litellm, newapi, bifrost, magpie) |
| `data/models/schema.py` | Canonical Python dataclasses + provenance |
| `data/process/normalize.py` | Normalization logic |

---

## 8. Version History

| Date | Change |
|------|--------|
| 2026-10-26 | Unified `dataSources.ts` registry created; migrated all generators |
| 2026-10-25 | Added `ollama` to `KNOWN_DATA_SOURCES`; fixed `resolveBaseUrl` |
| 2026-10-22 | Magpie generator added; `kilo` keysUrl fixed |
| 2026-10-21 | Ollama Cloud integrated; VibeCafé/VibeLoft telemetry added |
| 2026-10-20 | Ollama provider + free filter added |
| 2026-10-08 | Major pipeline refactor (data_source/provider namespace) |

---

*Document generated from source code as of 2026-10-26. For latest, see `data/models/schema.py`, `web/functions/lib/dataSources.ts`, `web/functions/lib/projection.ts`, `web/functions/lib/generators/*.ts`.*