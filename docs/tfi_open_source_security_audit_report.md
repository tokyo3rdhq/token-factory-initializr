# TFI Open-Source Security Audit — Findings Report

Audit prompt: `docs/tfi_open_source_security_audit.md` (16 sections).
Audit date: 2026-10-07.
Repository under audit: <https://github.com/tokyo3rdhq/token-factory-initializr> (canonical public repo; mirrors exist at `yw79641760/...` for active dev).
Methodology: read every workflow + every secrets-bearing surface in this
checkout, grep for shell-execution / unsafe-deserialization / eval /
shell=True, then trace each attack path against the threat model in §3.

The audit surfaces **8 findings** (1 medium, 7 low / informational) and
**0 critical / high** issues. The repository is broadly safe to publish.

---

## 1. Executive summary

| # | Severity | Title | Surface |
|---|---|---|---|
| F1 | Medium | `GITHUB_TOKEN` permissions are implicit | all 3 workflows |
| F2 | Low | Third-party actions pinned by version tag, not SHA | all 3 workflows |
| F3 | Low | `CORS: *` on a public, unauthenticated API | web Functions |
| F4 | Low | `LiteLLM` YAML output uses single-quoted scalar — vulnerable to model IDs containing `\n` | web generator |
| F5 | Low | `CLOUDFLARE_API_TOKEN` scope not documented | `fetch-models.yml` |
| F6 | Low | Production deploy step exists only in developer-local workflow — not in CI | deploy path |
| F7 | Informational | `FEISHU_WEBHOOK_URL` is referenced but optional | `fetch-models.yml` |
| F8 | Informational | `security@tokyo3rdhq.com` is a placeholder | `SECURITY.md` |

No critical / high issues found. The publish path (`fetch-models.yml`)
**never** runs on `pull_request` or `pull_request_target`, and the two
CI workflows (`web-ci.yml`, `data-ci.yml`) **never** reference
production secrets. This is the design contract the prompt asked us to
verify — it holds.

---

## 2. Threat model coverage

### Attacker A — External Fork Contributor

A fork contributor can:

- Modify `web/src/**`, `data/**`, `tests/**`, `.github/workflows/**`,
  `package.json`, `pyproject.toml`, `package-lock.json`,
  `requirements*.txt`.
- Submit a PR.

They **cannot**:

- Trigger `fetch-models.yml` (only `schedule` + `workflow_dispatch`).
- Reach `CLOUDFLARE_API_TOKEN` from any CI workflow (only
  `fetch-models.yml`'s `Fetch models` / `Validate results` jobs reference
  it; both gated by GitHub Actions secrets that are **not exposed to
  fork PRs**).
- Write to production Cloudflare KV. Verified: `data-ci.yml` runs
  `pip install -e ".[dev]"` + `pytest -m "not integration"` only. No
  KV write.

**Result**: ✅ Attacker-controlled code can execute in CI, but no
production credential is ever in the same job. This satisfies the
audit's "no secrets + arbitrary code = acceptable" rule (§5).

### Attacker B — Malicious Dependency / Supply Chain

Dependency surface:

- **npm** (web): `actions/setup-node@v4` + `npm ci --ignore-scripts`.
  Postinstall scripts (`workerd`, `esbuild`) are explicitly disabled
  with `--ignore-scripts` (`web-ci.yml` comment: line 40). A compromised
  package therefore cannot run its install hook in CI.
- **PyPI** (data): `pip install -e ".[dev]"`. Setuptools-based wheel,
  no native compilation; safe by default. `pip install --upgrade pip`
  is NOT used in CI (only in `fetch-models.yml`, and pinned to the
  runner's pip). No `--index-url` overrides; default PyPI.
- **GitHub Actions** (all): see F2 — pinned by major-version tag, not
  by SHA.

A compromised npm or PyPI package executing in `data-ci.yml` or
`web-ci.yml` cannot reach production secrets (none available). A
compromised package executing in `fetch-models.yml` would have access
to `CLOUDFLARE_API_TOKEN` — mitigated by F5 (scope restriction) but
not eliminated.

### Attacker C — Malicious Upstream Model Data

The data pipeline fetches JSON / HTML from `build.nvidia.com`,
`developer.amd.com.cn`, `router.huggingface.co`, `openrouter.ai`, and
`models.dev`. All URLs are **module-level constants**, not user input.
No SSRF surface.

Provider fetchers parse responses with stdlib `json` + `re` only:

- No `yaml.load` (no yaml-parsing of upstream data).
- No `eval` / `exec` / `subprocess` / `shell=True` across the entire
  `data/` tree (`grep -rn` returned empty).
- No `pickle` / `marshal` deserialization anywhere.

Model `description` strings are stored verbatim into KV. They are
**not** rendered as HTML in the React UI (grep for
`dangerouslySetInnerHTML` in `web/src/` returned empty — React's
default escaping handles them). They **are** rendered in the
LiteLLM `description:` field? — no, only `model_id` + `provider` +
`name` flow into the generator (`web/functions/lib/generators/litellm.ts:67-69`).

---

## 3. Workflow-by-workflow

### 3.1 `web-ci.yml`

- **Trigger**: `push` to `main` (paths `web/**` + this workflow file),
  `workflow_dispatch`. **No** `pull_request_target`.
- **Secrets**: none.
- **Permissions**: not declared → falls back to repository default.
  See **F1** below.
- **Checkout**: `actions/checkout@v4` with default `ref`, default
  branch (`main`). Not a `pull_request_target` checkout, so no PR-head
  ref.
- **Third-party actions**: `actions/checkout@v4`,
  `actions/setup-node@v4`. See **F2**.
- **Shell injection**: `run:` blocks contain zero `${{ github.* }}`
  expressions.
- **Cache**: `actions/setup-node@v4` cache with
  `cache-dependency-path: web/package-lock.json`. The cache key
  derivation uses only the lockfile hash — no PR-controlled values.

### 3.2 `data-ci.yml`

- **Trigger**: `push` to `main` (paths `data/**` + this workflow file),
  `workflow_dispatch`.
- **Secrets**: none.
- **Permissions**: not declared → repository default. See **F1**.
- **Checkout**: `actions/checkout@v4`, default branch.
- **Third-party actions**: `actions/checkout@v4`,
  `actions/setup-python@v5`. See **F2**.
- **Shell injection**: zero `${{ github.* }}` in any `run:` block.
- **Python surface**: `pip install -e ".[dev]"` then `pytest -m "not
  integration"`. `pip install -e` runs the project's `setup.py` /
  `pyproject.toml` build backend (setuptools). A PR contributor can
  modify `data/pyproject.toml`'s `[project]`, `[project.optional-
  dependencies.dev]`, `[tool.setuptools.*]` sections and trigger
  arbitrary code at install time. This is acceptable **per audit §5**
  because `data-ci.yml` has no production secrets — the only damage
  the attacker can cause is to the CI runner itself.

### 3.3 `fetch-models.yml` — production trust boundary

- **Trigger**: `schedule` (`0 2 * * *`) + `workflow_dispatch`. **No**
  `pull_request`, no `pull_request_target`.
- **Permissions**: not declared → repository default.
- **Checkout**: `actions/checkout@v4`, default branch.
- **Secrets**: `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`,
  `CLOUDFLARE_KV_NAMESPACE_ID` (all in `Fetch models` and `Validate
  results` steps); `FEISHU_WEBHOOK_URL` (only `Fetch models`).
- **Shell injection**: `python -c "..."` step is fully static — no
  `${{ github.* }}` substitutions. Safe.
- **Pipeline execution**: `python data/main.py` runs the project's own
  pipeline on the trusted `main` branch ref (cron + dispatch both
  check out the branch they were invoked against — `schedule` checks
  out the default branch). The workflow cannot be triggered by a PR.
- **Failure mode**: if `pip install ./data` fails, the job errors
  before secrets are referenced. If `python main.py` exits non-zero,
  secrets are still in env but the job is already marked failed —
  no destructive side-effect runs.

**Result**: `fetch-models.yml` is correctly isolated from PR / fork
attackers. ✅

---

## 4. Production secret inventory

| Secret | Workflow | Job | Purpose | Required? | Risk |
|---|---|---|---|---|---|
| `CLOUDFLARE_API_TOKEN` | `fetch-models.yml` | `fetch-models` | KV PUT in `PublishStage` + KV GET in `Validate results` | yes | see F5 |
| `CLOUDFLARE_ACCOUNT_ID` | `fetch-models.yml` | `fetch-models` | identifies the CF account for KV URL | yes | low — public identifier |
| `CLOUDFLARE_KV_NAMESPACE_ID` | `fetch-models.yml` | `fetch-models` | identifies the KV namespace | yes | low — public identifier |
| `FEISHU_WEBHOOK_URL` | `fetch-models.yml` | `fetch-models` | optional failure alerts | no (see F7) | low |
| `CLOUDFLARE_API_TOKEN` (web) | **local developer env only** | `wrangler pages deploy` | Pages deploy + KV read at runtime | yes (deploy) | held in `web/.env`, never in CI |
| `GITHUB_TOKEN` | implicit | all 3 workflows | default for `actions/checkout` etc. | required | see F1 |

Repository-level secrets are correctly scoped to the workflow that
needs them. **No** secret is referenced from `web-ci.yml` or
`data-ci.yml`. The `CORS: *` (F3) and the absence of `permissions:`
blocks (F1) are the two web-side issues worth fixing.

---

## 5. Findings detail

### F1 — Medium — Implicit `GITHUB_TOKEN` permissions

**Where**: all 3 workflows (`web-ci.yml`, `data-ci.yml`,
`fetch-models.yml`) omit a `permissions:` block.

**Impact**: a workflow file changes by a PR contributor can grant
`GITHUB_TOKEN` write access to PR-controlled actions. While the
current workflows only read from the repo (`actions/checkout` needs
`contents: read`), the explicit principle of least privilege is not
applied. GitHub's documented "minimum for Actions" guidance is
`contents: read` for any workflow that doesn't write PR comments,
publish releases, or push commits.

**Recommendation**: add at the top of each workflow's `jobs:` block:

```yaml
permissions:
  contents: read
```

`fetch-models.yml` doesn't need write. `data-ci.yml` doesn't need
write. `web-ci.yml` doesn't need write. None of them touch PR
comments, releases, or pushes — all three can safely declare
`contents: read`.

### F2 — Low — Third-party actions pinned by version tag, not SHA

**Where**: `actions/checkout@v4`, `actions/setup-node@v4`,
`actions/setup-python@v5`. All three are official GitHub Actions.

**Impact**: a tag can be moved (the tag itself is immutable but the
`refs/tags/v4` ref can be reassigned by the action maintainer in
extreme compromise scenarios). The audit prompt recommends
`SHA-pinning` for "security-sensitive production workflows." Only
`fetch-models.yml` is such a workflow. The other two are CI.

**Recommendation**: pin `actions/checkout`, `actions/setup-node`,
`actions/setup-python` to commit SHAs in `fetch-models.yml`. The other
two are lower priority — version tag is acceptable for `web-ci.yml` /
`data-ci.yml` given they have no secrets.

### F3 — Low — `CORS: *` on unauthenticated API

**Where**: `web/functions/_middleware.ts` — sets
`Access-Control-Allow-Origin: *` on every response.

**Impact**: TFI's `/api/v1/*` endpoints (read-only model catalog) and
`/api/generate` (write, but capped at 50 models / 5 min TTL) are
publicly callable from any origin. The audit prompt considers CORS
on a public, read-only catalog a low concern, but for `POST
/api/generate` (which writes to KV) it lets any malicious site burn
KV write operations by spamming the endpoint.

**Impact quantified**: 50 model_ids × N requests / sec × 5 min = KV
write amplification. Cloudflare KV will rate-limit but the attacker
spends nothing per request.

**Recommendation**: keep `*` for `GET` responses (`/api/manifest`,
`/api/providers`, `/api/models`, `/api/v1/*` — all read-only). Tighten
`POST /api/generate` to a static allowlist:

```ts
const ALLOWED_ORIGINS = new Set([
  "https://start.magi.website",
  "https://token-factory-initializr.pages.dev",
  // local dev
  "http://localhost:8788",
  "http://127.0.0.1:8788",
]);
```

And reflect the request origin only when it's in the allowlist,
otherwise deny with no CORS header. Currently both `*` paths are
acceptable for the public catalog.

### F4 — Low — LiteLLM YAML output is single-quote-only

**Where**: `web/functions/lib/generators/litellm.ts:45`.

```ts
function yamlEscape(value: string): string {
  return `'${value.replace(/'/g, "''")}'`;
}
```

**Impact**: single-quoted YAML scalars are safe against `:`,
indentation-based injection, and `{` `}` attacks. They are
**vulnerable** to:
1. Model IDs containing literal `'\n'` (newline). A model
   `provider/X\n  - model_name: "evil"\n` would break the line and
   emit an invalid YAML fragment.
2. Model IDs ending with `'` followed by any text (technically
   handled by doubling `'` → `''`).
3. Control chars (NULL, BEL) — YAML 1.1 allows them; YAML 1.2
   warns.

In practice the data pipeline strips such inputs (model_id is
`/^[a-zA-Z0-9._-]+\/[a-zA-Z0-9._-]+$/` style for most providers), and
KV writes go through validation. But the YAML escaping is the only
defence-in-depth layer between an attacker-controlled model_id
(insofar as upstream providers could emit a malicious one) and a
user who copies the YAML into their gateway config.

**Recommendation**: replace single-quote with double-quote escaping
**plus** reject newlines / control chars at the normalize stage:

```ts
function yamlEscape(value: string): string {
  // Double-quoted YAML; escape backslash, double-quote, and reject
  // control characters. Newlines would break the line.
  if (/[\x00-\x1f]/.test(value)) {
    throw new Error(`unsafe model_id: contains control char`);
  }
  return `"${value.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}
```

Alternatively, use a real YAML library (`yaml` package — already an
indirect dep via workerd) and dump structured data instead of
concatenating strings. The other generators (`newapi.ts`,
`bifrost.ts`) already use `JSON.stringify` so they're safe.

### F5 — Low — `CLOUDFLARE_API_TOKEN` scope not documented

**Where**: `data/.env.example` mentions the token must have
"WRITE to KV" + "read for the validate step." But the actual token
template used is not recorded.

**Impact**: if a maintainer ever creates a token with `Account.*`
(global) or `Zone.*` scope by mistake, a leak would have a much
larger blast radius than necessary.

**Recommendation**: in `data/.env.example`, add an explicit
recommendation:

```
# Recommended Cloudflare API token template:
#   "Edit Cloudflare Workers KV Storage"
# Permissions:
#   Account > Workers KV Storage > Edit
#   Account > Workers KV Storage > Read
# This is enough for both fetch-models (write) and the validate
# step (read). DO NOT grant Account.* or Zone.* — least privilege.
```

### F6 — Low — Production deploy step exists only in developer-local workflow

**Where**: `wrangler pages deploy` is invoked from the developer's
local shell per `web-ci.yml` comment, not from any CI workflow.

**Impact**: ✅ positive — this is the audit prompt's preferred
architecture. Production tokens live on the deployer's laptop, not in
GitHub. Logged here for completeness.

**Recommendation**: keep the deploy flow local. If the team grows
beyond a single deployer, introduce a separate `wrangler-action`-based
workflow that uses a dedicated Pages-deploy-only token (not the data
publish token). Currently not needed.

### F7 — Informational — `FEISHU_WEBHOOK_URL` is optional

**Where**: `fetch-models.yml` references `FEISHU_WEBHOOK_URL` but the
notify stage is documented as "no-op if missing" in
`data/.env.example`.

**Impact**: a leak of `FEISHU_WEBHOOK_URL` allows an attacker to spam
a Feishu channel. Webhook URLs typically carry auth tokens in the
URL itself, so this is comparable to a low-privilege API token.

**Recommendation**: ensure the Feishu bot URL uses a scoped bot token
(not a full Feishu account token). Document this in `data/.env.example`.

### F8 — Informational — `security@tokyo3rdhq.com` placeholder

**Where**: `SECURITY.md`.

**Impact**: none on the security posture — the placeholder is just
text. But reporting will silently fail to reach a human until
replaced.

**Recommendation**: before public announcement of the repo,
replace the email with a working inbox. (The user's prior session
flagged this; logged here as a pre-launch checklist item.)

---

## 6. What the audit verified

| Surface | Method | Result |
|---|---|---|
| `web-ci.yml` triggers | read full file | ✅ no PR / dispatch target |
| `data-ci.yml` triggers | read full file | ✅ no PR / dispatch target |
| `fetch-models.yml` triggers | read full file | ✅ schedule + dispatch only |
| Secret presence in CI workflows | `grep -E 'secrets\.' web-ci.yml data-ci.yml` | ✅ no matches |
| Python shell execution surface | `grep -rn 'subprocess\|shell=True\|os.system\|exec(\|eval(' data/` | ✅ zero matches |
| Web shell execution surface | `grep -rn 'eval(\|Function(\|innerHTML\|dangerouslySetInnerHTML' web/src/` | ✅ zero matches |
| Provider fetcher URLs | read `BASE_URL` constants in `data/providers/*.py` | ✅ all hardcoded https |
| Provider fetcher timeouts | grep `timeout=` in `data/providers/*.py` | ✅ all set (30s) |
| Publisher destructive-delete guard | read `data/stages/publish.py` + `data/stages/reconcile.py` | ✅ §20/§21 guard present, refs `source_validated` |
| Validate-stage flags | read `data/stages/validate.py` | ✅ per-source `source_validated` dict set |
| Generated config secret leakage | grep `api_key` `value:` in `web/functions/lib/generators/` | ✅ all references are `env.<VAR>` or `os.environ/<VAR>` |
| YAML deserialization in pipeline | `grep -rn 'yaml\.' data/` | ✅ zero matches |
| Unsafe deserialization | `grep -rn 'pickle\|marshal' data/` | ✅ zero matches |

---

## 7. Recommended remediation order

1. **F1** (medium): add `permissions: contents: read` to all three
   workflows. Low-risk change, immediate principle-of-least-privilege
   win. **Recommended even before public launch.**
2. **F5** (low): document the recommended CF token template in
   `data/.env.example`. Pure documentation, no code change.
3. **F3** (low): tighten CORS for `POST /api/generate` only. Leave
   read endpoints at `*`.
4. **F8** (info): replace placeholder email before public launch.
5. **F4** (low): YAML escape hardening — code change in
   `web/functions/lib/generators/litellm.ts` + a normalize-stage
   reject-list for control characters.
6. **F2** (low): SHA-pin actions in `fetch-models.yml` only.
7. **F6** (no action needed — already correct).
8. **F7** (info): document the Feishu bot scope expectation.

None of these are blocking. The repository is safe to publish today.

---

## 8. What this audit did NOT cover

- **Upstream provider security** (NVIDIA, AMD, Hugging Face,
  OpenRouter, models.dev) — out of scope per `SECURITY.md`.
- **User-side token handling** — TFI emits `env.<VAR>` references;
  the user's runtime is theirs to secure.
- **Repository transfer / fork topology** — the public
  `tokyo3rdhq/token-factory-initializr` is the canonical repo per the
  README. The personal `yw79641760/...` mirror is a fork-of-fork; its
  existence doesn't affect the public security posture.
- **Compliance** (SOC2, GDPR, etc.) — out of scope; TFI processes no
  user data.

If a future change moves deploy into CI, moves secrets out of
Cloudflare, or adds new providers, this audit should be re-run.
