# Current State — 2026-09-25

A factual snapshot of the two runtimes as they exist in the tree on
this date. Everything below is grounded in files actually present in
the repo; nothing here is aspirational.

Repo root: `/home/yw/Projects/code/token-factory-initializr`

This document is intentionally narrow in scope: it describes what the
code does *today*, not what AGENTS.md / roadmap.md aspire to. For the
aspirational view, see those docs.

---

## 1. Repository layout

```
.
├── .github/workflows/
│   ├── fetch-models.yml      Python pipeline (daily + manual)
│   └── pages-deploy.yml      Web deploy on push to main
├── AGENTS.md                 Architecture & implementation prompt
├── README.md                 Concise project overview
├── data/                     Python data ingestion pipeline
├── web/                      Cloudflare Pages application
├── shared/schema/            JSON schema (cross-runtime contract)
├── docs/                     Architecture + roadmap + this file
└── .gitignore                Python/Node/Wrangler/build artifacts
```

---

## 2. Data runtime (`data/`)

### 2.1 Entry point

* `data/main.py` — calls `build_default_pipeline().run(PipelineContext())`,
  logs `Pipeline complete: N endpoints (aborted=False)`.

### 2.2 Pipeline DSL

`build_default_pipeline()` in `data/stages/__init__.py` composes:

```
FetchStage → ParseStage → FilterFreeStage → NormalizeStage
  → ValidateStage → EnrichStage → SummarizeStage → StoreStage → NotifyStage
```

Stages live under `data/stages/` and subclass `data.pipeline.stage.Stage`.
Pipeline context is `data/pipeline/context.py` (a dataclass with
`data: dict`, `state: dict`, `metrics: dict`, `errors: list`).

### 2.3 Provider modules (`data/providers/`)

| Module | Fetch | Parse | Free rule |
|---|---|---|---|
| `nvidia.py` | `NvidiaCatalogParser.fetch_all_pages(filters, max_pages=5)` | `parse_html(html)`, `_normalize_model(obj)` | `labels[].nimType.values contains "Free Endpoint"` |
| `amd.py` | `fetch_bootstrap(ua, timeout)` + `fetch_detail(model_id, ua)` | `build_endpoint_dict(detail)` | `model.token_factory.status.key == "free_endpoint"` |
| `huggingface.py` | `fetch_router_json(timeout)` (uses SOCKS5 proxy when set) | `parse_huggingface_models(payload)` → one endpoint per `(model, provider)` | `provider.pricing.input == 0 AND provider.pricing.output == 0 AND provider.status == "live"` |

Concrete hooks used by `build_default_pipeline`'s `FetchStage`:

```python
("nvidia", fetch_catalog_page),       # nvidia.py
("amd", fetch_amd_models),            # amd.py
("huggingface", fetch_huggingface_models),  # huggingface.py
```

Each fetcher returns `list[dict]` (provider-shaped endpoints; normalize
converts to `ModelEndpoint`).

### 2.4 NVIDIA fetch specifics

`BASE_URL = "https://build.nvidia.com/models?pageSize=96&filters=nimType%3Anim_type_preview"`.
The `?filters` query parameter is **ignored by the upstream RSC payload**
(same 48 ENDPOINT objects / 24 unique resource ids regardless of filter).
The web URL is hardcoded so requests match the public "Free models"
view; the actual filtering happens locally via the `free` flag.

The live RSC payload returns each model **twice** (byte-identical
duplicates); `_normalize_model` is called per object and `parse_html`
deduplicates by `model_id`, so the parser emits **24 unique models**.

### 2.5 HF parse specifics

`parse_huggingface_models(payload)` emits one endpoint per
`(model, router_provider)` pair. The top-level `provider` field on
the resulting `ModelEndpoint` is the **upstream router name**
(`"novita"`, `"fireworks-ai"`, `"together"`, `"cloudflare"`, etc.),
NOT `"huggingface"`. The aggregate `"huggingface"` snapshot keeps all
endpoints grouped together; per-router-provider snapshots are also
written so `/api/models?provider=cohere` style queries work.

### 2.6 FilterFreeStage (`data/stages/filter_free.py`)

Per-provider dispatch via `data/providers/free_filter.py`:

| Provider | Function | Rule |
|---|---|---|
| `nvidia` | `filter_nvidia_free(endpoints)` | drop `not ep.free` |
| `amd` | `filter_amd_free(endpoints)` | drop `ep.get("free") is not True` |
| `huggingface` | `filter_huggingface_free(endpoints)` | drop `ep.get("free") is not True` (defensive; HF parse already filters upstream) |

Stage writes `context.data["filtered"]` AND aliases
`context.data["parsed"]` to the filtered output so `NormalizeStage`
(which reads `parsed`) sees the filtered data without changes.

### 2.7 Normalize & validate

`normalize_endpoints(raw)` (`data/process/normalize.py`):
* Lifts `metadata.context_length` (or top-level fallback) → `ModelEndpoint.context_length`
* Lifts `item["architecture"]` (if `{input: list[str], output: list[str]}`) → `ModelEndpoint.architecture`
* Lifts `item["pricing"]` (if non-empty dict) → `ModelEndpoint.pricing`
* Uses `object.__setattr__` because `ModelEndpoint` is a frozen dataclass

`validate_endpoint(ep)` (`data/process/validate.py`):
* `provider` must be a non-empty string (no allowlist — HF router names are opaque)
* `model_id` must match `^\S+$`
* `context_length` if set must be `int`
* `metadata.context_length` if set must be `int` (back-compat)
* `architecture` if set must be `{input: list[str], output: list[str]}`
* `pricing` if set must be non-empty `dict[str, scalar]`

### 2.8 Schema (`data/models/schema.py`)

`ModelEndpoint` is a frozen dataclass:

```python
@dataclass(frozen=True)
class ModelEndpoint:
    provider: str
    model_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    free: bool
    fetched_at: datetime
    capabilities: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    architecture: Optional[dict] = None
    lab: Optional[str] = None
    canonical_model_id: Optional[str] = None
    model_family: Optional[str] = None
    organization: Optional[str] = None
    version: Optional[str] = None
    context_length: Optional[int] = None
    license: Optional[str] = None
    quantization: Optional[str] = None
    pricing: Optional[dict] = None
    endpoint_url: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = None
    limits: Optional[dict] = None
    score: Optional[float] = None
```

The `metadata` field shape **differs per provider**:
* NVIDIA: `{raw_obj?, attributes?, labels?}` — labels are normalized to
  `{key: {values: [...], unresolved: [...]}}`.
* AMD: `{family, context_length, free_status, original_id}` (back-compat;
  duplicates top-level `context_length`/`lab`).
* HF: `{supports_tools, supports_structured_output, first_token_latency_ms,
  throughput, is_model_author}`. **`router_provider` is no longer
  here** — it moved to the top-level `provider` field.

### 2.9 Storage (`data/storage/cloudflare_kv.py`)

* All keys prefixed with `"tfi:"`.
* `model_key(provider) → "tfi:models:{provider}:latest"`
* `manifest_key(date) → "tfi:manifest:{date}"` (or `"tfi:manifest:latest"`)
* `saveGenerated` (legacy python helpers, not the web's): `"tfi:gen:{id}"`.
* `KVStorage.from_env()` reads `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`,
  `CLOUDFLARE_KV_NAMESPACE_ID` from the environment.

### 2.10 Tests

`cd data && python -m pytest tests/ -q` — **294 passed, 9 skipped** as of
2026-09-25 (commit `c4d2f94`). Skipped tests are the
`@pytest.mark.integration` ones that need network.

Tests live under `data/tests/`. Curated fixtures (the 6 hand-crafted
samples) are **not** in git — `data/tests/fixtures/*.json` and
`data/tests/fixtures/*.html` are gitignored. They must be regenerated
locally via `python -m tests.download_fixtures` (the live-fresh
versions are downloaded into `*_live.*` files via the same script).

### 2.11 CI

`.github/workflows/fetch-models.yml`:
* `cron: "0 2 * * *"` + `workflow_dispatch`
* Python 3.11, installs runtime deps (`pip install ./data` — dev deps
  are NOT installed in CI), runs `python main.py`.
* Secrets required: `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`,
  `CLOUDFLARE_KV_NAMESPACE_ID`, optionally `FEISHU_WEBHOOK_URL`.
* A Validate step reads back `tfi:manifest:YYYY-MM-DD` from KV and
  fails if `total == 0`.

---

## 3. Web runtime (`web/`)

### 3.1 Build

* Vite + React 18 + react-router-dom 6.
* `npm run build` runs `tsc --noEmit && vite build`, output → `./dist/`.
* `pages_build_output_dir = "./dist"` (in `wrangler.toml`); the
  Functions directory (`./functions/`) is bundled separately by the
  Pages runtime, not by Vite.

### 3.2 React UI

| Route | File | Purpose |
|---|---|---|
| `/` | `web/src/pages/Home.tsx` | Provider tabs + model grid, search, click-to-select |
| `/generate` | `web/src/pages/Generate.tsx` | Selected models list + Generate button → POST /api/generate |
| `/generated/:id` | `web/src/pages/Generated.tsx` | Fetches `/api/generated/{id}`, renders YAML + share URL + agent prompt + copy buttons + TTL countdown |

Shared:
* `web/src/App.tsx` — top-level layout (header, nav, Outlet).
* `web/src/components/ModelCard.tsx` — one card per endpoint.
* `web/src/components/SelectionContext.tsx` — app-wide selection
  state (`{selected, toggle, clear, isSelected}`) keyed by
  `provider::model_id`.
* `web/src/kv.ts` — fetch wrapper for `/api/*` + bundled fixture
  fallback (`FIXTURES` imported from `web/src/data/fixtures.json`).

### 3.3 Pages Functions

```
functions/
├── _middleware.ts                       CORS + cache headers
├── lib/
│   ├── kv.ts                            TFI_KV binding helpers + Env type
│   ├── litellm.ts                       YAML generator + agent prompt + id generator
│   └── fixtures.ts                      Bundled fallback (small subset)
├── api/
│   ├── manifest.ts                      GET /api/manifest
│   ├── providers.ts                     GET /api/providers
│   ├── models.ts                        GET /api/models[?provider=X]
│   ├── generate.ts                      POST /api/generate
│   └── generated/
│       ├── [id].ts                      GET /api/generated/{id}  (JSON metadata)
│       └── [id]/prompt.ts               GET /api/generated/{id}/prompt
└── generated/                           (public routes per AGENTS.md §19-20)
    ├── [id].ts                          GET /generated/{id}            (YAML body)
    └── [id]/prompt.ts                   GET /generated/{id}/prompt     (text body)
```

Route map:

| URL | Method | Handler | Purpose |
|---|---|---|---|
| `/api/manifest` | GET | `api/manifest.ts` | Latest manifest; falls back to `fixtures.ts` if `TFI_USE_LOCAL_FIXTURES=1` |
| `/api/providers` | GET | `api/providers.ts` | List of provider keys; falls back to `["nvidia","amd","huggingface"]` |
| `/api/models?provider=X` | GET | `api/models.ts` | Per-provider snapshots |
| `/api/generate` | POST | `api/generate.ts` | Create 5-min artifact |
| `/api/generated/{id}` | GET | `api/generated/[id].ts` | JSON metadata |
| `/api/generated/{id}/prompt` | GET | `api/generated/[id]/prompt.ts` | Agent-friendly prompt text |
| `/generated/{id}` | GET | `generated/[id].ts` | Public YAML (text/yaml, Content-Disposition) |
| `/generated/{id}/prompt` | GET | `generated/[id]/prompt.ts` | Public prompt (text/plain) |

### 3.4 LiteLLM output shape

```yaml
model_list:
  - model_name: 'nvidia-deepseek-v4.1-flash'
    litellm_params:
      model: 'nvidia/deepseek-ai/deepseek-v4.1-flash'
      api_key: os.environ/NVIDIA_API_KEY
  - model_name: 'novita-Ling-3.0-flash-Fin'
    litellm_params:
      model: 'novita/inclusionAI/Ling-3.0-flash-Fin'
      api_key: os.environ/NOVITA_API_KEY
```

API key env mapping (`functions/lib/litellm.ts`):
* `nvidia` → `NVIDIA_API_KEY`
* `amd` → `AMD_API_KEY`
* `huggingface` → `HF_TOKEN`
* any other router-provider → `<UPPER>_API_KEY` fallback

### 3.5 TTL handling

`saveGenerated(env, artifact)` writes to `tfi:gen:{id}` with both:
* KV-level `expirationTtl: 300` (5 min) — the storage layer evicts it.
* Embedded `expires_at: now + 300_000` ms — the readers re-check
  on every read because Cloudflare KV TTL eviction is best-effort.

Read handlers (`generated/[id].ts`, `api/generated/[id].ts`,
`api/generated/[id]/prompt.ts`, `generated/[id]/prompt.ts`) all
check `art.expires_at <= Date.now()` and return **410 Gone** with
a clear "artifact expired" message — not 404, so callers can tell
"this URL was valid but is now stale" from "this URL was never valid".

### 3.6 Configuration

`web/wrangler.toml`:

```toml
name = "token-factory-initializr"
compatibility_date = "2026-09-15"
compatibility_flags = ["nodejs_compat"]
pages_build_output_dir = "./dist"

[[kv_namespaces]]
binding = "TFI_KV"
id = "0d4734eae9ce4b5d9ad4fa32e6ef462c"   # hardcoded, not ${ENV}

[vars]
TFI_TTL_SECONDS = "300"
TFI_USE_LOCAL_FIXTURES = "0"     # local dev passes --var TFI_USE_LOCAL_FIXTURES=1
```

`web/.env.example` documents the dual-token setup:
* `web/.env` → Pages edit + KV read token (scoped to the web).
* `data/.env` → KV write token (scoped to the data pipeline).

### 3.7 Cloudflare Pages project

* Project name: `token-factory-initializr`
* Production URL: `https://token-factory-initializr.pages.dev`
* Production branch: `main`
* Production data: 165 endpoints across 11 providers (as of 2026-09-25)

### 3.8 CI

`.github/workflows/pages-deploy.yml`:
* Triggers: push to `main` with `web/**` or `.github/workflows/pages-deploy.yml` changes; manual dispatch.
* Steps: checkout → setup-node 22 → `npm ci` → `npm run build` →
  `npx wrangler pages deploy ./dist --project-name token-factory-initializr --branch main`.
* Secrets required: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.
* Deploy step strips whitespace from secrets before invoking
  wrangler (Cloudflare API rejects account IDs with trailing
  newlines which GitHub's secret UI sometimes adds on paste).

---

## 4. Cross-runtime contract

* `shared/schema/model.schema.json` is the canonical JSON schema. It
  is the same shape that both Python and TypeScript validate against.
* Python: `data/models/schema.py` (frozen dataclass).
* TypeScript (browser): `web/src/types.ts`.
* TypeScript (Pages Functions): `web/functions/lib/kv.ts`.

The three runtimes do NOT share code; they share the schema.

---

## 5. Current KV state (production)

As of 2026-09-25, the `magi-kv` namespace (`0d4734eae9ce4b5d9ad4fa32e6ef462c`)
holds 15 keys:

```
tfi:manifest:2026-09-24
tfi:manifest:2026-09-25
tfi:manifest:latest
tfi:models:amd:latest
tfi:models:cohere:latest
tfi:models:featherless-ai:latest
tfi:models:fireworks-ai:latest
tfi:models:groq:latest
tfi:models:huggingface:latest
tfi:models:latest
tfi:models:novita:latest
tfi:models:nvidia:latest
tfi:models:scaleway:latest
tfi:models:together:latest
tfi:models:zai-org:latest
```

The 8 per-router-provider HF keys (`cohere`, `featherless-ai`,
`fireworks-ai`, `groq`, `novita`, `scaleway`, `together`, `zai-org`)
were written by a manual Python script during initial KV population;
they're **not** a side-effect of the web runtime. They enable
`/api/models?provider=<router>` queries.

---

## 6. Known gaps vs. AGENTS.md / roadmap.md

| Doc says | Code actually has |
|---|---|
| `Provider` Protocol with `fetch_models` returning `ModelEndpoint` | Each provider has its own free-shaped fetcher; `FetchStage` consumes `list[dict]` (provider-specific) and converts via `NormalizeStage` |
| Pipeline order is "fetch → parse → normalize → validate → deduplicate → snapshot" | `build_default_pipeline()` is fetch → parse → **filter_free** → normalize → validate → **enrich** → summarize → store → notify. No `deduplicate` step. |
| `D1` may be needed for "historical analysis, complex filtering" | Only `CloudflareKV`; `D1` not wired |
| `model.identity` ≠ `endpoint.identity` ≠ `quota.identity`; canonical model identity future work | Not implemented; endpoints are kept per-provider without canonical dedup |
| Benchmark/score from Artificial Analysis / HF evals | Not implemented; `EnrichStage` is a no-op |
| `litellm_params` always references `os.environ/<KEY>` | ✓ Confirmed in `functions/lib/litellm.ts` |
| 5-minute TTL on generated artifacts | ✓ Confirmed — `TFI_TTL_SECONDS=300`, KV `expirationTtl`, embedded `expires_at` re-checked on read |
| Agent-friendly prompt at `/generated/{id}/prompt` | ✓ Confirmed — `generated/[id]/prompt.ts` + `api/generated/[id]/prompt.ts` |
| OpenRouter / Groq as future providers | Not implemented; would be a one-line addition to `FetchStage.PROVIDER_FETCHERS` |

---

## 7. How to run locally

### 7.1 Data pipeline

```bash
cd data
pip install -e ".[dev]"
# .env required for KV writes (data-side token):
#   CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_KV_NAMESPACE_ID
python -m data.main                   # full pipeline
python -m tests.download_fixtures     # refresh *._live.json / *._live.html
python -m pytest tests/ -q            # 294 passed, 9 skipped
```

### 7.2 Web runtime

```bash
cd web
npm install
# .env required (web-side token, with Pages edit + KV read):
#   CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_KV_NAMESPACE_ID
npm run dev                            # wrangler pages dev with fixtures fallback
npm run build                          # tsc --noEmit && vite build
npm run deploy                         # wrangler pages deploy ./dist
```

Local dev defaults to `TFI_USE_LOCAL_FIXTURES=1` via the `dev` script.
Production deploys use the GitHub Actions secrets.

---

## 8. Verified end-to-end (2026-09-25)

* `curl https://token-factory-initializr.pages.dev/api/manifest` →
  200, `total: 165`, 11 providers (amd:7, cohere:12, featherless-ai:78,
  fireworks-ai:10, groq:1, huggingface:0, novita:1, nvidia:34,
  scaleway:1, together:2, zai-org:19).
* `curl https://token-factory-initializr.pages.dev/api/models?provider=nvidia` →
  200, 34 models.
* `curl -X POST .../api/generate` with `{model_ids: [...]}` → 200,
  returns `{id, url, yaml, agent_prompt, expires_at}`.
* `curl https://token-factory-initializr.pages.dev/generated/<id>` →
  200, `text/yaml`, `Content-Disposition: inline; filename="<id>.yaml"`.
* `curl https://token-factory-initializr.pages.dev/generated/<id>/prompt` →
  200, `text/plain`, agent-prompt body.
* CI: `pages-deploy.yml` workflow `36131874436` succeeded (all 7 steps
  green); `fetch-models.yml` workflow `36057440493` succeeded (all 8
  steps green).
* Local screenshot of `https://token-factory-initializr.pages.dev/`
  rendered with chromium shows 165 endpoints across the provider
  tabs with correct modality / context-length tags.