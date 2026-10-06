# Changelog

All notable changes to Token Factory Initializr are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Dates are in `YYYY-MM-DD` format. Versions are sorted in reverse
chronological order (newest first). Unreleased changes are at the top.

## [Unreleased]

### Changed

- **License**: project is now Apache License 2.0 (was: previously
  described as proprietary in README.md; no LICENSE file existed).
- **Repository URL**: `data/pyproject.toml` `Repository` field now
  points at `tokyo3rdhq/token-factory-initializr` (was: yw79641760/...).
- **Web package**: `web/package.json` `private` flag set to `false`
  (was: `true`).
- **README**: added License / Contributing / Code of Conduct /
  Security sections per Apache 2.0 community-file conventions.

### Added

- `LICENSE` — full Apache License 2.0 text.
- `CONTRIBUTING.md` — development setup, commit / PR conventions,
  testing requirements.
- `CODE_OF_CONDUCT.md` — Contributor Covenant v2.1.
- `SECURITY.md` — private vulnerability reporting channel +
  threat model + contribution security checklist.
- `.github/ISSUE_TEMPLATE/bug_report.yml` — structured bug reports.
- `.github/ISSUE_TEMPLATE/feature_request.yml` — feature proposals
  with workflow + alternatives field.
- `.github/PULL_REQUEST_TEMPLATE.md` — PR checklist (test plan +
  area checkboxes + new-factory / new-provider checklist).
- `CHANGELOG.md` — this file.
- `CODEOWNERS` — default review assignment.

### Removed

- README's "Proprietary — internal use by the MAGI project family"
  clause, replaced by the Apache 2.0 license pointer.

## Earlier history

The project was bootstrapped privately; prior commits are listed
in the [git history](https://github.com/tokyo3rdhq/token-factory-initializr/commits/main).
Highlights:

- **LiteLLM generator** (`web/functions/lib/generators/litellm.ts`)
- **NewAPI generator** (`web/functions/lib/generators/newapi.ts`)
- **Bifrost generator** (`web/functions/lib/generators/bifrost.ts`)
  with 17 OpenAI-compatible provider mappings (NVIDIA NIM, AMD
  Radeon Cloud, Hugging Face router upstreams: together, deepinfra,
  cerebras, novita, cohere, fireworks, baseten, scaleway, nscale,
  ovhcloud, publicai, featherless; plus native Bifrost providers:
  Hugging Face, Groq, OpenRouter).
- **Agent API**: `/api/v1/models` (OpenAI-shaped), per-route metadata,
  ETag revalidation, cache headers, CORS, `X-Robots-Tag: noindex`
  on `/generated/{id}` + `/llms.txt` + `/agents.md`.
- **Data pipeline**: 5 providers (NVIDIA, AMD, Hugging Face,
  OpenRouter, models.dev) feeding 12 stages
  (fetch → parse → normalize → reconcile → filter_free → validate
  → enrich → snapshot → store → notify → publish → summarize).
- **SEO**: static `robots.txt`, `sitemap.xml`, JSON-LD
  `SoftwareApplication` + `Organization`, Twitter Card,
  per-route `useSeo()` hook for SPA deep links.
- **CI**: GitHub Actions `web CI (lint + test + build)` +
  `Fetch Free Models` (daily cron, pipeline-only).

## Versioning policy

TFI is in active development. The first semver release (`0.1.0`)
will be tagged once:

- The data pipeline has run cleanly against all 5 providers for
  at least 30 days without manual intervention.
- All three Token Factories (LiteLLM, NewAPI, Bifrost) emit
  configs that are validated by the gateway's own schema check.
- The `/api/v1/models` + `/api/v1/models/{id}` contract is
  declared stable (no breaking changes for 90 days).

Until then, every push to `main` is deployable but not a
"release" in the semver sense.