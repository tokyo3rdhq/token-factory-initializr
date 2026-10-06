# Security Policy

## Supported versions

| Version | Supported           |
| ------- | ------------------- |
| `main`  | ✅ active development |
| latest released tag | ✅ security fixes backported as time permits |
| older releases | ❌ best-effort, no backports |

TFI does not yet ship numbered releases. All work happens on `main`
and gets deployed to `https://start.magi.website/` from a maintainer's
local `wrangler pages deploy` invocation. Subscribe to repository
**Watch → Releases only** to be notified of security-relevant tags.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email **security@tokyo3rdhq.com** (placeholder — replace before
publishing). Include:

1. A clear description of the vulnerability and its impact.
2. Reproduction steps (curl transcript, screenshot, etc.).
3. The affected commit SHA / release tag / deployed commit.
4. Your name / handle for the public credit line in the fix release
   (or "anonymous" if you prefer).

We aim to acknowledge within **3 business days** and to publish a CVE
remediation within **30 days** of confirmation for critical issues,
**90 days** for lower severity. The disclosure timeline is coordinated
with you — we won't publish a fix until you confirm or 30 days elapse,
whichever is earlier.

## Threat model

TFI is a **read-only public catalog + generator**:

| Surface | Trust boundary |
|---|---|
| `/`, `/browse`, `/generate` | unauthenticated HTML; no server state |
| `/api/v1/*` | unauthenticated OpenAI-compatible API; Agents + SDKs |
| `/api/generate` | unauthenticated; produces 5-min TTL KV artifact |
| `/generated/{id}` | unauthenticated; shareable URL, expires in 5 min |
| `/llms.txt`, `/agents.md` | unauthenticated; Agent discovery resources |
| Cloudflare KV (`TFI_KV`) | pipeline writes, web reads |
| Generated configurations (API tokens) | configured by user at deploy time |

### In scope

- **Server-side request forgery (SSRF)** in Pages Functions when
  proxying upstream provider endpoints. We sanitize + URL-allowlist
  where possible. See `web/functions/lib/`.
- **Prototype pollution / XSS** via the model `description` field
  (rendered as innerHTML in some templates). We use React's default
  escaping everywhere; if you spot a `dangerouslySetInnerHTML`,
  file a bug.
- **ReDoS** in the Python pipeline regex over provider payloads. We
  keep regexes anchored + tested with adversarial fixtures.
- **Secret leakage in generated artifacts** — TFI references
  env vars (`env.OPENAI_API_KEY` style), never literals. Any output
  that contains a literal `sk-…` style prefix is a bug.

### Out of scope

- **The user's own token grants.** Each user wires their own
  `OPENAI_API_KEY` / `HF_TOKEN` etc. via environment variables; TFI
  never sees plaintext values at runtime (only the user sees them).
- **Upstream provider security** (OpenAI, NVIDIA, AMD, etc.). We
  consume their APIs; their auth models are theirs to secure.
- **Generated `config.yaml` files downstream.** Once TFI emits the
  config, the user owns its secrets.

## Security checklist for contributors

When opening a PR, please verify:

- [ ] No new `dangerouslySetInnerHTML` unless the input is from a
      trust-evaluated internal source (KV literal we wrote).
- [ ] No new `eval`, no `Function()` constructor calls.
- [ ] No new `innerHTML`/`outerHTML`/`document.write` from string
      interpolation.
- [ ] URLs emitted to user-visible surfaces go through
      `escapeHtml` / React's escaping. If you need raw HTML, justify
      it in the PR description.
- [ ] New providers go through the `Provider` protocol and validate
      inputs before they're stored in KV.
- [ ] New Pages Functions set explicit cache headers
      (`Cache-Control`, `X-Robots-Tag`) — don't fall back to defaults.
- [ ] No new `env.<VAR>` references that aren't documented in
      `web/.env.example` + `data/.env.example`.
- [ ] New dependencies are pinned to specific versions
      (`@cloudflare/workers-types@^5.20260923.1` style, not `latest`).
- [ ] Tests cover at least one adversarial fixture (long input, special
      characters, missing optional fields).

## Reporting a Cloudflare / Wrangler / dependency vulnerability

TFI depends on a small set of upstream packages. If you find a
vulnerability in one of them, please also report it upstream:

- `wrangler` / `workerd`: <https://github.com/cloudflare/workerd/security>
- `react` / `react-dom`: <https://github.com/facebook/react/security>
- `@tokyo3rdhq/magi-design-system`: <https://github.com/tokyo3rdhq/magi-design-system/security>

## Acknowledgments

We follow [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories)
for publishing CVE-level fixes. The TFI public advisory database will
appear at
<https://github.com/tokyo3rdhq/token-factory-initializr/security/advisories>
once a CVE-worthy issue is disclosed.