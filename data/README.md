# Token Factory Initializr — Data Pipeline

Offline ingestion pipeline that discovers free AI model endpoints from
multiple providers, normalizes them into a canonical schema, validates
each record, and persists snapshots to Cloudflare KV.

The web runtime (Cloudflare Pages / Pages Functions) reads from KV and
serves the catalog.

## Pipeline

```
fetch → parse → normalize → validate → enrich → store → summarize → notify
```

Each Stage is a thin adapter — the actual logic lives in
`data/providers/`, `data/process/`, `data/storage/`, and `data/notify/`.
See [`docs/arch_models_intelligence_layer_evo.md`](../docs/arch_models_intelligence_layer_evo.md)
for the target architecture and deferred work (enrich stage is a placeholder).

## Local Development

### Prerequisites

- Python ≥ 3.10
- `requests` (NVIDIA provider)
- `PySocks` (only if `SOCKS5_PROXY` is set)

### Install

```bash
cd data
python -m pip install -e ".[dev,socks]"
```

### Run Tests

Offline unit + integration tests (the integration tests are gated behind
`RUN_INTEGRATION_TESTS=1`; by default only unit tests run):

```bash
pytest tests/ -v --timeout=30
```

With network access:

```bash
RUN_INTEGRATION_TESTS=1 pytest tests/ -v --timeout=60
```

### Run the Pipeline

```bash
cd data
python -m data.main
```

Or as a module:

```bash
python -m data.main
```

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Purpose |
|---|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | yes (for store) | Cloudflare account ID |
| `CLOUDFLARE_API_TOKEN` | yes (for store) | API token with KV write scope |
| `CLOUDFLARE_KV_NAMESPACE_ID` | yes (for store) | Target KV namespace ID |
| `FEISHU_WEBHOOK_URL` | no | Feishu / Lark custom-bot webhook |
| `SOCKS5_PROXY` | no (local only) | `socks5h://host:port` for HF provider |

Without `CLOUDFLARE_*` the store stage records a severe error to
`context.errors` and the notify stage fires a Feishu alert (if configured) —
the pipeline does NOT silently no-op.

### Failure Alerting

When a stage records a severe error (KV init failure, per-key write
failure, etc.), the notify stage sends **two** Feishu messages:

1. The summary card (now with red header and inline error list)
2. A plain-text alert summarizing which stage failed

If `FEISHU_WEBHOOK_URL` is unset, errors are only logged to stderr.

## GitHub Actions / Production Deploy

The `.github/workflows/fetch-models.yml` workflow at the repo root runs
the pipeline daily at 02:00 UTC and on manual dispatch. Required secrets:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_KV_NAMESPACE_ID`
- `FEISHU_WEBHOOK_URL` (optional but recommended)

## Cloudflare KV Key Naming

All keys written by the pipeline share a single `tfi:` prefix so the
namespace can also host unrelated keys (e.g. when shared with another
app during development) without collision.

| Key | Type | Lifetime | Purpose |
|---|---|---|---|
| `tfi:models:latest` | JSON dict | overwritten on every run | aggregate list of all endpoints across providers |
| `tfi:models:<provider>:latest` | JSON dict | overwritten on every run | per-provider slice (provider ∈ `nvidia` / `amd` / `huggingface` / ...) |
| `tfi:manifest:latest` | JSON dict | overwritten on every run | current run manifest (counts + per-provider status) |
| `tfi:manifest:<YYYY-MM-DD>` | JSON dict | retained forever | dated snapshot of each daily run; verified by GitHub Actions |

### Why the dated manifest key?

The GitHub Actions "Validate results" step GETs
`tfi:manifest:<UTC date>` to verify the pipeline produced something
*today*. It can't trust `tfi:manifest:latest` alone because that key
might still hold yesterday's payload if today's run failed silently
before the `store` stage could complete.

### Helpers — don't hand-roll the strings

Always build keys via the helpers in `data.storage.cloudflare_kv`:

```python
from data.storage.cloudflare_kv import model_key, manifest_key, KEY_PREFIX

model_key("amd")                       # -> "tfi:models:amd:latest"
manifest_key()                          # -> "tfi:manifest:latest"
manifest_key("2026-09-24")              # -> "tfi:manifest:2026-09-24"

assert KEY_PREFIX == "tfi:"
```

The `KEYS` dict is exported for backward compatibility but new code
should use the helpers. `KEYS["snapshot"]` is kept as a deprecated alias
for `KEYS["dated_manifest"]`.

### Adding a new provider

1. Implement the fetcher in `data/providers/`
2. Register it in `data/stages/fetch.py:PROVIDER_FETCHERS`
3. The pipeline will automatically write `tfi:models:<your_provider>:latest`
   — no change to `KEYS` is needed because `model_key(provider)` is
   parameterized.

## Module Layout

```
data/
├── main.py                      # entry point
├── pyproject.toml
├── .env.example
├── models/                      # canonical ModelEndpoint + JSON Schema validator
├── pipeline/                    # DSL: Pipeline, Stage, Context, Result
├── stages/                      # thin adapters bound to PipelineContext
├── providers/                   # nvidia / amd / huggingface
├── process/                     # normalize / validate / summarize
├── storage/                     # Cloudflare KV adapter
├── notify/                      # Feishu webhook adapter
└── tests/                       # 202 offline tests + 6 integration tests (skipped by default)
```

The shared cross-runtime JSON Schema lives at
[`shared/schema/model.schema.json`](../shared/schema/model.schema.json).