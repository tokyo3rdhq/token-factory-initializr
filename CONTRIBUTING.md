# Contributing to Token Factory Initializr

Thanks for your interest in contributing! TFI is a Cloudflare Pages
application with a Python data pipeline. The two runtimes are
independently runnable but share canonical state via Cloudflare KV
and a single JSON schema.

## Ground rules

- Be respectful. We follow the [Contributor Covenant](./CODE_OF_CONDUCT.md).
- All contributions are licensed under [Apache License 2.0](./LICENSE).
  By submitting a patch, you agree to license it under those terms.
- Keep PRs scoped. One concern per PR; avoid drive-by refactors.
- Discuss first for big changes. Open an issue before sending a 500-line
  PR — design feedback is cheaper than code review.

## Reporting issues

- **Bugs:** use the [Bug Report](../../issues/new?template=bug_report.yml) template.
  Include reproduction steps, expected vs actual behavior, browser +
  OS, and (if you can) a curl/transcript against the deployed site.
- **Security vulnerabilities:** do **not** open a public issue. See
  [`SECURITY.md`](./SECURITY.md) for the private reporting channel.
- **Feature requests:** use the [Feature Request](../../issues/new?template=feature_request.yml) template.
  Explain the user journey, not just the implementation.

## Development environment

### Web (`web/`)

```bash
$ cd web
$ npm ci --ignore-scripts
$ npm test                  # tsx --test (43 assertions across 8 files)
$ npm run build             # tsc --noEmit && vite build
$ npm run dev               # wrangler pages dev ./dist --var TFI_USE_LOCAL_FIXTURES=1
```

You need a Cloudflare account + KV namespace + Pages project to fully
run the data → SPA loop without `TFI_USE_LOCAL_FIXTURES=1`. For UI-only
work the fixture file ships a small subset of real endpoints and the UI
renders meaningfully without any external dependency.

### Data (`data/`)

```bash
$ cd data
$ pip install -e .[dev]
$ pytest                    # 30+ unit tests
$ python -m data.main       # runs the full pipeline against live sources
```

For local development where Hugging Face router is unreachable from
your network, set `SOCKS5_PROXY=socks5h://127.0.0.1:7897` in `data/.env`.

## Repository layout

```
data/                         Python ingestion pipeline (fetch → normalize → …)
  providers/                  Source adapters (NVIDIA/AMD/HF/OpenRouter/models_dev)
  stages/                     Pipeline stages
  models/                     Canonical ModelEndpoint dataclass
  notify/                     Feishu webhook
  storage/                    Cloudflare KV writer
  tests/                      Unit tests
  main.py                     CLI entry point

web/                          Cloudflare Pages application
  src/                        React 18 SPA
  functions/                  Pages Functions (Workers runtime)
  public/                     Static SEO assets (robots.txt, sitemap.xml)
  __tests__/ → src/__tests__   tsx --test suite

shared/schema/                Cross-runtime contract (JSON schema)
docs/                         Project documentation + design specs
.github/                      Workflows + community files
```

## Coding conventions

### Python

- `ruff format` + `ruff check` (configured in `pyproject.toml`).
- Strict type hints on every public function.
- Provider adapters under `data/providers/<name>.py` must implement
  the `Provider` protocol — see existing adapters for the shape.
- Stage implementations under `data/stages/` are thin orchestrators.
  Real logic lives in `data/process/<stage>.py` and `data/models/`.
- Tests under `data/tests/test_<module>.py` — fixtures downloaded live,
  not committed (`data/tests/fixtures/*.json` is gitignored).

### TypeScript

- Strict mode (`tsc --noEmit` runs in CI — no implicit any).
- Components in `web/src/components/` are presentational; pages in
  `web/src/pages/` compose them. Shared state lives in
  `web/src/initializr/InitializrContext.tsx`.
- Generator implementations under `web/functions/lib/generators/<id>.ts`
  must implement `TokenFactoryGenerator` (see existing generators).
  Register in `index.ts`. Add a case to `agentPrompt.ts`. Add a fixture
  entry in `web/functions/lib/fixtures.ts` if you want offline dev support.
- Tests under `web/src/__tests__/` use `tsx --test` (Node 22 built-in
  runner). The `__browseFilters` export from `Browse.tsx` is the
  pattern for testable pure functions inside React files.

### Commits

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Bifrost as a third Token Factory
fix: AMD provider now supported in Bifrost config
docs: rewrite README to reflect current architecture
refactor: extract metafield as new module
test: add coverage for the persist helper
chore: bump vite to 5.4.10
```

A PR title should match this format. The body should explain *why*,
not *what* — the diff shows the what.

### Branches

- `main` — the only long-lived branch. Tagged releases only.
- Feature branches: `feat/<short-name>`, `fix/<short-name>`. Rebase
  onto `main` before requesting review; no merge commits in your PR.

## Pull request process

1. **Open an issue first** for non-trivial changes. Reference it
   from the PR (`Closes #123`, `Refs #123`).
2. **Create a feature branch** off `main`.
3. **Make your changes.** Run the full test suite locally:
   ```bash
   $ cd web && npm test && npm run build
   $ cd ../data && pytest
   ```
4. **Push to your fork.** Open a PR targeting `main`. The PR template
   will ask for: summary, test plan, screenshots (UI changes), and
   a checklist of docs that need updating.
5. **Wait for CI.** The `web CI (lint + test + build)` workflow must
   pass. The `Fetch Free Models` workflow runs only on schedule, not
   on PRs.
6. **Wait for review.** Maintainers will respond within ~5 business
   days. Be prepared to iterate.

## Coding style notes

- **No emoji as primary UI icon.** TFI uses [lucide-react](https://lucide.dev/)
  per the design system contract.
- **No hidden SEO text.** Real product content stays semantic HTML.
- **No fabricated data in tests.** Use fixtures or recorded network
  responses, never hand-crafted "looks right" data.
- **Determinism is a contract.** Generators must produce identical output
  for identical inputs. Tests assert this explicitly.

## License

By contributing, you agree that your contributions will be licensed
under the [Apache License 2.0](./LICENSE).