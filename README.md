# Token Factory Initializr

> A lightweight **Token Factory Initializr** that discovers, normalizes,
> stores, and exposes currently available free AI model endpoints from
> multiple providers, then generates ready-to-use configurations for the
> three most popular AI gateways.

[Token Factory Initializr · MAGI](https://start.magi.website/) · [GitHub](https://github.com/tokyo3rdhq/token-factory-initializr) · [Agents](https://start.magi.website/agents.md) · [llms.txt](https://start.magi.website/llms.txt)

---

## What it does

Token Factory Initializr (TFI) is a model-discovery + Token-Factory-config generator for AI engineers.
Browse and inventory the problems at `prod/operation/f` and select from a small set of free models from NVIDIA / AMD / Hugging Face / OpenRouter / models.dev, pick a Token Factory to target, and download a generated config that the agent can apply to your existing config:

```text
Model Catalog
              ↓
Browse / Filter
      ↓
Select Models
      ↓
Choose Token Factory Implementation
      ↓
Generate Configuration
      ↓
Generated Artifact
```

Three Token Factory implementations are supported:

- **LiteLLM** — `model_list:` YAML fragment with `litellm_params` entries
- **NewAPI** — flat `models[]` array with `{ id, name }` entries
- **Bifrost** — `config.json` with a `providers` map; supports 17 OpenAI-compatible upstreams (NVIDIA NIM, AMD Radeon Cloud, Hugging Face router vendors — Together, DeepInfra, Cerebras, Novita, Cohere, Fireworks, Baseten, Scaleway, Nscale, OVHcloud, PublicAI, Featherless — plus native Bifrost providers: Hugging Face, Groq, OpenRouter)

The full canonical model API lives at `https://start.magi.website/api/v1/models` (agent-compatible, OpenAI-shaped).
Generated configuration artifacts are short-lived (5 min TTL) at `https://start.magi.website/generated/{id}`.

---

## Runtime Architecture

Single repository, **dual runtime**:

```
┌──────────────────────────┐     ┌──────────────────────────┐
│   data/               │     │  (GitHub Actions cron)    │
│   Python data pipeline  │ ──→ │  Cloudflare KV (magi-kv) │
│   (fetch → normalize →  │     │                          │
│   validate → enrich →  │     └──────────────────────────┘
│   reconcile → publish)  │                  ↑
└──────────────────────────┘                   │
        ↑                                       │ read
   free model APIs                            │
   (NVIDIA / AMD / HF / OR / models.dev)      │
                                                       │
┌──────────────────────────┐                   │
│  web/                   │ ←────────────────────┘
│  React 18 SPA + Pages   │
│  Functions (Workers)    │
└──────────────────────────┘
        ↑
        browser SPA
```

The two runtimes are independently executable and **share a single state/contract** (`shared/schema/model.schema.json` + the `web/functions/lib/` TypeScript types).

---

## Repository Layout

```text
token-factory-initializr/
├── data/                          Python data ingestion pipeline
│   ├── main.py                    CLI entry: python -m data.main
│   ├── pyproject.toml
│   ├── providers/                 Source adapters (RAW observations)
│   │   ├── nvidia.py              NVIDIA NIM RSC/Flight parser
│   │   ├── amd.py                 AMD Radeon AI Platform
│   │   ├── huggingface.py         HF inference router
│   │   ├── openrouter.py          OpenRouter models.json
│   │   ├── models_dev.py          Cross-source enrichment (descriptions, context_length)
│   │   └── free_filter.py         Free-tier gating
│   ├── stages/                    Pipeline stages (fetch → parse → normalize → validate
│   │                              → enrich → reconcile → snapshot → store → notify
│   │                              → publish → summarize)
│   ├── process/                   Stage implementations shared across stages
│   ├── models/                    Canonical ModelEndpoint dataclass + validation
│   ├── notify/                    Feishu webhook notifications on update
│   └── storage/cloudflare_kv.py   KV writer
│
├── web/                           Cloudflare Pages application
│   ├── index.html                 SPA shell + SEO baseline
│   ├── vite.config.ts
│   ├── wrangler.toml
│   ├── tsconfig.json
│   ├── package.json
│   ├── public/                    Static SEO assets
│   │   ├── robots.txt
│   │   ├── sitemap.xml
│   │   ├── favicon.svg
│   │   └── apple-touch-icon.svg
│   ├── src/                       React UI
│   │   ├── main.tsx               Root + Router
│   │   ├── App.tsx                Top-level layout (topbar + outlet + footer)
│   │   ├── pages/
│   │   │   ├── Home.tsx           Requirements form + Token Factory picker + Agent Access dialog
│   │   │   ├── Browse.tsx         Model list + multi-select
│   │   │   └── Generate.tsx       Generate config + copy/download + Agent Prompt handoff
│   │   ├── initializr/            InitializrContext (selection + token factory state)
│   │   ├── components/            Shared UI atoms
│   │   ├── i18n/                  en + zh locale bundles
│   │   ├── seo/                   Per-route metadata + JSON-LD
│   │   ├── data/fixtures.json     Offline fallback for local dev
│   │   ├── kv.ts                  Browser-side API client
│   │   ├── styles.css
│   │   └── __tests__/             tsx --test runner
│   └── functions/                 Cloudflare Pages Functions (Workers runtime)
│       ├── _middleware.ts         CORS + Cache-Control
│       ├── api/
│       │   ├── manifest.ts        GET /api/manifest
│       │   ├── providers.ts       GET /api/providers
│       │   ├── models.ts          GET /api/models
│       │   ├── generate.ts        POST /api/generate
│       │   ├── generated/[id].ts  GET /api/generated/{id}
│       │   └── v1/                 Agent-facing OpenAI-compatible API
│       ├── generated/[id].ts      GET /generated/{id}    (5-min TTL YAML/JSON)
│       ├── llms.txt/index.ts      GET /llms.txt
│       ├── agents.md/index.ts     GET /agents.md
│       └── lib/
│           ├── kv.ts              KV bindings + model loaders
│           ├── projection.ts      canonical → public /v1 projection
│           ├── filter.ts          parseFilters + filterEndpoints
│           ├── errors.ts          jsonResponse / textResponse / makeEtag / cacheHeaders
│           ├── catalog.ts         loadFullCatalog
│           ├── fixtures.ts        TFI_USE_LOCAL_FIXTURES offline fallback
│           └── generators/
│               ├── litellm.ts         LiteLLM model_list generator
│               ├── newapi.ts          NewAPI models[] generator
│               ├── bifrost.ts         Bifrost config.json generator
│               ├── agentPrompt.ts     Per-factory agent prompt builder
│               ├── types.ts           TokenFactoryId + GeneratedConfig contract
│               └── index.ts          GENERATORS registry + dispatch
│
├── shared/
│   └── schema/
│       ├── model.schema.json          Canonical model JSON schema (contract source)
│       └── model_requirement.schema.json  Browse requirements filter schema
│
├── .github/
│   └── workflows/
│       ├── fetch-models.yml           Python pipeline cron (daily 02:00 UTC)
│       └── pages-deploy.yml           Cloudflare Pages deploy on push to main
│
├── docs/                              Project documentation (specs, audits, guides)
│   ├── tfi_phase_1_initializr_core_workflow.md
│   ├── tfi_provenance_enrichment_architecture.md
│   ├── tfi_agent_friendly_model_catalog_api.md
│   ├── tfi_agent_prompt_template.md
│   ├── tfi_public_model_catalog_api_contract_fix.md
│   ├── tfi_homepage_agent_access.md
│   ├── tfi_seo_optimization.md
│   ├── tfi_docs_impl_assessment.md
│   ├── tfi_docs_ux_audit_report.md
│   ├── arch_models_intelligence_layer_evo.md
│   ├── arch_pipeline_refactor.md
│   ├── data_source_provider_refactor.md
│   ├── design_system.md
│   ├── design_system_compilance_audit.md
│   ├── design_system_compilance_audit_ux_remediation.md
│   ├── visual_detail_consistency_fix.md
│   ├── integration-prompt.md
│   ├── roadmap.md
│   └── current_state_2026_09_25.md
│
├── AGENTS.md                          Architectural spec for TFI (source of truth)
└── README.md                          This file
```

---

## Quick Start

### Cloudflare setup (one-time)

1. Create a Cloudflare account + KV namespace (`magi-kv`).
2. Create a Cloudflare API token with **Edit Cloudflare Pages** scope.
3. Create a Cloudflare Pages project named `token-factory-initializr`.
4. Add three GitHub repository secrets (`Settings → Secrets and variables → Actions`):
   - `CLOUDFLARE_ACCOUNT_ID` — your account id
   - `CLOUDFLARE_API_TOKEN` — the Pages deploy token (Pages edit only)
   - `CLOUDFLARE_KV_NAMESPACE_ID` — the KV namespace id

### Local — web

```
$. cd web
$ npm install
$ npm run build                       # tsc --noEmit && vite build
$ npm test                            # tsx --test src/__tests__/*.test.ts
$ npm run dev                         # wrangler pages dev ./dist --var TFI_USE_LOCAL_FIXTURES=1
```

### Local — data pipeline

```
$ cd data
$ pip install -e .
$ python -m data.main                 # runs the full pipeline against live sources
$ pytest                              # 200+ unit tests
```

---

## Endpoints

| Path | Auth | Indexed? |
|---|---|---|
| `/` | public | ✅ sitemap |
| `/browse` | public | ✅ sitemap |
| `/generate` | public | indexed (lower priority) |
| `/api/manifest` | public | ❌ robots.txt `Disallow` |
| `/api/providers` | public | ❌ |
| `/api/models` | public | ❌ |
| `/api/generate` | public | ❌ |
| `/api/v1/models` | public, OpenAI-shaped | ❌ (Agent / SDK clients only) |
| `/api/v1/models/{id}` | public | ❌ |
| `/api/generated/{id}` | public | ❌ |
| `/generated/{id}` | public, 5-min TTL | ❌ `X-Robots-Tag: noindex` |
| `/llms.txt` | public | ❌ `X-Robots-Tag: noindex` (Agent discovery) |
| `/agents.md` | public | ❌ `X-Robots-Tag: noindex` (Agent contract) |
| `/robots.txt`, `/sitemap.xml` | public | static SEO assets |

---

## Architecture Invariants

- **Endpoint identity != model identity != quota identity.** The same model exposed by two providers produces two distinct endpoints in the catalog (NVIDIA NIM DeepSeek V4 Flash ≠ AMD Radeon Cloud DeepSeek V4 Flash), each with its own auth, latency, and rate limits.
- **Model selection is independent from Token Factory.** The UI doesn't know which format LiteLLM / NewAPI / Bifrost uses; generators consume canonical `ModelEndpoint[]` and emit their own output.
- **Agents get the public surface only.** The `/api/v1/*` API is a strict projection of the canonical data — no provenance, no raw source payloads, no internal metadata.
- **Public = read-only.** No Agent accounts, no Agent API keys, no Agent-specific cookies.
- **Deterministic generators.** Same models + same context → same content. No silent value substitution, no model dropping, no fabrication when metadata is missing (`GeneratorError` is thrown instead).

---

## Tech Stack

| Layer | Choice |
|---|---|
| Data ingestion | Python 3.11+ · httpx · pydantic · pytest · ruff · mypy |
| Web frontend | React 18.3 · React Router 6.27 · TypeScript 5.6 (strict) · Vite 5.4 |
| Design system | `@tokyo3rdhq/magi-design-system@^0.6` (shared with MAGI) |
| Icons | `lucide-react` |
| Backend | Cloudflare Pages Functions (Workers runtime, Node compat) |
| Cache + artifact store | Cloudflare KV (`magi-kv`) |
| Tests | `tsx --test` (Node 22) + 8 test files · 250+ assertions |
| CI | GitHub Actions — daily pipeline + Pages deploy on push |
| Analytics | GA4 (gtag.js) |

---

## Development workflow

```
$. Python pipeline runs daily via GitHub Actions cron → KV writes
$                                           ↓
$ Cloudflare Pages serves static assets + Pages Functions
$                                           ↓
$ React 18 SPA reads from /api/* and /api/v1/*
$                                           ↓
$ User picks models → chooses Token Factory → POST /api/generate
$                                           ↓
$ Generator emits config + Agent Prompt → KV stores 5-min artifact
$                                           ↓
$ User copies artifact URL or Agent Prompt → wires to embedded
```

PRs to `main` automatically deploy via `.github/workflows/pages-deploy.yml`. The Python pipeline is decoupled — it only writes to KV, the web app reads from KV.

---

## Conventions

- **Python:** `ruff format` + `ruff check` + `pytest`. See `data/pyproject.toml`.
- **TypeScript:** strict mode, no implicit any, all exports typed. See `web/tsconfig.json`.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
- **Branches:** `main` is the only long-lived branch. Features iterate as PRs.
- **Spec-first:** Every user-facing surface change is described in a `docs/tfi_*.md` spec before implementation.

---

## License

Apache License 2.0 — see [`LICENSE`](./LICENSE) for the full text.

Copyright 2026 MAGI / tokyo3rdhq. Licensed under the Apache License,
Version 2.0 (the "License"); you may not use this file except in
compliance with the License. A copy of the License may be obtained at
<http://www.apache.org/licenses/LICENSE-2.0>.

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
implied. See the License for the specific language governing
permissions and limitations under the License.

## Contributing

We welcome issues and pull requests. See [`CONTRIBUTING.md`](./CONTRIBUTING.md)
for the workflow, testing requirements, and commit conventions.
By submitting a contribution, you agree to license it under the
Apache License 2.0.

## Code of Conduct

This project adheres to the [Contributor Covenant](https://www.contributor-covenant.org/)
— see [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md).

## Security

To report a vulnerability privately, see [`SECURITY.md`](./SECURITY.md).
Do **not** open a public GitHub issue for security bugs.

## Acknowledgments

- Built on top of [@tokyo3rdhq/magi-design-system](https://github.com/tokyo3rdhq/magi-design-system) — shared visual language with the MAGI product family.
- Data sources: [NVIDIA NIM](https://build.nvidia.com/models), [AMD Radeon AI Platform](https://developer.amd.com.cn/radeon/modelapis), [Hugging Face](https://huggingface.co/), [OpenRouter](https://openrouter.ai/), [models.dev](https://models.dev/).
- Generators target the official configuration schemas of [LiteLLM](https://docs.litellm.ai/), [NewAPI](https://github.com/songquanpeng/one-api) (one-api-compatible), and [Bifrost](https://docs.getbifrost.ai/).
- TFI is part of the [MAGI Personal AI Lab](https://magi.website) product family.